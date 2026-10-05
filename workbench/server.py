#!/usr/bin/env python3
"""Local-only WeChat image uploader for the article workbench."""

import argparse
import base64
import getpass
import hashlib
import json
import os
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser
from http.cookies import SimpleCookie
from pathlib import Path
from threading import Lock
import library
import wellbeing
import health_mcp


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = int(os.environ.get("WECHAT_WORKBENCH_PORT", "8766"))
APP_ID = "wechat-article-producer-workbench-v2"
KEYCHAIN_SERVICE = "Tang WeChat Publisher"
TOKEN_CACHE = {"value": "", "expires_at": 0.0, "credentials": b""}
DRAFT_RECEIPTS = {}
DRAFT_LOCK = Lock()
PUBLIC_ORIGIN = os.environ.get("WORKBENCH_PUBLIC_ORIGIN", "")
CREDENTIAL_FILE = os.environ.get("WECHAT_CREDENTIAL_FILE", "")


class WeChatError(Exception):
    def __init__(self, message, errcode=None):
        super().__init__(message)
        self.errcode = errcode


def keychain_get(account):
    if CREDENTIAL_FILE:
        try:
            return json.loads(Path(CREDENTIAL_FILE).read_text()).get(account, "")
        except (OSError, ValueError):
            return ""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def keychain_set(account, value):
    result = subprocess.run(
        ["security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
        input=f"{value}\n{value}\n",
        text=True,
        capture_output=True,
        start_new_session=True,
    )
    if result.returncode:
        raise RuntimeError("无法写入 macOS 钥匙串")


def configure():
    saved_app_id = keychain_get("appid")
    if saved_app_id:
        app_id = input("公众号 AppID（直接回车沿用已保存值）：").strip() or saved_app_id
    else:
        app_id = input("公众号 AppID：").strip()
    app_secret = getpass.getpass("公众号 AppSecret（输入时不会显示）：").strip()
    if not app_id or not app_secret:
        raise SystemExit("AppID 和 AppSecret 都不能为空。")
    keychain_set("appid", app_id)
    keychain_set("appsecret", app_secret)
    print("已安全保存到 macOS 钥匙串。")


def api_json(url, data=None, headers=None):
    request = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise WeChatError(f"微信接口连接失败：{error}") from error
    if result.get("errcode"):
        rejected_ip = re.search(r"invalid ip ([0-9.]+)", result.get("errmsg", ""))
        simple_errors = {
            40013: "公众号 AppID 不正确",
            40125: "公众号 AppSecret 不正确",
            40164: f"请将当前网络 IP {rejected_ip.group(1) if rejected_ip else ''} 添加到公众号 IP 白名单，并保留原有条目",
            48001: "当前公众号没有开通此接口权限",
        }
        message = simple_errors.get(result["errcode"], result.get("errmsg", "未知错误"))
        raise WeChatError(f"微信接口错误 {result['errcode']}：{message}", result["errcode"])
    return result


def access_token(force=False):
    app_id, app_secret = keychain_get("appid"), keychain_get("appsecret")
    if not app_id or not app_secret:
        raise WeChatError("尚未配置公众号 AppID/AppSecret")
    credentials = hashlib.sha256(f"{app_id}\0{app_secret}".encode()).digest()
    if not force and TOKEN_CACHE["value"] and TOKEN_CACHE["expires_at"] > time.time() and TOKEN_CACHE["credentials"] == credentials:
        return TOKEN_CACHE["value"]
    query = urllib.parse.urlencode({"grant_type": "client_credential", "appid": app_id, "secret": app_secret})
    result = api_json(f"https://api.weixin.qq.com/cgi-bin/token?{query}")
    TOKEN_CACHE.update(
        value=result["access_token"],
        expires_at=time.time() + max(60, int(result.get("expires_in", 7200)) - 300),
        credentials=credentials,
    )
    return TOKEN_CACHE["value"]


def decode_image(data_url):
    if not isinstance(data_url, str):
        raise WeChatError("图片数据格式错误")
    match = re.fullmatch(r"data:image/(png|jpeg);base64,(.+)", data_url, re.DOTALL)
    if not match:
        raise WeChatError("只支持 JPG 或 PNG 图片")
    try:
        payload = base64.b64decode(match.group(2), validate=True)
    except ValueError as error:
        raise WeChatError("图片数据损坏") from error
    if len(payload) >= 1024 * 1024:
        raise WeChatError("微信正文图片必须小于 1 MB")
    mime = "image/png" if match.group(1) == "png" else "image/jpeg"
    signature_ok = payload.startswith(b"\x89PNG\r\n\x1a\n") if mime == "image/png" else payload.startswith(b"\xff\xd8\xff")
    if not signature_ok:
        raise WeChatError("图片格式与内容不一致")
    return mime, "article.png" if mime == "image/png" else "article.jpg", payload


def multipart_image(mime, filename, payload):
    boundary = f"----TangWechat{secrets.token_hex(12)}"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"media\"; filename=\"{filename}\"\r\n"
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    return boundary, body


def upload_image(data_url):
    mime, filename, payload = decode_image(data_url)
    boundary, body = multipart_image(mime, filename, payload)
    for attempt in range(2):
        token = urllib.parse.quote(access_token(force=bool(attempt)), safe="")
        try:
            result = api_json(
                f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={token}",
                body,
                {"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "Tang-WeChat-Workbench/1.0"},
            )
            break
        except WeChatError as error:
            if attempt or error.errcode not in {40001, 40014, 42001}:
                raise
            TOKEN_CACHE.update(value="", expires_at=0.0, credentials=b"")
    if not result.get("url"):
        raise WeChatError("微信没有返回图片地址")
    return result["url"]


def wechat_request(path, data, content_type="application/json; charset=utf-8"):
    for attempt in range(2):
        token = urllib.parse.quote(access_token(force=bool(attempt)), safe="")
        try:
            return api_json(f"https://api.weixin.qq.com/cgi-bin/{path}{'&' if '?' in path else '?'}access_token={token}", data, {"Content-Type": content_type})
        except WeChatError as error:
            # Only an explicit token rejection is safe to retry, never a timeout.
            if attempt or error.errcode not in {40001, 40014, 42001}:
                raise


class DraftImages(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag == "img":
            source = urllib.parse.urlparse(dict(attrs).get("src", ""))
            if source.scheme not in {"http", "https"} or source.hostname not in {"mmbiz.qpic.cn", "mmbiz.qlogo.cn"}:
                raise WeChatError("请先将正文图片上传到微信，再导入草稿")


class Markup(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            attrs = dict(attrs)
            source = attrs.pop("data-src", None) or attrs.get("src", "")
            parsed = urllib.parse.urlparse(source)
            # WeChat changes src to data-src and selects a display size for the same asset.
            parent, _, size = parsed.path.rpartition("/")
            if parsed.hostname == "mmbiz.qpic.cn" and parent.startswith("/mmbiz") and size.isdigit():
                source = "https://mmbiz.qpic.cn" + parent
            attrs["src"] = source
            attrs = list(attrs.items())
        self.parts.append(("start", tag, sorted(attrs)))

    def handle_endtag(self, tag):
        self.parts.append(("end", tag))

    def handle_data(self, data):
        self.parts.append(("text", data))


def same_html(left, right):
    a, b = Markup(), Markup()
    a.feed(left or ""); b.feed(right or "")
    return a.parts == b.parts


def create_draft(body):
    article = {}
    for key, label in (("title", "标题"), ("author", "作者"), ("digest", "摘要"), ("content", "正文")):
        value = body.get(key, "")
        if not isinstance(value, str):
            raise WeChatError(f"{label}格式错误")
        article[key] = value.strip()
    if not article["title"] or not article["content"]:
        raise WeChatError("请填写标题和正文")
    DraftImages().feed(article["content"])
    mime, filename, image = decode_image(body.get("cover_data_url"))
    article_id = body.get("article_id", "")
    if not isinstance(article_id, str) or len(article_id) > 100:
        raise WeChatError("文章编号格式错误")
    request_id = body.get("request_id", "")
    if not isinstance(request_id, str) or len(request_id) > 128:
        raise WeChatError("本次导入编号格式错误")
    operation = b"\0" + request_id.encode() if request_id else b""
    fingerprint = hashlib.sha256(json.dumps(article, ensure_ascii=False, sort_keys=True).encode() + image + keychain_get("appid").encode() + article_id.encode() + operation).hexdigest()
    # One owner's imports are serialized; successful and uncertain receipts survive restart.
    with DRAFT_LOCK:
        previous = library.receipt_get(fingerprint)
        if previous:
            if previous.get("pending"):
                raise WeChatError("上次导入结果尚不确定，请先检查微信草稿箱，勿重复导入。")
            return {**previous, "reused": True}
        boundary, upload = multipart_image(mime, filename, image)
        cover = wechat_request("material/add_material?type=image", upload, f"multipart/form-data; boundary={boundary}")
        if not cover.get("media_id"):
            raise WeChatError("微信未返回永久封面素材，请稍后检查素材库")
        article["thumb_media_id"] = cover["media_id"]
        article.update(need_open_comment=0, only_fans_can_comment=0)
        library.receipt_put(fingerprint, {"pending": True})
        try:
            result = wechat_request("draft/add", json.dumps({"articles": [article]}, ensure_ascii=False).encode())
        except WeChatError as error:
            if error.errcode is None:
                raise WeChatError("未收到草稿创建回执，结果暂不确定。请先查看公众号草稿箱，勿立即重复导入。") from error
            library.receipt_delete(fingerprint)
            raise
        if not result.get("media_id"):
            raise WeChatError("微信未返回草稿编号，请先检查草稿箱，勿重复导入")
        receipt = {"media_id": result["media_id"], "title": article["title"], "verified": False}
        library.receipt_put(fingerprint, receipt)
        try:
            saved = wechat_request("draft/get", json.dumps({"media_id": result["media_id"]}).encode())
            item = saved.get("news_item", [{}])[0]
            receipt["verified"] = item.get("title") == article["title"] and same_html(item.get("content"), article["content"]) and item.get("thumb_media_id") == article["thumb_media_id"]
        except (WeChatError, IndexError):
            pass  # Creation succeeded; readback failure must never create another draft.
        library.receipt_put(fingerprint, receipt)
        return receipt


def allowed_origin(origin):
    return not origin or origin in {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}", PUBLIC_ORIGIN}


class Handler(SimpleHTTPRequestHandler):
    def session_cookie(self):
        try:
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            return cookies["tang_workbench"].value if "tang_workbench" in cookies else ""
        except Exception:
            return ""

    def authenticated(self):
        if not PUBLIC_ORIGIN:
            return True
        bearer = self.headers.get("Authorization", "").removeprefix("Bearer ")
        return library.authorized(bearer, self.session_cookie())

    def send_json(self, status, payload, cookie=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", f"tang_workbench={cookie}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=2592000")
            self.send_header("Set-Cookie", "tang_workbench=; HttpOnly; Secure; SameSite=Strict; Path=/wechat/; Max-Age=0")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/wechat/status":
            authenticated = self.authenticated()
            return self.send_json(200, {
                "app": APP_ID,
                "configured": bool(keychain_get("appid") and keychain_get("appsecret")),
                "authenticated": authenticated, "cloud": bool(PUBLIC_ORIGIN),
            }, cookie=self.session_cookie() if authenticated else None)
        if parsed.path.startswith("/api/"):
            if not self.authenticated():
                return self.send_json(401, {"error": "请先登录自己的文章工作台"})
            if parsed.path == "/api/access":
                return self.send_json(200, {"authenticated": True})
            query = urllib.parse.parse_qs(parsed.query)
            if parsed.path == '/api/health/mcp':
                return self.send_json(405, {'error':'Use POST for stateless MCP requests'})
            article_id = query.get("id", [""])[0]
            if parsed.path == "/api/wellbeing":
                return self.send_json(200, wellbeing.snapshot())
            if parsed.path == "/api/health":
                return self.send_json(200, wellbeing.health_snapshot())
            if parsed.path == '/api/health/sleep':
                try:
                    result = wellbeing.sleep_day_detail(query.get('day', [''])[0])
                except ValueError:
                    return self.send_json(400, {'error': '请选择有效日期'})
                return self.send_json(200 if result else 404, result or {'error': '这天还没有睡眠记录'})
            if parsed.path == "/api/ideas":
                return self.send_json(200, {"ideas": wellbeing.ideas(), "keywords": wellbeing.keywords()})
            if parsed.path == "/api/health/setup":
                if not PUBLIC_ORIGIN.startswith("https://"):
                    return self.send_json(400, {"error": "请从线上工作台配置手机同步"})
                endpoint = PUBLIC_ORIGIN + "/wechat/api/health/import"
                kind = query.get('kind', ['metrics'])[0]
                if kind not in ('metrics', 'workouts', 'sleep'):
                    return self.send_json(400, {'error': '同步类型不支持'})
                source = {'metrics':'iphone', 'workouts':'iphone-workouts', 'sleep':'iphone-sleep'}[kind]
                params = {"name": {'metrics':'泽龙健康指标直传','workouts':'泽龙训练记录直传','sleep':'泽龙睡眠分期直传'}[kind], "url": endpoint, "format": "json",
                    "datatype": "workouts" if kind == 'workouts' else 'healthMetrics', "period": "none",
                    "exportversion": "v2", "syncinterval": "minutes", "syncquantity": "15",
                    "headers": "Authorization,Bearer " + wellbeing.upload_key() + ",X-Health-Source," + source, "enabled": "true",
                    "notifywhenrun": "false"}
                if kind == 'metrics':
                    params.update(aggregatedata="true", aggregatesleep="true", interval="days")
                    params['metrics'] = ','.join(['Sleep Analysis'] + [spec[0] for spec in wellbeing.METRICS.values()])
                elif kind == 'sleep':
                    params.update(aggregatedata="false", aggregatesleep="false", metrics="Sleep Analysis", batchrequests="false")
                else:
                    params.update(includeroutes="false", includeworkoutmetadata="false")
                return self.send_json(200, {"setup_url": "com.HealthExport://automation?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote), "endpoint": endpoint})
            if parsed.path == "/api/articles":
                if not article_id:
                    return self.send_json(200, {"articles": library.list_articles()})
                try:
                    version = int(query["revision"][0]) if "revision" in query else None
                except ValueError:
                    return self.send_json(400, {"error": "版本格式错误"})
                item = library.get_article(article_id, version)
                return self.send_json(200 if item else 404, item or {"error": "文章不存在"})
            if parsed.path == "/api/versions":
                return self.send_json(200, {"versions": library.versions(article_id)})
            return self.send_json(404, {"error": "接口不存在"})
        # Source, credentials and database are never served by this process.
        if parsed.path not in {"/", "/index.html", "/library.js", "/library.css", "/desk.js", "/desk.css", "/ideas.js", "/ideas.css", "/xiaoqiu.png", "/body-album.jpg"} and not parsed.path.startswith("/examples/"):
            return self.send_json(404, {"error": "文件不存在"})
        return super().do_GET()

    def do_POST(self):
        if self.path == '/api/health/mcp':
            if not allowed_origin(self.headers.get('Origin','')):
                return self.send_json(403, {'error':'Origin not allowed'})
            if not self.authenticated():
                return self.send_json(401, {'error':'Authentication required'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 1000000:
                    return self.send_json(413, {'error':'Request too large or empty'})
                result=health_mcp.handle(json.loads(self.rfile.read(length)))
            except (ValueError,UnicodeDecodeError):
                result={'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Parse error'}}
            if result is None:
                self.send_response(202);self.send_header('Content-Length','0');self.end_headers();return
            return self.send_json(200,result)
        if self.path not in {"/api/wechat/upload-image", "/api/wechat/draft", "/api/articles", "/api/session", "/api/health/import", "/api/health/sync", "/api/checkin", "/api/notes", "/api/ideas", "/api/keywords"}:
            return self.send_json(404, {"error": "接口不存在"})
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            return self.send_json(415, {"error": "请求格式错误"})
        if not allowed_origin(self.headers.get("Origin", "")):
            return self.send_json(403, {"error": "请从工作台页面发起操作"})
        health_upload = self.path in {"/api/health/import", "/api/health/sync"} and wellbeing.upload_authorized(self.headers.get("Authorization", ""))
        if self.path != "/api/session" and not health_upload and not self.authenticated():
            return self.send_json(401, {"error": "请先登录自己的文章工作台"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_json(400, {"error": "请求长度错误"})
        if not 0 < length < 16_000_000:
            return self.send_json(413, {"error": "请求过大，请缩小图片或正文后重试"})
        try:
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise WeChatError("请求格式错误")
            if self.path == "/api/health/import":
                if not isinstance(body.get("data"), dict):
                    raise ValueError("睡眠数据格式错误")
                if self.headers.get("X-Health-Source"):
                    body["sync_source"] = self.headers["X-Health-Source"]
                try:
                    result = wellbeing.import_sleep(body)
                except ValueError:
                    source, interval = wellbeing.sync_identity(body)
                    wellbeing.report_sync({'sync_source': source, 'sync_interval': interval,
                                           'status': 'error', 'error': 'invalid_source_data'})
                    raise
                return self.send_json(200, result)
            if self.path == "/api/health/sync":
                return self.send_json(200, wellbeing.report_sync(body))
            if self.path == "/api/checkin":
                return self.send_json(200, wellbeing.check_in(body))
            if self.path == "/api/notes":
                return self.send_json(200, wellbeing.save_note(body))
            if self.path == "/api/ideas":
                return self.send_json(200, wellbeing.save_idea_links(body))
            if self.path == "/api/keywords":
                return self.send_json(200, wellbeing.save_keyword(body))
            if self.path == "/api/session":
                token = library.login(body.get("code", ""))
                return self.send_json(200 if token else 401, {"ok": bool(token), "error": "" if token else "密码不正确，或一次性登录码已失效"}, cookie=token)
            if self.path == "/api/articles":
                return self.send_json(200, library.save_article(body))
            if self.path == "/api/wechat/draft":
                self.send_json(200, create_draft(body))
            else:
                url = upload_image(body.get("data_url", ""))
                self.send_json(200, {"url": url})
        except library.Conflict as error:
            self.send_json(409, {"error": str(error)})
        except (ValueError, WeChatError) as error:
            self.send_json(400, {"error": str(error)})


def self_test():
    sample = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\nTEST").decode()
    mime, filename, payload = decode_image(sample)
    boundary, body = multipart_image(mime, filename, payload)
    assert mime == "image/png" and filename == "article.png"
    assert payload in body and boundary.encode() in body
    try:
        decode_image("data:image/gif;base64,R0lGODlh")
    except WeChatError:
        pass
    else:
        raise AssertionError("GIF should be rejected")
    original_run = subprocess.run
    captured = {}
    try:
        def fake_run(args, **kwargs):
            captured.update(args=args, kwargs=kwargs)
            return subprocess.CompletedProcess(args, 0)

        subprocess.run = fake_run
        keychain_set("test", "test-secret")
    finally:
        subprocess.run = original_run
    assert captured["args"][-1] == "-w" and "test-secret" not in captured["args"]
    assert captured["kwargs"]["input"] == "test-secret\ntest-secret\n"
    assert captured["kwargs"]["start_new_session"] is True
    print("self-test: PASS")


def main():
    parser = argparse.ArgumentParser(description="Tang 公众号排版工作台")
    parser.add_argument("command", nargs="?", choices=["serve", "configure", "self-test", "login-code"], default="serve")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    if args.command == "configure":
        return configure()
    if args.command == "self-test":
        return self_test()
    if args.command == "login-code":
        print(library.login_code())
        return
    library.owner_key()
    server = ThreadingHTTPServer((HOST, PORT), partial(Handler, directory=ROOT))
    print(f"公众号排版工作台：http://{HOST}:{PORT}/")
    if args.open_browser:
        webbrowser.open(f"http://{HOST}:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()

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
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = int(os.environ.get("WECHAT_WORKBENCH_PORT", "8766"))
APP_ID = "wechat-article-producer-workbench-v2"
KEYCHAIN_SERVICE = "Tang WeChat Publisher"
TOKEN_CACHE = {"value": "", "expires_at": 0.0, "credentials": b""}


class WeChatError(Exception):
    def __init__(self, message, errcode=None):
        super().__init__(message)
        self.errcode = errcode


def keychain_get(account):
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
        simple_errors = {
            40013: "公众号 AppID 不正确",
            40125: "公众号 AppSecret 不正确",
            40164: "当前网络 IP 没有加入公众号 IP 白名单",
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


def allowed_origin(origin):
    return not origin or origin in {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}


class Handler(SimpleHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/wechat/status":
            return self.send_json(200, {
                "app": APP_ID,
                "configured": bool(keychain_get("appid") and keychain_get("appsecret")),
            })
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/wechat/upload-image":
            return self.send_json(404, {"error": "接口不存在"})
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            return self.send_json(415, {"error": "请求格式错误"})
        if not allowed_origin(self.headers.get("Origin", "")):
            return self.send_json(403, {"error": "只允许本地排版器调用"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_json(400, {"error": "请求长度错误"})
        if not 0 < length < 1_500_000:
            return self.send_json(413, {"error": "图片请求过大"})
        try:
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise WeChatError("请求格式错误")
            url = upload_image(body.get("data_url", ""))
            self.send_json(200, {"url": url})
        except (json.JSONDecodeError, WeChatError) as error:
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
    parser.add_argument("command", nargs="?", choices=["serve", "configure", "self-test"], default="serve")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    if args.command == "configure":
        return configure()
    if args.command == "self-test":
        return self_test()
    server = ThreadingHTTPServer((HOST, PORT), partial(Handler, directory=ROOT))
    print(f"公众号排版工作台：http://{HOST}:{PORT}/")
    if args.open_browser:
        webbrowser.open(f"http://{HOST}:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Shared article-workbench client. Python standard library only; never publishes."""
import argparse
import base64
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser


class Error(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the owner's credential to a redirect target.


def read_config(path):
    path = Path(path).expanduser()
    if path.stat().st_mode & 0o077:
        raise Error("配置文件必须仅本人可读写：chmod 600 " + str(path))
    config = json.loads(path.read_text())
    url = config.get("url", "").rstrip("/")
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise Error("配置 url 必须是无账号、查询参数的 HTTPS 工作台地址")
    token = config.get("token", "")
    if not isinstance(token, str) or not token.strip() or any(c.isspace() for c in token):
        raise Error("配置缺少有效的工作台 token；不要使用公众号 AppSecret")
    return url, token


class Client:
    def __init__(self, url, token):
        self.url, self.token = url, token

    def request(self, path, body=None):
        request = urllib.request.Request(self.url + "/api/" + path,
            data=None if body is None else json.dumps(body, ensure_ascii=False).encode(),
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            labels = {401: "工作台授权失效", 403: "工作台拒绝访问", 409: "版本冲突，请先读回最新稿，不要覆盖"}
            message = labels.get(error.code, "工作台请求失败")
            raise Error(f"HTTP {error.code}：{message}；未自动重试") from None
        except (OSError, ValueError) as error:
            message = "网络请求未完成" if isinstance(error, OSError) else "服务器返回了无法解析的结果"
            if body is not None:
                message += "；写入结果可能已生效，请先核对，勿重复提交"
            raise Error(message + "；未自动重试") from None

    def get(self, article_id, revision=None):
        query = {"id": article_id}
        if revision is not None:
            query["revision"] = revision
        return self.request("articles?" + urllib.parse.urlencode(query))

    def link(self, article_id):
        return self.url + "/?" + urllib.parse.urlencode({"article": article_id})


def summary(client, item):
    return {key: item[key] for key in ("id", "revision", "archived")} | {
        "title": item["document"].get("title"), "url": client.link(item["id"])}


def image_data(path):
    data = Path(path).read_bytes()
    mime = "png" if data.startswith(b"\x89PNG\r\n\x1a\n") else "jpeg" if data.startswith(b"\xff\xd8\xff") else None
    if not mime or len(data) >= 1024 * 1024:
        raise Error("封面必须是小于 1 MB 的 JPG/PNG")
    return f"data:image/{mime};base64," + base64.b64encode(data).decode()


def checked_article(client, args):
    item = client.get(args.id)
    if item["revision"] != args.revision:
        raise Error(f"版本冲突：现在是第 {item['revision']} 版，请重新读取并核对")
    return item


def run(args, client):
    if args.command == "status":
        return client.request("wechat/status")
    if args.command == "wellbeing":
        return client.request("wellbeing")
    if args.command == "list":
        items = client.request("articles")["articles"]
        return {"articles": [summary(client, {**x, "document": x}) for x in items
            if (args.all or not x["archived"]) and (not args.search or args.search.casefold() in x["title"].casefold())]}
    if args.command == "get":
        item = client.get(args.id, args.revision)
        if not args.raw:
            doc = item["document"].copy()
            doc["has_cover"] = bool(doc.pop("cover", None))
            doc["image_slots"] = list(doc.pop("images", {}))
            item = {**item, "document": doc}
        return {**item, "url": client.link(args.id)}
    if args.command == "versions":
        return client.request("versions?" + urllib.parse.urlencode({"id": args.id}))
    if args.command == "open":
        client.get(args.id)
        url = client.link(args.id)
        return {"url": url, "opened": bool(webbrowser.open(url))}
    if args.command == "save":
        if args.id:
            if args.revision is None:
                raise Error("更新文章必须传 --revision，取自 get 的返回值")
            item = checked_article(client, args)
        else:
            if args.revision is not None or not args.title or not args.file:
                raise Error("新建文章需要 --title 和 --file，不传 --revision")
            item = {"id": str(uuid.uuid4()), "revision": 0, "archived": False,
                    "document": {"theme": "editorial", "images": {}}}
        doc = item["document"].copy()
        for key in ("title", "author", "byline", "digest", "theme"):
            value = getattr(args, key)
            if value is not None:
                doc[key] = value
        if args.file:
            doc["markdown"] = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
        if args.cover:
            doc["cover"] = image_data(args.cover)
            doc["cover_meta"] = {"name": Path(args.cover).name}
        archived = item["archived"] if args.archived is None else args.archived == "yes"
        # Print the id before writing so an uncertain new save can be read back.
        print(json.dumps({"saving_id": item["id"]}), file=sys.stderr)
        return summary(client, client.request("articles", {"id": item["id"],
            "revision": item["revision"], "document": doc, "archived": archived, "source": args.source}))
    if args.command == "draft":
        if not args.confirm:
            raise Error("需要针对这篇成稿的导入授权，再传 --confirm；不会正式发布")
        item = checked_article(client, args)
        doc = item["document"]
        content = Path(args.html).read_text(encoding="utf-8")
        if not content.strip() or not doc.get("cover"):
            raise Error("需要已审阅的正文 HTML 和已保存的封面")
        payload = {key: doc.get(key, "") for key in ("title", "author", "digest")}
        payload.update(content=content, cover_data_url=doc["cover"], article_id=args.id, request_id=args.request_id)
        receipt = client.request("wechat/draft", payload)
        result = {"draft_created": True, "verified": receipt.get("verified", False),
                  "receipt": receipt, "request_id": args.request_id, "published": False}
        try:
            saved = client.request("articles", {"id": args.id, "revision": item["revision"],
                "archived": item["archived"], "source": args.source,
                "document": {**doc, "wechat": {**receipt, "sent_at": time.time()}}})
            result.update(workbench_saved=True, article=summary(client, saved))
        except Error as error:
            result.update(workbench_saved=False, warning=str(error) + "；微信草稿已创建，不要重新导入")
        return result


def main():
    parser = argparse.ArgumentParser(description="公众号工作台：共享文章库、保留版本、送入微信草稿箱（不正式发布）")
    parser.add_argument("--config", default=os.environ.get("WXWORK_CONFIG", "~/.config/wechat-workbench/config.json"))
    parser.add_argument("--source", default="zelong/agent", help="版本记录署名")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("status", help="检查连接及工作台授权")
    subs.add_parser("wellbeing", help="读取已同步的睡眠、感受和灵感；不会放进文章")
    p = subs.add_parser("list", help="列出文章，可搜索")
    p.add_argument("--search"); p.add_argument("--all", action="store_true")
    for command in ("get", "versions", "open"):
        p = subs.add_parser(command, help={"get": "读取文章", "versions": "查看历史版本", "open": "打开网站预览"}[command])
        p.add_argument("id")
        if command == "get":
            p.add_argument("--revision", type=int); p.add_argument("--raw", action="store_true", help="包含封面和图片数据")
    p = subs.add_parser("save", help="新建或局部更新；未指定的字段原样保留")
    p.add_argument("--id"); p.add_argument("--revision", type=int)
    for field in ("file", "title", "author", "byline", "digest", "theme", "cover"):
        p.add_argument("--" + field)
    p.add_argument("--archived", choices=("yes", "no"))
    p = subs.add_parser("draft", help="将指定版本的已排版 HTML 导入微信草稿；需要明确授权")
    p.add_argument("id"); p.add_argument("--revision", type=int, required=True)
    p.add_argument("--html", required=True); p.add_argument("--request-id", required=True)
    p.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    try:
        result = run(args, Client(*read_config(args.config)))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (Error, OSError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

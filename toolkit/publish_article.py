#!/usr/bin/env python3
"""
publish_article.py — 一键推送 Markdown 文章到公众号草稿箱

用法:
    python3 publish_article.py article.md
    python3 publish_article.py article.md --theme sspai
    python3 publish_article.py article.md --cover cover.png --theme tech-modern

自动从 front matter 提取 title/author/summary；
从 config.yaml 读取 appid/secret。
"""
import sys
import os
import argparse
import yaml
import json
import urllib.request
import urllib.parse
from pathlib import Path

SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR))
sys.path.insert(0, str(SKILL_DIR / "toolkit"))


def load_config():
    for p in [SKILL_DIR / "config.yaml", Path.home() / ".config/wewrite/config.yaml"]:
        if p.exists():
            return yaml.safe_load(p.read_text()) or {}
    return {}


def parse_front_matter(md_text):
    """提取 YAML front matter"""
    if not md_text.startswith("---"):
        return {}, md_text
    parts = md_text.split("---", 2)
    if len(parts) < 3:
        return {}, md_text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    body = parts[2].strip()
    return meta, body


def get_access_token(appid, secret):
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}"
    resp = json.loads(urllib.request.urlopen(url).read())
    if "access_token" in resp:
        return resp["access_token"]
    raise Exception(f"获取 access_token 失败: {resp}")


def upload_image(token, image_path):
    """上传封面图到微信素材库"""
    import mimetypes
    boundary = "----WeWriteBoundary"
    filename = os.path.basename(image_path)
    content_type = mimetypes.guess_type(image_path)[0] or "image/png"

    with open(image_path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    url = f"https://api.weixin.qq.com/cgi-bin/media/upload?access_token={token}&type=image"
    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    resp = json.loads(urllib.request.urlopen(req).read())

    if "media_id" in resp:
        return resp["media_id"]
    raise Exception(f"上传图片失败: {resp}")


def upload_thumb(token, image_path):
    """上传封面图到永久素材（草稿箱要求 thumb_media_id 是永久素材）"""
    import mimetypes
    boundary = "----WeWriteBoundary"
    filename = os.path.basename(image_path)
    content_type = mimetypes.guess_type(image_path)[0] or "image/png"

    with open(image_path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=thumb"
    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    resp = json.loads(urllib.request.urlopen(req).read())

    if "media_id" in resp:
        return resp["media_id"]
    # fallback: 用临时素材
    print(f"  ⚠ 永久素材上传失败({resp.get('errmsg','')}), 尝试临时素材...")
    return upload_image(token, image_path)


def convert_md_to_html(md_text, theme="tech-modern"):
    """Markdown → 微信兼容 HTML（wechat-tech 内联样式）"""
    try:
        from wechat_tech_converter import convert_md_to_wechat_html
        html = convert_md_to_wechat_html(md_text)
        print(f"   ✅ wechat-tech 主题加载成功（绿色边框 + 蓝色引用 + 黄色高亮）")
        return html, ""
    except Exception as e:
        print(f"  ⚠ wechat-tech 转换失败({e}), 降级到基础样式")
        import markdown as md_lib
        html = md_lib.markdown(md_text, extensions=["tables", "fenced_code"])
        styled = f'''<section style="max-width:680px;margin:0 auto;padding:14px 12px;
            font-family:-apple-system,BlinkMacSystemFont,sans-serif;
            font-size:15px;line-height:1.8;color:#1a1a1a;">{html}</section>'''
        return styled, ""


def create_draft(token, title, content, thumb_media_id, author="", digest=""):
    """创建草稿"""
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
    data = {
        "articles": [{
            "title": title[:64],
            "author": author,
            "digest": digest[:120] if digest else "",
            "content": content,
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
        }]
    }
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    resp = json.loads(urllib.request.urlopen(req).read())

    if "media_id" in resp:
        return resp["media_id"]
    raise Exception(f"创建草稿失败: {resp}")


def main():
    parser = argparse.ArgumentParser(description="推送 Markdown 到公众号草稿箱")
    parser.add_argument("input", help="Markdown 文件路径")
    parser.add_argument("--theme", default="tech-modern", help="排版主题 (默认 tech-modern)")
    parser.add_argument("--cover", help="封面图路径")
    parser.add_argument("--title", help="覆盖标题")
    parser.add_argument("--author", help="覆盖作者")
    parser.add_argument("--digest", help="覆盖摘要")
    args = parser.parse_args()

    # 1. 加载配置
    print("📋 [1/5] 加载配置...")
    config = load_config()
    appid = config.get("wechat", {}).get("appid", "")
    secret = config.get("wechat", {}).get("secret", "")
    if not appid or not secret:
        print("❌ 缺少 config.yaml 中的 wechat.appid / wechat.secret")
        sys.exit(1)
    print(f"   AppID: {appid}")

    # 2. 解析 Markdown
    print("📝 [2/5] 解析 Markdown...")
    md_text = Path(args.input).read_text(encoding="utf-8")
    meta, body = parse_front_matter(md_text)

    title = args.title or meta.get("title", "") or Path(args.input).stem
    author = args.author or meta.get("author", "") or config.get("wechat", {}).get("author", "")
    digest = args.digest or meta.get("summary", "") or body[:100].replace("\n", " ")

    print(f"   标题: {title}")
    print(f"   作者: {author}")
    print(f"   摘要: {digest[:50]}...")
    print(f"   主题: {args.theme}")

    # 3. 转换 HTML
    print("🎨 [3/5] 转换为微信格式 HTML...")
    html, converter_title = convert_md_to_html(body, theme=args.theme)
    if not title and converter_title:
        title = converter_title
    print(f"   HTML 长度: {len(html)} 字符")

    # 4. 获取 token + 上传封面
    print("🔑 [4/5] 获取 access_token + 上传封面...")
    token = get_access_token(appid, secret)
    print("   ✅ token 获取成功")

    thumb_media_id = ""
    if args.cover and os.path.exists(args.cover):
        print(f"   上传封面: {args.cover}")
        thumb_media_id = upload_thumb(token, args.cover)
        print(f"   ✅ 封面 media_id: {thumb_media_id[:20]}...")
    else:
        print("   ⚠ 未指定封面图, 草稿可能没有封面")

    # 5. 创建草稿
    print("🚀 [5/5] 推送到草稿箱...")
    media_id = create_draft(token, title, html, thumb_media_id, author, digest)

    print()
    print("═" * 50)
    print("✅ 推送成功！")
    print("═" * 50)
    print(f"  📝 标题:    {title}")
    print(f"  👤 作者:    {author}")
    print(f"  🎨 主题:    {args.theme}")
    print(f"  📦 media_id: {media_id}")
    print()
    print("  👉 登录 mp.weixin.qq.com → 内容管理 → 草稿箱 查看")
    print()


if __name__ == "__main__":
    main()

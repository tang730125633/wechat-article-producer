"""
wechat_tech_converter.py — 把 Markdown 转成带 wechat-tech 内联样式的微信兼容 HTML

来源：baoyu-post-to-wechat 的 wechat-tech.css 主题
特点：绿色左边框标题 + 蓝色引用框 + 黄色加粗高亮 + 渐变分割线
"""
import re
import markdown
from markdown.extensions.toc import TocExtension


# ============================================================
# wechat-tech 内联样式定义（来自 baoyu wechat-tech.css）
# ============================================================

CONTAINER = (
    'max-width:680px;margin:0 auto;padding:14px 16px 32px;'
    'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;'
    'font-size:15px;line-height:1.75;color:#2c3e50;background-color:#fff;'
    'word-wrap:break-word;letter-spacing:0.02em;'
)

STYLES = {
    'h1': (
        'font-size:24px;font-weight:700;color:#1a1a1a;line-height:1.3;'
        'margin:36px 0 18px;padding:0 0 12px;border-bottom:3px solid #0066cc;'
        'display:block;text-align:left;'
    ),
    'h2': (
        'font-size:20px;font-weight:700;color:#1a1a1a;line-height:1.3;'
        'margin:32px 0 16px;padding:6px 0 6px 16px;'
        'border-left:5px solid #00a67d;'
        'background:linear-gradient(to right,#f0f9ff 0%,transparent 100%);'
        'display:block;text-align:left;'
    ),
    'h3': (
        'font-size:18px;font-weight:600;color:#2c3e50;line-height:1.4;'
        'margin:28px 0 14px;padding-left:12px;border-left:3px solid #ff9800;'
    ),
    'h4': (
        'font-size:16px;font-weight:600;color:#2c3e50;'
        'margin:24px 0 12px;padding-left:10px;border-left:2px solid #ff9800;'
    ),
    'p': (
        'margin:18px 0;line-height:1.8;color:#3a3a3a;letter-spacing:0.02em;font-size:15px;'
    ),
    'strong': (
        'font-weight:700;color:#1a1a1a;background-color:#fff3cd;padding:2px 4px;border-radius:4px;'
    ),
    'em': 'font-style:italic;color:#666;',
    'a': 'color:#0066cc;text-decoration:none;border-bottom:1px solid #0066cc;',
    'ul': 'margin:18px 0;padding-left:28px;color:#2c3e50;',
    'ol': 'margin:18px 0;padding-left:28px;color:#2c3e50;',
    'li': 'display:block;margin:10px 0;line-height:1.8;color:#3a3a3a;',
    'blockquote': (
        'margin:20px 0;padding:12px 16px;background-color:#f5f9fc;'
        'border-left:4px solid #2196f3;color:#555;line-height:1.7;'
        'font-style:normal;border-radius:4px;'
    ),
    'code': (
        'font-family:"Fira Code",Consolas,Monaco,"Courier New",monospace;'
        'font-size:13px;padding:3px 6px;background-color:#ffe6e6;'
        'color:#d63031;border-radius:4px;font-weight:500;'
    ),
    'pre': (
        'margin:24px 0;padding:16px 20px;background-color:#1e1e1e;'
        'border-radius:8px;overflow-x:auto;line-height:1.6;'
        'box-shadow:0 2px 8px rgba(0,0,0,0.1);font-size:13px;color:#d4d4d4;'
    ),
    'hr': (
        'margin:36px 0;border:none;height:2px;'
        'background:linear-gradient(to right,transparent,#0066cc,transparent);'
    ),
    'img': (
        'max-width:100%;height:auto;display:block;margin:24px auto;'
        'border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);'
    ),
    'table': (
        'width:100%;margin:24px 0;border-collapse:collapse;font-size:14px;'
        'box-shadow:0 1px 4px rgba(0,0,0,0.1);color:#2c3e50;'
    ),
    'th': (
        'background-color:#0066cc;color:#fff;padding:12px;text-align:left;'
        'border:1px solid #0052a3;font-weight:600;'
    ),
    'td': 'padding:12px;border:1px solid #e0e0e0;background-color:#fff;color:#2c3e50;',
}

# ============================================================
# Callout 容器样式
# ============================================================
CALLOUT_STYLES = {
    'info': (
        'margin:20px 0;padding:14px 18px;border-radius:6px;'
        'background-color:#e8f4fd;border-left:4px solid #2196f3;'
        'color:#1565c0;line-height:1.7;font-size:14px;'
    ),
    'warning': (
        'margin:20px 0;padding:14px 18px;border-radius:6px;'
        'background-color:#fff8e1;border-left:4px solid #ff9800;'
        'color:#e65100;line-height:1.7;font-size:14px;'
    ),
    'tip': (
        'margin:20px 0;padding:14px 18px;border-radius:6px;'
        'background-color:#e8f5e9;border-left:4px solid #4caf50;'
        'color:#2e7d32;line-height:1.7;font-size:14px;'
    ),
    'danger': (
        'margin:20px 0;padding:14px 18px;border-radius:6px;'
        'background-color:#ffebee;border-left:4px solid #f44336;'
        'color:#c62828;line-height:1.7;font-size:14px;'
    ),
}

CALLOUT_ICONS = {
    'info': '💡',
    'warning': '⚠️',
    'tip': '✅',
    'danger': '🚨',
}


def process_callouts(md_text):
    """把 :::callout type ... ::: 转成 HTML"""
    def replace_callout(match):
        ctype = match.group(1).strip().lower()
        content = match.group(2).strip()
        style = CALLOUT_STYLES.get(ctype, CALLOUT_STYLES['info'])
        icon = CALLOUT_ICONS.get(ctype, '💡')
        # 把 content 里的 markdown 转成简单 HTML
        content_html = content.replace('\n', '<br>')
        return f'<div style="{style}"><span style="font-size:16px;">{icon}</span> {content_html}</div>'

    return re.sub(
        r':::callout\s+(\w+)\s*\n(.*?)\n:::',
        replace_callout,
        md_text,
        flags=re.DOTALL
    )


def inject_inline_styles(html):
    """把 CSS 样式注入为内联 style 属性"""
    for tag, style in STYLES.items():
        # 处理自闭合标签（如 <hr>, <img>）
        if tag in ('hr', 'img'):
            html = re.sub(
                rf'<{tag}(\s[^>]*)?\s*/?>',
                lambda m: f'<{tag}{m.group(1) or ""} style="{style}">',
                html
            )
        else:
            # 处理开放标签
            html = re.sub(
                rf'<{tag}(\s[^>]*)?>',
                lambda m, t=tag, s=style: f'<{t}{m.group(1) or ""} style="{s}">',
                html
            )

    # blockquote 内的 p 标签特殊处理
    html = re.sub(
        r'(<blockquote[^>]*>)\s*<p style="[^"]*">',
        r'\1<p style="display:block;font-size:1em;color:#555;margin:0;letter-spacing:normal;">',
        html
    )

    return html


def convert_md_to_wechat_html(md_text):
    """
    完整的 Markdown → 微信兼容 HTML 转换
    使用 wechat-tech 主题（绿色左边框 + 蓝色引用 + 黄色高亮）
    """
    # 1. 处理 callout 容器语法
    md_text = process_callouts(md_text)

    # 2. Markdown → HTML
    html = markdown.markdown(
        md_text,
        extensions=[
            'tables',
            'fenced_code',
            'nl2br',
            TocExtension(marker=''),
        ]
    )

    # 3. 注入内联样式
    html = inject_inline_styles(html)

    # 4. 列表项加 bullet（微信有时不显示默认 bullet）
    html = re.sub(
        r'<li style="([^"]*)">(?!•)',
        r'<li style="\1">• ',
        html
    )

    # 5. 包裹容器
    result = f'<section style="{CONTAINER}">{html}</section>'

    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python3 wechat_tech_converter.py article.md")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        content = f.read()

    # 去掉 front matter
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            content = parts[2]

    html = convert_md_to_wechat_html(content)
    print(html)

# wechat-article-producer

把真实想法整理成文章，完成排版和配图，再交付到微信公众号。

项目现在提供两条互不冲突的路径：

- `workbench/`：本地可视化排版器。粘贴文章、选择主题、插入图片、上传微信、复制 HTML。
- `toolkit/`：原有命令行发布器。适合把 Markdown 自动转换并推送到公众号草稿箱。

## 推荐用法：可视化排版器

适合个人创作和人工终审，不需要搭建网站或数据库。

### macOS 启动

进入 `workbench/`，双击：

```text
打开公众号排版器.command
```

首次启动会询问公众号 AppID 和 AppSecret。凭据只保存在 macOS 钥匙串，不会写进网页、仓库或浏览器草稿。

### 创作流程

1. 粘贴 Markdown 或普通分段文章。
2. 按需插入小标题、引用、金句、流程、图片位、分隔符和结尾签名。
3. 从 11 套主题中选择排版。
4. 粘贴或选择 JPG/PNG 图片，点击“上传到微信”。
5. 点击“复制 HTML 源码”，粘贴到公众号编辑器。

正文始终是原生文字，不会被栅格化成长图。图片上传后使用微信 `mmbiz.qpic.cn` 地址，导出时不会携带工作台按钮或脚本。

## 工作台能力

- 11 套原创公众号主题
- Markdown 与普通文本输入
- 公众号手机宽度预览
- 7 类内容组件
- 剪贴板图片粘贴和本地图片选择
- 微信正文图片上传
- macOS 钥匙串凭据保存
- HTML 源码、公众号富文本和完整 HTML 下载
- 浏览器本地文字草稿恢复

`workbench/examples/` 包含四张可编辑 SVG 和对应 PNG，用于演示解释型配图，而不是随机装饰图。

## 命令行草稿发布器

原有自动草稿发布能力继续保留：

```bash
python3 -m pip install -r requirements.txt
cp config.example.yaml config.yaml
python3 toolkit/publish_article.py examples/test-article.md --cover path/to/cover.png
```

`config.yaml` 已被 `.gitignore` 排除。不要把 AppSecret、access token 或公众号 Cookie 提交到 Git。

## 本地验证

```bash
python3 -m unittest discover -s workbench -p 'test_*.py'
python3 workbench/server.py self-test
python3 -m py_compile workbench/server.py toolkit/*.py
zsh -n workbench/打开公众号排版器.command
```

## 项目结构

```text
wechat-article-producer/
├── workbench/                  # 可视化排版器与示例图
├── toolkit/                    # Markdown → 微信草稿箱工具
├── skills/                     # OpenClaw 编排 Skill
├── examples/                   # Markdown 示例
├── config.example.yaml         # 命令行发布配置示例
├── requirements.txt
├── VERSION
└── CHANGELOG.md
```

## 安全边界

- 工作台只监听 `127.0.0.1`，不会暴露到局域网或公网。
- 正文图片仅接受小于 1MB 的 JPG/PNG。
- 上传、创建草稿和正式发布是不同动作；工作台不会自动发布文章。
- 公众号 AppSecret 只进入 macOS 钥匙串。

## License

MIT

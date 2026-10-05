# wechat-article-producer

![Zel 和橘猫一起把语音与手写想法送入排版工作台，最终生成公众号文章](assets/readme/hero-zel-v1.webp)

把真实想法整理成文章，完成排版和配图，再交付到微信公众号。

## Agent 快速入口

Codex、Pi、OpenClaw、Hermes 等能执行命令的 Agent 使用同一个 Python 标准库客户端，直接连接现有网站文章库。无需浏览器操作来读写文章，也不用将公众号 AppSecret 交给 Agent。

```sh
python3 skills/wechat-article-producer/scripts/wxwork.py status
python3 skills/wechat-article-producer/scripts/wxwork.py list
python3 skills/wechat-article-producer/scripts/wxwork.py save --title '今天的想法' --file article.md
python3 skills/wechat-article-producer/scripts/wxwork.py get ARTICLE_ID
python3 skills/wechat-article-producer/scripts/wxwork.py save --id ARTICLE_ID --revision 1 --file revised.md
python3 skills/wechat-article-producer/scripts/wxwork.py open ARTICLE_ID
```

输出包含文章 ID、版本和网站预览链接。更新保留未指定的封面、配图、主题等字段，版本冲突会停止，不会自动覆盖其他 Agent 的稿件。`get` 默认不输出大体积图片，`--raw` 可取完整快照。

把 [创作技能](skills/wechat-article-producer/SKILL.md) 所在目录链接或复制到 Agent 的技能目录即可发现；配置、调用说明和微信草稿导入边界都在该文件。客户端需要 Python 3.9+，无额外依赖。

本机授权配置：`~/.config/wechat-workbench/config.json`（权限 600）。使用部署管理员提供的工作台 owner key，不是公众号 AppSecret。不同朋友需使用自己的实例/授权；当前后端是单用户工作台，不隔离多人数据。

## 网站与预览

日常入口：[公众号工作台](https://zelong.vip/wechat/)。Agent 写入文章后，在网站审阅、微调、选择主题、添加封面和正文图，按授权导入公众号草稿箱。微信导入成功与正式发布不同，工具不会群发。

本机辅助版：进入 `workbench/`，双击 `打开公众号排版器.command`。首次配置的凭据保存在 macOS 钥匙串。服务器版说明见 [workbench/README.md](workbench/README.md)。

## 工作台能力

- 11 套原创公众号主题
- Markdown 与普通文本输入
- 公众号手机宽度预览
- 7 类内容组件
- 剪贴板图片粘贴和本地图片选择
- 微信正文图片上传
- macOS 钥匙串凭据保存
- HTML 源码、公众号富文本和完整 HTML 下载
- 云端文章库、版本历史、并发修改保护与浏览器文字恢复

`workbench/examples/` 包含四张可编辑 SVG 和对应 PNG，用于演示解释型配图，而不是随机装饰图。

## 命令行草稿发布器

以下为旧版独立发布器；日常 Agent 创作优先使用上面的 wxwork，以保留网站版本和统一凭据：

```bash
python3 -m pip install -r requirements.txt
cp config.example.yaml config.yaml
python3 toolkit/publish_article.py examples/test-article.md --cover path/to/cover.png
```

`config.yaml` 已被 `.gitignore` 排除。不要把 AppSecret、access token 或公众号 Cookie 提交到 Git。

## 本地验证

```bash
python3 -m unittest discover -s skills/wechat-article-producer/scripts
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
├── skills/                     # 跨 Agent 创作 Skill 与 wxwork 客户端
├── examples/                   # Markdown 示例
├── config.example.yaml         # 命令行发布配置示例
├── requirements.txt
├── VERSION
└── CHANGELOG.md
```

## 安全边界

- 后端只监听 `127.0.0.1`；服务器通过 HTTPS 代理与工作台授权提供私有文章接口。
- 正文图片仅接受小于 1MB 的 JPG/PNG。
- 上传、创建草稿和正式发布是不同动作；工作台不会自动发布文章。
- 公众号 AppSecret 存在 macOS 钥匙串或服务器私有配置；Agent 只需独立的工作台授权。

## License

MIT

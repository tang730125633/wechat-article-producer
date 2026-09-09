# 可视化公众号排版器

## 使用

1. 双击 `打开公众号排版器.command`。
2. 粘贴文章并选择主题。
3. 粘贴图片，点击“上传到微信”。
4. 点击“复制 HTML 源码”，粘贴到公众号编辑器。

第一次启动时输入 AppID/AppSecret。AppSecret 不会显示，也不会写入项目文件。

需要更换公众号时，运行 `python3 server.py configure`，输入新的 AppID 和 AppSecret。
双击启动器固定使用 `127.0.0.1:8767`，这样浏览器草稿可以在下次启动时恢复。

## 微信图片要求

- JPG 或 PNG
- 单张小于 1MB
- 当前公网 IP 必须加入公众号 API IP 白名单

## 验证

```bash
python3 -m unittest discover -s . -p 'test_*.py'
python3 server.py self-test
python3 -m py_compile server.py
zsh -n 打开公众号排版器.command
```

`examples/` 中的 SVG 可以继续编辑，PNG 可直接作为公众号示例配图。

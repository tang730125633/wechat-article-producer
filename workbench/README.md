# 可视化公众号排版器

## 使用

1. 双击 `打开公众号排版器.command`。
2. 粘贴文章并选择主题。
3. 粘贴图片，点击“上传到微信”。
4. 点击“复制 HTML 源码”，粘贴到公众号编辑器。

也可以在第 4 区填写公众号作者、摘要，选择小于 1 MB 的 JPG/PNG 封面，点击“导入公众号草稿”。工具上传永久封面、保留当前正文排版并创建草稿，再读回核对；不会群发或正式发布。正文图片随导入上传微信，空图片位会提示补齐。

网站版直接保存文章并通过服务器导入微信草稿，不再跳转本机。首页展示文章库，支持新建、自动保存、搜索、归档、查看和恢复历史版本；正文配图与封面也随稿件保存。默认私有，需一次性登录码换取本人浏览器会话。

白名单错误会显示应添加的当前 IP。微信后台的网页登录和接口授权是两回事。遇到“结果暂不确定”请先检查草稿箱，不要反复点击；相同文章和封面会复用已成功的回执，服务重启后仍保留。未取得回执的请求不会自动重复创建。

## 网站与 AI 接口

服务器依然只使用 Python 标准库和 SQLite。`WORKBENCH_DATA_DIR` 指向公开目录外的私有目录，`WORKBENCH_PUBLIC_ORIGIN=https://zelong.vip` 开启登录验证，`WECHAT_CREDENTIAL_FILE` 指向仅服务用户可读的 JSON（字段 appid / appsecret）。缺少该配置时本机继续使用钥匙串。后端监听回环地址，网站将 `/wechat/api/` 代理到后端 `/api/`。

- 在相同数据目录环境下运行 `python3 server.py login-code`，生成十分钟有效、只能使用一次的登录码。浏览器在 `#login=` 中接收后立即移除，通过 POST 交换 HttpOnly 会话。
- AI 使用私有目录 `owner.key` 作为 Bearer 凭据；只在受保护环境读取，不输出值。
- `GET /api/articles`：文章摘要列表；`GET /api/articles?id=...`：完整当前稿；加 `revision=...` 读历史稿。
- `POST /api/articles`：传 `{id, revision, document, archived, source}`。新文章 revision 为 0，之后使用刚读取的版本号；过期版本返回 409，不覆盖另一端修改。
- document 保存 title、markdown、theme、byline、author、digest、cover（图片 data URL）、images（排版图片映射）及微信回执。内容以用户实际稿件为准。
- `GET /api/versions?id=...`：版本时间和来源。恢复旧稿时，用当前 revision 提交旧稿 document，形成新版本而非删除历史。
- `POST /api/wechat/draft`：已有导入协议不变；网站与本机共用代码。

自动保存使用完整快照，适合个人文章库；图片较多导致数据量增长时，再独立存储和去重素材。SQLite 数据和登录凭据都不在网站静态发布目录内，发布新代码不覆盖文章数据。

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

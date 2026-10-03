# 可视化公众号排版器

## 使用

1. 双击 `打开公众号排版器.command`。
2. 粘贴文章并选择主题。
3. 粘贴图片，点击“上传到微信”。
4. 点击“复制 HTML 源码”，粘贴到公众号编辑器。

也可以在第 4 区填写公众号作者、摘要，选择小于 1 MB 的 JPG/PNG 封面，点击“导入公众号草稿”。工具上传永久封面、保留当前正文排版并创建草稿，再读回核对；不会群发或正式发布。正文图片随导入上传微信，空图片位会提示补齐。

网站版直接保存文章并通过服务器导入微信草稿，不再跳转本机。首页展示文章库，支持新建、自动保存、搜索、归档、查看和恢复历史版本；正文配图与封面也随稿件保存。默认私有，需一次性登录码换取本人浏览器会话。

每次主动点击导入都会新建一份微信草稿，即使内容相同也不覆盖或复用旧稿。发送过程中按钮暂时禁用；同一次请求重复到达时才复用回执，服务重启后回执仍保留。遇到“结果暂不确定”先检查草稿箱，后续主动点击仍代表另外新建一份，不会自动重试。

封面可选择文件，也可点“粘贴封面图片”或选中右侧封面卡，再按 ⌘V / Ctrl+V。支持剪贴板中的 JPG/PNG 图片，仍按微信接口要求小于 1 MB；图片网址或普通文字不会被误当作封面。

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

## 生活与创作首页

首页复用文章工作台与登录，新增奶油白/柔和绿的创作书桌。文字输入可保存为灵感，或保存原话并进入文章编辑器；浏览器支持时可使用语音输入，不支持时使用系统听写。当前不包含网页内模型改写或自动主动关怀。

- `GET /api/wellbeing`：本人已同步睡眠、今日感受与最近灵感/回顾，需工作台授权。
- `POST /api/health/import`：Health Auto Export 的 JSON 睡眠汇总；仅保留 sleep_analysis，重复日期更新。可使用私有 health-upload.key，只有此接口接受该钥匙。
- `GET /api/health/setup`：本人登录后获取手机应用的同步配置链接。链接含专用上传凭据，不记录、不分享；只选 Sleep Analysis、按天汇总前一天与当天。
- `POST /api/checkin`：`{"mood":"good|okay|tired"}`，按北京时间记录当日感受。
- `POST /api/notes`：`{"id":"UUID","kind":"idea|reflection","text":"原话"}`，同一编号防重，不静默覆盖不同文本。

健康与生活记录放在公开目录外的 `wellbeing.sqlite3`，与 `articles.sqlite3` 分开，不自动进入文章或微信草稿。手机持续自动同步需现场确认；本机读到后的一次性导入不等于手机自动同步。

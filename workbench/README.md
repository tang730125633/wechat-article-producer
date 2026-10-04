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

## 灵感关联

灵感页采用左侧原句、右侧关键词和交互图谱。节点支持点击定位、关键词筛选、拖动和缩放；记忆背景与下一步为可选说明，来源可链接到网页或已核对的 Codex 会话。使用原生 SVG，不引入图数据库或图形库。

- `GET /api/ideas` 返回全部 idea 原句与关联元数据，不受首页最近 60 条记录的限制。
- `POST /api/ideas` 接收 `id`、关联 `revision`、`keywords`、`context`、`next_step`、`source_label`、`source_url`、`source`。未提供字段视为空，因此局部更新应先读取并合并；wxwork 客户端会保留未指定字段。
- 关联单独存在 `idea_links` 表，原句不变。重复保存相同内容不增加版本，旧版本修改返回 409。
- 同名关键词（Unicode NFC、忽略大小写）共享节点；所有连接来自保存的元数据，不做正则自动抽词或猜测因果。新灵感可由用户或 Agent 整理关键词。

关键词也可独立于原话存在：`POST /api/keywords {"keyword":"词语"}` 保存到 `idea_keywords`，同名词按 NFC / 忽略大小写防重。`GET /api/ideas` 的 `keywords` 返回独立词库；前端将其与原话已有标签合并显示，并为未关联词绘制独立节点，不创建假的原句。

## 旧 Mac 睡眠中转（已停用，保留恢复工具）

`health_sync.py` 是保留的故障恢复程序：直接读取 iCloud 已同步到本机的最近七天睡眠文件，使用专用上传钥匙发送到工作台。仅传睡眠，不传其他指标。现场已在手机直传成功后卸载 launchd 任务，并将启动文件移出 LaunchAgents 留存；不再依赖 Mac 中转。以下说明只用于明确选择恢复旧路径时。

- 私有配置 `~/.config/health-auto-export/workbench.json`（600）：`url` 与专用上传 `token`。同步不再依赖 MCP 请求头或健康应用的数据接口；授权上传钥匙不在命令或日志输出。
- `POST /api/health/import` 支持 `sync_source`（manual / mac-bridge / iphone）与 `sync_interval`。只有内容变化才改写 sleep_days.received；每轮检查结果存在 health_sync，不伪造新睡眠。
- `POST /api/health/sync` 记录 empty/error，允许同一上传钥匙调用；不会授予读取文章或健康数据权限。
- `GET /api/health` 返回睡眠、感受、同步状态，不读取灵感/文章。页面可见时每分钟查询，切回页面立即查询；不自动打断原话、文章或关联编辑。
- 同步状态区分最近检查、最近成功、内容实际变化、任务周期；超过预期 2.5 个周期（至少 30 分钟）未收到检查时显示延迟，历史数据保留。

本机运行文件安装在 `~/.local/libexec/tang-health-sync/health_sync.py`，任务标签 `ai.zelong.health-sync`。日志在 `~/Library/Logs/tang-health-sync.log`，只记结果、数量和错误类别。程序退出码 0 代表本轮上报完成，不能单凭此证明手表已经生成当天数据。

### 应用重启后的恢复修复

Mac 版应用重新启动不会自动恢复内部 MCP 端口。因此同步程序改为读取官方 Sync to Mac 路径下的 `sleep_analysis/yyyyMMdd.hae`，使用 macOS 自带 Compression 库解开 LZFSE，再对当前已验证的 Health Auto Export 4.x 睡眠片段格式做日期、单位、时长及重叠校验。仅合计睡眠，清醒片段不计入；忽略 iCloud 的带编号冲突副本。未知格式或冲突片段报错，不当成空数据或零睡眠。

这条路径不启动、关闭或控制健康应用，MCP 端口关闭也能同步。仍依赖 iPhone → iCloud 文件同步、Mac 在线及文件已下载；文件来自用户已有授权导出，不修改原文件。默认目录可用 `--source-dir` 指定。

运行身份：launchd 需指向已授权的真实 `Python.app/Contents/MacOS/Python`，不能只使用 `/usr/bin/python3` 命令行启动壳。现场 macOS 日志显示该启动壳的身份曾被归到 git，导致重新加载后的 iCloud 读取被拒绝。真实 Python 的完全磁盘访问授权必须由用户明确同意，并通过系统设置、本人身份验证完成；不得修改 TCC 数据库绕过。修复验收需覆盖重新加载任务与随后自动计时运行，而不是只看一次手动成功。

## iPhone 直传、运动与服务器 MCP

当前通路是 iPhone Health Auto Export → HTTPS 接收接口 → 私有数据库 → 网站 / MCP。已通过真机健康指标、训练记录上传验收，并在 Mac 中转停用后观察到后续自动上传。Mac 只作为查看端。手机锁屏、低电量模式与 iOS 后台调度仍会影响上传时机，不能承诺仅开机即可固定频率读取健康数据。

- 登录后 `GET /api/health/setup?kind=metrics` / `kind=workouts` 生成两个手机配置入口。一个同步睡眠和日常指标，一个同步 V2 训练记录；不启用路线/GPS导出。入口包含上传凭据，不公开分享。
- 用 iPhone Safari 打开配置入口；真机 Chrome 未完成自定义协议跳转时改用 Safari。健康指标使用按天汇总；训练配置不能携带 aggregatedata / aggregatesleep / interval 等健康专用参数，否则应用拒绝导入。两项期望间隔均为 15 分钟，现场训练范围为近七天，重复记录按 UUID 更新。
- `POST /api/health/import` 接受原生按天汇总的 JSON。活动指标保存到 health_metrics；训练按 UUID 保存到 workouts。只存支持的指标；重复上传不叠加计数。kJ/kcal、km/mi 等统一换算，训练热量不重复加进日常活动热量。
- 来源 `iphone` / `iphone-workouts` 分别保留成功时间。收到手机直传后，页面优先显示手机状态；尚未收到的指标清楚留空。
- 任一已配置手机通路报错或超过预期间隔，总状态都会提示异常；训练上传成功不能掩盖健康指标断流。验收分别检查手机响应、服务器回执、网页真实值和后续自动运行。
- 只读 MCP：`POST /api/health/mcp`，使用已有工作台 owner Bearer 授权，上传钥匙无读取权限。支持 initialize、ping、tools/list、tools/call；提供 get_health_overview、get_health_history、get_workouts。工具只读数据库，不调用模型或采集设备。

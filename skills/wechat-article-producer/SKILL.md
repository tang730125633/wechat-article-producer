---
name: wechat-article-producer
description: 把想法整理成公众号文章，直接读写网站文章库、查看历史版本、排版预览并按授权导入微信草稿。用于写公众号、把对话变文章、改稿、查稿、公众号工作台和草稿箱；不正式发布文章。
---

# 公众号创作工具

使用本技能旁的 `scripts/wxwork.py`，只依赖 Python 3.9+ 标准库。本机已安装快捷命令 `~/.local/bin/wxwork`。Codex、Pi、OpenClaw、Hermes 使用同一工具、同一网站文章库；无需各自搭服务器或持有公众号 AppSecret。

## 快速调用

```sh
wxwork status
wxwork wellbeing  # 私有睡眠、感受和灵感，按用户需要读取
wxwork list --search '关键词'
wxwork get ARTICLE_ID
wxwork versions ARTICLE_ID
wxwork save --title '标题' --file article.md --author '用户确认的署名'
wxwork save --id ARTICLE_ID --revision 7 --file revised.md
wxwork save --id ARTICLE_ID --revision 8 --cover cover.jpg
wxwork open ARTICLE_ID
```

如果 PATH 不包含命令，使用 `~/.local/bin/wxwork`；其他机器直接运行 `python3 <本技能目录>/scripts/wxwork.py`。各子命令有 `--help`。输出 JSON，保存结果含文章 ID、版本和网站预览链接；不输出认证信息。`get` 默认省略大体积图片，确实要完整备份时使用 `--raw` 并保存到私有文件，不塞进对话。

- 网站是当前稿件的权威来源。修改前 `get`，将返回的 revision 传给 `save`。没有指定的作者、主题、图片等原样保留。冲突时重新核对，不能盲目换成最新版本号覆盖。
- `--file -` 从标准输入读取正文。正文用网站支持的 Markdown，不放 YAML 元数据；标题、作者、摘要用参数。更新摘要用 `--digest`，网页署名用 `--byline`。
- `save --archived yes` 归档，`--archived no` 恢复，都需要文章 ID 与版本。`list --all` 包含归档。不会删除。
- 网络写入失败不自动重试。新建前 stderr 会给出 saving_id，先用该 ID 读回确认。
- 版本记录默认署名 `zelong/agent`，需要区分执行端可用全局参数 `--source zelong/codex` 等。

## 创作与预览

用户已有明确意图和素材时直接整理、保存、展示，不逐步索要确认。缺少关键事实或目标账号才集中询问。保留本人经历、语气和不确定性，不编故事、数据、心理活动，不用模糊措辞掩饰没核实的事实。不强制字数、三段模板、营销结尾或默认作者。

保存返回的链接打开同一篇文章。网页继续负责 11 套主题、图片和公众号手机预览，不另写渲染器。预览须实际查看正文和配图；保存成功不等于微信导入成功。

## 身体、灵感与回顾

首页包含已同步睡眠、今日感受和灵感；身体页还有日常活动、身体信号和训练记录。`wellbeing` 返回真实记录，缺失日期不能当作零，日汇总的 start/end 不能当入睡和起床时间。小秋可在用户问到时结合原话解读；未授权时不把健康记录自动改写为公众号文章。首页“开始写这篇”保存原话并打开编辑器，尚未接入网页内的大模型自动改写。页面每分钟读取服务器健康状态，切回页面也会检查。`wellbeing.sync` 中的检查时间与记录 received 的内容变化时间不同，不能把检查成功说成新增数据。网页健康区会显示断流/取数异常。

## 手机健康与只读 MCP

当前通路为 iPhone 直接上传服务器，Mac 仅查看；已真机验收健康指标、训练和睡眠分期上传。本机旧桥接任务已卸载，启动文件移出 LaunchAgents 留存，不要为更新网站数据重新启用 Mac 中转。

健康页提供健康指标、训练记录、睡眠分期三个配置入口，使用 iPhone Safari 打开；只给尚未配置的通路创建自动化，避免重名重复。配置存在不代表已收到数据，要分别核对 `sync.sources` 中 iphone / iphone-workouts / iphone-sleep 的成功时间。期望间隔为 15 分钟，但手机锁屏、低电量模式和 iOS 后台调度会影响实际上传；若较久未更新，先检查手机运行日志与健康数据权限。不能承诺每次固定准点，更不能把旧数据的时间改成现在。训练上传正常也不能掩盖健康指标断流。

本机配对 iPhone 的“打开微信时”自动化立即运行快捷指令“书桌健康直传”，依次调用训练、健康指标和睡眠分期，三项“运行时显示”关闭。这个触发不读取微信内容。解锁 iPhone、打开微信后查看网站接收时间，不需要进入 Auto Export。不要把这项 App 打开事件验收说成纯后台定时保证。若用户换设备或改动自动化，先重新核对真实配置与回执，不重复创建同名项。

服务器 `/wechat/api/health/mcp` 使用工作台 owner Bearer 授权，支持只读 get_health_overview、get_health_history、get_workouts。网页与 MCP 共用真实数据；缺失不是零，日期不是实时测量时刻。不要仅凭心率/HRV等数字诊断用户。

2026-10-05 已增加第三条 `iphone-sleep` 分期直传：`health/setup?kind=sleep` 只导出 Sleep Analysis 原始片段，取消汇总和批量请求，日期保留默认。既有日汇总保持独立。服务器兼容实际中文分期名称，重复片段不叠加；有修正时更新覆盖区间。点击每日睡眠柱可查看 `GET /api/health/sleep?day=YYYY-MM-DD` 的真实时间轴、分期时长、逐段列表与当天身体信号。没有片段时只显示汇总，不能从总时长编造阶段。新增通路已加入“书桌健康直传”，运行时显示关闭；保存并重新确认微信自动化引用后，真机打开微信已读回三项成功回执。后续验收须分别检查三条通路，不从一次成功推断永久准点。

## 灵感库与关系图谱

`wxwork ideas` 读取全部灵感原句及其关联，网页入口为 `/wechat/?view=ideas`。

```sh
wxwork keyword "长期迭代"  # 可以只记词，暂不关联原话
wxwork capture-idea --file quote.txt
wxwork link-idea NOTE_ID --revision 0 --keywords '随时创作' '长期迭代' --source-label '与小秋的对话' --source-url 'codex://threads/VERIFIED_THREAD_ID'
```

用户让你记录/整理灵感时，保留实际原话；在关联字段中提炼有依据的关键词、真实记忆背景和已经表达的下一步意图。复用意思准确的已有关键词，让相关原句连接起来，不为凑连线把不同概念强行合并。不知道的场景留空，不从心理标签推测经历。没有依据的建议留在对话里供用户选择，不当作用户既定计划。

`link-idea` 使用 `ideas` 返回的关联 revision（与文章版本无关）。未指定的字段保留，可用 `--context`、`--next-step` 补充背景与下一步；`--keywords` 后面不跟词表示清空关键词。来源链接必须实际核对，不能编造会话 ID。原句不能被这个命令改写，冲突时先重新核对。网页右侧可直接输入关键词并回车保存，不要求先写原句；未关联的词也保留在图谱中，稍后可关联已有原话或补一句新原话。网页支持搜索、关键词筛选、节点拖动/缩放和“整理关联”。同名关键词连到共同节点；连线表达记录中的明确关联，不意味着因果或事实证明。当前未接入网站自动抽词，整理工作由使用本技能的 Agent 或用户完成。

## 微信草稿

得到具体成稿与账号的导入授权后，优先在网页点击“导入公众号草稿”：现有流程会上传正文图片、创建草稿、读回核对并记录回执。已有授权不用再次询问。

需要无界面导入时，使用同一版本已审阅的微信公众号 HTML（只含正文片段、内联样式、已上传微信的图片），不能把 Markdown 或带编辑控件的页面 HTML 传入：

```sh
wxwork draft ARTICLE_ID --revision 9 --html approved-body.html --request-id UNIQUE_OPERATION_ID --confirm
```

HTML 必须与该版本正文和图片一致；命令会校验版本、使用网站保存的标题/作者/摘要/封面，并保存导入回执。该命令不提供 Markdown 渲染或正文图片上传，含本地图片时走网页导入。每次用户新授权的发送使用新 request-id；结果不明时先查微信草稿箱，不能换编号重发。回执保存冲突不影响已创建的微信草稿，不能因此再次导入。

`verified=true` 表示本次微信读回核对通过，`published=false` 表示未正式发布。历史回执不能证明草稿仍存在。不会自动群发或正式发布。

## 安装与授权

配置默认在 `~/.config/wechat-workbench/config.json`，权限必须为 600，格式：

```json
{"url":"https://YOUR-SITE/wechat","token":"WORKBENCH_OWNER_KEY"}
```

这是工作台授权，不是公众号 AppSecret。从已授权部署的私有 `owner.key` 安全配置，不把真实 token 放在参数、聊天或仓库。可用 `WXWORK_CONFIG` 指向另一份私有配置。凭据只会发给配置的 HTTPS 地址，重定向被拒绝。

本机几个 Agent 共享的是用户本人账号。朋友应配置自己的工作台与授权；当前服务是单用户文章库，不具备朋友之间的账号隔离，不要分发用户的 owner.key。

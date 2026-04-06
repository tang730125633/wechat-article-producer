# wechat-article-producer · 公众号文章全流程自动化

> 对话 → 写文 → 排版 → 推送草稿箱，全程不离开聊天界面。
> OpenClaw Skill + 推送工具链 + 一键部署。

**版本**：v1.0 · 2026-04-06
**适用**：OpenClaw 2026.3.x+
**依赖**：WeWrite skill（写作引擎）、微信公众号 API

---

## 这是什么

一个 OpenClaw Skill，让 AI 助手（如"小婷"）在飞书/微信群聊中完成公众号文章的**全流程自动化**：

```
用户："小婷，把刚才聊的写成公众号文章"
         ↓
[1] 从对话中提取核心观点，整理成写作 brief
         ↓ 用户确认
[2] AI 写作（1500-2500 字 + callout + 引用）
         ↓ 用户确认
[3] 排版（wechat-tech/deepread 等 17 种主题）
         ↓
[4] 一键推送到公众号草稿箱
         ↓
✅ "登录 mp.weixin.qq.com → 草稿箱查看"
```

## 实测效果

- ✅ 从 Markdown 到草稿箱推送成功（6 次测试全通过）
- ✅ 支持 17 种排版主题（wechat-tech / wechat-deepread / sspai 等）
- ✅ 封面图自动上传
- ✅ front matter 自动解析（标题/作者/摘要）
- ✅ 微信兼容内联样式（所有 CSS 内联化）
- ✅ 首次使用引导（教用户找 AppID/AppSecret）

## 目录结构

```
wechat-article-producer/
├── skills/
│   └── wechat-article-producer/
│       └── SKILL.md                # 编排 Skill（5 步全流程）
├── toolkit/
│   └── publish_article.py          # 推送脚本（MD → HTML → 草稿箱）
├── examples/
│   └── test-article.md             # 示例文章
├── config.example.yaml             # 微信配置模板
├── style.example.yaml              # 风格配置模板
├── install.sh                      # 一键安装脚本
└── README.md
```

## 🚀 安装

```bash
git clone https://github.com/tang730125633/wechat-article-producer.git
cd wechat-article-producer
./install.sh
```

安装脚本会：
1. 复制 Skill 到 `~/.openclaw/skills/`
2. 复制工具链到 `~/.openclaw/skills/wewrite/`
3. 引导你配置公众号 AppID/AppSecret
4. 验证 API 连通性

## ⚙️ 手动配置

### 1. 微信公众号凭证

复制 `config.example.yaml` 为 `config.yaml`，填入你的公众号信息：

```yaml
wechat:
  appid: "你的AppID"
  secret: "你的AppSecret"
  author: "公众号名称"
```

**怎么找 AppID / AppSecret**：
1. 打开 [微信开发者平台](https://developers.weixin.qq.com)（注意：2025 年 12 月后从公众号后台迁移到这里）
2. 点"公众号" → 选择你的号
3. "基础信息"页面有 AppID
4. "开发密钥"区域点"启用/重置"获取 AppSecret（**只显示一次，立即保存**）
5. 在"API IP白名单"里添加你的公网 IP（`curl ifconfig.me` 查看）

### 2. 单独推送文章

```bash
cd ~/.openclaw/skills/wewrite
python3 publish_article.py article.md --cover cover.png --theme wechat-deepread
```

## 🎨 可用主题

| 主题 | 风格 | 适合 |
|---|---|---|
| `wechat-tech` | 绿色左边框 + 蓝色引用 | 科技/技术文章 |
| `wechat-deepread` | 极简纯净 | 深度分析/行业观察 |
| `sspai` | 少数派风格 | 工具评测/效率文 |
| `latepost-depth` | 晚点红色风格 | 商业深度报道 |
| `modern` | 大圆角药丸标题 | 轻松科普 |
| `minimal` | 极度简约 | 文学/随笔 |

更多主题见 WeWrite 的 `toolkit/themes/` 目录。

## 与 business-advisor 协同

如果同时安装了 [business-advisor](https://github.com/tang730125633/business-advisor) skill：

1. 戴总和小婷聊完战略/团队/投资问题
2. 说"把刚才聊的写成公众号文章"
3. 小婷自动从对话 + 24 本书的知识库中提取观点
4. 生成带行业深度的文章 → 推送到草稿箱

**对话即内容，内容即推文。**

## License

MIT

## 致谢

- [WeWrite](https://github.com/oaker-io/wewrite) — 写作引擎（MIT）
- baoyu-post-to-wechat — wechat-tech 等排版主题
- Tang + Opus — 编排设计与全流程打通

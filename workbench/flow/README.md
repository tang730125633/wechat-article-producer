# 心流与书桌的连接

`index.html` 延续已上线的心流界面、题目、算法、历史记录与对照图；`desk.css` 接入书桌导航和窄屏布局。入口链路是个人站“我的书桌” → 书桌“心流”。

个人答案不写进代码。既有 `comparison_data.json` 和历史数据库留在服务器原位置并受同一登录保护；发布时只替换 `index.html` 与 `desk.css`，不要删除数据文件或覆盖数据库。旧本地原型仍保留在个人战略分析项目的 `outputs/flow-workbook/`。

部署需要 Nginx 为整个 `/flow/`（包括数据文件）与 `/flow/api/` 启用 `auth_request`，子请求指向书桌的 `/api/access`。页面未登录跳转 `/wechat/?next=flow`，接口未登录返回 401。书桌既有会话通过状态检查平滑迁移到站点 Cookie，登录成功仅允许返回固定 `/flow/` 路径。

当前作答仍使用 `flow_assessment_state_v1`，历史仍使用 `flow_assessment_history_v1`；保留旧浏览器内容。新归档等待真实接口响应后才报告同步成功，失败保留本地记录与重试入口。浏览器返回键恢复页面标签，切换题组保留进度。

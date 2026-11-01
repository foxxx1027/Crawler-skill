---
name: page-owned-api-recon
description: |
  当用户动态页面抓不到数据、想复用站点自己那条取数通道、问有没有内部接口时调用；不适用于需要绕过登录/签名/访问控制，或官方已有文档 API。
  When the rendered page has data but the scraper gets an empty shell, and you want the request the page itself uses instead of driving a browser. Not for bypassing auth/signature/access-control, nor when a documented API exists. Triggers: undocumented API, XHR, network panel, HAR, 内部接口, 动态加载, Ajax 数据, 抓不到数据.
source_book: 《Python网络爬虫权威指南（第2版）》 瑞安·米切尔（Ryan Mitchell）
source_chapter: 第2章 p.14；第11章 p.143；第12章 p.156、p.159–163
tags: [api-recon, xhr, dynamic-content, har, json]
related_skills: [api-table-replication, data-path-cost-ladder, dynamic-page-and-min-params, http-request-replication, pagination-acceptance, scrapy-multipage-assembly, semantic-selector-robustness]
---

# 页面自有 API 侦察

## R — 原文 (Reading)

> 当然，这些API 并未打算供除网页本身以外的任何人或者任何事使用，因此开发者未为这些API 提供文档，并且假设（或者说希望）没有人会发现这些API。但是这些API 的确是存在的。
>
> — 瑞安·米切尔，《Python网络爬虫权威指南（第2版）》，第12章，p.159

> • 它们通常包含JSON 或XML。你可以利用搜索/ 过滤字段过滤请求列表。
> • 利用GET 请求，URL 中会包含一个传递给它们的参数……
> • 它们通常是XHR 类型的。
>
> — 同上，第12章，p.159

> 每个API 调用都可以通过留心以下几个字段识别和记录下来：
> • 使用的HTTP 方法
> • 输入 – 路径参数 – 请求头（包括cookie）– 正文内容（对于PUT 和POST 调用）
> • 输出 – 响应头（包括cookie 集合）– 响应正文类型 – 响应正文字段
>
> — 同上，第12章，p.160

---

## I — 方法论骨架 (Interpretation)

核心判断只有一句：**页面能显示数据，就说明浏览器拿到过那份数据；那份数据一定来自某一条可被观察的请求。** 任务不是"猜接口"，而是把那条请求从一堆网络调用里筛出来、记下来、能重放。

**第一步是判定数据在哪。** 先关掉 JS 再打开页面做对照：数据还在，就是服务端渲染，回去解析 HTML；数据消失，才进入 JS 通道。JS 通道又分两种：数据被写死在 `<script>` 里的变量/数组（直接读源码、正则取变量再按 JSON 解析），或由 XHR/fetch 异步拉取（进网络面板）。

**第二步是筛。** 无文档接口有三个可操作特征：返回 JSON/XML、GET 且 URL 带参数、类型是 XHR。在大型站点里可能上百条调用，用"你正在搜的那个词/页面 ID"过滤参数，通常一次就能定位。

**第三步是记。** 找到不等于能用。必须按五要素归档：方法、路径与参数、请求头（含 cookie）、正文（POST/PUT）、响应头与正文字段。记下来才能判断"换个页面/换组参数时它怎么变"，也才能交给别人重放。

**第四步是先验格式。** 接口不一定返回你以为的东西：正常 JSON、`{"success": true}`、错误对象、一段栈跟踪、甚至普通英文都可能出现。解析前先断言格式，把"抓取失败"提前成"数据校验失败"，而不是让 `json.loads` 直接炸。

**最后是边界意识。** 这条通道是给页面自己用的，它没有文档、没有承诺、也可能有签名与频率限制；"能找到"不等于"可以无限调用"，更不等于"可以绕过它的访问控制"。

---

## A1 — 书中的应用 (Past Application)

### 案例 1: Google Maps——经纬度不在 DOM，在 JS 的标记点数组里
- **问题**: 要把一批街道地址整理成经纬度数组，页面上看到的是地图，DOM 里找不到坐标。
- **方法论的使用**: 作者没有解析渲染后的地图，而是去读页面内嵌的 Google Maps JavaScript 文件，定位 `new google.maps.LatLng(...)` 这样的标记点。
- **结论**: "Python 可以轻松地抽取出所有位置在 `google.maps.LatLng()` 里的坐标"，再交给 Reverse Geocoding API 转成规范地址。
- **结果**: 直接从 JS 资源取结构化数据，比截图/OCR/解析 DOM 都省；这也正是"页面自用通道"的第一种形态——数据写死在 JS 里。

### 案例 2: 纽约时报搜索——1 次 60KB vs 100 次 600–700KB
- **问题**: 用 urllib 抓 NYT 搜索结果页，抓不到任何结果，因为结果是 Ajax 单独加载的。
- **方法论的使用**: 在网络面板里找到那条 XHR：`https://query.nytimes.com/svc/add/v1/sitesearch.json?q=python&spotlight=true&facet=true`，按五要素记录后直接请求。
- **结论**: 用 Selenium 加载该页面"将发起100 次请求并在每次搜索时传输600~700KB"，直接调 API "只需发起一次请求，并且只传输你所需要的大约60KB"。
- **结果**: 抓取路径从"浏览器执行"降到"一次 HTTP 请求"，成本差一个数量级，且拿到的就是格式良好的 JSON。

### 案例 3: apiscraper——把"找接口"从手工艺变成流水线
- **问题**: 大型站点一次加载上百次调用，人工在面板里翻找、抄写五要素既慢又容易漏。
- **方法论的使用**: 作者写了 apiscraper：Selenium + ChromeDriver + BrowserMob Proxy 加载页面、滚动到底、把网络流量存成 HAR，再由 `harParser.py` 解析成结构化 API 调用。
- **结论**: 侦察本身是"程序性任务"，可以自动化；输出应是一张可读的 API 调用表，而不是"我找到了"。
- **结果**: 工具支持按初始 URL 抓多页、按关键词筛、去除不影响返回值的参数，并把结果输出为命令行/HTML/JSON。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. **抓到空壳**: 浏览器里数据正常，`requests`/`urllib` 拿到的 HTML 里没有目标内容。
2. **不想上浏览器**: 已知 Selenium/Playwright 能抓到，但嫌慢、嫌重、嫌要维护无头环境，想找更轻的通道。
3. **接口复用**: 想让脚本直接调站点自己用的 JSON 接口，按参数翻页、按 ID 取详情。
4. **接口不稳定**: 已经找到一条接口，但换个页面/换组参数就返回空、返回错误对象或返回 HTML 错误页。
5. **组合数据**: 手上有一个来源的数据，想用另一个站点的接口做交叉解释（如 IP → 地理位置）。

### 语言信号 (用户的话里出现这些就应激活)

- "页面能看到但爬不到" / "返回的 HTML 里没有数据" / "数据是动态加载的"
- "有没有内部接口" / "Network 里那个 XHR 能不能直接用" / "怎么找 undocumented API"
- "抓包" / "HAR 文件" / "请求参数怎么构造" / "接口返回不是 JSON"
- "find the API behind the page" / "XHR / fetch endpoint" / "network panel" / "hidden JSON API"

### 与相邻 skill 的区分

- 与 `data-path-cost-ladder` 的区别: 那个 skill 负责"在所有取数路径里排序"（打印版/移动版→JS 内嵌→slug→换源→请求头→内部 API→浏览器）；本 skill 只负责其中"内部 API / JS 内嵌"这一级的**具体侦察动作**。当用户还没决定走哪条路时，先走阶梯。
- 与 `semantic-selector-robustness` 的区别: 那个 skill 处理"数据已经在 HTML 里，怎么定位"；本 skill 处理"数据根本不在 HTML 里，去哪找那条通道"。
- 与 `http-request-replication` 的区别: 本 skill 输出"接口清单与五要素"，后者负责"把这条请求原样重放并处理会话/失败"。发现接口之后通常要接上它。
- 与 `anti-bot-triage-and-human-parity` 的区别: 接口返回 403/验证页属于反爬分诊，不是侦察问题。

---

## E — 可执行步骤 (Execution)

1. **判定数据位置（关 JS 对照）**
   - 用"禁用 JavaScript 再打开页面"或"查看源代码"对照：目标数据是否在首屏 HTML/内联 script 里。
   - 完成标准: 得出一句结论——"服务端渲染（走解析）"或"客户端获取（继续侦察）"。
   - 判停条件: 若数据在静态 HTML 中，停止本流程，转 `semantic-selector-robustness`。

2. **先查内嵌数据，再查 XHR**
   - 在源码里找 `<script type="application/json">`、`window.__INITIAL_STATE__`、JSON-LD、`data-*`、模板字符串/数组；找不到再打开网络面板（须在页面加载前打开，否则不记录）。
   - 完成标准: 明确记录"数据在 JS 变量 X（可正则提取并 JSON 解析）"或"数据来自 XHR/fetch 请求 Y"。

3. **三特征筛出候选请求**
   - 用面板过滤：类型 XHR/Fetch、响应含 JSON/XML、URL 带本次搜索词或页面 ID 的 GET 参数。
   - 完成标准: 候选收敛到 1–3 条，且能说明每条"为什么是它"（参数里出现了目标标识）。
   - 判停条件: 若过滤后仍 >10 条且无法区分，改用 HAR 归档后离线比对，或检查 WebSocket/GraphQL（书中未覆盖，需另找通道）。

4. **五要素归档**
   - 逐条记录：HTTP 方法、路径参数、请求头（含 cookie/Referer/Origin/X-Requested-With）、正文（POST/PUT）、响应头与正文字段；同时记录"换页面时哪些字段变、哪些不变"。
   - 完成标准: 仅凭这份记录，另一个人不打开浏览器就能重放该请求。

5. **验证可重放性并先验格式**
   - 用最小脚本重放一次；先断言响应是期望格式（JSON/XML），再取字段；对"成功对象/错误对象/栈跟踪/HTML 错误页"分别写分支。
   - 完成标准: 至少两个不同参数取值都能返回期望结构；异常返回被识别为异常而不是被当成数据。
   - 判停条件: 若重放返回 401/403/验证页/签名错误，停止侦察，转 `anti-bot-triage-and-human-parity` 或走官方通道；不得尝试绕过访问控制。

6. **产出清单并按需组合**
   - 把接口写成一张表（用途、方法、URL 模板、必需参数、返回字段、频率约束），并注明"单接口只是复制已发布数据，组合才产生新结论"。
   - 完成标准: 表可直接交给下游 `http-request-replication` 或数据模型设计使用。

---

## B — 边界 (Boundary) ★

**使用范围硬约束：本 skill 仅适用于自有系统、已获得明确授权的目标，或公开的测试环境。它提供的是"观察页面自己发出的请求并记录"的方法，不提供绕过访问控制的具体手段——不涉及绕过登录、验证码、签名、加密、频率限制或任何技术保护措施。**

### 不要在以下情况使用此 skill

- **需要登录态才能看到的接口**: 侦察可以做，但"用别人的登录态去调"超出范围；应走官方 API 或书面授权。
- **接口带签名/nonce/加密**: 现代接口常见 `sign`、`timestamp`、响应加密；本 skill只能记录这些字段的存在，**不提供逆向或伪造手段**。遇到即止，改走官方渠道。
- **已有文档 API**: 有文档、有配额、有 ToS 时直接读文档，不要逆向内部接口"图省事"。
- **为了绕开付费/权限/访问控制**: 即使技术上能找到端点，也不等于有权调用；这是合规判断，转 `scraping-compliance-layering`。

### 作者在书中警告的失败模式

- **不先验格式就解析**: "如果API 没有很好地进行配置，你得到的可能是一个不可解析的栈跟踪（stack trace）或者一些普通的英文文本"（p.156）；直接 `json.loads` 会炸。
- **只盯着"有没有 XHR"**: 数据也可能在 JS 变量、内联 JSON、或非 XHR 通道里；只筛 XHR 会漏。
- **找到但不记录**: 不按五要素归档，换页面就无法判断字段变化，也无法交接（p.160）。
- **把单接口当成果**: "如果你用API 作为唯一的数据源，那么你最多就是复制别人数据库里的数据"（p.163）；价值在组合与解释。

### 作者的盲点 / 时代局限

- **默认端点"裸奔"**: 书中假设无文档 API 可被直接、长期调用；2019 年以后这类端点普遍加了签名、CSRF token、响应加密与指纹风控，这个假设已过期。
- **HAR 方案已换代**: BrowserMob Proxy + Selenium 存 HAR 的做法过时；现代用 Playwright 的 request/response 事件或 CDP 导出，思路（归档成表）不变。
- **通道覆盖不全**: WebSocket、EventSource、GraphQL、gRPC-web 书中未讨论；"找页面自用通道"的判断逻辑仍适用，但具体手法要另补。
- **法律风险一笔带过**: 作者在 p.230 引用了 DMCA"不得绕过安全措施"，却在 p.157–161 教读者直接调内部接口，二者之间缺少"什么时候这条线被跨过"的判据。
- **法律框架纯美国法**: 全书合规讨论基于美国判例，未覆盖 GDPR、中国《网络安全法》《数据安全法》《个人信息保护法》；跨境或涉个人信息时应先咨询本地律师。

### 容易混淆的邻近方法论

- **"内部 API" vs "官方 API"**: 前者无文档、无承诺、可能随时变；后者有配额与条款。不要把两者当成同一条路径。
- **"侦察" vs "反爬分诊"**: 找不到接口是侦察问题，找到但被 403 是分诊问题。
- **"抓包记录" vs "协议逆向"**: 本 skill 只到"记录并重放同一条请求"；签名生成、加密还原属于协议逆向，不在范围内。

---

## 相关 skills (阶段 3 填充)

- depends-on: data-path-cost-ladder
- contrasts-with: semantic-selector-robustness, anti-bot-triage-and-human-parity, dynamic-page-and-min-params, api-table-replication, scrapy-multipage-assembly
- composes-with: http-request-replication, scraping-compliance-layering, pagination-acceptance

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 待测
- **蒸馏时间**: 2026-10-30

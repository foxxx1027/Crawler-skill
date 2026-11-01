---
name: scrapy-new-site-onboarding
description: |
  接手陌生站点要"每天同步数据"、或写 parse 前不确定数据是否在初始 HTML 时调用；也用于"Scrapy 页面与浏览器不一致"分诊。不适用于一次性小任务、已有 API、只差选择器写法、已跑通只差部署。
  When onboarding a new site: is data in the initial HTML? Verify in Shell, then scaffold. Triggers: 新站接入, 数据在哪, Scrapy Shell, scrapy view, onboarding, page differs from browser.
source_book: 《Scrapy网络爬虫实战》 东郭大猫
source_chapter: 第2章 PAGE 21–22（书页 10–11）；第3章 PAGE 89–99（书页 78–88）；第10章 PAGE 219–220（书页 208–209）
tags: [scrapy, onboarding, shell, devtools, workflow]
related_skills: [crawl-scope-and-halt, data-path-cost-ladder, semantic-selector-robustness, scrapy-login-route-choice, scrapy-middleware-layering, scrapy-production-setup]
---

# 新站接入 SOP：先判数据在哪，再验选择器，最后建项目

## R — 原文 (Reading)

> 一个好的习惯是，我们在做元素提取时，始终在 Scrapy Shell中运行检测后再写入代码中，确保不会因为元素提取问题引出异常。
>
> — 东郭大猫，《Scrapy网络爬虫实战》，第10章，PAGE 220（书页 209）

---

## I — 方法论骨架 (Interpretation)

接入一个陌生站点，最大的时间浪费不是写代码，而是在错误的层上反复改选择器。作者把它拆成一条有产物、可回退的流水线，顺序不可颠倒：

**先 Network，后 Elements。** 打开页面第一件事不是选元素，而是看初始 HTML 里到底有没有这批数据：列表页的响应只有几 KB、条数恒等于首页条数，就说明数据来自 XHR 或接口，此时继续在 Elements 里抠选择器是白费。两个面板是互补视图——Network 回答"数据由哪条请求返回"，Elements 回答"这个字段在哪个节点上"。

**Shell 是不可跳过的验收门，不是调试技巧。** 拿到的每条表达式都要对着真实 Response 跑一次，看命中数量与文本，改一行再跑一次；它省掉的是"初始化 Spider→中间件→管道→落库"的整条链路。作者在全书第二次重复这条，说明它被当成硬性流程。

**view 用来分诊"是选择器错，还是页面没渲染"。** 它把 Scrapy 实际下载到的 HTML 丢进浏览器，和正常浏览器并排看：缺失内容若本来就不在静态 HTML 里，结论是通道问题而不是表达式问题。

**建项目是验证之后的事。** 顺序是建骨架 → 选 Spider 模板 → 写 Item 与解析 → 接出口 → 小批量跑通，中间件与调参留到最后。上浏览器（Selenium）是最后一级手段，只在 Network 与 Shell 都证明"静态拿不到"时才用。

一句话判据：每一步都要能当场回答"我验证了什么"，答不上来就说明跳步了。

---

## A1 — 书中的应用 (Past Application)

### 案例 1: quotes 站——不启动爬虫就把四个字段的选择器试出来
- **问题**: 要在写 Spider 前确认标题、名言、作者、标签各自用什么表达式，直接写进 parse 再跑 crawl 反馈太慢。
- **方法论的使用**: `scrapy shell http://quotes.toscrape.com/ --nolog` 起交互终端，先看预置对象（response/request/settings/spider），再依次试 `response.xpath('//title/text()')` 与 `response.css('title::text')` 对比两种写法，最后对 `.quote` 容器做链式提取。
- **结论**: 表达式命中数与文本当场可见，可反复改一行重跑；这些表达式之后原样进入 CrawlSpider 的 parse。
- **结果**: 作者把"Shell 里验证 → 粘进 parse → 再跑 crawl"固定成两段式开发（第3章 PAGE 97，书页 86）。

### 案例 2: view——先分清"选择器写错"和"页面根本没渲染"
- **问题**: 同一个 URL，浏览器里有完整内容，Scrapy 拿到的却是空壳或结构不同，容易误判成选择器 bug。
- **方法论的使用**: 执行 `scrapy view <url>`，用浏览器打开 Scrapy 实际下载到的那份 HTML，与正常页面并排对比，看缺失部分是静态 HTML 本来没有，还是被 JS 注入。
- **结论**: 若确认是 JS 渲染，改选择器无效，应改走 Shell 的 fetch 改写或上 Selenium。
- **结果**: view 被定位为"下载结果的可视化对照工具"，成为通道判断的独立证据（第3章 PAGE 96，书页 85）。

### 案例 3: IT之家——把 Shell 检测写成项目里的习惯条款
- **问题**: 文章页字段多（标题、作者、来源、来源 URL、发布日期、关键词），任一表达式取空都可能让整批数据带缺口。
- **方法论的使用**: 作者在写完 parse_item 之后补一句流程要求——做元素提取时始终先在 Scrapy Shell 里跑检测再写入代码；同时在 close() 里把关闭时间写进 stats 的 finish_time。
- **结论**: 验收门放在"表达式进代码之前"，而不是等 crawl 跑完看日志猜。
- **结果**: 形成"表达式先验、项目后建"的硬性顺序，并把运行起止时间留在 Stats 里便于核对（第10章 PAGE 220，书页 209）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. **接手新站**：领导/客户说"把这个站的数据每天同步下来"，手上只有一个域名，还没想好从哪下手。
2. **写 parse 之前卡住**：不确定目标字段是在 HTML 里还是在接口里，怕写完才发现方向错。
3. **页面不一致**：浏览器能看到的列表，Scrapy 抓回来是空的或只有首页几条，怀疑被反爬。
4. **脚手架选择**：在 startproject / genspider 的 basic、crawl、csvfeed、xmlfeed 模板之间犹豫，不知道该建哪种 Spider。
5. **出口未定**：能抓到数据但不知道落 JSON、文件还是数据库，也没有验收标准。

### 语言信号 (用户的话里出现这些就应激活)

- "这个站的数据怎么抓" / "数据是不是在 HTML 里" / "为什么只抓到第一页"
- "Scrapy 抓到的页面和浏览器不一样" / "response 只有几 KB" / "是不是被反爬了"
- "先用 Shell 试试" / "scrapy shell 怎么用" / "genspider 选哪个模板"
- "onboarding a new site" / "where does the data come from" / "page differs from browser"

### 与相邻 skill 的区分

- 与 `data-path-cost-ladder` 的区别: 那条只判"走哪条取数通道"（打印版/内嵌 JSON/接口/浏览器），本 skill 管从通道判断到项目骨架落地的整段顺序与验收点；通道判完仍要建项目、定出口。
- 与 `semantic-selector-robustness` 的区别: 那个回答"锚点怎么绑、用哪个解析库"；本 skill 回答"什么时候才轮到写选择器"——表达式在 Shell 里命中数不对时，先回本 skill 的步骤 1，而不是加固选择器。
- 与 `scrapy-production-setup` 的区别: 那个是跑通之后的上生产（JOBDIR、部署形态）；本 skill 只到"小批量跑通"为止。
- 与 `crawl-scope-and-halt` 的区别: 那个管"抓多宽、何时停"；本 skill 管"从哪一层开始抓"。

---

## E — 可执行步骤 (Execution)

1. **先判通道：数据在不在初始 HTML 里**
   - 打开 DevTools 的 Network，只留文档请求，看响应体大小与条数。
   - 完成标准: 能写出一句判据——如"响应 6KB、列表 20 条 = 首页条数，数据不在初始 HTML"。
   - 判停条件: 若确认数据由 XHR/接口返回，记录那条请求的 URL、方法与参数，跳到步骤 4（改按接口建 Spider），不要在 Elements 里继续抠。

2. **再定位节点：Elements 里确认字段落在哪个节点**
   - 用鼠标选中目标，右键 Copy selector / Copy XPath 拿到一条能命中的起点表达式。
   - 完成标准: 每条字段都有一条候选表达式，且已标注它依赖的是 id/class 还是"第 N 个元素"。
   - 判停条件: 若同一字段在列表页和详情页结构不同，先分别记录，不要合并成一条。

3. **Shell 验证 + view 对照（验收门）**
   - `scrapy shell <url>` 对真实 Response 跑每条表达式，比对命中数量；再用 `scrapy view <url>` 看 Scrapy 实际下载到的 HTML。
   - 完成标准: 每个表达式命中数与手工点数一致、抽 1 条核对文本无误；且已排除"页面没渲染"这一可能。
   - 判停条件: 若 Shell 里命中为 0 而 view 显示内容确实缺失，判定为通道问题，回步骤 1；若两者都有内容但表达式为 0，才是表达式问题。

4. **建项目与选型：让骨架匹配站点形态**
   - `scrapy startproject` 建骨架；按页面形态选模板——单层列表用 basic，要自动跟进多层用 `genspider -t crawl`，结构化订阅源用 csvfeed/xmlfeed；只想验证一个最小 Spider 时用 `runspider` 跑单文件，不建项目。
   - 完成标准: 能说明为什么选这个模板（"需要按规则跟进三层，所以用 crawl"），而不是复制教程默认值。

5. **定出口与最小验收**
   - 先写 Item 字段，再定落点（JSON 文件/媒体/数据库），写进 Pipeline 并**在 settings.py 注册**。
   - 完成标准: 一条记录能完整穿过 Spider → Pipeline 落盘，且字段无空值缺口。

6. **小批量跑通后才谈中间件与调参**
   - 限 `CLOSESPIDER_ITEMCOUNT` 或小 `start_urls` 跑一轮，核对条数与字段。
   - 完成标准: 跑一轮的条数、字段完整率、状态码分布都有数字；中间件、并发、限速留到这一步之后。
   - 判停条件: 若小批量就出 403/空页，转失败分诊，不要先加中间件掩盖问题。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- **一次性抓几页**：runspider 一个文件十行就够，建完整项目是过度工程。
- **站点已有结构化出口**：官方 API、CSV、RSS、sitemap 存在时，先读结构化数据，别从页面开始。
- **已经能跑通、只是选择器改版失效**：那是 `semantic-selector-robustness` 的活；本 skill 的 Shell 步骤只是复现手段，不是修复方法。
- **需要登录才能看到数据**：通道判断不成立，先解决登录路线，再回来接入。

### 作者在书中警告的失败模式

- **把 JS 空壳当数据源**：只读 Elements 不看 Network，会把异步渲染出来的空 DOM 当成数据来源（第2章 PAGE 21，书页 10）。
- **先写循环再猜选择器**：定位错了，后面的翻页、清洗、落库全部白做（第2章 PAGE 22，书页 11）。
- **Shell 直接打开本地文件**：`scrapy shell index.html` 会把裸文件名当 URL 解析并报错，必须用 `file:///` 或 `./index.html`（第3章 PAGE 96，书页 85）。
- **写了组件却没注册**：Pipeline、中间件只有在 settings 里登记才会实例化，否则代码完整也静默不执行（第5章 PAGE 123，书页 112）。

### 作者的盲点 / 时代局限

- **书是 Scrapy 1.5 的说明书**：`scrapy.contrib.*` 路径、`make_requests_from_url` 等 API 在 2.x 已改或已移除；SOP 的顺序（先判通道、Shell 验证、再建项目）不受影响，命令与导入需按当前版本改写。
- **"页面不一致"只归因到渲染**：书中默认差异来自 JS，未讨论服务端按 UA/Cookie/地区分桶返回不同内容——那种情况下 view 与 Shell 都正常，只有换身份才复现。
- **无增量与分布式概念**：全书按"从头跑一遍"设计，没有断点续跑、增量更新、多机去重，也没有 robots/ToS 的合规讨论。
- **判据靠人工经验**："响应体几 KB 就是接口"这类阈值没有给出量化方法，站点规模一大就会失效。

### 容易混淆的邻近方法论

- **Network vs Elements**：不是"哪个更好用"，而是"这个问题该问谁"——数据来源问 Network，节点位置问 Elements。
- **Shell vs view**：Shell 验表达式，view 验页面内容；顺序是先 view 排除渲染差异，再 Shell 验命中数。
- **建项目 vs runspider**：前者为长期维护，后者为一次性验证；用错方向的代价是要么过度工程，要么代码无法交接。

---

## 相关 skills (阶段 3 填充)

- depends-on: （无）
- contrasts-with: crawl-scope-and-halt、data-path-cost-ladder、semantic-selector-robustness（框架接站 vs 范围/通用取数阶梯/选择器写法）
- composes-with: scrapy-login-route-choice、scrapy-middleware-layering、scrapy-production-setup（接站→登录→中间件→上生产常在同一项目连用）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 92.3%（12/13；应调用召回 6/7，诱饵误触发 0/4，边界判对 2/2；详见 test-results.md）
- **蒸馏时间**: 2026-10-31

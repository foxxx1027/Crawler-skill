---
name: scrapy-crawlspider-rule-division
description: |
   CrawlSpider 只抓到起始页、rules 不跟进、callback 没调用，重写 start_requests 后规则全失效。做法：先按页面角色拆规则（列表页/详情页各自的 allow/deny 与 callback），再核对 parse 是否被占用、入口是否接回。不适用于：部署形态、断点续跑与 allow/deny 工程化（转 scrapy-production-setup）；只抓一层或调宽度不是（转 crawl-scope-and-halt）。trigger：只抓到第一页/rules 不生效/callback 没调用/parse 被覆写/only first page。
source_book: 《Scrapy网络爬虫实战》 东郭大猫
source_chapter: 第4章 PAGE 104–109（书页 93–98）；第10章 PAGE 219（书页 208）；第11章 PAGE 239–244（书页 228–233）
tags: [scrapy, crawlspider, rules, linkextractor, troubleshooting]
related_skills: [scrapy-new-site-onboarding, crawl-scope-and-halt, scrapy-production-setup, semantic-selector-robustness, scrapy-middleware-layering]
---

# CrawlSpider 规则分工：parse 被占用、列表页不回调、入口要接回

## R — 原文 (Reading)

> 用户关注列表页……记录了该用户关注的用户列表，只需跟进此链接进入列表页即可。
>
> 在 4.2.1 节中我们讲过，CrawlSpider 中的 parse() 有特殊的作用不能进行复写，但当重写 start_request() 时仍需将其关联起来。
>
> — 东郭大猫，《Scrapy网络爬虫实战》，第11章，PAGE 240、PAGE 241（书页 229、230）

---

## I — 方法论骨架 (Interpretation)

CrawlSpider 把"抓哪些页、抓到后交给谁、要不要继续跟"写成一组 Rule。它出问题几乎都不是正则写错，而是**职责分错**——三条约定各自对应一种症状：

**parse 是框架的方法，不是你的入口。** CrawlSpider 用 `parse` 按 rules 提取链接并构造跟进请求，这是它能自动爬全站的根本。子类覆写它，rules 整体失效（只剩 start_urls 那几条）；Rule 的 callback 写 `'parse'`，命中页会回到规则分发而不是解析（200 在涨、items 不涨）。要处理起始页用 `parse_start_url`，字段解析一律另起名字（`parse_item`/`parse_quotes`）。

**列表页只喂链接，不产 Item。** 列表/分页规则的职责是把实体链接交回调度器，所以只写 `follow=True`、不写 callback。给它 callback 的代价是同一页被解析两次、或字段从列表页错位取到详情页的结构。判据很简单：这一页有没有你要的字段？没有就不该有 callback。

**入口必须接回规则。** 为了带 Cookie 而重写 `start_requests` 时，起始 URL 若用普通 `Request` 发出，就绕过了 `parse`，CrawlSpider 退化成普通 Spider——rules 明明写了却不跟进。书中做法是在登录后对每个 start_url 调 `make_requests_from_url`，由它生成会走 `parse` 的请求。

**规则按"第一条命中生效"执行**，所以要从窄到宽排；`follow` 的默认值取决于 callback 是否存在（无 callback 时默认 True，有时默认 False），这条默认值正是"列表页漏写 follow"与"详情页意外深层抓取"两种翻车的来源。

**规则描述 URL 的形态，而不是页面的结构。** 书中 IT之家用 `/\d/\d{3}/\d{3}` 匹配文章路径，同一套规则因此能在第三个站点复用；一旦 allow 依赖列表页的 class 或层级，站点改版与换站都会让它失效。

排障顺序：先看 items 是否恒等于已知条目数，再看 dupefilter/enqueued 比例，最后才动正则。

---

## A1 — 书中的应用 (Past Application)

### 案例 1: quotes 站——两类目标页用两条 Rule 分流
- **问题**: 一个站点里既有名言内容页（`/page/N`）又有作者详情页（`/author/xxx`），字段不同，却要用一套 Spider 同时跟进。
- **方法论的使用**: 继承 CrawlSpider，rules 写成 tuple：`Rule(LinkExtractor(allow='/page/\d+'), callback='parse_quotes', follow=True)` 负责内容页并持续翻页；`Rule(LinkExtractor(allow='/author/\w+'), callback='parse_author')` 只解析作者页、不再深层跟进。
- **结论**: 详情页给 callback，列表/分页只 follow；两条规则各自命中、互不干扰。
- **结果**: 内容页持续翻页、作者页只解析一次；同时验证了"callback 为 None 时 follow 默认 True，否则默认 False"的语义（第4章 PAGE 109，书页 98）。

### 案例 2: SegmentFault——四条规则按页面角色分工
- **问题**: 用户主页、关注列表、粉丝列表、列表分页四种页面，只有主页有业务字段。
- **方法论的使用**: 四条 Rule：`/u/\w+$` 命中用户主页，`callback='parse_item'`、`follow=True`；`/users/followed$`、`/users/following$`、`page=\d+` 三条只写 `follow=True`，不写 callback。
- **结论**: 列表页的职责是"把里面的用户主页链接喂回调度器"，它本身不产 Item，所以不该有回调。
- **结果**: 从粉丝/关注列表出发，能逐层扩散到用户主页并解析，四种链接都被触发（第11章 PAGE 239–240，书页 228–229）。

### 案例 3: 重写 start_requests 后，用 make_requests_from_url 把入口接回 parse
- **问题**: 项目要先带 Cookie 登录才能抓，因此必须重写 `start_requests`；但 CrawlSpider 的 `parse` 不能覆写，起始请求一旦绕过它，rules 就全废。
- **方法论的使用**: `start_requests` 先 yield 登录请求，`after_login` 校验登录态后，对每个 start_url 调 `self.make_requests_from_url(url)`，由它生成会走 `parse` 的 Request。
- **结论**: 自定义入口不等于放弃规则链——只要用框架的方法构造起始请求，登录后仍回到 `parse → rules`。
- **结果**: 四条 Rule（主页、关注列表、粉丝列表、分页）都能被触发，且 Cookie 生效；作者在项目篇再次强调"parse 有特殊作用不能复写"（第11章 PAGE 241，书页 230）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. **只抓了一页**：日志里 200 不少，但 items 恒定等于起始页条数，且没有任何报错。
2. **规则不跟进**：Rule 写了、正则也测过，dupefilter/enqueued 几乎不增长，抓取深度停在第一层。
3. **回调没被调用**：命中页确实下载了，但字段解析方法一次都没执行（往往是 callback 写成了 `'parse'`）。
4. **解析了两次**：items 数是详情页数的两倍，或字段值来自错误层级（往往是列表页也被给了 callback）。
5. **登录后失效**：为了带 Cookie 重写 `start_requests`，之后所有 rules 都不生效。

### 语言信号 (用户的话里出现这些就应激活)

- "只抓到第一页" / "rules 不生效" / "follow 没跟"
- "callback 没调用" / "parse 被覆写" / "同一页抓了两次"
- "CrawlSpider 和普通 Spider 的区别" / "LinkExtractor allow 怎么写" / "make_requests_from_url"
- "crawlspider only scrapes the start url" / "rules not followed" / "overriding parse kills rules"

### 与相邻 skill 的区分

- 与 `crawl-scope-and-halt` 的区别: 那个决定"抓多宽、何时停、要不要跟外链"；本 skill 只解决"规则怎么排、为什么抓不到第二层"。规则写对后发现抓不完/跑飞，转那个 skill。
- 与 `scrapy-production-setup` 的区别: 那个讲 Spider 类型选型与上线（JOBDIR、allow/deny 的工程化）；本 skill 是单机排障层的规则职责划分。
- 与 `semantic-selector-robustness` 的区别: 那个管字段表达式怎么写；本 skill 管"哪个方法负责解析哪类页"，回调根本没被调用时改选择器是无效动作。
- 与 `scrapy-middleware-layering` 的区别: 若请求被 Offsite/UrlLength 中间件过滤，症状类似"规则不跟"，但根因在过滤器不在 Rule——先用日志确认有没有 `Filtered offsite request`。

---

## E — 可执行步骤 (Execution)

1. **先给页面分角色**
   - 把站点上的页面列成角色：入口页、列表页、分页页、详情页；标出"哪几类有我要的字段"。
   - 完成标准: 一张角色表，每类页面都能回答"它产 Item 吗、它要往下跟吗"。
   - 判停条件: 若只有一层且有字段，用普通 Spider 更简单，不要上 CrawlSpider。

2. **一条规则只做一件事，从窄到宽排**
   - 详情/实体页：`LinkExtractor(allow=...)` + `callback='parse_<角色>'` + `follow=True`（需要更深时）。
   - 列表/分页页：只写 `follow=True`，不要 callback。
   - 完成标准: 每条 Rule 能一句话说清职责，且正则之间没有重叠区间。
   - 判停条件: 若两条规则会命中同一 URL，先收窄前者，因为"第一条命中生效"，后面的规则不会再看它。

3. **回调方法另起名字，绝不动 parse**
   - 用 `parse_item` / `parse_quotes` / `parse_author`；确实要处理起始页时用 `parse_start_url`。
   - 完成标准: 全项目 `grep 'def parse'` 只命中框架继承来的那个，没有自定义覆写；Rule 里没有 `callback='parse'`。

4. **列表页确认"无 callback、有 follow"**
   - 逐条核对：列表/分页规则的 follow 是否显式为 True（callback 为 None 时才默认 True，靠默认值容易在重构后失效）。
   - 完成标准: 每个列表页规则的 follow 都写死为 True，且该页不产 Item。
   - 判停条件: 若发现 items 数是详情页数的两倍，先查是否有列表页被给了 callback。

5. **重写 start_requests 时把入口接回规则**
   - 登录/带 Cookie 的场景：先 yield 登录请求，成功回调里用 `make_requests_from_url`（现代 Scrapy 用 `scrapy.Request(url, callback=self.parse)`）为每个 start_url 构造请求，保留默认 callback。
   - 完成标准: 起始请求的 callback 指向 CrawlSpider 的 `parse`（或被 make_requests_from_url 生成），而不是你的 `parse_item`。
   - 判停条件: 若起始请求带了 `callback=self.parse_item`，rules 必然不生效，先改回再排查别处。

6. **用三个守恒量验收**
   - 看三组数：`item_scraped_count` 是否约等于详情页数；`dupefilter/filtered` 与 `scheduler/enqueued` 的比例是否合理；日志里有没有 `Filtered offsite request`。
   - 完成标准: items 数与站点实际详情页数量同量级，且没有"200 增长但 items 不变"的分离现象。
   - 判停条件: 若 200 只来自 start_urls、dupefilter 几乎为 0，直接回步骤 3（parse 被覆写）；若 200 增长而 items 不变，回步骤 3（callback 指向 parse）；若起始页之后完全无请求，回步骤 5。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- **只抓一层固定列表**：普通 Spider + 一个 for 循环就够，CrawlSpider 的规则抽象是额外负担。
- **需要 POST、状态机或表单交互**：rules 只做链接跟进，无法表达"先提交再翻页"的流程。
- **数据其实来自接口**：先解决取数通道（JSON/XHR），规则再完美也拿不到数据。
- **要精细控制抓取宽度与停机**：那是 `crawl-scope-and-halt` 的范围；本 skill 只管规则职责。
- **访问控制/登录权限**：Cookie 登录是否被站点允许，需要授权判断，不是规则问题。

### 作者在书中警告的失败模式

- **子类覆写 parse**：Rule 不能把 parse 作为 callback，因为 CrawlSpider 默认用 parse 实现爬虫逻辑，覆写后"将不能继续正确执行"，表现为只抓到 start_urls 第一页（第4章 PAGE 105，书页 94）。
- **Rule.callback='parse'**：命中页会重新走规则分发而不是解析，200 在涨、items 不涨（第4章 PAGE 105，书页 94）。
- **重写 start_requests 用普通 Request**：起始请求绕过 parse，CrawlSpider 退化为普通 Spider，四条规则全部不触发（第11章 PAGE 241，书页 230）。
- **给列表页也写 callback**：同一页被解析两次或字段从错位结构取值；作者在项目里明确列表页"只需跟进此链接进入列表页即可"（第11章 PAGE 240，书页 229）。
- **范围过滤被 dont_filter 穿透**：OffsiteMiddleware 对 `dont_filter` 的 Request 不做域名过滤，规则收窄失效（第7章 PAGE 180，书页 169）。

### 作者的盲点 / 时代局限

- **关键 API 已废**：`make_requests_from_url` 在 Scrapy 1.7 起弃用、2.x 中移除；书中"必须用它接回 parse"的结论要翻译成现代写法——在 `start_requests` 里 `scrapy.Request(url, callback=self.parse)`，原则（入口 callback 必须是 parse）不变。
- **版本与路径漂移**：`scrapy.contrib.*` 路径、`from scrapy.spiders import Rule` 等导入写法在 2.x 已改；照抄书里的 import 会直接失败。
- **没讲规则重叠与优先级**：作者只说"第一条命中生效"，没有给出多规则交错时的调试方法，也没有 `process_links` / `restrict_xpaths` 的实战用法。
- **分布式与增量零覆盖**：整本书假设单机从头跑；多机去重、增量更新、断点续跑在 CrawlSpider 场景下如何做，完全没有讨论。
- **合规视角缺席**："用 Cookie 登录后按规则扩散"只讨论技术实现，未讨论站点是否允许自动化访问、频率与数据范围。

### 合规红线

- 带登录/Cookie 的规则扩散、以及为突破限制而改 `dont_filter`/域名范围：仅限自有系统、已授权目标或公开测试环境；不提供针对未授权目标的攻击配方。

### 容易混淆的邻近方法论

- **CrawlSpider vs 手写递归 parse**：前者用规则声明"哪些链接跟、交给谁"，后者用代码控制流程；规则无法表达条件分支与状态，流程复杂时别硬塞进 rules。
- **callback vs follow**：回调决定"这一页由谁解析"，follow 决定"这一页还要不要继续找链接"；两者独立，列表页只需后者。
- **Rule 范围 vs Offsite/Depth 中间件**：规则是"想抓什么"，中间件是"框架允许抓到什么"；症状相同，证据在日志里。
- **parse_start_url vs parse**：起始页需要特殊处理时用前者；动后者等于接管框架调度。

---

## 相关 skills (阶段 3 填充)

- depends-on: scrapy-new-site-onboarding（先判页面角色，才谈规则分工）
- contrasts-with: crawl-scope-and-halt、scrapy-production-setup、semantic-selector-robustness（框架规则分工 vs 范围/部署/选择器写法）
- composes-with: scrapy-middleware-layering（规则里常挂中间件链）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 100%（13/13；应调用召回 7/7，诱饵误触发 0/4，边界判对 2/2；详见 test-results.md）
- **蒸馏时间**: 2026-10-31

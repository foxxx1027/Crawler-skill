---
name: scrapy-production-setup
description: |
  Scrapy 上生产、或 Scrapy 出现"抓到登录页/被限速/重启后重复抓"时调用：按"遍历什么、抽哪类页"选 Spider 类型，覆盖默认 16 并发零延时，每条 allow 配 deny，用 JOBDIR 让长任务可中断续跑。不适用于：只需算速率预算（转 crawl-pacing-and-concurrency）、只需内容缓存（转 cache-as-cost-tradeoff）。Trigger：Scrapy / CrawlSpider / JOBDIR / Resuming crawl / DOWNLOAD_DELAY / allow deny / 生产化 / 抓全了没。
source_book: 《用 Python 写网络爬虫（第2版）》 Katharine Jarmul / Richard Lawson
source_chapter: 第8章 8.2–8.4（PAGE 175–184）
tags: [scrapy, framework, resilience, production]
related_skills: [crawl-pacing-and-concurrency, crawl-scope-and-halt, cache-as-cost-tradeoff]
---

# Scrapy 生产化：类型选型 + 覆盖默认吞吐 + 可中断续跑

## R — 原文 (Reading)

> 默认情况下，Scrapy 对同一域名允许最多16 个并发下载，并且两次下载之间没有延时，这样就会比真实用户浏览时的速度快很多。该行为很容易被服务器检测到并阻止。
>
> — Katharine Jarmul / Richard Lawson, 第8章 8.2 启动项目（PAGE 175）

> 要开启该功能，我们只需定义用于保存爬虫当前状态目录的JOBDIR 设置即可。需要注意的是，多个爬虫的状态需要保存在不同的目录当中。
>
> — 同上, 第8章 8.4.2 中断与恢复爬虫（PAGE 183）

---

## I — 方法论骨架 (Interpretation)

Scrapy 上手只要几十行，但"能跑"和"能上生产"之间有三个开关必须自己拨。

- **类型选型**看两个变量：遍历范围（单个页面 / 一个域名 / 一类数据源）与抽取目标（一类页面 / 多类）。`Spider` 抓已知的同类页面；`CrawlSpider` 沿链接遍历域名、只抽指定类型；`XMLFeedSpider` / `CSVFeedSpider` / `SitemapSpider` 面向结构化数据源。
- **覆盖默认吞吐**：默认值是为"跑得越快越好"调优的，不是为"礼貌"调优的。新项目第一步就把 `CONCURRENT_REQUESTS_PER_DOMAIN` 改成 1、`DOWNLOAD_DELAY` 改成站点能接受的值（书中示例用 5），并知道延时本身带随机偏移。
- **规则必须成对**：`allow` 只表达"我要什么"，不表达"我不要什么"。查询串编码会把登录页伪装成 `/index/` 的命中，所以每条 `Rule` 都要配 `deny`。
- **可中断续跑**：`JOBDIR` 把调度状态落成 `requests.queue` / `requests.seen` / `spider.state` 三个文件；前提是**优雅退出**（按一次 Ctrl+C 等它写完，按两次会强杀）、多个爬虫各自一个目录。
- 验收不靠"没报错"，靠 `stats` 对账：`downloader/request_count` 与 `item_scraped_count` 要能和业务总量（如数据库行数）对上，`dupefilter/filtered` 说明去重生效。
- 框架接管的是调度、URL 去重、限速、断点、输出格式；**业务主键去重与增量抓取不在框架范围内**，要自己补。

---

## A1 — 书中的应用 (Past Application)

### 案例 1: 用 CrawlSpider 重写第2章的爬虫，代码短了、还能对账

- **问题**: 手写爬虫要自己维护队列、seen、深度、限速、输出，改一处要动多处。
- **方法论的使用**: `scrapy startproject` 后用 crawl 模板生成 `CrawlSpider`，写两条 `Rule`：`/index/` 跟进、`/view/` 交给 `parse_item`；`parse_item` 里用 `response.css(...).extract()` 抽字段。
- **结论**: 调度、去重、限速、CSV 输出都由框架接管，业务代码只剩选择器与 item 组装。
- **结果**: 结束统计 `downloader/request_count: 280`、`item_scraped_count: 252`（与数据库中的国家数量一致）、`dupefilter/filtered: 61`、`request_depth_max: 26`——"因此我们知道爬虫已经找到了所有的国家（或地区）数据"（PAGE 182）。

### 案例 2: allow 命中了登录页，必须补 deny

- **问题**: 规则写 `allow=r'/index/'` 后，日志里出现大量 `/user/login?_next=%2Findex%2F0`、`/user/register?_next=%2Findex%2F0`，白白浪费请求。
- **方法论的使用**: 认出 `?_next=%2Findex%2F1` 就是 `_next=/index/1` 经过 URL 编码的结果，因此它匹配了 `/index/` 规则；给两条 Rule 都加上 `deny=r'/user/'`。
- **结论**: `allow` 只表达"要什么"，"不要什么"必须显式写 `deny`；只加白名单一定会漏。
- **结果**: 登录/注册页不再入队，请求量回到正常水平（PAGE 177）。

### 案例 3: JOBDIR 让一次中断变成"从上次的地方继续"

- **问题**: 抓取中途需要重启机器或修代码，重跑会从头再来。
- **方法论的使用**: 命令行加 `-s JOBDIR=.../crawls/country_or_district`，按一次 Ctrl+C 触发优雅退出（"Received SIG_SETMASK, shutting down gracefully"），确认目录里出现三个状态文件，再用同样的命令重启。
- **结论**: 状态是"队列 + 已见 URL + 爬虫状态"，靠框架落盘，不需要改爬虫代码；但必须等它正常结束。
- **结果**: 重启日志出现 `Resuming crawl (13 requests scheduled)`，从暂停处继续；作者同时注明 cookie/会话过期等边界情况书里没有覆盖（PAGE 183–184）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. 用户已经决定用 Scrapy，问"默认配置能不能直接跑生产 / 要不要改什么"。
2. 任务要跑很多天、运维会重启服务，用户问"怎么不从头再抓一遍"。
3. 日志里出现登录页、注册页、标签页等无关 URL，请求量明显偏高。
4. 爬完了，用户问"怎么知道抓全了 / 有没有漏"，需要一套验收口径。
5. 要选爬虫类型：只有一个列表页要翻，还是要沿链接遍历整个域名。

### 语言信号 (用户的话里出现这些就应激活)

- "Scrapy 默认配置 / 要不要改 settings / CONCURRENT_REQUESTS_PER_DOMAIN"
- "JOBDIR / 中断续跑 / 重启后重复抓 / Resuming crawl"
- "爬到登录页了 / 规则把无关链接也抓了 / allow 只管白名单吗"
- "选 Spider 还是 CrawlSpider / SitemapSpider 怎么选"
- "怎么验证抓全了 / item 数和数据库对不上 / dupefilter"
- "Scrapy 能不能上生产 / scrapy 2.x 和书里的差异"

### 与相邻 skill 的区分

- 与 `crawl-pacing-and-concurrency` 的区别：后者负责"算出速率预算"（并发与延时是同一笔账、先测拐点）；本 skill 只负责把那个结论**落到 Scrapy 的两个 settings 上**，并处理规则与续跑。
- 与 `cache-as-cost-tradeoff` 的区别：JOBDIR 的 `requests.seen` 是 URL 级去重游标，不是内容缓存；要"命中即不下载、可离线复用"是后者的范围。
- 与 `form-hidden-state-and-readback` 的区别：JOBDIR 不保存 cookie/会话，所以带登录的长任务在会话过期后仍会失败——那种情况要先解决会话可重入。
- 与 `data-path-cost-ladder` 的区别：本 skill 假设"已经确定要爬 HTML 列表页"，不讨论是否该改走接口。

---

## E — 可执行步骤 (Execution)

当 skill 被激活后，agent 应按以下步骤执行：

1. **选 Spider 类型**
   - 回答两个问题：遍历范围（单页 / 单域名 / 一个 feed）与抽取目标（一类页 / 多类页），据此落到 `Spider` / `CrawlSpider` / `XMLFeedSpider` / `CSVFeedSpider` / `SitemapSpider`。
   - 完成标准: 能一句话说清"我用 X，因为它要遍历 Y、只抽 Z"；说不清就说明还没想清抓取边界。

2. **覆盖默认吞吐值**
   - 在 `settings.py` 里设 `CONCURRENT_REQUESTS_PER_DOMAIN = 1`、`DOWNLOAD_DELAY = <站点可接受值>`（不低于 robots 的 `Crawl-delay`）。
   - 完成标准: 两个值都有明确来源（robots 或实测），不是照抄；确认随机偏移已生效（Scrapy 2.x 默认开启）。

3. **规则成对：每条 allow 配一条 deny**
   - 为每条 `Rule` 写 `deny`，覆盖登录/注册/用户中心/搜索等无关路径。
   - 完成标准: 用一条形如 `/user/login?_next=%2Findex%2F1` 的 URL 自测，验证它不会入队；日志中不再出现登录页请求。

4. **开 JOBDIR 并演练一次中断**
   - 加 `-s JOBDIR=<每爬虫独立目录>`，按一次 Ctrl+C 等优雅退出，确认目录里出现 `requests.queue` / `requests.seen` / `spider.state`，再用同命令重启。
   - 完成标准: 重启日志出现 `Resuming crawl (...)`，且请求计数从断点处继续而不是从 0 开始。
   - **判停条件**: 若爬虫带登录态，先说明"JOBDIR 不保存会话"，需要额外做会话重入，否则续跑仍会失败。

5. **拿 stats 对账验收**
   - 读结束统计里的 `downloader/request_count`、`item_scraped_count`、`dupefilter/filtered`、`request_depth_max`。
   - 完成标准: `item_scraped_count` 与业务总量（数据库行数、sitemap 条目数）相等，或差异有明确解释（如分页上限、被 deny 的路径）。

6. **补框架外的两个缺口**
   - 在 pipeline 里按**业务主键** upsert；用增量游标只抓变动集。
   - 完成标准: 同一记录的两个不同 URL（排序参数、路径别名）不会入库两次；第二次运行只处理变动部分。
   - **判停条件**: 若规模已到跨机/百万级，转共享队列方案，而不是继续加大单机并发。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- 还在纠结"允不允许抓、抓多快"：先过 `scrape-preflight-and-entry-ladder` 与 `crawl-pacing-and-concurrency`，本 skill 不负责合规与速率推导。
- 数据其实来自 XHR/JSON 接口：Scrapy 也能发请求，但入口选型归 `data-path-cost-ladder`。
- 只需要给 requests 加缓存：用 `cache-as-cost-tradeoff`，不必引入框架。

### 作者在书中警告的失败模式

- **直接沿用默认值**：默认 16 并发 + 零延时"很容易被服务器检测到并阻止"，作者据此要求新项目第一步就改（PAGE 175）。
- **只写 allow**：登录链接因 URL 编码命中白名单，浪费大量请求（PAGE 177）。
- **打断不优雅**：要保存状态"就必须等待它正常结束，而不能……再次按下终止键强行立即关闭"（PAGE 184）。
- **JOBDIR 覆盖不到会话**：作者自己承认 cookie/会话过期等边界情况"在这里没有覆盖"（PAGE 184）。
- **把 URL 去重当业务去重**：`dupefilter` 只按 URL 判重，同一实体的不同 URL 仍会重复。

### 作者的盲点 / 时代局限（Scrapy 版本差异）

- 书中是 **Scrapy 1.3.3**，当前是 2.x：`RANDOMIZE_DOWNLOAD_DELAY` 已默认 `True`；`.extract()` 现在多写作 `.get()` / `.getall()`；`scrapy genspider -t crawl`、`--output` 仍可用；settings 名基本未变。
- **Portia**（8.5 节的可视化标注）已基本停更，不建议再走那条路径；改用 Scrapy + 手写选择器或 Scrapely 类方案。
- 书中把"能中断续跑"当成接近万无一失，实际还要处理：状态文件与代码版本的兼容、`requests.seen` 过大后的内存/磁盘、以及关联的会话失效。
- 全书用自制示例站教学，真实站点的 429/验证码/反爬不会出现在 stats 里，验收口径需自行补监控。

### 容易混淆的邻近方法论

- JOBDIR（URL 级调度游标）vs 内容缓存（HTML + 状态码 + 过期）：前者保证不重复调度，后者保证不重复下载。
- `CrawlSpider` 的 `Rule`（链接过滤）vs `allowed_domains`（域名边界）：前者管路径，后者管站外，两者都要设。

---

## 相关 skills (阶段 3 填充)

- depends-on: `crawl-pacing-and-concurrency`（先算出速率预算，再来落 settings）
- contrasts-with: `cache-as-cost-tradeoff`（去重游标 vs 内容缓存）
- composes-with: `form-hidden-state-and-readback`（带登录的长任务需先解决会话重入）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 待测
- **蒸馏时间**: 2026-10-30

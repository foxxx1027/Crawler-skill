---
name: scrapy-middleware-layering
description: |
  中间件不生效、顺序不对、请求消失、403/404 进不了回调时调用；也用于判断该写 Downloader 中间件、Spider 中间件还是 Pipeline。不适用于单请求例外、字段清洗、部署上线。
  When a middleware no-ops, runs out of order, drops requests, or non-2xx never reaches the callback. Triggers: 中间件不生效, order, 543, middleware not working, request dropped.
source_book: 《Scrapy网络爬虫实战》 东郭大猫
source_chapter: 第7章 PAGE 176–188（书页 165–177）
tags: [scrapy, middleware, ordering, contract, troubleshooting]
related_skills: [crawl-pacing-and-concurrency, crawl-scope-and-halt, http-request-replication, scrapy-production-setup, scrapy-cookie-pool-selfheal, scrapy-crawlspider-rule-division, scrapy-new-site-onboarding, scrapy-settings-precedence-triage]
---

# 中间件选层、order 坐标与返回契约

## R — 原文 (Reading)

> 第一个中间件是最靠近引擎的，最后一个中间件是最靠近Spider的。……如果不能确定自己的自定义中间件应该靠近哪个方向，就在500～700之间选择最为妥当。
>
> — 东郭大猫，《Scrapy网络爬虫实战》，第7章，PAGE 177（书页 166）

---

## I — 方法论骨架 (Interpretation)

中间件出问题，几乎都能被三问定位，顺序固定：**写对层了吗 → order 与 BASE 表对得上吗 → 返回值合契约吗**。

**第一问，层。** 三条扩展轴各管一段：Downloader 中间件处理 Engine↔Downloader 的请求与响应，能改 URL、头、代理、Cookie、超时；Spider 中间件处理进入 Spider 的 Response 和 Spider 吐出的 Item/Request，能统计、过滤、改写；Pipeline 只碰 Item，负责清洗、校验、落库。把字段清洗写进 Spider 中间件，或把请求改道写进 Pipeline，都能"跑通"，但后续复用、测试、排障会成倍变难。

**第二问，order。** 自定义项与内置 `*_MIDDLEWARES_BASE` 是**合并**（不是覆盖），再按数字升序排成一条链。数字小 = 靠近引擎，数字大 = 靠近 Spider/Downloader；response 方向是逆序。依赖某个内置项产物（Cookies、Retry、Redirect）就必须排在它之后。拿不准落 500–700；要禁用内置项，在同路径写 `None` 而不是删掉。同号的多个自定义项，实际先后只能靠 BASE 表推，不能凭直觉。

**第三问，契约。** 返回值是路由信号，不是"随便返回"：`process_request` 返回 None 继续、Response 短路、Request 丢弃当前链重调度、抛 IgnoreRequest 走 errback；`process_spider_output` 必须原样透传 Item 与 Request，只 `yield item` 会把翻页请求吞掉且不报错；只观察也必须显式 `return None`，漏写 return 等于意外放行。

三个看似无关的症状由此归位：404 进不了回调（HttpError 层拦的）、翻页请求消失（output 吞的）、"改了没作用"（层或 order 错了）。

---

## A1 — 书中的应用 (Past Application)

### 案例 1: 链家项目——两个中间件都登记 543，靠 BASE 表推真实顺序
- **问题**: 要同时加两段逻辑：Spider 侧统计同一小区出现次数，Downloader 侧每个请求随机注入一个代理。
- **方法论的使用**: 两段分别写进 `LianjiaSpiderMiddleware`（process_spider_output 里 `stats.inc_value(小区名)`）与 `LianjiaDownloaderMiddleware`（`from_crawler` 读 `PROXY_LIST`，process_request 里 `random.choice` 后写 `request.meta['proxy']`），settings 里两者都填 543。
- **结论**: 同号并不冲突——Spider 与 Downloader 是两条独立的链，各自与对应 BASE 合并排序；代理注入交给内置 HttpProxyMiddleware 消费，资源池与选择策略分离。
- **结果**: 运行后 Stats 输出各小区出现次数（万年花城三期 1、三环新城 7 号院 2 等），证明两段中间件都已生效（第7章 PAGE 187，书页 176）。

### 案例 2: HttpErrorMiddleware——404 进不了 callback，不是解析写错
- **问题**: 有一批 URL 明明能访问，回调里的解析逻辑却完全没执行，items 也没有这些记录。
- **方法论的使用**: 回到层去看：内置 HttpErrorMiddleware 在 Spider 之前就过滤掉非 2xx/3xx 响应；要处理 404，需要显式放行——Spider 级 `handle_httpstatus_list`、项目级 `HTTPERROR_ALLOWED_CODES`、或请求级 `meta['handle_httpstatus_list']`，也可以 `handle_httpstatus_all=True`。
- **结论**: "解析没执行"的第一嫌疑人不是 parse，而是中间件层；放行后还必须在回调里自己判 `response.status`。
- **结果**: 作者同时提醒"除非必要且目的明确，否则不推荐处理非 200 状态码"——放行面越大，脏数据越多（第7章 PAGE 179–180，书页 168–169）。

### 案例 3: process_spider_output 只 yield item，翻页请求被无声吞掉
- **问题**: 作者在链家与第 11 章 SegmentFault 两处都按"遍历 result，只回传 Item"的方式实现 Spider 中间件。
- **方法论的使用**: 契约原文写明该方法"必须返回包含 Request 或 Item 的可迭代对象"：Item 交给 Pipeline，Request 交给调度器。但实现里用 `isinstance` 过滤后只 yield item，非 Item 分支被丢弃。
- **结论**: Spider 的 result 是混合流，中间件是必经出口闸门；只透传一半，等于把后续请求全部截断。
- **结果**: 表现为深度停在起始页、详情/翻页请求凭空消失，日志无报错——这是本书自己踩中、也最容易复现的一类隐性 bug（第7章 PAGE 178、第11章 PAGE 244，书页 167、233）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. **加了不生效**：中间件类写好了、也 import 了，但代理没换、头没加、统计没出，日志一切正常。
2. **顺序不对**：自定义项依赖 Cookie/Retry/Redirect 的产物，但明显在它之前跑了；或两个中间件互相看不到对方的改动。
3. **请求消失**：翻页、详情页请求没发出，`enqueued` 数远小于预期，没有任何 error。
4. **状态码被拦**：403/404/302 的响应进不了回调，用户以为解析写错或"被反爬"。
5. **选层犹豫**：一段逻辑（去重、UA 轮换、字段归一化、落库前校验）不知道写 Downloader 中间件、Spider 中间件还是 Pipeline。

### 语言信号 (用户的话里出现这些就应激活)

- "中间件不生效" / "order 填多少" / "543 是什么意思"
- "请求凭空消失了" / "翻页没发出去" / "items 为 0 但日志正常"
- "404 进不了 parse" / "403 页面拿不到" / "handle_httpstatus_list"
- "middleware not working" / "request dropped" / "wrong order"

### 与相邻 skill 的区分

- 与 `scrapy-production-setup` 的区别: 那条讲部署形态、JOBDIR 续跑、allow/deny 面；本 skill 只解决"写了却不生效/顺序不对/请求消失"这类链条内部问题。
- 与 `crawl-pacing-and-concurrency` 的区别: 那个调速率旋钮并用 stats 验收；本 skill 处理的是链路结构，限速失败（被封）应转那个 skill，而不是加中间件。
- 与 `crawl-scope-and-halt` 的区别: 那个决定"抓多宽、何时停"；本 skill 只解释 Offsite/Depth/UrlLength 这些内置中间件为什么在过滤你的请求。
- 与 `http-request-replication` 的区别: 那个复现单次请求（含头、Cookie、表单）；本 skill 管请求在链上的走向与返回值契约。

---

## E — 可执行步骤 (Execution)

1. **判层：这段逻辑改的是"请求/响应"还是"Item"**
   - Downloader 轴：改 URL、头、代理、Cookie、超时、重试决策；Spider 轴：进入 Spider 的 Response、吐出的 Item/Request、统计；Pipeline：字段清洗、校验、落库。
   - 完成标准: 写出"这段逻辑在第 X 层，因为它在 Y 之前/之后必须看到 Z"的一句话理由。
   - 判停条件: 若只是"某一个请求要例外"（单个 URL 放宽状态码、单个站加超时），改用 Request.meta，不要新建中间件。

2. **定 order：先查 BASE 表坐标，再选数字**
   - 打开对应 `*_MIDDLEWARES_BASE`，找出依赖项的位置（如 Cookies 700、Redirect 600、Retry 550）；自定义项要看到它的产物就排在其数字之后。
   - 完成标准: 每个自定义项都能指向 BASE 表里的一个参照项，并说明在前还是在后。
   - 判停条件: 若确实没有依赖关系，直接落 500–700，不要为了"好看"编数字。

3. **写方法并显式返回**
   - `process_request` 想继续就 `return None`（不能漏）；要改道 `return Request`；要用本地/缓存响应 `return Response`；放弃就抛 `IgnoreRequest`。
   - `process_spider_output` 用生成器逐项透传：需要加工的 Item 改完再 yield，Request 原样 yield。
   - 完成标准: 每个分支都有明确 return，没有靠"函数末尾自然结束"的路径。

4. **契约自检：用守恒量对账**
   - 对同一次运行比较：Spider 吐出的 Request 数 vs `scheduler/enqueued`；callback 数量 vs `item_scraped_count`；放行状态码前后的 `httperror/allow_status` 计数。
   - 完成标准: Request 数量守恒（除显式改道外不减少），Item 数量与已知条目数一致。
   - 判停条件: 若 Request 数减少且代码里有 `for item in result` 只 yield item 的写法，先改透传再看别处。

5. **验收：用日志与 Stats 证明"这段逻辑真的执行了"**
   - 内置项的日志是证据：`Filtered offsite request to ...`、`Ignored`、`Retrying ...`；自定义项应留下可搜索的一行日志或一个 stats 键。
   - 完成标准: 能贴出一条日志或一个 stats 数字，证明该中间件在目标请求上被调用过；禁用项则确认同路径已写 `None`。
   - 判停条件: 若完全没有任何痕迹，回步骤 1 检查是否注册在错的 settings 字典里（SPIDER 与 DOWNLOADER 不可混用）。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- **单请求例外**：只有一个 URL 要放宽状态码/加超时/换代理时，用 `Request.meta` 覆盖，别为此写中间件。
- **字段清洗与落库**：日期归一化、去重、写库属于 Pipeline；放进 Spider 中间件会与 Item 定义分离，既难测也容易吞请求。
- **只是想跑得更快/不被封**：那是速率预算与失败分诊的问题，加中间件只会把症状藏起来。
- **部署与续跑**：JOBDIR、多机、调度去重是 `scrapy-production-setup` 的范围。

### 作者在书中警告的失败模式

- **process_spider_output 只 yield item**：契约要求透传 Request，书中两处实现都只回传 Item，导致翻页链断裂且日志无错（第7章 PAGE 178、第11章 PAGE 244，书页 167、233）。
- **把日期归一化塞进中间件**：注册日期有"绝对日期/3 天前/3 小时前"三种形态，作者放在 process_spider_output 里统一转换，规则与 Item 定义分离、复用困难（第11章 PAGE 244，书页 233）。
- **默认放行面的代价**：HttpErrorMiddleware 只放 200–300，随便放开 404 会让脏数据进入 Item；作者明确"除非必要且目的明确"，不推荐处理非 200（第7章 PAGE 180，书页 169）。
- **dont_filter 会穿透范围过滤**：OffsiteMiddleware 对设置了 `dont_filter` 的 Request 不做域名过滤，范围控制会失效（第7章 PAGE 180，书页 169）。

### 作者的盲点 / 时代局限

- **API 已换代**：全书用 Scrapy 1.5，`scrapy.contrib.*` 路径与同步中间件写法在 2.x 已变（新版支持 `async def` 中间件、路径迁到 `scrapy.downloadermiddlewares.*`）；"合并而非覆盖、order 是坐标、返回值是契约"这三条不变。
- **没有分布式视角**：书中中间件假设单进程；Scrapy-Redis 一类分布式去重、共享 Cookie 池带来的"中间件在多机上不一致"完全未覆盖。
- **只讲"能不能跑通"，不讲并发安全**：中间件实例是共享的，作者的项目代码直接在实例上存状态（stats、代理列表），在多线程/异步下是否需要加锁、状态是否会串，书中没有讨论。
- **对"中间件当业务层"的代价讲得不够**：作者自己就在 Spider 中间件里做字段加工，只留下"复用困难"这一句提示，没有给出可替代的分层规范。

### 合规红线

- 代理池、UA 池、Cookie 池这类身份轮换中间件：仅限自有系统、已授权目标或公开测试环境；不提供针对未授权目标的攻击配方。

### 容易混淆的邻近方法论

- **中间件 vs Pipeline**：两者都能"处理数据"，区别是中间件在链上、能改路由，Pipeline 只在 Item 出口、不能改请求走向。
- **order 数字 vs 优先级**：数字不是"重要程度"，是位置坐标；数字小靠引擎、大靠端，response 方向逆序。
- **禁用 vs 删除**：禁用内置项要在项目 settings 里写 `None`；不写只是"没动它"，写了才是不启用。
- **Spider 中间件 vs Downloader 中间件**：前者看得到 Item，后者看得到原始 Response（含状态码、头），选错层就拿不到需要的字段。

---

## 相关 skills (阶段 3 填充)

- depends-on: （无）
- contrasts-with: crawl-pacing-and-concurrency、crawl-scope-and-halt、http-request-replication、scrapy-production-setup（中间件机制 vs 节奏/范围/复刻/部署）
- composes-with: scrapy-cookie-pool-selfheal、scrapy-crawlspider-rule-division、scrapy-new-site-onboarding、scrapy-settings-precedence-triage（这些能力都靠中间件落地）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 100%（14/14；应调用召回 8/8，诱饵误触发 0/4，边界判对 2/2；详见 test-results.md）
- **蒸馏时间**: 2026-10-31

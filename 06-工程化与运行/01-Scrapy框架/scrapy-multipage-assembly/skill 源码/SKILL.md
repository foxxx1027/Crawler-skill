---
name: scrapy-multipage-assembly
description: |
  当一个 Item 的字段分散在多个页面、需要二级页/三跳接力，或出现"成功率很高但入库记录缺字段"时调用：用 meta 携带半成品逐跳补字段，按 Failure 类型分派补救，末跳前断言字段齐备。不适用于单页即可取全、数据其实在接口里，或只需复现单次请求的场景。
  Triggers: 二级页, 详情页, meta 传参, 半成品 Item, errback, 多跳, 缺字段, multi-page assembly, callback chain, Failure.check.
source_book: 《Scrapy网络爬虫实战》 东郭大猫
source_chapter: 第6章 PAGE 168–173；第11章 PAGE 235–246；第5章 PAGE 124–128
tags: [meta, errback, item-assembly, multipage, scrapy]
related_skills: [scrapy-crawlspider-rule-division, http-request-replication, page-owned-api-recon, scrapy-login-route-choice, scrapy-production-setup]
---

# 二级页组装：meta 半成品接力与 errback 分类

## R — 原文 (Reading)

> 许多情况下，我们需要在不同的回调函数间传递参数，这时就可以使用Request.meta来处理参数的传递。
>
> — 东郭大猫，《Scrapy网络爬虫实战》，第6章，PAGE 171（书页 160）

> errback指定的异常处理方法接收一个TwistedFailure实例作为第1个参数，可用于追踪连接超时、DNS 错误等。
>
> — 同上，第6章，PAGE 172（书页 161）

---

## I — 方法论骨架 (Interpretation)

一个 Item 的字段分散在列表页、详情页、作者页时，Scrapy 的 `parse` 不能"等所有页抓完再返回"，只能一跳一跳把半成品传下去。

标准做法是：第一个回调 `new` 出 Item，填本页能拿到的字段，`request.meta['item'] = item`，再 `yield` 下一跳的 Request；下一跳 `item = response.meta['item']`，补字段后继续传或最终 `yield`。

这解决了"跨回调状态"的问题，但留下一个更隐蔽的问题：**meta 只保证传播，不保证成功**。任一跳失败，Item 就永久停在半成品状态，而末跳的 `yield` 并不知道自己少了字段——数据静默缺失，Stats 上却是一次成功抓取。

所以接力必须配两件事：

1. **每跳挂 errback，并按 Failure 类型分派补救**。`HttpError` 把 URL 与缺失字段写入补抓清单；`DNSLookupError`/`TimeoutError` 换代理或重试；未匹配的走默认。只记一行日志等于没有补救。
2. **末跳前断言关键字段齐备**。缺字段的记录标 `pending` 或进补抓集合，不写入正式集合；字段清洗放 Pipeline，不塞进 Spider 中间件。

还有一个机制要记住：`meta` 会随重定向与重试继承，所以它能保留上下文，但不能用来判断"这是第几次尝试"。

---

## A1 — 书中的应用 (Past Application)

### 案例 1: 示例 6-2——用户名在第一页，年龄在第二页
- **问题**: 同一个 Item 的字段出现在两个页面；回调之间不能直接共享局部变量。
- **方法论的使用**: `parse_page1` 里 `new` 出 Item，填 `name`，把 `request.meta['item'] = item` 后 `yield request`；`parse_page2` 里 `item = response.meta['item']`，补 `age`，最后 `yield item`。
- **结论**: 只要后续请求还需要前一页的中间结果，就用 meta 携带，而不是全局变量或类属性。
- **结果**: 第二页产出完整 Item；同一手法后来被复用到项目的二级页（第6章 PAGE 171）。

### 案例 2: SegmentFault 三跳——主页→问题详情→徽章详情
- **问题**: 用户主页给属性与统计，问题详情页给回答标签，徽章详情页给徽章名称与数量；一个 Item 要跨三页凑齐。
- **方法论的使用**: `parse_item` 建 20 字段 Item，把 Item 与徽章详情页 URL 都放进 meta；`parse_answer` 先 `item = response.meta['item']`、`badge_url = response.meta['badge_url']`，补问题标签后继续传；`parse_badge` 再取 `response.meta['item']`，补徽章字段，末跳才 `yield`。
- **结论**: 半成品 Item 逐跳接力，每一跳都要显式取出与改写 meta，而不是依赖隐式继承。
- **结果**: 完整 Item 落入 `userinfo` 集合；跳数与七步抓取流程的骨架一一对应（第11章 PAGE 245–246、PAGE 237）。

### 案例 3: httpbin——errback 按异常类型分派
- **问题**: 一组 URL 会分别触发 DNS 失败、超时、非 200 响应；统一 `try/except` 无法区分"该换代理、该重试还是该补抓"。
- **方法论的使用**: Request 同时挂 `callback` 与 `errback`；errback 先 `logger.error(repr(failure))` 留全量现场，再用 `failure.check(HttpError)` 取 `failure.value.response`，`failure.check(DNSLookupError)` 与 `TimeoutError, TCPTimedOutError` 取 `failure.request`，每类分别记录 URL 与处置。
- **结论**: Failure 是可判别的事件；不同失败原因需要不同补救时，用 `check` 路由而不是统一重试。
- **结果**: 三类错误各自留下 URL 与原因，后续可分别处理（第6章 PAGE 172–173）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. **列表页 + 详情页**: 列表只能给标题与链接，正文、作者、日期在详情页。
2. **三跳以上**: 详情页还要再进作者页/徽章页/评论页才能凑齐字段。
3. **静默缺字段**: 日志与 Stats 都显示抓取成功，但入库记录里某些字段大量为空，且没有补抓。
4. **失败没兜底**: 中间跳偶发 404/超时，最终仍 yield 了缺字段的 Item。
5. **媒体/附件要带业务字段**: 下载文件名需要请求以外的 Item 字段。

### 语言信号 (用户的话里出现这些就应激活)

- "二级页怎么抓" / "详情页字段怎么合并" / "meta 怎么传 Item"
- "三跳怎么接力" / "半成品 Item" / "callback 链"
- "成功率很高但数据不全" / "字段为空没报错" / "404 之后没补抓"
- "multi-page assembly / callback chain / meta item / errback / Failure.check"

### 与相邻 skill 的区分

- 与 `scrapy-crawlspider-rule-division` 的区别: 那条决定"抓哪些链接、列表页要不要 callback"；本 skill 决定"已经进入的这几页，字段怎么逐跳拼成一条记录"。
- 与 `http-request-replication` 的区别: 那条复现单次请求；本 skill 管理跨多个回调的状态链与失败兜底。
- 与 `page-owned-api-recon` 的区别: 如果所有字段其实在一个接口响应里，就不该做多跳；先侦察接口，再决定是否需要组装。
- 与 `scrapy-production-setup` 的区别: 那条讲部署、JOBDIR 续跑与长任务恢复；本 skill 讲单条记录在运行期内的接力与补抓清单。
- 与 `scrapy-login-route-choice` 的区别: 那条解决登录身份；本 skill 解决登录之后、跨页字段的组装。

---

## E — 可执行步骤 (Execution)

1. **画字段—页面矩阵**
   - 列出 Item 每个字段来自哪一页、哪一跳；标出必须跨页的字段与可选的并行分支。
   - 完成标准: 每一跳的输入/输出字段明确，没有来源不明的字段。
   - 判停条件: 若某字段实际在同一页或同一接口可得 → 拆掉该跳，减少失败面。

2. **首跳建半成品**
   - 首个回调 `new` 出 Item，填本页字段，写入固定的 meta 键（如 `meta['item']`），再 `yield` 下一跳 Request。
   - 完成标准: 下一跳能取到非空半成品；meta 键名固定且全项目一致。

3. **中间跳接力**
   - 每跳 `response.meta['item']` 取出并补字段；并行分支把 URL 也放 meta，分别 `yield`；构造新 Request 前显式改写 meta。
   - 完成标准: 每条记录的跳数与矩阵一致；重定向/重试后仍能取到原 Item 与 URL。

4. **失败按类型分派**
   - 每个跨页 Request 同时挂 `callback` 与 `errback`；errback 先记录 `repr(failure)`，再 `failure.check(HttpError)` → 写补抓清单；`DNSLookupError`/`TimeoutError` → 换代理或重试；其余走默认。
   - 完成标准: 人为让中间跳 404，补抓清单出现该 URL 与缺失字段；不是只多一行日志。
   - 判停条件: 若某跳失败率高且集中 → 先修该跳的取数方式或权限，别用加大重试掩盖。

5. **末跳断言与入库**
   - 末跳 `yield` 前断言关键字段齐备；缺则标 `pending` 或进补抓集合，不写正式集合；字段清洗放 Pipeline，不放 Spider 中间件。
   - 完成标准: 抽查 20 条记录，关键字段缺失率为 0；补抓后可回填。

6. **验收：成功率与可用率分开看**
   - 对比 Stats 的 `item_scraped_count` 与"字段齐全条数"；故意制造 30% 中间跳失败，观察是否静默缺字段。
   - 完成标准: "抓取成功率"与"可用数据率"两个数字都可见，差值有解释与补抓路径。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- **单页即可取全**: 再加 meta 只是无谓复杂度，也增加失败面。
- **数据在初始 HTML 之外（XHR/JS 渲染）**: 先做取数通道判断或接口侦察；这不是"多跳接力"能解决的。
- **纯媒体下载/附件**: 下载文件名要靠 `get_media_requests` 注入 meta，是另一条管道链路，别与本 skill 混为一谈。
- **只为证明一次请求可复现**: 转 `http-request-replication`；本 skill 关注的是跨回调的多跳状态。

### 作者在书中警告的失败模式

- **meta 只保证传播，不保证成功**: 中间跳 404 后若只记日志，Item 永久停在半成品状态，末跳仍会 yield 缺字段的 Item 并入库，形成 Stats 看不见的静默缺口（第6章 PAGE 172；第11章 PAGE 245–246）。
- **errback 只记日志不补救**: 记录 `repr(failure)` 就结束，没有补抓清单或换代理，失败页面永不重试（第6章 PAGE 172–173）。
- **process_spider_output 只 yield item**: 契约要求返回包含 Request 或 Item 的可迭代对象；只回传 Item 会把翻页/详情 Request 吞掉，表现为"只抓了起始页"却没有报错（第7章 PAGE 178 的契约；第11章 PAGE 244 的实现）。
- **把字段清洗塞进 Spider 中间件**: 作者把日期归一化放进 `process_spider_output`，既吞 Request，又让清洗规则与 Item 定义分离，难以复用和测试（第11章 PAGE 244）。
- **媒体文件名拿不到业务字段**: `file_path` 只能拿到 request，业务字段必须在 `get_media_requests` 时注入 `meta['item']`，否则只能按 URL 命名（第5章 PAGE 124–128）。

### 作者的盲点 / 时代局限

- **meta 不能区分"第几次尝试"**: 它随重定向与重试继承，判断重试次数要看 `retry_times` 一类字段，而不是 meta（第6章 PAGE 172）。
- **没有 schema/断言层**: 书中靠人工检查 Item，缺少"入库前必填字段校验"；Stats 的成功率天然掩盖缺字段。
- **Failure 分类绑定异常类型**: 现代重试中间件、异步客户端可能改变抛出的异常类型，`check` 列表需要随依赖版本复核。
- **示例与站点强绑定**: 字段名、徽章页 URL 都是硬编码；站点改版后矩阵与 errback 判据都要重跑。
- **缺少补抓任务化**: 书中只演示 errback 分派，没有把补抓清单做成可重跑的二阶段任务。

### 容易混淆的邻近方法论

- **"meta 传参" vs "全局状态"**: 全局变量会跨请求串数据；meta 是单条记录的单向接力，丢一跳只影响这一条。
- **"errback 分派" vs "宽泛 try/except"**: 后者把不同失败原因压成一个出口，无法给出不同补救。
- **"多跳组装" vs "多请求复现"**: 前者是一条记录的状态链；后者是一次请求的忠实重放。

---

## 相关 skills (阶段 3 填充)

- depends-on: scrapy-crawlspider-rule-division（多页接力建立在规则分工之后）
- contrasts-with: http-request-replication、page-owned-api-recon、scrapy-login-route-choice、scrapy-production-setup（多跳组装 vs 单请求/接口/登录/部署）
- composes-with: （无）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 92.3%（12/13；应调用召回 6/7，诱饵误触发 0/4，边界判对 2/2；详见 test-results.md）
- **蒸馏时间**: 2026-10-31

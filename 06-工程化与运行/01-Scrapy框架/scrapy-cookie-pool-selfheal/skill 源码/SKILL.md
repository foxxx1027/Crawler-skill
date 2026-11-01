---
name: scrapy-cookie-pool-selfheal
description: |
  当登录态会过期、需要多账号轮换，或长跑任务出现"无报错但结果全空、302 跳登录页"时调用：把 Cookie 当可轮换资源，走收集→注入→检测→替换闭环，并让 UA 与 Cookie 来自同一身份包。不适用于单次短期抓取、只需复现一次请求、无授权账号，或需绕过验证码/MFA 的场景。
  Triggers: cookie pool, account rotation, session expired, redirected to login, 302 登录页, Cookie 池, 掉登录, 换号, 登录态失效, UA 与 Cookie 不配对.
source_book: 《Scrapy网络爬虫实战》 东郭大猫
source_chapter: 第11章 PAGE 247–251；第9章 PAGE 208；第7章 PAGE 184
tags: [cookie-pool, session, self-healing, middleware, login]
related_skills: [scrapy-login-route-choice, form-hidden-state-and-readback, http-request-replication, scrapy-middleware-layering]
---

# Cookie 池与登录态自愈

## R — 原文 (Reading)

> SegmentfaultCookiesMiddleware有两个目的：一是每次请求添加cookies，二是在发生重定向到登录页面时，替换原来的cookies，并将原来的cookies 删除。
>
> — 东郭大猫，《Scrapy网络爬虫实战》，第11章，PAGE 248（书页 237）

> 在 Request.meta 中 cookiejar 是没有黏性的。
>
> — 同上，第7章，PAGE 184（书页 173）

---

## I — 方法论骨架 (Interpretation)

这条方法论把登录态从"一份写死的配置"改造成"一个会过期、可轮换、可回收的资源池"。

它先把动作拆开：**收集**（用真实浏览器登录并导出 Cookie）、**存储**（带稳定主键入库）、**注入**（请求发出前选一份塞进去）、**检测**（响应是否把你踢回登录页）、**替换**（删旧取新并重排请求）。五个动作各自独立，哪一环坏了都能单独替换。

关键判据不是"Cookie 有没有值"，而是"这次请求是否被当成已登录"。所以检测要放在响应侧，而不是请求侧。

第二层是身份一致性：UA、Cookie（必要时还有代理）必须来自同一个账号身份包。若各自独立随机，就会发出"桌面 UA + 移动端 Cookie"这类自相矛盾的请求；池化方案最容易漏掉这一环。

第三层是池的维护：删除必须按稳定主键，不能随机删；否则池子越用越少，最后全是死号，而日志没有任何报错。

它和"重新登录一次"的区别在于：自愈要让长任务在无人值守时继续跑，而不是把失败留给第二天的人工重启。

---

## A1 — 书中的应用 (Past Application)

### 案例 1: SegmentFault 多账号 Cookie 池（收集→注入→302 自愈）
- **问题**: 单账号 Cookie 随时过期；关注/粉丝列表会跳登录页；手工复制多条 Cookie 不可维护。
- **方法论的使用**: 在项目同级建 `get_cookies.py`，用 Selenium 按账号列表逐个登录，`driver.get_cookies()` 导出后整理成 name→value 存 MongoDB；下载器中间件 `process_request` 每次随机取一条赋给 `request.cookies`；`process_response` 遇到 301/302 且 Location 指向登录页时，取新 Cookie、删旧记录、改 `request.cookies`，再 `return request` 放回调度器。
- **结论**: 收集、注入、检测、替换是四个独立动作；登录态是可轮换资源，不是一次性配置。
- **结果**: 失效请求无需重启爬虫即可换号重排；但删除逻辑用 `popitem()` 随机取键，存在误删有效账号的风险（第11章 PAGE 249）。

### 案例 2: 豆瓣静态 Cookie 登录——省事但欠下 TTL 债
- **问题**: 不想分析登录 URL 与表单字段，只想复用浏览器里已有的登录态。
- **方法论的使用**: 登录成功后打开任意站内页面，从开发者工具复制请求 Cookie 成字典，在 `start_requests` 里用 `cookies` 参数发送，并带同样的请求头。
- **结论**: Cookie 登录绕过表单细节与加密流程，但有效期一过就必须重新获取；静态 Cookie 不适合长期任务。
- **结果**: 短期请求直接以已登录身份返回目标页；作者同时点明"有效期过后，需要重新获取Cookie的值"（第9章 PAGE 208、PAGE 213）。

### 案例 3: 链家代理池——同一形状的资源池
- **问题**: 代理地址会变，但不希望每次换代理都改爬虫与解析代码。
- **方法论的使用**: 把 `PROXY_LIST` 放进 settings，由 `from_crawler` 注入下载器中间件；`process_request` 里 `random.choice` 后写入 `request.meta['proxy']`，交给 `HttpProxyMiddleware` 消费。
- **结论**: 资源池与选择策略分离，请求阶段统一注入；同一形状可迁移到 UA 池与 Cookie 池。
- **结果**: 每个请求被随机分配一个代理，运行结束用 Stats 验证中间件确实生效（第7章 PAGE 186–188）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. **长跑任务静默跑空**: 半夜 Cookie 过期，日志无 error、items 为 0、Stats 里 302 很多。
2. **多账号轮换**: 需要 3 个以上账号分摊访问，手工复制 Cookie 已不可维护。
3. **登录态反复失效**: 请求被重定向到登录页，但没人盯着重启爬虫。
4. **身份不一致被风控**: 同一请求带 A 账号 Cookie 与 B 浏览器 UA，出现掉登录或验证页。
5. **要评估池化方案**: 已有单份静态 Cookie，不确定该不该升级成池。

### 语言信号 (用户的话里出现这些就应激活)

- "Cookie 过期了怎么办" / "Cookie 池怎么建" / "多账号怎么轮换"
- "掉登录" / "302 跳到登录页" / "半夜任务跑空了" / "没报错但没数据"
- "Cookie 和 UA 对不上" / "身份不一致" / "登录态自愈"
- "cookie pool / account rotation / session expired / redirected to login / 302 login"

### 与相邻 skill 的区分

- 与 `http-request-replication` 的区别: 那条讲"把一次浏览器请求忠实重放"（含 cookie 怎么带）；本 skill 讲"长期运行中登录态如何池化、检测与替换"。
- 与 `form-hidden-state-and-readback` 的区别: 那个处理隐藏字段/一次性 token 的读取、回填与回读断言；本 skill 处理已获得 Cookie 之后的轮换与失效检测，不碰登录表单。
- 与 `page-owned-api-recon` 的区别: 那个找页面自己用的取数接口；本 skill 与取数通道无关，只维护请求身份。
- 与 `scrapy-login-route-choice` 的区别: 那条决定"第一次登录走 FormRequest 还是 Cookie"；本 skill 接手"已经选了 Cookie、且要长期多账号"之后的池化。
- 与 `scrapy-production-setup` 的区别: 那条讲部署形态与 JOBDIR 续跑；本 skill 只讲登录态资源的运行期维护。

---

## E — 可执行步骤 (Execution)

1. **授权与账号盘点**
   - 完成标准: 确认目标属于自有系统、已授权目标或公开测试环境；记录账号数、Cookie 预期 TTL、登录是否需要验证码/MFA/扫码。
   - 判停条件: 无授权，或必须绕过验证码/MFA → 停止，转人工接管或官方 API。

2. **收集并给每条 Cookie 一个稳定主键**
   - 用真实浏览器/Selenium 逐账号登录导出 Cookie；每条记录带主键（账号名或 Cookie 指纹）、获取时间、预期 TTL。
   - 完成标准: 池中任意一条都能唯一定位；重复收集不会产生无法归属的孤儿记录。
   - 判停条件: 只有单账号且任务时长小于 TTL → 直接用静态 Cookie，不必建池（转 `scrapy-login-route-choice`）。

3. **存库与取用前清洗**
   - 存 MongoDB/Redis；取用时剔除 `_id`、统计用 Cookie 等非会话字段，按站点要求刷新时间戳字段。
   - 完成标准: 同一主键连续两次取出的 name→value 一致，且不夹带内部字段。

4. **注入时整包选择身份**
   - 下载器中间件 `process_request` 一次选一个"身份包"（Cookie + UA [+ 代理]），整包写入 `request.cookies` / headers / meta；不要让 UA 与 Cookie 各自独立随机。
   - 完成标准: 任抽一条请求日志，Cookie 所属账号与 UA 属于同一身份包；不出现"桌面 UA + 移动端 Cookie"。

5. **响应侧检测与替换**
   - `process_response` 用多信号判定失效（301/302 + Location 含登录路径 + 目标页关键字段缺失）；命中后按主键删旧、取新、改 `request.cookies`，`return request` 重排。
   - 完成标准: 手工让一份 Cookie 过期，下一次请求被换号重试；池中该主键被替换而非随机删，有效账号数不下降。
   - 判停条件: 站点已改为 200 + 前端跳转 → 先扩判据再上线，不要用单一 302 硬编码。

6. **验收：对照组 + Stats**
   - 人为让一条 Cookie 失效，观察 items 数、302 数、池大小；对比 Stats 与日志。
   - 完成标准: 无人工干预下恢复；items 不归零；池大小稳定；每次替换可追溯到主键。

---

## B — 边界 (Boundary) ★

**合规红线：仅限自有系统、已授权目标或公开测试环境；不提供针对未授权目标的攻击配方。**

### 不要在以下情况使用此 skill

- **单次或短于 TTL 的任务**: 池化、存库、自愈的成本高于重新登录一次。
- **没有账号授权，或需要绕过验证码/MFA/设备校验**: 这已超出"登录态维护"，不属于本 skill。
- **目标根本不需要登录**: 公开页面误上 Cookie 池只会引入身份不一致与额外风险。
- **账号共享/轮换违反站点条款**: 多账号池化可能触犯 ToS 或账号政策，先做合规判断。

### 作者在书中警告的失败模式

- **随机删号**: 失效的是某一条 Cookie，但 `remove_cookies` 用 `i = cookies.popitem()` 随机取键，再按键值删除任意匹配文档，可能删掉仍有效的账号，池子越用越少（第11章 PAGE 249）。
- **UA 与 Cookie 不配对**: UA 中间件与 Cookie 中间件各自独立随机，同一请求可能带 A 账号 Cookie 与 B 浏览器 UA，设备/会话一致性校验会判定异常（第11章 PAGE 248）。
- **只认单一 302 判据**: 自愈只认 301/302 + Location 含 `/user/login`；站点改版后表现为"没报错但全空"，替换永不触发（第11章 PAGE 248）。
- **把 cookiejar 当自动续期**: `meta['cookiejar']` 没有黏性，后续请求不显式写回就会落到默认罐，出现"登录后仍看到未登录页"（第7章 PAGE 184）。

### 作者的盲点 / 时代局限

- **判据绑定状态码与 Location 字符串**: 现代站点常用 200 + JSON code 或前端跳转，必须扩成多信号，否则自愈成摆设。
- **浏览器与库 API 已过时**: 书中 Selenium 用 `find_element_by_name`，现代应改 `By.NAME` 或 Playwright；短信/扫码/MFA 登录完全未覆盖。
- **未处理令牌刷新**: 现代会话常带短时 access token / refresh token / CSRF 轮换，仅换 Cookie 不足以恢复登录。
- **存储 API 过时**: 书中删除用 `collection.remove`（pymongo 已弃用），现代应 `delete_one`/`delete_many`。
- **合规视角缺失**: 多账号、自动化登录涉及账号共享与个人信息，书中未讨论 ToS、PIPL/《网络安全法》等约束。

### 容易混淆的邻近方法论

- **"Cookie 罐" vs "Cookie 池"**: 罐（cookiejar）负责同一次会话的保持；池负责多份登录态的资源管理与轮换。两者不是一层东西。
- **"自愈" vs "掩盖错误"**: 自愈必须留下替换记录与主键；只 return request 而不记录，会把失败藏起来。
- **"池化" vs "反爬"**: 身份一致性只是让请求不自相矛盾，不等于绕过站点风控。

---

## 相关 skills (阶段 3 填充)

- depends-on: scrapy-login-route-choice（先定登录路线，才谈 Cookie 池轮换）
- contrasts-with: form-hidden-state-and-readback、http-request-replication（会话自愈 vs 单次回读/单请求）
- composes-with: scrapy-middleware-layering（Cookie 池以中间件落地）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 100%（13/13；应调用召回 7/7，诱饵误触发 0/4，边界判对 2/2；详见 test-results.md）
- **蒸馏时间**: 2026-10-31

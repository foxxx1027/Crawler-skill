---
name: qr-poll-session
description: |
  当你要设计或排查「出码—等人操作—轮询状态—换令牌—带令牌调用」的异步会话时调用：扫码登录、设备授权、支付或审批回调、长轮询同步。核心是三态显式建模、探活与取数拆成两个请求、凭据固定信封随请求携带并可落盘。不适用于：单次表单隐藏字段（转 form-hidden-state-and-readback）；有文档的一次性接口（转 http-request-replication）；验证码或未授权绕过（转 captcha-cost-routing）。trigger：扫码登录、轮询登录、长轮询、票据、token 失效、QR login polling。
source_book: 《Python项目案例开发从入门到实战：爬虫、游戏和机器学习》 郑秋生、夏敏捷
source_chapter: 第8章 PAGE 170–186（附第7章 PAGE 155）
tags: [polling, qr-login, session, credential-envelope, idempotency]
related_skills: [captcha-cost-routing, crawl-scope-and-halt, form-hidden-state-and-readback, http-request-replication, scrapy-login-route-choice, api-table-replication]
---

# 轮询式会话：三态 / 探活分离 / 票据信封

## R — 原文 (Reading)

> "window.code=xxx;
> xxx：408表示登录超时；201表示扫描成功；200表示确认登录"
>
> — 郑秋生、夏敏捷, 第8章 PAGE 171–173

---

## I — 方法论骨架 (Interpretation)

1. 先按请求角色分三类：出码（只做一次）、轮询状态（多轮）、换票与取数（带凭据）。三类混在一个循环里，就会出现"每轮都申请新码，用户扫的码下一轮失效"。
2. 中间态必须显式建模。`pending`（还没扫）、`scanned`（已扫未确认）、`expired`（过期重取）、`confirmed`（成功换票）各自有独立分支；把 pending 与 expired 合并成一个"失败"分支，会把"用户还没点确认"读成失败。
3. 会话键只取一次、全程复用（`uuid` / `state`），并写进日志，便于证明轮询没有换键。
4. 探活与取数是两个请求：探活只回答"会话是否有效、有没有增量"，取数请求才真正拉数据。混成一个请求，就无法区分"没新消息"与"会话已死"。
5. 退出用状态码而不是异常或超时：例如 `retcode` 0 正常、1100/1101/1102 分别对应退出、他处登录、手机退出，一律 break。异常只留给网络故障。
6. 凭据要变成固定信封：登录换来的票据（`skey/sid/uin/pass_ticket` 一类）加上首次生成后固定的 `DeviceID`，组装成一个结构，后续每个请求原样携带；字段每次重新生成就会出现"登录成功但下一个接口 401"。
7. 凭据可落盘并预留失效分支：能存文件就存（如 `auto_login(True)`），调试不必每次扫码；同时写清"token 过期 → 重走扫码"的唯一入口，而不是每轮都扫。
8. 写接口要幂等键：`ClientMsgId` 用时间戳 + 随机数；单条最多重发一次，不整队重试、不做无上限退避。
9. 验收放在流程末尾：confirmed 后立刻发一次带 token 的探针请求，否则 200 与 401 只会体现在下一步，排查时已隔了一层。
10. 空转要节流：无增量就 sleep 一个短周期再轮询，避免打满 CPU 与对方配额。

---

## A1 — 书中的应用 (Past Application)

### 案例 1: 微信扫码登录的三态轮询
- **问题**: 用户扫码有先后，出码、被扫、确认三件事在时间上分离，脚本必须知道"现在到哪一步了"才能换票。
- **方法论的使用**: 先 `jslogin` 拿 `uuid`，用 `uuid` 出二维码；再轮询 `login` 接口，按 `window.code` 分支：408 继续等、201 提示已扫描、200 才成功；200 后从 `redirect_uri` 抠 `ticket` 保存，再换 `skey/sid/uin/pass_ticket`，连同 `DeviceID` 组成 `BaseRequest`（PAGE 170–173、PAGE 175）。
- **结论**: "已扫描"不是"已完成"；只有 200 才能进入换票，且票据必须落地、后续每个请求都带。
- **结果**: 得到完整会话票据；初始化、同步、发消息全部复用同一个 `BaseRequest`（第8章 PAGE 170–173、PAGE 175）。

### 案例 2: 消息同步的探活 / 取数分离
- **问题**: 常驻机器人要判断"有没有新消息"和"账号是否还活着"，但这两件事不能靠同一个请求的同一个字段回答。
- **方法论的使用**: 先 `synccheck` 探活——原文标注"retcode：0为正常；1100表示失败/退出微信；1101表示在其他地方登录Web版微信;"（PAGE 175）；`retcode` 为 0 时再看 `selector`：0 就 `sleep` 后下一轮，非 0 才调 `webwxsync` 拉增量；1100/1101/1102 一律 break（PAGE 182）。
- **结论**: 探活与取数分开，退出条件是状态码而不是异常，进程才能长期驻留。
- **结果**: 空转被 sleep 压住；作者的主循环用 `while True` 常驻，退出由 retcode 触发而非抛错（PAGE 182）。

### 案例 3: 发消息的幂等键与有限重发
- **问题**: 发送失败后重试，如何避免同一条消息被服务端当成两条；连续失败时该重发几次。
- **方法论的使用**: 请求里带 `ClientMsgId`（时间戳 + 随机数）作为幂等键；封装成 `while flag< 2：#出错会进行一次重发`（PAGE 185）的有限重试，异常时 `flag+1` 只再试一次，第二次仍失败就放弃；不重试整个队列，也不做退避。
- **结论**: 幂等键解决"重复"，有限次数解决"雪崩"；重试粒度落在单条消息而不是整批。
- **结果**: 单条消息最多请求两次；登录态另用 `auto_login(True)` 落盘，程序重启短期免扫码（第7章 PAGE 155、第8章 PAGE 185）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. 要写扫码登录脚本，或正在调"点登录 → 手机确认 → 前端轮询状态"的接口，发现脚本把"还没确认"当成了失败。
2. 要做一个常驻监听程序（消息、订单、审批、支付回调），需要判断"有增量"和"会话失效"两件事。
3. 登录能成功，但下一个接口稳定 401/403，怀疑是凭据没带全或每次都被重新生成。
4. 写操作偶发重复（重复发消息、重复提交订单），需要幂等键与有限重试策略。
5. 调试一次就要重新扫码/重新授权，想确认登录态能不能落盘、失效时怎么重登。

### 语言信号 (用户的话里出现这些就应激活)

- "扫码之后脚本一直报登录失败，其实我还没点确认"
- "轮询到什么时候才算登录成功"
- "登录成功了，但后面的接口 401"
- "这个 token 要不要存起来 / 过期了怎么办"
- "重发会不会重复发两条消息"
- "QR login keeps returning pending — is my state expiring?"
- "polling status endpoint, scanned vs confirmed"
- "session token expires after 2 hours, how to refresh"
- "idempotency key for sending messages"
- "long-poll sync loop, how to exit on invalid session"

### 与相邻 skill 的区分

- 与 `form-hidden-state-and-readback` 的区别: 后者处理单次 GET 产出的隐藏 token/CSRF 与 cookie jar，写后回读一次即可；本 skill 处理异步多轮、有人或手机在环的流程，核心是中间态分支、探活/取数分离与凭据信封。
- 与 `http-request-replication` 的区别: 后者是"把浏览器里的一条请求原样重放"；本 skill 管的是多步时序里"哪一步产生凭据、哪一步带凭据、何时换票"。
- 与 `scrapy-login-route-choice` 的区别: 后者决定"登录走表单/扫码/Cookie 导入哪条路线"；本 skill 是在路线已定（扫码或轮询授权）之后，把状态机、探活与票据纪律落地。
- 与 `captcha-cost-routing` 的区别: 后者处理出现验证码时"自动过/人工过/降频/换端"的成本选择；本 skill 不处理人机验证本身，也不提供绕过配方。
- 与 `crawl-scope-and-halt` 的区别: 后者管遍历范围、外链与停机上限；本 skill 管会话生命周期，不管抓多少页。

---

## E — 可执行步骤 (Execution)

当 skill 被激活后, agent 应按以下步骤执行:

1. **画状态表：把服务端可能返回的状态与终态列出来**
   - 完成标准: 得到一张表，pending / scanned / expired / confirmed（或等价状态）各自写明"下一步做什么、是否终态"。
   - 判停条件: 若状态语义无法从文档或现有抓包确认，先抓一次完整流程记录全部状态码，再写代码；不要猜。

2. **出码只做一次，会话键固定**
   - 完成标准: `uuid` / `state` 只申请一次并贯穿整个轮询；日志里能看到同一个键被复用于每一轮。
   - 判停条件: 若站点要求每轮刷新 state（例如服务端强制），先确认是否真的如此，否则按"键固定"实现。

3. **实现中间态分支**
   - 完成标准: pending/scanned 继续轮询（可 sleep 节流），expired 才 break 并重新取码，confirmed 才进入换票；代码中不存在"pending 与 expired 合并"的分支。
   - 判停条件: 若流程需要用户重新扫码（expired），要显式回到步骤 2，而不是在循环里静默继续。

4. **拆开探活与取数，退出用状态码**
   - 完成标准: 探活请求与取数请求是独立函数；退出条件可枚举（如 retcode 0 / 1100 / 1101 / 1102），异常只用于网络故障。
   - 判停条件: 若站点是纯 WebSocket 推送、没有轮询端点，改用推送模型，不套本骨架。

5. **建立凭据信封：落地、复用、失效分支**
   - 完成标准: 票据与首次生成的 `DeviceID` 组成固定结构，每个请求原样携带；凭据可落盘；重启后能证明免扫码；401/过期只有一条重登入口。
   - 判停条件: 若凭据无法落盘（服务端只发内存态 token），把"有效期 + 重登"写进流程，不让它在第 N 步静默爆炸。

6. **写接口幂等 + 流程末尾探针验收**
   - 完成标准: 写请求带幂等键（时间戳 + 随机数），单条最多重发一次；confirmed 后立刻发一次带 token 的探针请求并记录结果（200/401）。
   - 判停条件: 探针若返回 401，回到步骤 5 检查信封，而不是继续调用业务接口。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- 有官方文档、一次请求就能完成的接口调用：直接按文档拼参数，轮询骨架是多余复杂度（转 `http-request-replication`）。
- 单次表单提交里的隐藏字段 / CSRF / cookie jar：那是同步的一次性事务，转 `form-hidden-state-and-readback`。
- 目标站已有验证码、滑块或设备指纹风控，且未获授权：本 skill 不提供绕过配方（转 `captcha-cost-routing`、`anti-bot-triage-and-human-parity`）。
- 只是想限制抓取范围、外链与停机：转 `crawl-scope-and-halt`。
- 依赖单一、已关闭的平台入口：书中微信网页版对多数账号已不可用（PAGE 152–190），不要承诺任何具体平台可复现。

### 作者在书中警告的失败模式

- **整章建立在单一入口 `wx.qq.com` 上且无失效预案**（第8章 PAGE 169，ce06-a）：登录、同步、发消息全指向同一域名，入口关闭即整章不可运行；本 skill 只取骨架，必须自带降级路径。
- **把"10 个好友、12 小时没被限"当成安全边界**（第8章 PAGE 186，ce07-a）：轮询与发送的节奏结论只能证明"这个组合下没炸"，不能推广成安全阈值。
- **`except: continue` 把失败吞掉**（第5章 PAGE 122，ce04-a）：探活/取数若沿用这种写法，会丢掉"会话已失效"与"网络抖动"的区别；退出必须用状态码，异常必须记录。

### 作者的盲点 / 时代局限

- 这是项目制入门教材，每章只写到"能演示"：无并发、无限速、无重试框架、无日志与告警（PAGE 120–123、150、182）。
- 成书环境为 Python 3.5（PAGE 4），依赖口径自相矛盾（如 `zbarlight` 仅支持 2.7 以下，PAGE 198；`sklearn.cross_validation` 在 0.20 后移除，PAGE 376），2021 年后的主流环境照抄大概率跑不通。
- 微信网页版入口在成书时已对多数账号关闭，`itchat` 亦停维护（PAGE 152–190）；书中仍把"扫码即登录"当稳定前提。
- 书中的"随机 1–4 秒"是规避风控的经验值（PAGE 186），不是速率预算；本 skill 不继承这种"以规避为目的"的节奏观。

### 容易混淆的邻近方法论

- **长轮询 vs WebSocket**：书中 `synccheck` 是客户端反复问，不是服务端推送；把推送模型套上"轮询三态"会多出无意义的状态。
- **会话票据 vs 请求签名**：票据解决"你是谁"，签名解决"参数没被改"；401 与签名错误是两类问题，不要用本 skill 修签名（见 `dynamic-page-and-min-params` 的参数排查）。
- **轮询登录 vs 表单登录**：表单登录的中间态是"隐藏字段何时取"，属于 `form-hidden-state-and-readback`；本 skill 的中间态是"人何时确认"。

### 合规红线

仅限自有系统、已授权目标或公开测试环境；不提供针对未授权目标的攻击配方，也不提供绕过访问控制、验证码或平台限制的手段。

---

## 相关 skills (阶段 3 填充)

- depends-on: （无）
- contrasts-with: captcha-cost-routing、crawl-scope-and-halt、form-hidden-state-and-readback（异步多轮 vs 单次提交）、http-request-replication、scrapy-login-route-choice
- composes-with: api-table-replication（轮询拿到的令牌要接进接口表）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 100%（13/13：应调用召回 6/6，诱饵误触发 0%，边界 2/2；详见 test-prompts.json / test-results.md）
- **蒸馏时间**: 2026-10-31

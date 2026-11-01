---
name: scrapy-login-route-choice
description: |
  当要模拟登录抓数据，在 FormRequest 与 Cookie 两条路线之间拿不准，或登录提交成功却仍显示未登录时调用：先做"真实接口、真实字段名、成功判据"三步定位，再按"复现加密成本 × 账号数"选路。不适用于需绕过验证码/MFA、未授权目标，或已有官方 API 的场景。
  Triggers: 模拟登录, 登录接口, FormRequest, from_response, dont_click, Cookie 登录, 表单提交, login route, form login, cookie login, hidden fields.
source_book: 《Scrapy网络爬虫实战》 东郭大猫
source_chapter: 第9章 PAGE 200–215；第11章 PAGE 233–250
tags: [login, formrequest, cookie, session, scrapy]
related_skills: [form-hidden-state-and-readback, http-request-replication, qr-poll-session, scrapy-multipage-assembly, scrapy-new-site-onboarding]
---

# 登录路线选择：FormRequest 还是 Cookie

## R — 原文 (Reading)

> 在 Scrapy 中，模拟提交表单需要用到 Request 的 FormRequest 子类，与 Request 相比, FormRequest多了一个formdata 参数
>
> — 东郭大猫，《Scrapy网络爬虫实战》，第9章，PAGE 205（书页 194）

> 不足之处是Cookie有有效期限制，有效期过后，需要重新获取Cookie的值。
>
> — 同上，第9章，PAGE 208（书页 197）

---

## I — 方法论骨架 (Interpretation)

登录页面前先别写代码：在 Network 面板里把三件事定下来——**提交到哪个接口**（URL 与 method）、**带哪些字段**（含隐藏字段与加密后的参数名）、**怎么算成功**（响应标记、跳转目标或目标页字段）。

三步没有完成之前，选路线没有意义。

路线只有两条：

- **FormRequest**：适合单账号、密码无重加密、需要过程可维护的场景。`from_response` 能自动合并隐藏字段，但默认会模拟点击第一个可提交元素；表单由 JS 接管时必须 `dont_click=True`，否则请求缺少 JS 计算出的字段，表面看像"账号密码错误"。
- **Cookie**：适合多账号、JS 加密重、长期运行。把浏览器/ Selenium 已登录的 Cookie 直接带上，省去接口、字段与加密流程。

选路判据不是"要不要过程"，而是两项成本对比：**复现加密的成本 × 账号数**，对 **一次性收集 Cookie 的成本 + TTL 维护成本**。账号越多、加密越重，越该走 Cookie。

Cookie 路线自带 TTL 债：有效期一过，请求集体被重定向到登录页，而爬虫本身不报错。所以选 Cookie 就等于同时承诺"要有失效检测与重新获取路径"；多账号还要接 Cookie 池。

两条路线都要用响应内容验证成功，不能以"请求发出去了"作为登录成功。

---

## A1 — 书中的应用 (Past Application)

### 案例 1: 豆瓣 FormRequest——先锁 basic 接口，再写表单
- **问题**: 不知道登录表单该提交到哪个 URL、用 GET 还是 POST、需要哪些字段与请求头。
- **方法论的使用**: 在登录页打开 Network 面板，筛选 XHR 并勾选持续日志，输入账号后观察请求记录，锁定 `basic` 对应的登录接口；再看消息头里的请求头/响应头，切到参数页读取 `name`、`password`、`remember` 等字段名；据此写 `FormRequest` 并补齐 User-Agent、Content-Type、X-Requested-With。
- **结论**: 登录的"真实接口 + 真实字段名"必须从一次成功登录的请求快照里取，不能照着页面表单猜。
- **结果**: FormRequest 携带 formdata 与浏览器头提交后，响应体含 `success` 即判定成功，再回到 `start_urls` 抓首页并提取用户名（第9章 PAGE 210–212）。

### 案例 2: 豆瓣 Cookie 登录——跳过流程，接受 TTL
- **问题**: 不想分析登录 URL、隐藏字段与提交流程，只想复用浏览器里已有的登录态。
- **方法论的使用**: 登录成功后随便打开一个站内页面（如豆瓣读书），在开发者工具里查看请求 Cookie；把 Cookie 存成字典，在 `start_requests` 里用 `cookies` 参数发送，而不是用 `formdata`，并带上同样的请求头。
- **结论**: Cookie 登录的优点是不知道登录 URL 和表单字段也能抓登录后页面；缺点是有效期过后必须重新获取。
- **结果**: 请求直接以已登录身份返回目标页面，跳过登录流程；作者同节点明这份 Cookie 不能一劳永逸（第9章 PAGE 213–215、PAGE 208）。

### 案例 3: SegmentFault 多账号——FormRequest 成本失控后转向 Cookie 池
- **问题**: 项目需要多个账号轮换，且每个账号都走一遍真实登录；继续用 FormRequest 意味着要为每个账号重复处理字段与流程。
- **方法论的使用**: 放弃逐账号提交表单，改用 Selenium 逐个账号登录并导出 Cookie，存 MongoDB；再由下载器中间件随机注入、在 301/302 跳登录页时换号重排。
- **结论**: 选路取决于账号数量与是否要复现加密；多账号场景下 Cookie 的一次性收集成本更低。
- **结果**: 形成 Cookie 池 + 自愈闭环，登录态可轮换、可替换（第11章 PAGE 233、PAGE 247–250）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. **要登录后才能抓**: 目标页只有登录可见，需要决定用表单提交还是带 Cookie。
2. **表单提交了但没登录**: 请求返回 200，后续页面仍是未登录状态。
3. **找不到真实接口**: 页面上有登录框，但不知道实际提交到哪个 URL、带哪些字段。
4. **多账号或加密重**: 密码由 JS 加密，或需要 3 个以上账号轮换，不确定 FormRequest 还值不值得做。
5. **Cookie 方案评估**: 已有浏览器 Cookie，想知道能不能直接用于长期任务。

### 语言信号 (用户的话里出现这些就应激活)

- "模拟登录怎么做" / "FormRequest 还是 Cookie" / "登录接口是哪个"
- "表单提交了还是未登录" / "隐藏字段要不要带" / "dont_click 是什么"
- "密码是 JS 加密的" / "多账号登录" / "Cookie 能直接用吗"
- "login route / form login / cookie login / from_response / hidden fields / session login"

### 与相邻 skill 的区分

- 与 `form-hidden-state-and-readback` 的区别: 那个专攻隐藏字段/一次性 token 的提取、回填与写后回读；本 skill 先决定走哪条路线，只把隐藏字段当作 FormRequest 的自动能力。
- 与 `http-request-replication` 的区别: 那条是把一次请求原样重放并处理会话/编码；本 skill 是 Scrapy 场景下的路线选择与三步定位。
- 与 `scrapy-cookie-pool-selfheal` 的区别: 本 skill 做"第一次登录怎么选"；那条接手"已选 Cookie 且要长期多账号"之后的池化与自愈。
- 与 `page-owned-api-recon` 的区别: 那个找页面自己用的数据接口；本 skill 找的是登录接口，并决定提交方式。
- 与 `scrapy-new-site-onboarding` 的区别: 那条管新站从通道判断到项目骨架的全流程；本 skill 只解决登录这一段。

---

## E — 可执行步骤 (Execution)

1. **授权与可行性预检**
   - 完成标准: 确认目标属于自有系统、已授权目标或公开测试环境；记录登录是否含验证码、MFA、扫码或设备校验。
   - 判停条件: 含验证码/MFA 且无合法人工通道，或无授权 → 停止自动化，转人工接管或官方 API。

2. **三步定位（全部在 Network 里做完再写码）**
   - 真实接口（提交 URL + method）、真实字段名（含隐藏字段与加密后的参数名）、成功判据（响应标记/跳转目标/仅登录可见页字段）。
   - 完成标准: 手上有一次浏览器成功登录的完整请求快照；字段名与浏览器逐字一致；成功与失败样本各一份。
   - 判停条件: 若接口参数由 JS 动态计算且无法低成本复现 → 直接转 Cookie 路线（步骤 4）。

3. **按成本选路**
   - 单账号、密码无重加密、需要过程可维护 → FormRequest；多账号、加密重、要结果 → Cookie。
   - 完成标准: 写下一句判据："复现加密成本 × 账号数"对比"一次性收集成本 + TTL 维护成本"，并注明账号数与 TTL。
   - 判停条件: 账号数 ≥3 且每个都需复现加密 → 直接走 Cookie 池（转 `scrapy-cookie-pool-selfheal`）。

4. **最小实现**
   - FormRequest: 先用 `from_response` 只填账号密码，隐藏字段由当次 response 补齐；JS 表单加 `dont_click=True`，必要时用 `clickdata`。
   - Cookie: `start_requests` 带 `cookies` 与必要请求头，跳过登录流程。
   - 完成标准: 登录后访问一个"仅登录可见"的页面能返回正确内容；换无效密码/过期 Cookie 则返回失败标记或登录页（对照组成立）。

5. **失败路径与长期性**
   - 记录失败判据；Cookie 路线记录获取时间与 TTL；长期任务接失效检测。
   - 完成标准: 手工使登录态失效，程序能识别并走替换/重登，而不是静默产出 0 条。
   - 判停条件: 失效表现为 200 + 前端跳转 → 先扩判据，或改用真实浏览器会话方案。

---

## B — 边界 (Boundary) ★

**合规红线：仅限自有系统、已授权目标或公开测试环境；不提供针对未授权目标的攻击配方。**

### 不要在以下情况使用此 skill

- **登录需要验证码/MFA/扫码**: 自动化会退化为破解人机验证；应人工接管、用官方 API 或申请授权。
- **没有账号授权或目标是他人账号**: 技术可行不等于可做；直接拒绝并转合规判断。
- **已有官方 API 或数据导出**: 优先走官方通道，不要逆向内部登录。
- **批量注册/刷单/发垃圾内容**: 这不是登录路线问题，是滥用。

### 作者在书中警告的失败模式

- **from_response 默认模拟点击**: 表单由 JavaScript 交互操作时，默认提交操作不合适；请求会缺少 JS 计算出的字段，服务端返回登录失败，表面看像账号密码错误，实际是提交路径不对（第9章 PAGE 207）。
- **静态 Cookie 跑长期任务**: Cookie 有有效期，过期后所有请求被重定向到登录页，抓取结果为空但爬虫不报错（第9章 PAGE 208）。
- **隐藏字段硬编码**: 隐藏字段每次会话不同，必须取自当次 response；写死会在下一次会话直接失败（第9章 PAGE 200–207）。
- **多账号仍逐账号 FormRequest**: 账号越多、加密越重，FormRequest 的复现成本按账号数放大；书中项目最终转向 Cookie 池（第11章 PAGE 233–250）。

### 作者的盲点 / 时代局限

- **只覆盖静态 HTML 表单**: `dont_click` 解决的是"点击语义"，救不了密码的 JS 加密/RSA/签名；这类场景书中没有低成本方案。
- **示例接口会过时**: 豆瓣的 mobile basic 登录接口是 2019 年的形态，现代站点普遍改版并叠加风控；照抄 URL 与字段名大概率失败。
- **浏览器 API 过时**: 书中 Selenium 使用 `find_element_by_*`，现代已废弃；短信/扫码/MFA 完全未讨论。
- **合规与账号来源缺失**: 未讨论账号共享、ToS、个人信息保护；涉及登录态与个人信息时应先做合规判断。
- **成功判据过于单一**: 书中以响应体含 `success` 为准；现代接口常用 JSON code + 后续接口鉴权，需多信号验证。

### 容易混淆的邻近方法论

- **"登录" vs "会话保持"**: 登录是换取凭证的那一次动作；会话保持是后续每个请求都带凭证。本 skill 只管前者。
- **"FormRequest" vs "from_response"**: FormRequest 是请求类型；from_response 是"从页面自动填表单"的构造方式，可选也可不用。
- **"Cookie 登录" vs "Cookie 池"**: 前者是一份凭证的一次性使用；后者是多份凭证的运行期轮换。

---

## 相关 skills (阶段 3)

- depends-on: （无）
- contrasts-with: form-hidden-state-and-readback、http-request-replication、qr-poll-session、scrapy-multipage-assembly（登录路线选择 vs 单次表单回读/单请求复刻/异步会话/多页组装）
- composes-with: scrapy-new-site-onboarding（登录是接站后的第一批决策，常连用）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 100%（13/13；应调用召回 7/7，诱饵误触发 0/4，边界判对 2/2；详见 test-results.md）
- **蒸馏时间**: 2026-10-31

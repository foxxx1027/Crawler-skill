---
name: form-hidden-state-and-readback
description: |
  登录或提交表单后"没报错但页面没变"、隐藏字段每次不同、或要确认写操作真的写入时调用：把一次性隐藏 token 与会话 cookie 当成同一次 GET 的产物，字段靠遍历读取而非猜，写后必须回读断言。不适用于：无状态只读抓取、纯接口逆向或渲染选路（转 data-path-cost-ladder）、只讨论速率（转 crawl-pacing-and-concurrency）。Trigger：登录失败 / 200 却回登录页 / _formkey / CSRF / cookie jar / 回读 / readback / get_attribute / assert。
source_book: 《用 Python 写网络爬虫（第2版）》 Katharine Jarmul / Richard Lawson
source_chapter: 第6章 6.1–6.3（PAGE 137–150）
tags: [form, session, hidden-state, readback]
related_skills: [http-request-replication, cache-as-cost-tradeoff]
---

# 表单的双层隐藏状态与写后回读

## R — 原文 (Reading)

> 这是因为我们缺失了另一个必要的组成部分——浏览器cookie。当普通用户加载登录表单时，_formkey 的值将会保存在cookie 中，然后该值会与提交的登录表单数据中的_formkey 值进行对比。
>
> — Katharine Jarmul / Richard Lawson, 第6章 6.1 登录表单（PAGE 139）

> 我们还使用了元素的get_attribute 方法，从页面的HTML 元素中获得指定的属性。因为我们正在处理的是HTML 的input 元素，因此我们需要得到value 属性，而不是检查text 属性。
>
> — 同上, 第6章 6.3 使用Selenium 实现自动化表单处理（PAGE 150）

---

## I — 方法论骨架 (Interpretation)

表单自动化的难点不在可见字段，而在**你看不见的那两层状态**。

- 第一层是一次性隐藏 token（`_formkey` / CSRF token）：每次加载页面都换一个新值，服务端用它判断"这张表是否已被提交过"。所以不能把它写死，也不能用上一次的值。
- 第二层是会话 cookie：token 的期待值同时被写进 cookie，提交时必须带上**同一次 GET** 产生的 cookie jar，服务端拿两者比对。
- 因此正确顺序是：先 GET 原表单页 → 用 `parse_form()` 遍历所有 `input` 的 `name/value`（读字段，不背字段）→ 把字段与这次的 cookie 一起 POST。
- 失败的表现是 **200 + 跳回登录页**，不是 4xx。这最容易被误判成"网络问题"或"选择器写错"，实际是状态缺失。诊断顺序应当是：先查可见字段 → 再查隐藏域 → 最后查 cookie。
- 成功判定也不能靠"没报错"：要么用页面特征（如导航栏第一个链接文本是 `Login` 还是 `Welcome ...`），要么用**写后回读**——重新读取刚写入的值并断言等于期望值。读 `input` 必须用属性 `value`，用 `text` 永远拿不到。
- 当会话寿命短于任务时长时，登录不是"前置步骤"，而是流水线里一个**可重入环节**：检测到登录页出现 → 重新登录 → 从保存的游标继续。

---

## A1 — 书中的应用 (Past Application)

### 案例 1: 三次失败，才凑齐"隐藏域 + cookie"两件套

- **问题**: 目标站的登录表单，脚本提交后 `response.url` 一直是登录页，但 HTTP 状态是 200，没有任何报错。
- **方法论的使用**:
  1. 第一版只 POST `{'email','password'}` → 返回登录页 URL，失败。
  2. 用 lxml 遍历 `form input`，写出 `parse_form()`，发现还缺 `_formkey` / `_formname` / `_next` / `remember_me` 四个域（被设为 hidden，浏览器里看不见），补齐后**仍然失败**。
  3. 回头检查 `response.cookies`，发现 `_formkey` 的值同时存在于 cookie 里；把**发起 GET 时**得到的 cookie jar 一并传给 POST。
- **结论**: token 与会话 cookie 必须来自同一次 GET 且互相匹配，只补其中一半必然失败。
- **结果**: `second_response.url` 变成主页，登录成功（PAGE 137–140）。

### 案例 2: 用页面特征判登录态，而不是靠跳转

- **问题**: 复用浏览器已登录的 cookie 后，请求不再发生登录跳转，"跳转即成功"这个判据失效了。
- **方法论的使用**: 抓取返回的 HTML，用 `tree.cssselect('ul#navbar li a')[0].text_content()` 读导航栏第一个链接文本。
- **结论**: 文本是 `Login` 说明会话没加载成功；是 `Welcome Test account` 说明已登录。
- **结果**: 作者据此把"页面特征"确立为登录态的判据，并在代码里写成可失败的断言（PAGE 143）。

### 案例 3: 写操作后回读，用断言代替"看起来成功了"

- **问题**: 用 Selenium 把某国人口数 +1 后，页面没有明显报错，但无法确认是否真的写入。
- **方法论的使用**: 先 `population.get_attribute('value')` 读当前值（不是 `text`）→ `clear()` → `send_keys(new)` → 等 `#places_population__row` 出现 → 读回该行文本、去掉千分位逗号 → `assert test_population == new_population`。
- **结论**: 只有回读值等于期望值才算成功；`assert` 通过就是"我们知道更新成功了"。
- **结果**: 断言通过，页面上人口数确实变成 62,348,449（PAGE 149–150）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. 登录脚本返回 200，但落到的还是登录页，日志里没有任何异常。
2. 表单里的隐藏字段名或值每次刷新都变（`_formkey`、CSRF token、`_next`），写死的字段一提交就失效。
3. 已经带上账号密码却仍然失败，用户开始怀疑"是不是要模拟浏览器"。
4. 有一个写操作（改资料、提交评论、下订单到测试环境），需要确认它真的写进去了，而不是"页面刷新了"。
5. 任务要跑几小时，而登录态十几分钟就过期，中途开始大面积失败。

### 语言信号 (用户的话里出现这些就应激活)

- "登录没成功但也没报错 / 200 却还是登录页"
- "_formkey / CSRF token / hidden input 怎么取"
- "cookie 要不要带 / cookie jar / 会话复用 / 保持登录"
- "表单提交了但数据没变 / 怎么确认写进去了"
- "回读 / readback / 断言 / assert 通过了吗"
- "Selenium 读输入框的值读不到 / text 是空的"
- "sessionstore.js / 从浏览器导 cookie / storage_state"

### 与相邻 skill 的区分

- 与 `data-path-cost-ladder` 的区别：后者解决"数据在哪、走哪条路取"（含要不要上浏览器渲染）；本 skill 解决"要提交带状态的写操作时，状态怎么凑齐、结果怎么验"。表单若依赖 JS 生成字段，才回退到渲染那条路。
- 与 `cache-as-cost-tradeoff` 的区别：本 skill 产出的 cookie jar 必须可序列化，否则断点续跑会丢登录态；但内容缓存本身归后者。
- 与 `crawl-pacing-and-concurrency` 的区别：后者关心"发多快"；本 skill 只提一句"填写与点击速度也是检测信号"，具体记账不在这里展开。
- 与 `scrapy-production-setup` 的区别：JOBDIR 不保存 cookie/会话，所以"带登录的长任务"即使有 JOBDIR 也会在会话过期后失败——这是两者的交界。

---

## E — 可执行步骤 (Execution)

当 skill 被激活后，agent 应按以下步骤执行：

1. **抓原始表单页，并留住这次会话**
   - 先 GET 表单页，保留响应 HTML 与 `response.cookies`（或 `requests.Session()`）。
   - 完成标准: 手里同时有 HTML 和 cookie jar，且两者来自**同一次请求**。

2. **遍历读取全部 input，而不是猜字段**
   - 用 `cssselect('form input')` 遍历，按 `name` 收集 `value`；没有 `name` 的跳过。
   - 完成标准: 字段数 ≥ 页面上可见字段数，且至少包含一个 `hidden` 类型的域；把结果打印出来人工核对一次。

3. **用同一次的 cookie + 全部字段提交**
   - `session.post(url, data)` 或 `requests.post(url, data, cookies=该次 GET 的 cookies)`。
   - 完成标准: 请求成功发出，且能说清"这次提交用的 cookie 是哪一次 GET 拿到的"。
   - **判停条件**: 若仍失败，按"可见字段 → 隐藏域 → cookie → 是否还有 JS 生成字段"的顺序逐层排查；四层都排除后再考虑渲染兜底。

4. **用可失败的判据确认结果**
   - 优先页面特征（导航栏文本、目标元素出现）；其次 URL 变化；不要只看状态码。
   - 完成标准: 写出一个**可能失败**的断言（如 `assert 'login' not in response.url` 或断言目标元素文本），并解释它在失败时会怎么表现。

5. **写操作后回读并断言**
   - 重新请求/重新渲染目标页，读取刚写入的字段；`input` 用 `get_attribute('value')`，文本节点才用 `text`；数值先去掉千分位等格式符再比较。
   - 完成标准: 回读值 == 期望值，且断言是实际执行过的（不是注释掉的）；失败时能区分"没写入"与"读错了元素"。

6. **判断会话是否覆盖任务时长**
   - 若会话寿命 < 任务预计时长，把登录抽成可重入函数：检测到登录页/401 → 重新登录 → 从游标继续；cookie jar 落盘以便断点续跑。
   - 完成标准: 人为让一次会话失效（清 cookie 或等过期），流程能自行恢复一次并继续，而不是整批失败。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- 无状态只读抓取：没有隐藏 token、不需要登录，引入本流程只是增加复杂度。
- 数据其实来自 XHR/JSON 接口：先按 `data-path-cost-ladder` 还原接口，比对着表单逐个字段模拟要稳得多。
- 只想解决"请求太频繁被封"：那是速率问题，不属于表单状态。

### 作者在书中警告的失败模式

- **只补隐藏域不补 cookie**：书中三次失败链的第三段明确证明，`_formkey` 同时在页面和 cookie 里，缺任一半都会静默失败（PAGE 139）。
- **把 200 当成功**：失败表现是"返回登录页 URL"而不是错误码，因此必须以页面特征或回读断言为判据（PAGE 138、PAGE 143）。
- **读 input 用 text**：书中专门提醒 "我们需要得到value 属性，而不是检查text 属性"（PAGE 150）。
- **固定 sleep 等页面**：等待应针对"目标元素出现"而非固定时长，否则网络一慢就抽到空值。

### 作者的盲点 / 时代局限

- `sessionstore.js` 已被 Firefox 的 `recovery.jsonlz4`（mozlz4 压缩）取代 → 改用 Playwright 的 `storage_state` 或浏览器扩展导出 cookie JSON。
- Selenium 3 的 `find_element_by_id` 在 Selenium 4 已移除 → `find_element(By.ID, ...)`；隐式等待语义也变了；书中 PhantomJS 驱动已不可用。
- 书中示例站的 `_formkey` 是 Werkzeug 表单机制；现代站点多用 CSRF 中间件，token 常放在 `meta` 标签或请求头而非 `input`。
- 书中把"登录一次"当作前置步骤，没有把"会话短于任务时长"当成结构性约束（这一步是外推补上的）。
- 适用范围：仅对自有账号、自有系统或已获授权的测试环境做自动化；本 skill 不提供绕过访问控制、绕过人机验证或伪造身份的手段。

### 容易混淆的邻近方法论

- 会话复用（省一次登录）vs 会话保活（让长任务不中断）：后者需要把登录写成可重入函数。
- 登录成功判据（页面特征）vs 写入成功判据（回读断言）：两个断言的对象不同，不能互相替代。

---

## 相关 skills (阶段 3 填充)

- depends-on: —
- contrasts-with: `data-path-cost-ladder`（取数路径 vs 有状态写操作）
- composes-with: `cache-as-cost-tradeoff`（cookie jar 序列化）、`crawl-pacing-and-concurrency`（交互节奏）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 待测
- **蒸馏时间**: 2026-10-30

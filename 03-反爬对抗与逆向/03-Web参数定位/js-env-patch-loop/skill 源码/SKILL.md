---
name: js-env-patch-loop
description: |
  用户把原站 JS 搬到 Node 跑，出现 window/document/navigator 未定义，或值算出来却被识别时调用：报错驱动逐个补、用 toStringTag 伪装类型、手补不动就升级 JSDOM/真浏览器。核心是"补了不等于像"，判据是产物与服务端一致而非报错消失。不适用于：还没找到生成代码（先定位）；也不适用于算法或字段集合本身不对（转验收）。trigger：补环境 / patch the JS environment / window is not defined / navigator.webdriver / toStringTag / JSDOM 被检测。
source_book: 《爬虫逆向进阶实战》 李玺
source_chapter: 第3章 3.7（PAGE 86–92）、第6章 6.3（PAGE 245）、第9章 9.5.4（PAGE 314–315）
tags: [environment-emulation, javascript, nodejs, detection]
related_skills: [js-param-locate-ladder, native-hook-or-unidbg, sign-reproduce-acceptance]
---

# 补环境的报错闭环与检测点自查

## R — 原文 (Reading)

> 一般在手动补充时，根据报错信息缺什么补什么。比如window is not defined，就补上window=global；或者window={}；当然也有通过Proxy 一键输出浏览器环境的脚本，该脚本后续会上传到本书代码库中。
>
> — 李玺, 第3章 3.7.2「手动补充环境」, PAGE 87

---

## I — 方法论骨架 (Interpretation)

补环境不是"配环境"，而是让一段原站 JS 在 Node 里跑出与浏览器一致的结果。所以它有两个目标，缺一不可：**跑得动**（不缺 API）和**跑得像**（不被识别）。

跑得动靠报错驱动：运行 → 报错 → 补那个名字 → 再运行。每一轮的产物是一条新报错；报错换名了，说明这一格补上了，可以继续；报错消失，说明语法层不缺东西了。

跑得像靠类型伪装：补了 `navigator.plugins` 还不够，因为 `toString` 检测会问"你是什么"；要用 `Symbol.toStringTag` 把它标成 `PluginArray`，把 `plugins[0]` 标成 `Plugin`。

检测点是有边界的清单：window/location/document 的一串属性、navigator（platform、plugins、webdriver、userAgent 等）、canvas 与 WebGL 指纹、自动化痕迹（chromedriver）、异常堆栈、native 方法是否被重写。

手补不动时按成本升级：手补 → Proxy 自动探测 → JSDOM → 真浏览器驱动。JSDOM 还原度高，但"在一些场景下也会被检测出来"。

最重要的判据不是"没有报错了"，而是"输出与真浏览器/抓包值一致，且服务端接受"。报错消失只说明缺的不是 API，不说明环境像。

---

## A1 — 书中的应用 (Past Application)

### 案例 1：CNVD 加速乐——最小集由代码决定（案例已过期，仅演示流程）
- **问题**: 要把第二次请求返回的混淆 JS 拿到本地执行。
- **方法论的使用**: 运行后发现代码碰了 `window` 和 `navigator`，于是先补 `window = {}`、`window.navigator = {}`，代码才继续往下走。
- **结论**: 补环境的最小集由"这段代码实际碰了谁"决定，不是一张固定清单。
- **结果**: 本地可执行，但作者随即指出"具体如何补环境可以参考下一节内容"，把这一环单独立成方法（第3章 3.6.7，PAGE 85）。

### 案例 2：toStringTag——补属性只是第一步（案例已过期，仅演示流程）
- **问题**: 报错"没有 plugins"，说明网站会查 `navigator.plugins`。
- **方法论的使用**: 先手写一个 plugins 结构，再用 `navigator.plugins[Symbol.toStringTag] = "PluginArray"`、`navigator.plugins[0][Symbol.toStringTag] = "Plugin"` 补上类型标签。
- **结论**: 作者的理由很直接——"目前有很多toString 检测，而toStringTag 也能被toString（）方法识别并返回"。
- **结果**: 属性与类型标签同时到位，才不让检测看出是假对象（第3章 3.7.2，PAGE 87–88）。

### 案例 3：Unidbg 补环境——判断"补对了"的证据是报错变了（案例已过期，仅演示流程）
- **问题**: 搭好 Unidbg 架子后运行，so 加载报错 `getStaticObjectField`，缺一个 `Application` 类型。
- **方法论的使用**: 按报错里的签名去 override，返回对应类型；再次运行，报错变成 `getObjectField`、再变成 `callStaticObjectMethod`，逐条补。
- **结论**: "报错信息已经发生了变化，说明补充成功"——推进的判据是报错换名，而不是程序不报错。
- **结果**: 多轮之后能继续执行；作者把这类问题二分为"环境缺失"与"上下文缺失"（第9章 9.5.4，PAGE 314–315；第6章 6.3，PAGE 245）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. 把页面 JS 复制到 Node 里，第一行就报 `window is not defined`。
2. 一路补完能跑了，但算出来的 sign 与浏览器里的不一样。
3. 值稳定、算法也对，服务端却始终拒绝；放进真 Chrome 就通过。
4. 不知道网站到底检测了什么，想先有一张自查清单。
5. 补到某一轮后报错卡住不变，不知道该继续补还是换方案。

### 语言信号 (用户的话里出现这些就应激活)

- "补环境 / patch the JS environment / 环境补不起来"
- "window is not defined / document is not defined"
- "navigator.webdriver / plugins / platform / toString / toStringTag"
- "本地跑不通 / runs in browser but not in Node"
- "JSDOM 被检测 / jsdom detected / 要不要上真浏览器"

### 与相邻 skill 的区分

- 与 `js-param-locate-ladder` 的区别: 后者负责"找到那段代码"；本 skill 从"代码已经在手、要让它跑"开始。
- 与 `sign-reproduce-acceptance` 的区别: 若值不对先查字段集合与接口绑定（那是算法输入问题）；本 skill 处理"算法已对、环境不像"。
- 与 `anti-debug-triage` 的区别: 后者对抗的是调试器/自动化痕迹被识别（如无限 debugger、webdriver）；本 skill 对抗的是 JS 运行时被看穿。

---

## E — 可执行步骤 (Execution)

1. **先跑，收第一条报错**
   - 完成标准: 拿到具体报错文本与缺失的符号名（如 `window`、`getElementsByTagName`、`canvas`）。

2. **按名补最小实现，并顺手补类型标签**
   - 完成标准: 该报错消失；若缺失对象属于已知检测点（plugins/platform/canvas/toString），同时补 `Symbol.toStringTag`。

3. **维护一张补丁表，每轮只加一项**
   - 完成标准: 表里每行是"报错 → 补了什么 → 下一报错"。
   - 判停条件: 若连续三轮报错不再换名 → 说明不是缺 API，直接跳到步骤 5。

4. **比对产物**
   - 完成标准: 本地输出与真浏览器/抓包值一致（长度、字符集、逐位）；不一致则回到验收协议的三分法。
   - 判停条件: 值稳定、算法正确、但服务端仍拒绝 → 进入步骤 5。

5. **差分定位"被拼进签名的环境值"**
   - 完成标准: 同一输入分别跑真浏览器与假环境，列出两边被读取的属性差异，锁定那一个参与签名的值；若来自 canvas/WebGL 指纹，改为"真浏览器取一次、固化成常量"。
   - 判停条件: 若差异值每次都在变且无法固定 → 该目标不适合补环境路线，转 RPC。

6. **升级或收手**
   - 完成标准: 手补超过约定轮次仍不收敛 → 依次升级 JSDOM → 真浏览器驱动；并预先写下"升级后仍失败则改用 RPC 远程调用"。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- 生成代码还没定位到——先做定位。
- 参数是明文，或只做了编码——不需要运行环境。
- 拦截发生在 TLS/JA3、HTTP/2 指纹或设备指纹层——补 JS 环境对它无效。
- 只是"想在 Node 里跑一下看看"、不打算与服务端结果比对——这会得到错误的安心感。

### 作者在书中警告的失败模式

- "该引擎调用对方Js 的可行性并不是100%"（PAGE 42）——补环境不是万能解，要有失败退出。
- JSDOM "能满足大部分测试场景下对浏览器环境的还原，但在一些场景下也会被检测出来"（PAGE 89）。
- 只补属性不伪装类型：`toString` 检测会把假 plugins 认出来（PAGE 87–88）。
- 报错消失 ≠ 成功：作者自己强调补完之后仍要按结果对比判定（PAGE 77）。

### 作者的盲点 / 时代局限

- BOOK_OVERVIEW 指出，作者虽承认可行性不满 100%，却**没有给出补环境失败的判定标准与回退路径**；书中只有个别案例的"对比无误则还原成功"。
- 检测点停留在 navigator/toString/堆栈这一代；2023 年后的设备指纹、行为序列、云端模型不在覆盖范围，canvas/WebGL 也只给了"应该不一样"的定性描述，没有可比对基线。
- 案例中"补充成功"的判据是报错变化，这在语法层成立，但容易被误读成"环境已还原"。

### 容易混淆的邻近方法论

- `native-hook-or-unidbg` 的"环境缺失 vs 上下文缺失"二分——同一套思路在 so 侧，但归因不同：缺 API 会报错，少初始化步骤会静默返回异常值。
- 一般的"依赖安装/环境配置"——那是把软件装起来，这里是伪造运行时。

### 合规红线

仅限自有系统、已授权目标或公开测试环境；不提供针对未授权目标的攻击配方。

---

## 相关 skills

- depends-on: js-param-locate-ladder
- contrasts-with: native-hook-or-unidbg
- composes-with: js-param-locate-ladder, sign-reproduce-acceptance

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 100%（6/6，详见 test-results.md）
- **蒸馏时间**: 2026-10-30

---
name: constant-fold-and-decoding
description: |
   用户要把 425871^425977、\u4e2d、eval(atob(…)) 这类写死的值折成字面量。做法：evaluate 且 confident 为真才 valueToNode+path.skip；eval/fromCharCode 把解密函数搬本地跑；转义靠 minified+jsescOption 两段 generate。不适用于：对象层层取值（转 junk-instruction-elimination）；改名（转 scope-safe-rename）。trigger：常量折叠/constant folding/confident/jsescOption/atob/转义还原。
source_book: 《反爬虫AST原理与还原混淆实战》 李岳阳、卓斌
source_chapter: 第6章 PAGE 107、112–117；第8章 PAGE 175；第10章 PAGE 207–212
tags: [constant-folding, babel-ast, evaluate, decoding, sequence-expression]
related_skills: [junk-instruction-elimination, ast-obfuscator-design-constraints, ast-restore-pipeline-acceptance, string-pool-decrypt-revive]
---

# 常量折叠与编码还原：三档阶梯

## R — 原文 (Reading)

> "path.evaluate方法用来计算节点的值,返回一个对象。返回的对象中的confident是一个布尔值，它代表节点是否可计算出结果。"
>
> "generator时，就已经把代码还原了。第二次的 parse 和 generator只是为了把代码格式化。"
>
> — 李岳阳、卓斌, 第10章 PAGE 208 / 第10章 PAGE 210

---

## I — 方法论骨架 (Interpretation)

常量还原最容易犯的错，是把它当成"一个 `evaluate` 走天下"。书里的做法是先把问题分层：这个值究竟在哪一层才算得出来。

第一层是语法层。纯字面量参与的四则、位运算、异或（`425871^425977`）、`parseInt('0x1f',16)`、字符串相加，都能在不动运行期的情况下算出来。`path.evaluate()` 返回 `{confident, value}`，其中 `confident` 是唯一的闸门——它表示"能否确定算出结果"，而不是"看起来像常量"。只有它为真才 `valueToNode` 替换。

替换后必须 `path.skip`。`valueToNode` 产出的仍是一个同类节点（如还是 `NumericLiteral`），同一个 visitor 会再次命中它；`skip` 只是跳过当前子树，`stop` 会把后面所有同类节点一起漏掉。

第二层是执行层。源码里的 `eval(atob('…'))`、`eval(String.fromCharCode(…))`，eval 的实参往往是一个自执行匿名函数，那个函数就是解密函数。还原的办法不是继续在树上算，而是把解密函数搬到本地执行一遍。`atob` 是浏览器内置，Node 里没有，必须补一个同名实现；名字不一致等于没补，会直接抛 `ReferenceError`。

第三层是生成层，也是最容易被搞错的一层。文件里的 `\u4e2d`、`\x61` 多数只是字面量的转义写法，节点的 `value` 早就是明文了——树上根本没有"待还原"的东西。真正的还原发生在第一次 `generator` 的选项上：`{minified:true, jsescOption:{minimal:true}}` 决定是否把字符再转义回去。所以要先 generate，再 parse，再 generate 一次拿格式化结果；只做一次会留下压缩成一行、仍带转义的产物。

逗号表达式单独一档：`SequenceExpression` 按 `expressions` 顺序求值，只有最后一个成员的值有用。它应该放在 `exit` 处理，因为 `exit` 是子先父后，这个方向恰好等于手工"找最内层括号、由内向外"的直觉。展平时要把前面的表达式提升为独立语句，最后一个的值仍须保留（通常是 `return` 或赋值），不能丢。

顺序之所以是这样：静态可算的先折（无副作用、不会改语义）；需要宿主函数的先补环境再算；编码只是输出层问题，必须放在最后。反过来做，就会把运行期相关的表达式（`Date.now()+1000`）、或者本应保留的转义，一起"算"进产物里。

失败几乎都是静默的。强折 `Date.now()+1000` 不会报错，只会把时间写死成"还原那一刻"，产出的 sign 与服务器永远不匹配，直到逐字段比对才暴露。所以折叠的停止条件是 `confident` 为真，不是"看起来像常量"。

---

## A1 — 书中的应用 (Past Application)

### 案例 1：异或常量还原（第10章 PAGE 207）
- **问题**: 数值常量被写成 `a^b` 的二元表达式，文件里遍地是位运算，逐个心算不现实。
- **方法论的使用**: 作者把 visitor 限定在 `BinaryExpression`，并且要求 left/right 都是 `NumericLiteral` 才处理；然后调用 `path.evaluate()` 拿到 `{confident, value}`，`confident` 为真时用 `valueToNode` 构造新节点替换回去，并 `path.skip`。
- **结论**: 不需要关心是 `^` 还是别的位运算，`evaluate` 直接给结果；但必须用 `confident` 守住"不可求值就不替换"，否则会把运行期才确定的表达式算错。
- **结果**: 异或、位运算一类纯字面量表达式被批量折成数字字面量；错误形态也被记录下来——不判 `confident` 直接替换，含变量/函数调用/`Date` 的表达式会被算成 `undefined`/`NaN` 或旧值（第10章 PAGE 207）。

### 案例 2：base64/ASCII 的 `atob` 要自己补一个同名实现（第10章 PAGE 208）
- **问题**: 源码里是 `eval(atob('…'))` 或 `eval(String.fromCharCode(…))`，把整段搬到 Node 里跑，第一句就报错。
- **方法论的使用**: 作者指出必须找到相应的解密函数，并且在本地定义时名字要一致——`atob` 是浏览器中的 Base64 解密函数，在文件里找不到它的定义。做法是在本地脚本里预先定义 `function atob(s){…}`（或用 Node 的 Buffer 做 base64），再由 AST 把整个 `eval` 调用求值后替换。
- **结论**: 浏览器内置函数在 Node 里不存在，缺哪个补哪个；名字不一致等于没补。
- **结果**: 文件中的 Base64/ASCII 常量被解成明文并替换为字面量；未补或补错名字时的表现是直接抛 `ReferenceError`，而不是静默错值（第10章 PAGE 208）。

### 案例 3：unicode/十六进制还原要走"两段 generate"（第10章 PAGE 210）
- **问题**: 源码里满是 `\u4e2d`、`\x61`，在 AST 上找不到可以"替换"的节点，改 visitor 也无从下手。
- **方法论的使用**: 作者的做法是第一次 `generator(ast, {minified:true, jsescOption:{minimal:true}})` 生成代码——`jsescOption` 决定是否把不可见字符再转义回 `\u`；然后 `parser.parse` 再 `generator` 一次，得到格式化后的可读代码。
- **结论**: 还原动作发生在"第一次 generate 的选项"上，第二次的 parse 和 generator 只是为了把代码格式化；只做一次会得到压缩成一行的结果，影响后续人工分析。
- **结果**: 转义字符被还原成明文，且产物可读；作者据此明确，"编码类还原"不在树里，而在生成选项里（第10章 PAGE 210）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. 代码里出现 `425871^425977`、`parseInt('0x1f',16)`、`'a'+'b'` 这类纯字面量表达式，想折成字面量。
2. 出现 `eval(atob('…'))`、`eval(String.fromCharCode(…))` 或 jsfuck 串，想拿到明文。
3. 整文件都是 `\u4e2d`、`\x61`，generate 出来仍然是转义形式。
4. 大量 `a=(b=(c=1,c+2),b+3)` 的逗号嵌套，语句被压成一行表达式。
5. 折叠之后代码能跑，但 sign 与抓包对不上——值被写死成某个时刻的常量。

### 语言信号 (用户的话里出现这些就应激活)

- "常量折叠 / 常量还原 / 把这个表达式折叠掉"
- "evaluate / confident / valueToNode / path.skip"
- "eval 加密 / 解密函数 / atob 找不到定义"
- "unicode 还原 / 还是转义 / 两段 generate"
- "逗号表达式 / SequenceExpression / 由内向外"
- "constant folding / fold constants"
- "path.evaluate returns confident=false"
- "jsescOption minimal / generator options"
- "sequence expression flatten / handle in exit"
- "value got hard-coded / sign mismatch after folding"

### 与相邻 skill 的区分

- 与 `junk-instruction-elimination` 的区别: 那边要通过对象/函数间接层（`_0x1['a']`、包装函数）找到定义侧，必须先建 `totalObj`；本 skill 只对"已经拿到手的表达式"求值，不需要索引。
- 与 `string-pool-decrypt-revive` 的区别: 那边是"大数组 + 乱序 + 解密函数"整池替换，受 `compact` 与引导代码约束；本 skill 处理零散的 `eval`/`atob`/`fromCharCode` 个案。
- 与 `scope-safe-rename` 的区别: 那边的失败是"改错绑定"（引用断裂或遮蔽），本 skill 的失败是"算错值"；顺序上常量与字符串解密必须先于改名，因为改名会断掉按属性键搜索的线索。
- 与 `sign-reproduce-acceptance` 的区别: 那边验最终参数值是否与服务端一致；本 skill 只保证折叠没有改语义，值不对时先查 `confident` 与 `Date`/`Math.random`，不要重写算法。
- 与 `ast-restore-pipeline-acceptance` 的区别: 本 skill 是那条七段流水线里的"常量还原"一段，必须服从"先字符串解密、再平坦化/改名"的全局顺序。

---

## E — 可执行步骤 (Execution)

顺序是一阶约束：静态可算的先折，需要宿主函数的先补环境，编码只影响输出层所以放最后；逗号要在 `exit` 展平，否则父节点先被处理、内层顺序就丢了；折叠完若值仍偏，多半是把 `confident=false` 的表达式也替换了。

1. **给每条候选表达式定"值确定层"**
   - 完成标准: 每条候选被标成"静态可算 / 需执行解密 / 仅是编码转义"三类之一，并注明节点类型（`BinaryExpression`、`CallExpression`、`StringLiteral`、`SequenceExpression`）。
   - 判停条件: 全文件没有常量表达式、也没有转义——不属于本 skill，回去定位真正的入口。

2. **第一档：`evaluate` + `confident` 闸门**
   - 完成标准: 只有 `confident` 为真才 `valueToNode` 并 `path.skip`；`confident` 为假的节点原样保留，并记入"运行期清单"（时间戳、随机数、cookie 依赖）。
   - 判停条件: 发现被折的节点依赖 `Date.now()`、`Math.random()`、`window` 状态 → 立即撤销替换；这类值交给包级验收的桩环境（`ast-restore-pipeline-acceptance` 的 L2），不要在这里硬算。

3. **第二档：补宿主函数，再在隔离沙箱执行解密**
   - 完成标准: `atob`、`String.fromCharCode` 等都有同名本地实现；`eval` 的实参可求值得到字符串；执行发生在一次性沙箱，不触碰生产环境与真实凭据。
   - 判停条件: 解密函数依赖网络、文件、运行期状态，或代码明显含反分析（内存爆破）→ 停止，不要 `eval` 不可信代码。

4. **第三档：两段 generate 解编码**
   - 完成标准: 第一次 `generate({minified:true, jsescOption:{minimal:true}})`，再 `parse`，再 `generate`；产物无 `\u`/`\x` 残留且已格式化。
   - 判停条件: 两段之后仍有转义 → 说明那些字符不是"转义写法"而是拼接/加密产物，转 `string-pool-decrypt-revive` 或回到步骤 3。

5. **逗号表达式在 `exit` 展平**
   - 完成标准: `SequenceExpression` 被提升为多条语句，前面的子表达式按序执行，最后一个成员的值仍被使用（`return` 或赋值的右值）。
   - 判停条件: 末尾值被丢弃、或语句顺序与括号嵌套不符 → 还原错，退回并改到 `exit` 处理。

6. **行为等价验收**
   - 完成标准: 折叠前后关键函数在同一输入下输出一致；"运行期清单"里的表达式一个都没被替换。
   - 判停条件: 值偏 → 先查是否强折了 `confident=false` 的节点，再查是否只做了一段 generate；不要重写算法。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- 表达式依赖运行期（`Date.now()`、`Math.random()`、`window`/`cookie` 状态）——`confident` 为假，折了就是把值写死，且不报错。
- 需要的是"去掉间接层"（对象属性链、包装函数）——那是 `junk-instruction-elimination`，要先建索引找到定义侧。
- 需要的是"解密大数组字符串池"——那是 `string-pool-decrypt-revive`，涉及引导代码、`compact` 与 `referencePaths` 过滤。
- 需要的是"改名"——那是 `scope-safe-rename`，而且必须在本 skill 与字符串解密之后。
- 代码只是被压缩（minified），没有常量混淆——只需要格式化输出，不需要折叠。

### 作者在书中警告的失败模式

- 只取 `value` 不判 `confident`，或对任意 `BinaryExpression` 都 `evaluate` 后替换：含变量、函数调用、`Date` 的表达式被算成 `undefined`/`NaN` 或旧值，代码静默变成常量（第10章 PAGE 207）。
- 替换后不用 `path.skip`：新节点仍是同类节点，会被同一个 visitor 再次命中；用 `path.stop` 则会漏掉后面的同类节点（第8章 PAGE 175）。
- 补宿主函数时名字不一致：`atob` 名字不对等于没补，解密直接抛 `ReferenceError`（第10章 PAGE 208）。
- 只做一次 generate：还原动作其实发生在选项上，第二次只是格式化；只做一次会得到压缩成一行、仍带转义的代码（第10章 PAGE 210）。
- 把 jsfuck 整段贴进控制台，尤其与其它代码混杂时会报错，误判为"无法还原"；真正的问题是分段与上下文，报错不等于加密强（第6章 PAGE 107）。
- `eval` 属不可信执行，书中按普通函数调用处理（第11章 PAGE 232）；实际必须放进隔离沙箱。

### 作者的盲点 / 时代局限

- 三档划分只覆盖书中四种形态（位运算、base64/ASCII、unicode/hex、逗号），未讨论模板字符串、`BigInt`、可选链、正则字面量里的转义（第10章 PAGE 207–212）。
- `jsescOption` 只解决"输出转义"，对"源码里本来就是拼接出来的字符"无效，作者未区分这两者。
- 无性能与规模约束：整文件多次 traverse + 同步 `eval`；对 1.8MB 级文件没有超时与内存上限（BOOK_OVERVIEW 批判节）。
- 2021 环境快照：`@babel/parser 7.9.4`、Node 12；现代 Babel 的 `evaluate` 行为与 `jsescOption` 默认值可能已变，照抄需实测（BOOK_OVERVIEW 基本信息）。
- 样本量 = 1，验收靠"打印 → 肉眼比对"，无自动断言。

### 容易混淆的邻近方法论

- 编译器的常量传播（constant propagation）：编译器在 SSA 上会把常量代进变量；本 skill 只替换表达式节点、不传播到变量，目标是可读性而非优化。
- 死代码消除（DCE）：按可达性删代码；本 skill 只改值、不改控制流结构。
- 编码 vs 加密：base64/hex/unicode 是编码（可逆、无需密钥），作者用"还原后有无密码学运算"来判定"看似加密实为编码"（第11章 PAGE 249）；不要把编码当加密去设计破解方案。

### 合规红线

仅限自有系统、已授权目标或公开测试环境；不提供针对未授权目标的攻击配方。第二档的 `eval` 属不可信执行，必须在隔离沙箱内做，不得在含真实凭据的环境运行。

---

## 相关 skills (阶段 3 填充)

- depends-on: junk-instruction-elimination（先剔花指令，常量与编码才露出来）
- contrasts-with: ast-obfuscator-design-constraints（造时编码 vs 拆时解码）
- composes-with: ast-restore-pipeline-acceptance、string-pool-decrypt-revive（折叠与解池同在流水线中连用）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 83%（10/12 用例，详见 test-prompts.json）
- **蒸馏时间**: 2026-10-31

---
name: scope-safe-rename
description: |
   用户批量为满屏下划线名改名，脚本跑完能运行、值却偏了、一行报错都没有。做法：getOwnBinding 带出子函数绑定，须按 binding.scope 过滤归属，再收自由名避撞、scope.rename 改，改完 generator→parse 重建。不适用于：没解密就改名（转 string-pool-decrypt-revive）；缺 window/document（转 js-env-patch-loop）；只验复现值（转 sign-reproduce-acceptance）。trigger：批量改名/值偏没报错/not defined/子函数被波及/搜不到属性键/rename。
source_book: 《反爬虫AST原理与还原混淆实战》 李岳阳、卓斌
source_chapter: 第8章 PAGE 162–170、182；第9章 PAGE 181–185；第11章 PAGE 233、249
tags: [babel-ast, scope, binding, rename, codemod]
related_skills: [constant-fold-and-decoding, control-flow-flattening-restore, junk-instruction-elimination, string-pool-decrypt-revive, js-env-patch-loop]
---

# 作用域安全重命名：binding 归属、全局避撞、改完重 parse

## R — 原文 (Reading)

> "把ast先转成代码，再次进行解析后，再进行标识符混淆。"
>
> "该函数用于获取当前节点自己的绑定，也就是不包含父级作用域中定义的标识符的绑定。但是该函数会得到子函数中定义的标识符的绑定，来看下面这个例子："
>
> — 李岳阳、卓斌, 第8章 PAGE 182 / 第8章 PAGE 165

---

## I — 方法论骨架 (Interpretation)

重命名是整套还原动作里唯一必须依赖语义的一个。语法层看不出两个 `a` 是不是同一个变量，只有 `scope`/`Binding` 知道。

它要同时满足四个前置条件，缺一个就会"改得动但改错"。

第一，绑定归属。`getOwnBinding` 听起来是"当前节点自己的绑定"，它确实不含父级作用域的名字，但它会带出子函数里定义的标识符——直接在父函数里全量改名，子函数的参数和局部变量会被一起改掉，子函数内部引用随即断裂。正确做法是拿到 binding 后再比较 `binding.scope` 与当前函数 scope 是否同一个，只处理归属当前函数的那部分。

第二，`kind` 不等于归属。`kind=='param'` 只说明"这是一个参数"，不说明它属于哪个函数。同名参数可能来自外层或兄弟函数，被当前函数引用；据此决定"要不要改名"必然误判。归属只能看 `binding.scope` 或 `binding.path` 的最近函数父节点。

第三，`scope.block` 依赖节点类型。在函数声明上遍历时，`scope.block` 返回的正是这个 FunctionDeclaration 节点本身，而不是"整个函数体范围"；拿它去查参数和局部声明会漏。要判断 `scope.block` 是否就是当前函数节点，是则取 `scope.parent`。

第四，避撞。函数体里引用了 window 上的名字（或任何"被引用但无本地声明"的自由变量）时，如果本地新名撞上它，局部就会遮蔽全局，语义被改写。做法是先收集全部自由名进 `globalBindingObj`，生成新名时避开。反过来，没有被引用到的全局名可以故意撞，那正是混淆想要的迷惑效果。

落地用 `scope.rename(旧名, 新名)` 批量改所有引用，省去手工维护 `referencePaths`；新名由 `scope.generateUidIdentifier` 生成，Babel 维护已用名字表，保证不冲突。它只保证"不冲突"，不保证"像混淆名"——要 `O/o/0` 那种迷惑形态，得在结果上再做字符映射，映射后还要自检冲突。

改完必须 `generator → parser.parse` 重建 AST。`types` 造出来的只是 Node，不是 Path，没有 binding 来源；继续在原 AST 上 `getBinding`/`rename`，拿到的是旧绑定或查不到，错误还是静默的。

顺序是硬约束：先字符串解密（以及花指令、平坦化），最后才改名。改名会把属性字符串键一起换成不可读的名字，断掉"按属性键逐跳上溯"这条唯一线索。造侧同一条依赖反过来讲了一遍：逐行加密会把标识符一起加密，所以必须排在标识符混淆之后。

两种失败形态要两套验收。报 `not defined` 是绑定断裂，会响，算好事；能跑但值偏是遮蔽或漏改引用，完全静默，只能靠"跑一遍 + 与抓包值逐字段比对"抓到。

---

## A1 — 书中的应用 (Past Application)

### 案例 1：`scope.block` 在 FunctionDeclaration 上取到自身（第8章 PAGE 163）
- **问题**: 遍历函数声明节点，想拿"整个函数体"的作用域做绑定分析，结果查不到参数和函数内声明。
- **方法论的使用**: 作者发现 `scope.block` 返回的正是该 FunctionDeclaration 节点本身，与预期的"整个 add 的范围"不符；据此判断需要去获取父级作用域，即先判断 `scope.block` 是否是当前函数节点，是则取 `scope.parent`。
- **结论**: `scope` 的落点依赖节点类型——变量声明场景 `scope.block` 直接可用，函数声明场景必须向上取；不能一把梭。
- **结果**: 改成取父级作用域后，函数体范围的绑定查询才完整；这条被记为"坑"，成为后续改名流程的前置检查（第8章 PAGE 163）。

### 案例 2：`getOwnBinding` 会带上子函数的局部绑定（第8章 PAGE 165）
- **问题**: 在函数 `demo` 内做 `getOwnBinding`，期望只拿到 `demo` 自己的 `a`，实际返回值里还出现了子函数 `add` 里的 `a`。
- **方法论的使用**: 作者用一个最小例子演示：`getOwnBinding` 不含父级作用域，但**会**得到子函数中定义的标识符绑定。直接据此改名，子函数的参数会被误改。解法是拿到 binding 后比较 `binding.scope` 与当前函数 scope 是否相同（或看 `binding.path` 的最近函数父节点），只处理归属当前函数的那部分。
- **结论**: `getOwnBinding ≠ 当前函数绑定`；`kind` 只描述种类不描述归属。
- **结果**: 加入归属过滤后，子函数的参数与局部变量不再被误改；这条成为"全量 rename 会静默改错"的典型证据（第8章 PAGE 165）。

### 案例 3：标识符混淆装配里的避撞与重新 parse（第8章 PAGE 182）
- **问题**: 写一个最简标识符混淆：遍历可改名的 `Identifier`，用 `scope.rename` 批量改名，新名用 `scope.generateUidIdentifier` 生成。看起来只差一个循环。
- **方法论的使用**: 作者在装配时补了两条约束：①重命名不能与"引用到的全局标识符"重名，需要先判断（否则局部遮蔽全局）；②改名完成后必须把 AST 转成代码、再重新解析，因为 `types` 生成的新节点没有 binding 来源。同样的坑在第9章造侧被独立复述：必须分域处理，否则子函数局部变量会被一起改（第9章 PAGE 181–185）。
- **结论**: 改名不是"替换字符串"，而是"维护一张名字与声明的关联表"；表的有效期只到下一次 AST 变更。
- **结果**: 书中示例最终输出形如 `2100xiaojianbang` 的标识符——数字加字母、形似而无意；`rename` 只换名字不改语义，真正落地还要叠加作用域分域与全局名避撞（第8章 PAGE 169、182）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. 满文件 `_0x21dd83`、`_0x21dd84`，想把它们改成 `a`、`b`、`c` 或可读名。
2. 改名脚本跑完，运行时报某个名字 `is not defined`，但源码里明明声明了它。
3. 改名后能跑，sign 或返回值却与抓包不一致，且没有任何报错。
4. 子函数的参数被父函数的改名波及，子函数内部引用断裂。
5. 改完名之后，再也搜不到某个属性字符串键，定位链断了。

### 语言信号 (用户的话里出现这些就应激活)

- "改名 / 重命名 / rename / 标识符还原"
- "getOwnBinding / binding.scope / 子函数被一起改了"
- "kind 是 param / 这个参数属于谁"
- "scope.block 返回的是函数自己"
- "globalBindingObj / 撞了全局名 / 局部遮蔽"
- "generateUidIdentifier / 新名字冲突"
- "a is not defined after rename"
- "rename broke the child function / wrong binding"
- "shadowing / global binding collision"
- "must re-parse after rename / types node has no binding"

### 与相邻 skill 的区分

- 与 `js-env-patch-loop` 的区别: 那套解决"补了 `window`/`document`/`navigator` 还被识别"，是运行期环境问题；本 skill 解决"改名改错对象且不报错"，是编译期作用域问题。
- 与 `constant-fold-and-decoding` 的区别: 那边折值、解编码，本 skill 换名字；顺序上常量与字符串解密在前，改名在后。
- 与 `string-pool-decrypt-revive` 的区别: 那边先解大数组字符串池，改名会断掉按属性键搜索的线索，所以它必须先完成。
- 与 `sign-reproduce-acceptance` 的区别: 那边验"复现的参数值对不对"；本 skill 的静默失败最后也要靠跑一遍比对值才抓得到，但定位手段是打印 `binding.scope` 与最近函数父节点，而不是比对签名算法。
- 与 `ast-restore-pipeline-acceptance` 的区别: 本 skill 是七段流水线里的"重命名"一段，必须服从"先字符串解密、再改名"的全局顺序；那套 skill 负责归因"错在顺序还是错在单点"。

---

## E — 可执行步骤 (Execution)

顺序与判据都建立在同一个事实上：binding 是 AST 当前的快照，任何一次造节点、改名、重排都会让它过期；归属只能从 `scope` 查，不能从名字或 `kind` 猜。

1. **确认改名时机**
   - 完成标准: 字符串池已解密、花指令已折叠、平坦化已还原；并且已经导出/备份了一份"属性字符串键 → 位置"的清单，供改名后回溯。
   - 判停条件: 字符串池还没解 → 转 `string-pool-decrypt-revive`；顺序颠倒 → 先补前序步骤，不要边解密边改名。

2. **收集全局自由名 `globalBindingObj`**
   - 完成标准: 全文件"被引用但无本地声明"的名字集合齐全，作为新名的黑名单。
   - 判停条件: 代码里存在 `with`、`eval` 动态作用域、或运行时拼接的全局访问 → 静态收集不可靠，停止批量改名。

3. **逐个 binding 判归属**
   - 完成标准: 每个待改名的 binding 都有明确的 `binding.scope` 与 owner 函数，且与目标函数一致；子函数绑定被排除；`kind=='param'` 的项已核对过归属。
   - 判停条件: `binding.scope` 与预期不符、或 `scope.block` 指向函数自身未向上取 `parent` → 先打印 `binding.path` 的最近函数父节点，确认后再继续。

4. **生成安全新名并 rename**
   - 完成标准: 新名由 `generateUidIdentifier` 产出且不在 `globalBindingObj` 中；`scope.rename` 后旧名的引用计数为 0，无残留引用。
   - 判停条件: 需要 `O/o/0` 之类形似名字 → 在 `generateUidIdentifier` 结果上做字符映射，映射后重新自检冲突；不要手搓随机名。

5. **`generator → parse` 重建 AST**
   - 完成标准: 重新解析成功，抽查若干名字的 binding 能查到，引用数与改名前一致。
   - 判停条件: 仍出现"binding 无来源"或查到旧绑定 → 说明改名发生在 `types` 造节点之后，回到步骤 5 重来，不要在旧树上打补丁。

6. **两条验收：语法 + 语义**
   - 完成标准: 语法验收——全文件无 `X is not defined`；语义验收——关键函数在同一输入下的输出与抓包/基线一致。
   - 判停条件: 报 `not defined` → 查绑定归属与 `globalBindingObj` 避撞；能跑但值偏 → 查遮蔽与漏改引用，不要重写算法。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- 代码只是"变量名不好看"，但可执行、可搜索——改名的收益低于断掉搜索线索的风险。
- 代码里有 `with`、`eval` 动态作用域、或多个脚本共享全局的拼接执行——静态 binding 不可靠。
- 还没做完字符串解密——改名会把属性字符串键换成不可读名，唯一的搜索线索就没了（第11章 PAGE 249）。
- 真正的问题是运行期环境缺 `window`/`document`/`navigator` 的桩——那是 `js-env-patch-loop`，不是改名。
- 真正要回答的是"参数值复现对不对"——那是 `sign-reproduce-acceptance`。

### 作者在书中警告的失败模式

- `getOwnBinding` 会得到子函数中定义的标识符绑定，直接全量 `rename` 会误改子函数（第8章 PAGE 165）。
- `scope.block` 在 FunctionDeclaration 上返回函数自身，据此查绑定会漏掉参数与函数内声明（第8章 PAGE 163）。
- 重命名不能与"引用到的全局标识符"重名，否则局部遮蔽全局，语义被改写（第8章 PAGE 182）。
- 用 `types` 生成的新节点没有 binding 来源，继续在原 AST 上改名必错，而且不报错——静默产出语义错误的代码（第8章 PAGE 182）。
- 应先字符串解密、再还原标识符混淆（第11章 PAGE 249）；造侧的同一依赖是"逐行加密必须放在标识符混淆之后"（第9章 PAGE 206）。

### 作者的盲点 / 时代局限

- 只讨论函数、变量与参数，未覆盖 class 私有字段、label、`import`/`export` 绑定、解构默认值里的改名。
- "避撞"只处理自由变量；对 `globalThis` 动态属性、`with`、跨模块共享、运行时 `eval` 未讨论。
- "先字符串解密再改名"这条法则在书内从未真正被使用——第11章根本没做标识符还原（PAGE 233），规则只有二元约束，没有传递闭包与失败模式示例（BOOK_OVERVIEW 内部矛盾 5）。
- 验收是"抽查 + 跑一遍"，没有语义等价性证明或自动断言；改名后的行为一致全靠肉眼。
- 2021 环境快照：`@babel/parser 7.9.4` 的 scope API 行为；新版本对 `types` 节点与 scope 缓存的处理可能不同，照抄需实测。

### 容易混淆的邻近方法论

- codemod 工具自带的重命名（jscodeshift / ts-morph）：工具替你维护引用，但边界仍是 scope；本 skill 的坑在"绑定归属"，不是 API 用法。
- 压缩器的变量名缩短（mangle）：目标是体积，会做使用频率分析；这里的目标是可读（或混淆），只关心不冲突、不遮蔽。
- 混淆器的标识符随机化（造侧，第9章 PAGE 181–185）：同一套 scope 分域约束，方向相反——一个求可读，一个求不可读。

### 合规红线

仅限自有系统、已授权目标或公开测试环境；不提供针对未授权目标的攻击配方。对退化的静态分析结果（`with`、`eval`、动态全局）宁可停止改名，也不要"大概能跑就上线"。

---

## 相关 skills (阶段 3 填充)

- depends-on: constant-fold-and-decoding、control-flow-flattening-restore、junk-instruction-elimination、string-pool-decrypt-revive（硬顺序，先解密/去花/去平坦化，最后改名）
- contrasts-with: js-env-patch-loop（静态改名 vs 运行期补环境）
- composes-with: （无）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 92%（11/12 用例，详见 test-prompts.json）
- **蒸馏时间**: 2026-10-31

---
name: ast-restore-pipeline-acceptance
description: |
   用户整份还原跑完了、一行报错都没有，可产出的值和抓包对不上；或替换回站点一请求就 403。做法：固定段序（字符串→花指令→常量→平坦化→改名→回站）且每段重 parse，再按 L1 值级、L2 整包、L3 回站三档验收归因。不适用于：单段怎么改不是（转对应单点 skill）；只验一个 sign 不是（转 sign-reproduce-acceptance）；只补环境不是（转 js-env-patch-loop）。trigger：整套还原顺序/全量还原/跑完不报错值不对/怎么验收/回站 403/pipeline order。
source_book: 《反爬虫AST原理与还原混淆实战》 李岳阳、卓斌
source_chapter: 第9章「JS代码自动化防护」PAGE 206；第10章「AST还原方案」PAGE 207–212；第11章「还原实战」PAGE 231–249
tags: [ast, babel, deobfuscation, acceptance]
related_skills: [obfuscation-fingerprint-triage, scope-safe-rename, js-env-patch-loop, sign-reproduce-acceptance, ast-obfuscator-design-constraints, ast-restore-locate-and-protocol, constant-fold-and-decoding, control-flow-flattening-restore, junk-instruction-elimination, string-pool-decrypt-revive]
---

# 还原流水线与三档验收：顺序是一阶约束，验收要能归因

## R — 原文 (Reading)

> 当各种混淆手段混合使用时，还原的顺序就显得尤为重要，如果还原的顺序不正确，就可能导致还原失败。
>
> — 李岳阳、卓斌, 第11章 11.5「小结」, PAGE 249

---

## I — 方法论骨架 (Interpretation)

流水线的价值不在某一步写得多巧，而在段间依赖不出错。顺序错时通常不报错，只静默产出语义漂移的代码——这才是最难查的一类失败。

固定段序：列手段清单 → 字符串池解密 → 剔花指令 → 常量还原 → 平坦化重排 → 标识符重命名 → 回站验证。

两条硬依赖：字符串必须先解，否则改名后连"按属性键搜索"这条唯一线索都断了；花指令必须先剔，否则分发器可能被包装层裹住，平坦化会误判成"没有平坦化"。

段间要重新 parse，因为 types 造出的新节点没有 binding，继续在原树上改名会拿到旧绑定。

验收分三档，且失败可归因。L1 值级：关键函数或表达式与已知样本比对，验"算法本体"；L2 包级：离线桩环境跑整包，与抓包逐字段比对，验"环境与拼接"；L3 站点级：把还原文件替换回站（Fiddler 自动响应 / Local Overrides），触发真实请求，验"整链可用"。

归因规则：L1 不过 = 还原错，回段序查该段；L1 过、L2 不过 = 环境桩缺东西（navigator/cookie/document/window/随机源），不要重写算法；L2 过、L3 不过 = 站点有完整性校验（SRI/CSP/文件哈希），此时是"验收手段不可用"，不是"还原错了"。

先把 L1 与 L2 做扎实，再谈 L3。L3 走不通不等于失败，只说明这一档在当前站点不可达。

---

## A1 — 书中的应用 (Past Application)

### 案例 1：靶站七段总装——顺序错则整链失败
- **问题**: 同一份 lebo.yzm.pc.min.js，手段多、段序不明，先做哪一段没有把握。
- **方法论的使用**: 先列混淆手段清单，再按"字符串池 → 花指令 → 常量 → 平坦化 → 改名"排段，并明确"应先字符串解密，再还原标识符混淆"；每段之间重新 parse。
- **结论**: 顺序是一阶约束，单点能力是二阶；顺序错时整链失败且不报错，只是结果偏。
- **结果**: 七段跑通，产物可读，生成参数与抓包同构（第11章 PAGE 231–249）。

### 案例 2：造侧的同向约束——逐行加密必须排在标识符混淆之后
- **问题**: 第9章装配混淆器时，逐行加密与标识符混淆谁先谁后。
- **方法论的使用**: 同一依赖方向在造侧被再讲一次：逐行加密会把整行里的标识符一起加密，所以必须放在标识符混淆之后。
- **结论**: 这不是某站的偶然经验，而是"先保留可改的结构，再做不可逆的文本加密"的通用约束。
- **结果**: 装配顺序被写成显式清单，而不是靠碰巧能跑（第9章 PAGE 206）。

### 案例 3：回站验证——静态看着像不等于还原对
- **问题**: 还原后静态阅读"像"了，怎么证明它对。
- **方法论的使用**: 按三档验收推进：先 L1 单函数比对，再 L2 离线桩逐字段比对，最后 L3 用 Fiddler 自动响应或 Chrome Local Overrides 把还原文件替换回站，触发真实请求，与新生成的 data/clientid/$strlen 逐字段比对。
- **结论**: 只看静态阅读不算验收；跑不通要按档归因，不能一律回去改算法。
- **结果**: 替换回站后能跑通即整链成立；被拒则归因为站点有完整性校验，而非算法错误（第11章 PAGE 245）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. 还原脚本写完，跑完无报错，但生成的 sign/data 与抓包不一致。
2. 面对一份多手段混合的样本，纠结先解密字符串还是先重命名、先平坦化还是先剔花指令。
3. 想用"替换回站"验收，结果请求返回 403 或被拒绝执行。
4. 还原产物里还残留 new window["Date"]() 或 _0x 名字，怀疑漏了步骤。
5. 要给团队定一条可重复执行的还原流程与验收标准。

### 语言信号 (用户的话里出现这些就应激活)

- "先做哪一步 / which step first / 顺序"
- "还原顺序 / restore order / 依赖"
- "跑完没报错但值不对 / wrong output no error / silent failure"
- "静默失败 / silently wrong"
- "怎么验收 / how to verify / acceptance"
- "回站验证 / replace back / Local Overrides / Fiddler AutoResponder"
- "403 / 被拒 / integrity check / SRI / CSP"
- "还原不完整 / leftover / new window"
- "改名后要重新 parse / binding 丢失"
- "整链 / end-to-end / pipeline"

### 与相邻 skill 的区分

- 与 `ast-restore-locate-and-protocol` 的区别: 后者到"找到生成链"为止；本 skill 从"决定要还原"开始管段序与验收。
- 与 `sign-reproduce-acceptance` 的区别: 后者验单参数复现值（相当于 L1 级）；本 skill 验整包与整链，并把失败归因到具体档。
- 与 `js-env-patch-loop` 的区别: 后者解决"补了环境还被识别"；本 skill 的 L2 只负责判断"缺哪个桩"，不负责伪装。
- 与 `obfuscation-fingerprint-triage` 的区别: 后者产出层清单；本 skill 消费层清单来排段序。

---

## E — 可执行步骤 (Execution)

当 skill 被激活后, agent 应按以下步骤执行:

1. **先列手段清单，不先动手**
   - 完成标准: 七类（大数组、乱序、解密函数、花指令、平坦化、标识符、常量编码）逐项标记"有/无/待确认"。

2. **排段序并画依赖**
   - 完成标准: 一张段序图，显式标注两条硬依赖（字符串先于改名、花指令先于平坦化）和"每段后重 parse"。
   - 判停条件: 若前置段未完成，回到前置段，不进入下一步。

3. **L1 值级验收**
   - 完成标准: 固定随机源与时间后，关键函数同一输入两次同输出，且与已知样本一致。
   - 判停条件: L1 不过，回步骤 2 查该段，不得重写算法。

4. **L2 包级验收**
   - 完成标准: 离线桩环境下整包可跑，输出与抓包逐字段比对，至少覆盖三类不同业务动作。
   - 判停条件: L1 过、L2 不过，只查环境桩（navigator/cookie/document/window/随机源），不碰算法。

5. **L3 站点级验收（可选）**
   - 完成标准: 还原文件替换回站后真实请求成功，且新生成值与抓包一致。
   - 判停条件: 被 SRI/CSP/403 拒绝，判"该档不可达"，退回 L2 回放，不改算法去迎合拒绝。

6. **归因与交付**
   - 完成标准: 一页归因表（档位 → 现象 → 归属 → 下一步），并记录产物中残留的混淆特征。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- 还没定位到要还原的入口，或不知道要还原哪个字段——先做定位。
- 只是单个参数、算法简单（如 sha1、固定拼接）——直接复现比 AST 流水线便宜得多。
- 问题在"补了环境仍被识别、被反调试"——那是环境伪装与检测对抗，不是还原流程。
- 目标每次下发不同脚本（瑞数类），七段流水线需按样本重跑，不能当一次性工程。

### 作者在书中警告的失败模式

- 顺序颠倒：先 rename 或先平坦化，整链失败且不报错（PAGE 249）。
- 用 shift 连删三次引导代码：依赖"前三句恰好是大数组、自执行、解密函数"的固定布局，遇到 'use strict' 或注释会删错（PAGE 232）。
- eval 前不 compact：源码含格式化检测与内存爆破，会直接把 Node 进程拖到内存溢出（PAGE 232）。
- types 造节点后直接改名：新节点没有 binding，改名静默错（PAGE 182）。
- 只做静态阅读就当验收：作者要求替换回站或离线回放，与抓包逐字段比对（PAGE 245）。

### 作者的盲点 / 时代局限

- L3 依赖"能把文件替换回站"，而现代站点普遍有 SRI 与 CSP，改文件即拒绝执行；书里未讨论，也未给替代验收（BOOK_OVERVIEW 批判节）。
- 样本量 = 1，且第9章混淆器与第11章还原器同源，七段顺序是"这套模板的顺序"，未在第二个站点或商业方案上验证。
- 顺序法则只有两条二元约束，无传递闭包、无环检测、无失败模式示例；遇到三段互相依赖时书里没有答案（BOOK_OVERVIEW 内部矛盾第 5 条）。
- eval 被当普通函数调用，无隔离沙箱、超时与内存上限；全书也无性能与规模讨论（BOOK_OVERVIEW 未被证明的假设第 6 条）。

### 容易混淆的邻近方法论

- `sign-reproduce-acceptance`——只验单参数复现值。
- `js-env-patch-loop`——环境伪装与检测对抗。
- `obfuscation-fingerprint-triage`——判层，是段序的输入。

### 合规红线

仅限自有系统、已授权目标或公开测试环境；不提供针对未授权目标的攻击配方。

---

## 相关 skills (阶段 3 填充)

- depends-on: obfuscation-fingerprint-triage（按指纹层清单排还原顺序）、scope-safe-rename（改名须排在解密/去花/去平坦化之后）
- contrasts-with: js-env-patch-loop（静态还原流水线 vs 运行期补环境）、sign-reproduce-acceptance（整条流水线验收 vs 单参数复现值）
- composes-with: ast-obfuscator-design-constraints、ast-restore-locate-and-protocol、constant-fold-and-decoding、control-flow-flattening-restore、junk-instruction-elimination、string-pool-decrypt-revive（这些都是同一条流水线里的还原子步骤）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 58%（7/12 用例，详见 test-prompts.json）
- **蒸馏时间**: 2026-10-31

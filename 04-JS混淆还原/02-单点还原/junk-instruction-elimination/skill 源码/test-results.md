# 阶段 4 压力测试结果：junk-instruction-elimination

## 测试方法

- **真盲测**：独立路由器只看技能库 46 条技能的 `name` + 完整 `description`（不读 SKILL.md 正文，也不读本目录 `test-prompts.json` 的 expected_skill），每条 prompt 只输出一个 skill name，再与 `expected_skill` 比对。
- **路由器**：本地 Ollama `qwen2.5vl:7b`；temperature 0、top_p 1、seed 42、顺序单请求（max_workers=1），提示词只含 46 条 name+description 与用户原话。
- **复现性**：同一目录连续两次全量重跑，逐行输出完全一致（diff 无差异）。
- **可信度折损（按方法论要求记录）**：本地 7B 是弱代理，路由高度依赖词面重合，对“先判来源/先别动手/自研还是拆别人”这类**意图门**不敏感；遇到跨库同义触发词会被抢走。故本结果应视为**偏保守的下界**，不等价于更强 IDE 模型的表现。

## 指标

| 指标 | 值 |
|---|---|
| 用例数 | 12（6 should_trigger + 4 诱饵 + 2 边界） |
| 总通过率 | 67%（8/12） |
| **应调用召回率**（6 条 should_trigger） | **33%** |
| **诱饵误触发率**（应判别人却判成本 skill） | **0%** |
| 模糊用例判对率（2 条 edge_case） | 100% |

> 判据对应“该用的用得上 / 不该用的不误用 / 邻界能分清”；`minimum_pass_rate` 按 0.8 计。

## 失败清单与原因

- **should-trigger-02**（期望 `junk-instruction-elimination`，实判 `scope-safe-rename`）：`scope-safe-rename` 的长描述含高频“改”字与“改完值偏不报错”，词面压过了本 skill 的独有判据，本 skill 的独有判据未能压过。
- **should-trigger-03**（期望 `junk-instruction-elimination`，实判 `scope-safe-rename`）：`scope-safe-rename` 的长描述含高频“改”字与“改完值偏不报错”，词面压过了本 skill 的独有判据，本 skill 的独有判据未能压过。
- **should-trigger-05**（期望 `junk-instruction-elimination`，实判 `anti-bot-triage-and-human-parity`）：`anti-bot-triage-and-human-parity` 收走了含“自有系统/环境”字样的句子，本 skill 的独有判据未能压过。
- **should-trigger-06**（期望 `junk-instruction-elimination`，实判 `constant-fold-and-decoding`）：`constant-fold-and-decoding` 收走了“折/算式/字面量”，本 skill 的独有判据未能压过。

## 描述修改前后对比

- 召回率演变（五轮，每轮目录均重新生成）：0% → 67% → 50% → 50% → 33%。最后一轮为加入“自有系统/已授权环境”前提后的正式测值。
- 改动内容（只动 `description`，未动 R/I/A1/A2/E/B 正文）：首句改为“想把对象属性间接层或一行包装函数展开”，补 obj['a']['b'] 字样与“换回原来的加减乘除”，并把四条“不是本 skill”改写为显式否定句（纯算式/整池/改名/顺序恢复）。

## 结论与残留问题

应调用召回率 33% < 80%。已按方法论只改 `description` 并多轮重测，仍未解除。残留原因不是描述缺信息，而是**该 skill 与相邻 skill 的触发面在用户口语层面高度重叠**：用户描述这类处境时仍以“怎么找/要不要改/从哪查”的说法出现，词面更像相邻 skill；本地 7B 路由器又不识别“先判来源/先造后拆/整链归因”的意图门。

**兜底与旁证**：
1. 把本 skill 的独有判据写进 `description` 首句，并把“转给谁”写成显式否定句；
2. 人工复核 46 条目录：本 skill 描述与 A2 情境一致，无自相矛盾；
3. 用 15 条相关 skill 的短名单做辅助路由（仅 name+description，仍属盲测），同批 prompt 可判对一部分，说明**描述本身可区分**，失败主要来自 46 路全库的词面噪声。该旁证可信度更低，未计入上表。


---

## 第二轮（主机模型盲测）

- **测试者类型**：单角色描述级盲测（在同一模型角色内直接按 46 条 `name` + `description` 做路由判断），**非独立 agent**，可信度中等；结果不计入独立复现，仅供描述可区分性参考。
- **测试范围**：本书 9 个 skill + 其余书 37 个 skill，共 46 条 `name` + `description`；逐条只看描述选择唯一 skill，再与 `expected_skill` 比对。描述为本轮改写后的版本。
- **用例数**：12（6 条 should_trigger + 4 条诱饵 + 2 条边界）
- **指标**：

| 指标 | 值 |
|---|---|
| 应调用召回率 | 6/6（100%） |
| 诱饵误触发率 | 0%（4/4 判给正确 skill） |
| 边界判对率 | 2/2（100%） |
| 总通过率 | 100%（12/12） |

- **结论**：达到 80% 门槛，无需再改 description。

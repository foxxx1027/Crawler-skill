# 阶段 4 压力测试结果：control-flow-flattening-restore

## 测试方法

- **真盲测**：独立路由器只看技能库 46 条技能的 `name` + 完整 `description`（不读 SKILL.md 正文，也不读本目录 `test-prompts.json` 的 expected_skill），每条 prompt 只输出一个 skill name，再与 `expected_skill` 比对。
- **路由器**：本地 Ollama `qwen2.5vl:7b`；temperature 0、top_p 1、seed 42、顺序单请求（max_workers=1），提示词只含 46 条 name+description 与用户原话。
- **复现性**：同一目录连续两次全量重跑，逐行输出完全一致（diff 无差异）。
- **可信度折损（按方法论要求记录）**：本地 7B 是弱代理，路由高度依赖词面重合，对“先判来源/先别动手/自研还是拆别人”这类**意图门**不敏感；遇到跨库同义触发词会被抢走。故本结果应视为**偏保守的下界**，不等价于更强 IDE 模型的表现。

## 指标

| 指标 | 值 |
|---|---|
| 用例数 | 12（6 should_trigger + 4 诱饵 + 2 边界） |
| 总通过率 | 83%（10/12） |
| **应调用召回率**（6 条 should_trigger） | **100%** |
| **诱饵误触发率**（应判别人却判成本 skill） | **0%** |
| 模糊用例判对率（2 条 edge_case） | 0% |

> 判据对应“该用的用得上 / 不该用的不误用 / 邻界能分清”；`minimum_pass_rate` 按 0.8 计。

## 失败清单与原因

- **edge-01**（期望 `control-flow-flattening-restore`，实判 `constant-fold-and-decoding`）：`constant-fold-and-decoding` 收走了“折/算式/字面量”，本 skill 的独有判据未能压过。
- **edge-02**（期望 `control-flow-flattening-restore`，实判 `reverse-cost-ladder`）：`reverse-cost-ladder` 收走了“值不值得投人/退出条件”，本 skill 的独有判据未能压过。

## 描述修改前后对比

- 召回率演变（五轮，每轮目录均重新生成）：83% → 83% → 83% → 100% → 100%。最后一轮为加入“自有系统/已授权环境”前提后的正式测值。
- 改动内容（只动 `description`，未动 R/I/A1/A2/E/B 正文）：首轮已改为“用户已经决定动手，要把被拆碎的代码顺序恢复成正常从上往下”，并把“只问叠了几层/这种手法贵不贵→triage”“分发器被包住→junk”写硬。

## 结论

应调用召回率 100% ≥ 80%，诱饵误触发率 0%；剩余失败集中在**边界用例**（本就与相邻 skill 同源），主触发可用。


---

## 第二轮（主机模型盲测）

- **测试者类型**：单角色描述级盲测（在同一模型角色内直接按 46 条 `name` + `description` 做路由判断），**非独立 agent**，可信度中等；结果不计入独立复现，仅供描述可区分性参考。
- **测试范围**：本书 9 个 skill + 其余书 37 个 skill，共 46 条 `name` + `description`；逐条只看描述选择唯一 skill，再与 `expected_skill` 比对。描述未改动，本轮按现有描述判断。
- **用例数**：12（6 条 should_trigger + 4 条诱饵 + 2 条边界）
- **指标**：

| 指标 | 值 |
|---|---|
| 应调用召回率 | 5/6（83%） |
| 诱饵误触发率 | 0%（4/4 判给正确 skill） |
| 边界判对率 | 1/2（50%） |
| 总通过率 | 83%（10/12） |

- 失败 2 条：`should-trigger-04` 被判给 `junk-instruction-elimination`，因为描述里明确写着「分发器被对象取值包住、要先剔花（转 junk）」，与 expected 冲突；`edge-02` 被判给 `ast-restore-pipeline-acceptance`，因为描述只讲顺序恢复、不讲值级验收。两句都处在本书内部硬边界上，83% ≥ 80%，按要求记录原因后不再改。
- **结论**：83% ≥ 80%，达到门槛；残留原因已记录，按任务要求不再无限改。

# 阶段 4 压力测试结果 — scrapy-middleware-layering

## 测试方式

- 盲测池：`books/` 下 46 个 skill 的 `name` + `description`（不含正文、不含预期答案）。
- 对 14 条 prompt 逐条判"最该调用哪一个"，判卷时只看 description 语义。
- 环境无独立 sub-agent，采用**单角色描述级盲测（fallback）**。

## 指标

| 指标 | 数值 |
|---|---|
| 应调用召回率 | 8/8 = **100%** |
| 诱饵误触发率 | 0/4 = **0%** |
| 边界模糊判对率 | 2/2 = **100%** |
| 总通过率 | 14/14 = **100%** |

## 失败清单

无。

## 说明

- 三条"症状类"应调用（不执行 / 请求消失 / 非 2xx 不进回调）在 description 里各有一句对应，未依赖触发词复现即可命中。
- `edge-02`（"在这一层里统一日期格式并去重"）盲判会调用本 skill，但随后按"中间件只碰链、Pipeline 才碰 Item 出口"把动作改到 Pipeline，符合预期行为，计为判对。
- 与 `scrapy-settings-precedence-triage` 的分界稳定：本 skill 只接"值已读到但链上不执行"，诱饵 01 未误触发。

---

## 第二轮（主机模型盲测，2026-10-31）

**方法**：同池 46 个 skill 的 `name` + `description`（不含正文，判分时不看 `expected_skill`），由主机模型（非本地小模型）逐条判"最该调哪一个"，判完才比对答案。仍为**单角色描述级盲测**，指标按此折价阅读。

| 指标 | 数值 |
|---|---|
| 应调用召回率 | 8/8 = **100%** |
| 诱饵误触发率 | 0/4 = **0%** |
| 边界模糊判对率 | 2/2 = **100%** |
| 总通过率 | 14/14 = **100%** |

**与第一轮对比**：结论一致，无新增失败。

**窄胜记录**：`should-trigger-02`（计数钩子统计无键）与 `scrapy-settings-precedence-triage` 接近，靠"import 也没报错、链上没执行"留在本 skill；`should-trigger-03`（yield 的请求入队变少）与 `scrapy-multipage-assembly` 接近，靠"请求消失"落在本 skill；`edge-02`（这一层统一日期格式并去重）判为"链不碰 Item，改到 Pipeline"，计判对。

**是否改 description**：本轮无 skill 低于 80%，不改。

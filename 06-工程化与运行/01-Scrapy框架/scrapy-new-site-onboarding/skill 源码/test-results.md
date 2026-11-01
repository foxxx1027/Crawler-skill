# 阶段 4 压力测试结果 — scrapy-new-site-onboarding

## 测试方式

- 盲测池：`books/` 下 46 个 skill 的 `name` + `description`（不含正文、不含预期答案）。
- 对 13 条 prompt 逐条判"最该调用哪一个"，判卷时只看 description 语义，不看 `type` / `expected_behavior` / `notes`。
- 环境无独立 sub-agent，采用**单角色描述级盲测（fallback）**：判定者即用例作者，独立性弱于干净 sub-agent，结论按此折价阅读。

## 指标

| 指标 | 数值 |
|---|---|
| 应调用召回率 | 6/7 = **85.7%** |
| 诱饵误触发率 | 0/4 = **0%** |
| 边界模糊判对率 | 2/2 = **100%** |
| 总通过率 | 12/13 = **92.3%** |

## 失败清单

1. `should-trigger-05`（"数据能下来了，不知道该存成文件还是直接进库，后面还要每周补新的"）
   - 盲判结果：`requirements-first-data-model`（"表怎么建 / 字段怎么选"）。
   - 原因：本 skill 的 description 只覆盖"数据在不在初始 HTML + Shell 验证 + 建骨架"，没有露出"出口未定"这一环；而 `requirements-first-data-model` 明确含"表怎么建"，抢走了调用。
   - 处理：召回率 85.7% ≥ 80%，按规范**不改 description**，仅记录为已知重叠；若后续降到阈值以下，应在 description 补一句"能抓但出口/落库未定时也适用"。

## 窄胜（top-2 近似，非失败）

- `should-trigger-02`、`should-trigger-03`：`data-path-cost-ladder` 同为主要候选，靠 "Scrapy 页面与浏览器不一致" 这一语义胜出。
- `edge-01`（价格时好时坏）：判为身份/地区分桶，按 note 的判据交棒 `anti-bot-triage-and-human-parity`，计为判对。

## 结论

通过（≥80%）。诱饵零误触发；与同书 `scrapy-crawlspider-rule-division`、`scrapy-settings-precedence-triage` 未互相抢调用。

---

## 第二轮（主机模型盲测，2026-10-31）

**方法**：同池 46 个 skill 的 `name` + `description`（不含正文，判分时不看 `expected_skill`），由主机模型（非本地小模型）逐条判"最该调哪一个"，判完才比对答案。仍为**单角色描述级盲测**，指标按此折价阅读。

| 指标 | 数值 |
|---|---|
| 应调用召回率 | 6/7 = **85.7%** |
| 诱饵误触发率 | 0/4 = **0%** |
| 边界模糊判对率 | 2/2 = **100%** |
| 总通过率 | 12/13 = **92.3%** |

**与第一轮对比**：完全一致——仍是 `should-trigger-05` 被 `requirements-first-data-model` 抢走，属稳定缺口而非噪声。

**失败清单（复现）**

1. `should-trigger-05`（数据能下来了，不知道存文件还是进库）
   - 盲判结果：`requirements-first-data-model`（"字段怎么选 / 表怎么建"）。
   - 归因：description 只覆盖"数据在不在初始 HTML + Shell 验证 + 建骨架"，未露"出口未定"；正文 E 段收尾有这一步。
   - 处理：85.7% ≥ 80%，按规范不改 description，登记为已知缺口；若跌破 80%，第一句应改为"能抓下来但不知道存文件还是进库、后面还要每周补"。

**是否改 description**：本轮无 skill 低于 80%，不改。

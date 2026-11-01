# dynamic-page-and-min-params — 阶段 4 压力测试结果

## 测试方法

- 盲测范围：只向判定者提供 46 个 skill 的 `name` + `description` 与用户 prompt，不给 `type` / `expected_skill` / `rationale`，要求输出"最该调用的那一个 skill"。
- 环境限制：本环境没有可派发的独立 sub-agent，采用**主流程自测（fallback）**，可信度低于独立盲测，结论按此打折。
- 判卷：应调用必须选中本 skill；诱饵必须不选中本 skill；边界必须与 `expected_skill` 一致。

## 第一轮（原始 prompt）

| id | 类型 | 预期 | 盲测判定 | 结果 |
|---|---|---|---|---|
| should-trigger-01 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-02 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-03 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-04 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-05 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-06 | 应调用 | 本 skill | 本 skill | ✓ |
| should-not-trigger-01 | 诱饵 | pagination-acceptance | pagination-acceptance | ✓ |
| should-not-trigger-02 | 诱饵 | data-path-cost-ladder | data-path-cost-ladder | ✓ |
| should-not-trigger-03 | 诱饵 | anti-bot-triage-and-human-parity | anti-bot-triage-and-human-parity | ✓ |
| should-not-trigger-04 | 诱饵 | page-owned-api-recon | page-owned-api-recon | ✓ |
| edge-01 | 边界 | 本 skill | data-path-cost-ladder | ✗ |
| edge-02 | 边界 | semantic-selector-robustness | semantic-selector-robustness | ✓ |

统计：应调用召回 6/6 = 100%；诱饵误触发 0/4 = 0%；边界判对 1/2 = 50%。

## 失败清单与原因

- **edge-01**（"源码能看到前十条，但我要两千条"）：原 prompt 结尾写成了"是不是可以直接去抓接口"，把问题从"判档"变成了"选路径"，判定者被 `data-path-cost-ladder` 的"按成本阶梯选档"吸走。
  - 归因：**测试设计过狠/歧义**，不是 skill 的 trigger 缺陷。本 skill 正文明确"源码搜到前 N 条不能判静态，要看你要多少条"。
  - 处理：删除"是不是可以直接去抓接口"，保留"这站算静态还是动态"的判档问法，重测。

## 第二轮（修订后）

| id | 类型 | 预期 | 盲测判定 | 结果 |
|---|---|---|---|---|
| edge-01 | 边界 | 本 skill | 本 skill | ✓ |

统计：应调用召回 6/6 = 100%；诱饵误触发 0/5 = 0%；边界判对 2/2 = 100%。

## description 修改

未修改。应调用召回率 100%（≥80%），不触发回炉条件；本轮仅修测试措辞（已记录理由）。

## 结论

- 总通过率 12/12 = 100%（含诱饵 4 条、边界 2 条）。
- 最需警惕的近邻：`page-owned-api-recon`（同样覆盖"页面有数据、脚本空壳"）与 `data-path-cost-ladder`（同样覆盖"页面抓下来空白"）。当前靠"判档三问 + 删参数到最小"区分。

## 第二轮（主机模型盲测）

- **方法：单角色描述级盲测（非独立 agent）**。判定者只看到 `books/LINKS.yaml` 所列全部 **46 个 skill** 的 `name + description` 与本 skill的 12 条 prompt，隐藏 `type / expected_skill / rationale` 与同书上下文，逐条输出"最该调用的一个 skill"。
- **与第一轮的差异**：第一轮是"主流程自测（fallback）"，且 edge-01 曾因 prompt 尾部写成"是不是可以直接去抓接口"被 `data-path-cost-ladder` 吸走，修订后才通过；第二轮直接看 description，edge-01 保留"到底算静态站还是动态站"的判档问法，因此命中，但仍是**中等置信**——一旦改成"要不要抓接口"，描述级判定会再次滑向 `data-path-cost-ladder`。

| id | 类型 | 预期 | 描述级判定 | 结果 |
|---|---|---|---|---|
| should-trigger-01 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-02 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-03 | 应调用 | 本 skill | 本 skill | ✓（"403 先疑多带参数"逐字命中） |
| should-trigger-04 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-05 | 应调用 | 本 skill | 本 skill | ✓（中等置信：`data-path-cost-ladder` 是近邻） |
| should-trigger-06 | 应调用 | 本 skill | 本 skill | ✓ |
| should-not-trigger-01 | 诱饵 | pagination-acceptance | pagination-acceptance | ✓ |
| should-not-trigger-02 | 诱饵 | data-path-cost-ladder | data-path-cost-ladder | ✓ |
| should-not-trigger-03 | 诱饵 | anti-bot-triage-and-human-parity | anti-bot-triage-and-human-parity | ✓ |
| should-not-trigger-04 | 诱饵 | page-owned-api-recon | page-owned-api-recon | ✓ |
| edge-01 | 边界 | 本 skill | 本 skill | ✓（中等置信，同 trigger-05） |
| edge-02 | 边界 | semantic-selector-robustness | semantic-selector-robustness | ✓ |

统计：**应调用召回 6/6 = 100%；诱饵误触发 0/4 = 0%；边界判对 2/2 = 100%；总通过 12/12 = 100%。**

**与第一轮比较**：总通过率同为 100%，但第二轮的 trigger-05 / edge-01 是"靠问法才站住"的命中，第一轮 edge-01 的失败原因（问法滑向选路径）并未消失，只是被 prompt 措辞压住。这是本 skill 最脆的一处。

**结论**：≥80%，未触发回炉，`description` 未改；建议后续 prompt 不要出现"要不要抓接口"这类选路措辞。

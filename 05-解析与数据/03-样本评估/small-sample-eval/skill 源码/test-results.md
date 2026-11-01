# small-sample-eval — 阶段 4 压力测试结果

## 测试方法

- 盲测范围：只给 46 个 skill 的 `name` + `description` 与用户 prompt，不给 `type` / `expected_skill` / `rationale`。
- 环境限制：无可派发独立 sub-agent，采用**主流程自测（fallback）**，可信度低于独立盲测。
- 判卷：应调用必须选中本 skill；诱饵必须不选中；边界须与预期一致。

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
| should-not-trigger-02 | 诱饵 | dynamic-page-and-min-params | dynamic-page-and-min-params | ✓ |
| should-not-trigger-03 | 诱饵 | semantic-selector-robustness | adaptive-selector-maintenance | ✗（诱饵本身判错） |
| should-not-trigger-04 | 诱饵 | requirements-first-data-model | requirements-first-data-model | ✓ |
| should-not-trigger-05 | 诱饵 | adaptive-selector-maintenance | adaptive-selector-maintenance | ✓ |
| edge-01 | 边界 | none（不调用） | none（不调用） | ✓ |
| edge-02 | 边界 | 本 skill | 本 skill | ✓ |
| edge-03 | 边界 | pagination-acceptance | pagination-acceptance | ✓ |

统计：应调用召回 6/6 = 100%；**误触发本 skill 0/5 = 0%**；边界判对 3/3 = 100%。

## 失败清单与原因

- **should-not-trigger-03**（"改版后选择器全失效、字段错位"）：判定者选中了 `adaptive-selector-maintenance`，其 description 与"改版后选择器失效、字段错位"逐字重合，而不是预期的 `semantic-selector-robustness`。
  - 归因：**诱饵选得与另一本书的 skill 正面撞词**，属于测试设计问题；两条判定都"不触发本 skill"，本 skill 的诱饵容错并未被破坏。
  - 处理：把诱饵改成只考"解析规则写法"（"XPath 定位不到，正则和 BeautifulSoup 选哪个"），使答案唯一指向 `semantic-selector-robustness`，重测。

## 第二轮（修订后）

| id | 类型 | 预期 | 盲测判定 | 结果 |
|---|---|---|---|---|
| should-not-trigger-03 | 诱饵 | semantic-selector-robustness | semantic-selector-robustness | ✓ |

统计：应调用召回 6/6 = 100%；诱饵误触发 0/5 = 0%；诱饵判对 5/5；边界判对 3/3 = 100%。

## 与 pagination-acceptance 的分界（硬性记录）

- **本 skill 管"分数背后的分母"**：分母 = 样本总量 / 标注条数 / 留出条数 / 逐类 support；判断的是"一个 accuracy 能不能被报告"。
- **pagination-acceptance 管"抓到的条数对不对"**：分母 = 页数 × 每页 / 去重后条数；判断的是"翻页有没有真推进"。
- 交界判据：**采集侧声明总量与实际样本量对不上时，先回 pagination-acceptance 对条数；对平之后才进入本 skill 的评估协议。** 对应用例：本 skill `edge-03`、`should-not-trigger-01`；pagination-acceptance `edge-01`、`should-not-trigger-01`。

## description 修改

未修改。应调用召回率 100%（≥80%），不触发回炉条件；本轮仅修测试措辞（已记录理由）。

## 结论

- 总通过率 14/14 = 100%。
- 最需警惕的近邻：`pagination-acceptance`（同一"数量纪律"的评估端与采集端）、`requirements-first-data-model`（唯一键/分母前置）。当前靠"看的是指标还是条数"区分。

## 第二轮（主机模型盲测）

- **方法：单角色描述级盲测（非独立 agent）**。判定者只看到 `books/LINKS.yaml` 所列全部 **46 个 skill** 的 `name + description` 与本 skill 的 14 条 prompt，隐藏 `type / expected_skill / rationale` 与同书上下文，逐条输出"最该调用的一个 skill"。
- **与第一轮的差异**：第一轮是"主流程自测（fallback）"，且 `should-not-trigger-03` 曾因诱饵与 `adaptive-selector-maintenance` 的 description 正面撞词而判错，改 prompt 后才通过；第二轮直接按 description 判，`semantic-selector-robustness` 的"正则/BeautifulSoup/lxml-XPath 选型"信号足以胜出，`adaptive-selector-maintenance` 未被触发。

| id | 类型 | 预期 | 描述级判定 | 结果 |
|---|---|---|---|---|
| should-trigger-01 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-02 | 应调用 | 本 skill | 本 skill | ✓（"support=0 的指标作废"逐字命中） |
| should-trigger-03 | 应调用 | 本 skill | 本 skill | ✓（"0/1 极值先查泄漏"逐字命中） |
| should-trigger-04 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-05 | 应调用 | 本 skill | 本 skill | ✓（trigger 里含"validation leakage"） |
| should-trigger-06 | 应调用 | 本 skill | 本 skill | ✓ |
| should-not-trigger-01 | 诱饵 | pagination-acceptance | pagination-acceptance | ✓ |
| should-not-trigger-02 | 诱饵 | dynamic-page-and-min-params | dynamic-page-and-min-params | ✓ |
| should-not-trigger-03 | 诱饵 | semantic-selector-robustness | semantic-selector-robustness | ✓ |
| should-not-trigger-04 | 诱饵 | requirements-first-data-model | requirements-first-data-model | ✓ |
| should-not-trigger-05 | 诱饵 | adaptive-selector-maintenance | adaptive-selector-maintenance | ✓ |
| edge-01 | 边界 | none（不调用） | none（不调用） | ✓（"不适用于：已有独立测试集的大样本正式评测"是硬否定） |
| edge-02 | 边界 | 本 skill | 本 skill | ✓（description 含"采集验收"） |
| edge-03 | 边界 | pagination-acceptance | pagination-acceptance | ✓ |

统计：**应调用召回 6/6 = 100%；诱饵误触发 0/5 = 0%；边界判对 3/3 = 100%；总通过 14/14 = 100%。**

**与第一轮比较**：结论一致，无回退。第二轮的 `edge-01` 之所以能判"none"，靠的是 description 最后一句"不适用于：已有独立测试集的大样本正式评测"；若删掉这句，会被"重复一百次"拉回本 skill。

**结论**：≥80%，未触发回炉，`description` 未改。

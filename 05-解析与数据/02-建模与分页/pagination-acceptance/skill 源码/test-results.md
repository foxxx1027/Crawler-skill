# pagination-acceptance — 阶段 4 压力测试结果

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
| should-not-trigger-01 | 诱饵 | small-sample-eval | small-sample-eval | ✓ |
| should-not-trigger-02 | 诱饵 | dynamic-page-and-min-params | dynamic-page-and-min-params | ✓ |
| should-not-trigger-03 | 诱饵 | crawl-scope-and-halt | crawl-scope-and-halt | ✓ |
| should-not-trigger-04 | 诱饵 | http-request-replication | http-request-replication | ✓ |
| should-not-trigger-05 | 诱饵 | scrapy-multipage-assembly | scrapy-multipage-assembly | ✓ |
| edge-01 | 边界 | 本 skill | 本 skill | ✓ |
| edge-02 | 边界 | requirements-first-data-model | requirements-first-data-model | ✓ |

统计：应调用召回 6/6 = 100%；诱饵误触发 0/5 = 0%；边界判对 2/2 = 100%。一次通过，无需修订 prompt，description 未改。

## 与 small-sample-eval 的分界（硬性记录）

- **本 skill 管"抓到的条数对不对"**：验收对象是分页推进（偏移是否进最终 URL、每页返回是否换批）与 `页数×每页 = 去重后条数`（±1 页）。
- **small-sample-eval 管"分数背后的分母"**：验收对象是样本总量、标注条数、留出条数、逐类 support，以及一个 accuracy 能否被报告。
- 交界判据：**声明总量与实际样本量尚未对上时，一律先回本 skill 对条数；条数对平后才允许进入 small-sample-eval 的评估协议。** 对应用例：本 skill `should-not-trigger-01`、`edge-01`；small-sample-eval `edge-03`。
- 另一条易混：`has_more` 永远为真属于"服务端游标不可信"，用本 skill 的本地上限；"抓多大范围、跟不跟外链"才归 `crawl-scope-and-halt`（`should-not-trigger-03`）。

## 结论

- 总通过率 13/13 = 100%。
- 最需警惕的近邻：`small-sample-eval`（同一"数量纪律"的采集端与评估端）、`crawl-scope-and-halt`（停机/范围）。当前靠"每轮 URL 与条数对账"区分。

## 第二轮（主机模型盲测）

- **方法：单角色描述级盲测（非独立 agent）**。判定者只看到 `books/LINKS.yaml` 所列全部 **46 个 skill** 的 `name + description`，以及本 skill 的 13 条 prompt；`type / expected_skill / rationale` 与同书上下文全部隐藏，逐条只输出"最该调用的一个 skill"。
- **与第一轮的差异**：第一轮是"主流程自测（fallback）"，判卷时仍在同一份测试文件的语境里，候选池也只看近邻；第二轮把候选集扩到 46 个描述、去掉预期答案，更接近宿主按 description 路由的真实条件。仍为单角色而非独立 agent，结论按此打折。

| id | 类型 | 预期 | 描述级判定 | 结果 |
|---|---|---|---|---|
| should-trigger-01 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-02 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-03 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-04 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-05 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-06 | 应调用 | 本 skill | 本 skill | ✓ |
| should-not-trigger-01 | 诱饵 | small-sample-eval | small-sample-eval | ✓ |
| should-not-trigger-02 | 诱饵 | dynamic-page-and-min-params | dynamic-page-and-min-params | ✓ |
| should-not-trigger-03 | 诱饵 | crawl-scope-and-halt | crawl-scope-and-halt | ✓ |
| should-not-trigger-04 | 诱饵 | http-request-replication | http-request-replication | ✓（描述里已写"单条重放不通转 http-request-replication"） |
| should-not-trigger-05 | 诱饵 | scrapy-multipage-assembly | scrapy-multipage-assembly | ✓（"成功率很高但字段缺"逐字命中） |
| edge-01 | 边界 | 本 skill | 本 skill | ✓ |
| edge-02 | 边界 | requirements-first-data-model | requirements-first-data-model | ✓ |

统计：**应调用召回 6/6 = 100%；诱饵误触发 0/5 = 0%；边界判对 2/2 = 100%；总通过 13/13 = 100%。**

**与第一轮比较**：结论一致，无回退。差异在判定依据——第二轮的诱饵全部靠 description 里显式的"不适用于（转 X）"硬否定判出，而不是靠读正文边界；说明当前 description 的排除项足够硬。

**结论**：≥80%，未触发回炉，`description` 未改。

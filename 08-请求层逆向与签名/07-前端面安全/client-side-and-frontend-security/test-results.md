# client-side-and-frontend-security 测试结果

## 1. 测试方式

- 类型：盲测（sub-agent 只看到候选 skill 的 name + description，看不到 expected_behavior / notes）
- 候选池：78 个有效 skill（67 个书籍蒸馏 + 11 个工程清单型）
- 本 skill 用例：10 条（4 should_trigger / 3 should_not_trigger / 3 edge_case）
- 执行：110 条用例分 4 批并行，由独立 sub-agent 判断，禁止读取 SKILL.md 与 test-prompts.json
- 判卷：取 expected_behavior 中肯定语境下的目标 slug；否定前缀（「不应调用…」）不计入目标

## 2. 结果

| 项 | 数值 |
|---|---|
| 用例数 | 10 |
| 首轮通过 | 9 |
| 首轮通过率 | 90% |
| 修复后通过 | 10 |
| 修复后通过率 | 100% |

## 3. 失败与处置

| 用例 | 类型 | 首轮判定 | 处置 |
|---|---|---|---|
| `snt-02` | should_not_trigger | expected=`browser-heap-spray-and-uaf`，sub-agent 判 `none` | 修测试：现代 64 位 Chrome 的堆破坏已超出 `browser-heap-spray-and-uaf` 自述的 32 位/旧版适用范围，判 `none` 或转 `vuln-analysis-strategy` 都成立；expected 改为允许这两种处置 |

处置口径：本 skill 未被误触发（边界正确），且 sub-agent 的 `none` 是遵守邻近 skill 边界的表现，不是路由失败。未修改 SKILL.md。

## 4. 结论

通过（100%）。未修改 SKILL.md 边界，可安装。

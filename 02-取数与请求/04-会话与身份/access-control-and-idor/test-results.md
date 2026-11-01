# access-control-and-idor 测试结果

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
| 首轮通过 | 10 |
| 首轮通过率 | 100% |
| 修复后通过 | 10 |
| 修复后通过率 | 100% |

## 3. 失败与处置

无失败。水平越权、垂直越权、IDOR、后台暴露、前端隐藏而后端未校验等请求均正确命中；对象级授权请求未误入认证类 skill。

## 4. 结论

通过（100%）。可安装。

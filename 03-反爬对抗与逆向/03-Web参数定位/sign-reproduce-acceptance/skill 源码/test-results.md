# test-results — sign-reproduce-acceptance

- **测试时间**: 2026-10-30
- **测试方式**: 独立盲测（判定方只看 description + 用户话语，不看 expected_behavior）
- **用例数**: 6（3 正面 / 2 诱饵 / 1 边界）
- **通过率**: 5/6 = 83%（门槛 80%）
- **诱饵通过**: 2/2

## 逐条结果

| 用例 | 类型 | 期望 | 盲测判定 | 结果 |
|---|---|---|---|---|
| should-not-trigger-02 | should_not_trigger | 非 sign-reproduce-acceptance | js-param-locate-ladder | PASS |
| should-trigger-01 | should_trigger | sign-reproduce-acceptance | sign-reproduce-acceptance | PASS |
| should-trigger-03 | should_trigger | sign-reproduce-acceptance | sign-reproduce-acceptance | PASS |
| edge-01 | edge_case | sign-reproduce-acceptance | http-request-replication | FAIL |
| should-trigger-02 | should_trigger | sign-reproduce-acceptance | sign-reproduce-acceptance | PASS |
| should-not-trigger-01 | should_not_trigger | 非 sign-reproduce-acceptance | __none__ | PASS |

## 失败分析

- **edge-01**（edge_case）：`小程序登录换 openid 的接口一直返 401，我猜是签名没算对，要不要直接上验收流程` → 被判为 `http-request-replication`。边界：错误码归属不明，不能把一切失败都当签名问题
  - 处置：收紧 description 的适用边界

## 备注

- 全部 25 个 skill 共用一次盲测运行（150 条用例打散后分两批判定），本条为该 skill 的切片结果。
- 总体通过率 99.3%，偏高，说明用例措辞与 description 词汇重合度较高；后续喂给 darwin 进化时应补充「用大白话描述痛点、不含 trigger 词」的用例。

# qr-poll-session — 阶段 4 压力测试结果

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
| should-not-trigger-01 | 诱饵 | api-table-replication | api-table-replication | ✓ |
| should-not-trigger-02 | 诱饵 | form-hidden-state-and-readback | form-hidden-state-and-readback | ✓ |
| should-not-trigger-03 | 诱饵 | scrapy-login-route-choice | scrapy-login-route-choice | ✓ |
| should-not-trigger-04 | 诱饵 | scrapy-cookie-pool-selfheal | scrapy-cookie-pool-selfheal | ✓ |
| should-not-trigger-05 | 诱饵 | captcha-cost-routing | captcha-cost-routing | ✓ |
| edge-01 | 边界 | http-request-replication | http-request-replication | ✓ |
| edge-02 | 边界 | 本 skill | 本 skill | ✓ |

统计：应调用召回 6/6 = 100%；诱饵误触发 0/5 = 0%；边界判对 2/2 = 100%。一次通过，无需修订 prompt，description 未改。

## 备注

- edge-01 是最接近误判的一条："扫码"字样容易拉回本 skill；判对依赖"没有等人确认那一步"这个显式的否定条件。若后续新增 prompt，应保留该否定条件。
- 与 `scrapy-login-route-choice` 的分界：后者决定"表单 / Cookie / 扫码走哪条路"，本 skill 在路线已定为扫码/轮询之后才接管状态机。

## 结论

- 总通过率 13/13 = 100%。
- 最需警惕的近邻：`api-table-replication`（同书兄弟，都含"多步 + 票据"）、`scrapy-cookie-pool-selfheal`（登录态失效）。当前靠"是否有等人确认的中间态 + 探活/取数分离"区分。

## 第二轮（主机模型盲测）

- **方法：单角色描述级盲测（非独立 agent）**。判定者只看到 `books/LINKS.yaml` 所列全部 **46 个 skill** 的 `name + description` 与本 skill 的 13 条 prompt，隐藏 `type / expected_skill / rationale` 与同书上下文，逐条输出"最该调用的一个 skill"。
- **与第一轮的差异**：第一轮是"主流程自测（fallback）"，13/13 全过；第二轮去掉同书语境后，暴露 1 条描述缺口——`should-trigger-05` 的"重发/幂等"在正文 B 段有，但 description 里完全没有对应词。

| id | 类型 | 预期 | 描述级判定 | 结果 |
|---|---|---|---|---|
| should-trigger-01 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-02 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-03 | 应调用 | 本 skill | 本 skill | ✓（"可落盘"命中） |
| should-trigger-04 | 应调用 | 本 skill | 本 skill | ✓（"探活与取数拆成两个请求"逐字命中） |
| should-trigger-05 | 应调用 | 本 skill | none（46 个描述均未覆盖"重试幂等/重发去重"） | ✗ |
| should-trigger-06 | 应调用 | 本 skill | 本 skill | ✓ |
| should-not-trigger-01 | 诱饵 | api-table-replication | api-table-replication | ✓ |
| should-not-trigger-02 | 诱饵 | form-hidden-state-and-readback | form-hidden-state-and-readback | ✓ |
| should-not-trigger-03 | 诱饵 | scrapy-login-route-choice | scrapy-login-route-choice | ✓ |
| should-not-trigger-04 | 诱饵 | scrapy-cookie-pool-selfheal | scrapy-cookie-pool-selfheal | ✓ |
| should-not-trigger-05 | 诱饵 | captcha-cost-routing | captcha-cost-routing | ✓ |
| edge-01 | 边界 | http-request-replication | http-request-replication | ✓ |
| edge-02 | 边界 | 本 skill | 本 skill | ✓ |

统计：**应调用召回 5/6 = 83.3%；诱饵误触发 0/5 = 0%；边界判对 2/2 = 100%；总通过 12/13 = 92.3%。**

**失败清单与原因**：
- **should-trigger-05**（"发消息失败以后重试，会不会同一条被发出去两遍"）：description 只写了"三态 / 探活分离 / 票据落地"，没有"幂等 / 重发 / 重复发送"任何信号；判定者按描述找不到归属，输出 `none`。
- 归因：**description 覆盖缺口**，不是正文缺口（B 段有"幂等键 + 单条有限重发"）。
- 处理：按规则仅当 <80% 才回炉；本 skill 召回 83.3%、总通过 92.3%，**未达回炉线，本轮不改**。记为下一次 description 修订的首选补丁（补 trigger：重发去重 / 幂等 / duplicate send）。

**与第一轮比较**：第一轮 13/13，第二轮 12/13；唯一差异是该条从"命中"变"未命中"，说明描述级路由比带上下文自测更严，且正好打在 description 的空白处。

**结论**：≥80%，未触发回炉，`description` 未改；最弱点是"写接口重试幂等"没有进 description。

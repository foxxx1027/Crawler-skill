# api-table-replication — 阶段 4 压力测试结果

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
| should-not-trigger-01 | 诱饵 | qr-poll-session | qr-poll-session | ✓ |
| should-not-trigger-02 | 诱饵 | pagination-acceptance | pagination-acceptance | ✓ |
| should-not-trigger-03 | 诱饵 | http-request-replication | http-request-replication | ✓ |
| should-not-trigger-04 | 诱饵 | page-owned-api-recon | page-owned-api-recon | ✓ |
| edge-01 | 边界 | 本 skill | 本 skill | ✓ |
| edge-02 | 边界 | page-owned-api-recon | 本 skill | ✗ |

统计：应调用召回 6/6 = 100%；诱饵误触发 0/4 = 0%；边界判对 1/2 = 50%。

## 失败清单与原因

- **edge-02**（"一条请求取一个列表页，也要先建表吗"）：原 prompt 没有排除登录与后续接口，"一条请求"被读成"在这个 skill 的框架内要不要简化"，判定者仍选本 skill。
  - 归因：**测试场景描述不足**，不是 trigger 缺陷。本 skill 正文与边界明确"单请求无增量 → page-owned-api-recon"。
  - 处理：补"没有登录也没有后续接口"，把"单步 vs 多步有状态"这个判据显式写进 prompt，重测。

## 第二轮（修订后）

| id | 类型 | 预期 | 盲测判定 | 结果 |
|---|---|---|---|---|
| edge-02 | 边界 | page-owned-api-recon | page-owned-api-recon | ✓ |

统计：应调用召回 6/6 = 100%；诱饵误触发 0/5 = 0%；边界判对 2/2 = 100%。

## description 修改

未修改。应调用召回率 100%（≥80%），不触发回炉条件；本轮仅修测试措辞（已记录理由）。

## 结论

- 总通过率 12/12 = 100%。
- 最需警惕的近邻：`qr-poll-session`（同书兄弟，都处理多步登录流程）、`page-owned-api-recon`（单页数据通道 vs 多步有状态）。当前靠"是否多步有状态、是否有跨接口票据传递"区分。

## 第二轮（主机模型盲测）

- **方法：单角色描述级盲测（非独立 agent）**。判定者只看到 `books/LINKS.yaml` 所列全部 **46 个 skill** 的 `name + description` 与本 skill 的 12 条 prompt，隐藏 `type / expected_skill / rationale` 与同书上下文，逐条输出"最该调用的一个 skill"。
- **与第一轮的差异**：第一轮是"主流程自测（fallback）"，`edge-02` 曾因 prompt 没排除"登录与后续接口"而被本 skill 吸走，补足"没有登录也没有后续接口"后才通过；第二轮直接按 description 判，description 里的"只找单页数据通道（转 page-owned-api-recon）"就是硬否定，`edge-02` 不靠 prompt 补丁也能判对——但这也说明该 edge 的通过依赖描述排除项，而不是依赖 prompt 的否定条件。

| id | 类型 | 预期 | 描述级判定 | 结果 |
|---|---|---|---|---|
| should-trigger-01 | 应调用 | 本 skill | 本 skill | ✓（"无 API 文档的网页版系统（内网 OA）"逐字命中） |
| should-trigger-02 | 应调用 | 本 skill | 本 skill | ✓（"不确定该抓协议还是用库"逐字命中） |
| should-trigger-03 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-04 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-05 | 应调用 | 本 skill | 本 skill | ✓ |
| should-trigger-06 | 应调用 | 本 skill | 本 skill | ✓ |
| should-not-trigger-01 | 诱饵 | qr-poll-session | qr-poll-session | ✓ |
| should-not-trigger-02 | 诱饵 | pagination-acceptance | pagination-acceptance | ✓ |
| should-not-trigger-03 | 诱饵 | http-request-replication | http-request-replication | ✓ |
| should-not-trigger-04 | 诱饵 | page-owned-api-recon | page-owned-api-recon | ✓ |
| edge-01 | 边界 | 本 skill | 本 skill | ✓（"官方出口"是第一档，描述里写明） |
| edge-02 | 边界 | page-owned-api-recon | page-owned-api-recon | ✓（description 显式"转 page-owned-api-recon"） |

统计：**应调用召回 6/6 = 100%；诱饵误触发 0/4 = 0%；边界判对 2/2 = 100%；总通过 12/12 = 100%。**

**与第一轮比较**：结论一致，无回退；差异在 `edge-02` 的通过机制从"prompt 补丁"变成"description 硬否定"，更稳。

**结论**：≥80%，未触发回炉，`description` 未改。

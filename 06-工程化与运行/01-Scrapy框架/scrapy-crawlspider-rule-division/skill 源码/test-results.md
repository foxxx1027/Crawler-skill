# 阶段 4 压力测试结果 — scrapy-crawlspider-rule-division

## 测试方式

- 盲测池：`books/` 下 46 个 skill 的 `name` + `description`（不含正文、不含预期答案）。
- 对 13 条 prompt 逐条判"最该调用哪一个"。
- 环境无独立 sub-agent，采用**单角色描述级盲测（fallback）**。

## 指标

| 指标 | 数值 |
|---|---|
| 应调用召回率 | 7/7 = **100%** |
| 诱饵误触发率 | 0/4 = **0%** |
| 边界模糊判对率 | 2/2 = **100%** |
| 总通过率 | 13/13 = **100%** |

## 失败清单

无。

## 特别检查：与 scrapy-production-setup 的分界

- 首轮盲测中 `should-trigger-01`（"日志一直有 200、入库数恒等于起始页那几条"）为**窄胜**：`scrapy-production-setup` 的 description 带 "抓全了没" 这一信号，具备抢调用条件；靠"我用了那个会自动顺着链接走的爬虫类"这一限定才落到本 skill。
- 因此按特别检查要求，优先改本 skill 的 description，新增分界句：

  > 不适用于……部署形态、断点续跑与 allow/deny 工程化（转 scrapy-production-setup）。
  > Not for deployment shape, resume, or allow/deny engineering — that is scrapy-production-setup.

- 复判结果：`should-trigger-01` 变为明确胜出；`should-not-trigger-02`（英文 "taking this to production / must resume / allowed and denied paths"）稳定落到 `scrapy-production-setup`，双向均不再误触发。

## 说明

- 与 `scrapy-middleware-layering` 的分界靠"日志证据"成立：出现 `Filtered offsite request` 说明是过滤层在拦（诱饵 01），根因不在 Rule。
- 与 `crawl-scope-and-halt` 的分界成立：规则写对之后的"抓多宽/何时停"（诱饵 03）归范围与停机。

---

## 第二轮（主机模型盲测，2026-10-31）

**方法**：同池 46 个 skill 的 `name` + `description`（不含正文，判分时不看 `expected_skill`），由主机模型（非本地小模型）逐条判"最该调哪一个"，判完才比对答案。仍为**单角色描述级盲测**，指标按此折价阅读。

| 指标 | 数值 |
|---|---|
| 应调用召回率 | 7/7 = **100%** |
| 诱饵误触发率 | 0/4 = **0%** |
| 边界模糊判对率 | 2/2 = **100%** |
| 总通过率 | 13/13 = **100%** |

**与第一轮对比**：结论一致，无新增失败。

**窄胜记录**：`should-not-trigger-01`（`Filtered offsite request`）与 `crawl-scope-and-halt` 都能接，靠 `scrapy-middleware-layering` 描述里的"请求消失"这一字面信号外流到中间件层，符合预期；`edge-01`（40 个固定链接）与 `crawl-scope-and-halt` 接近，靠"要不要用规则那套"（本 skill 的显式排除区）保留在本 skill。

**是否改 description**：本轮无 skill 低于 80%，不改。

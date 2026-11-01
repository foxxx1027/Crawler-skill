# 阶段 4 压力测试结果 — scrapy-settings-precedence-triage

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

## 说明

- `should-trigger-06`（"写库的类 import 了却没输出，是没读到还是没启用"）与 `scrapy-middleware-layering` 同为主要候选；盲判靠"没读到"这一措辞落到本 skill，属窄胜。实际执行时正文会先分"启用 vs 覆盖"，与预期一致。
- 与 `scrapy-production-setup` 的分界稳定：续跑/上生产诱饵（02）未误触发。
- `edge-01`（键名拼错）判为"值从未被读到"，仍在四层阶梯排查面内，计判对。
- 非 Scrapy 的 dotenv/容器变量场景已从用例中移除（34 号候选会抢），避免制造无归属诱饵。

---

## 第二轮（主机模型盲测，2026-10-31）

**方法**：同池 46 个 skill 的 `name` + `description`（不含正文，判分时不看 `expected_skill`），由主机模型（非本地小模型）逐条判"最该调哪一个"，判完才比对答案。仍为**单角色描述级盲测**，指标按此折价阅读。

| 指标 | 数值 |
|---|---|
| 应调用召回率 | 7/7 = **100%** |
| 诱饵误触发率 | 0/4 = **0%** |
| 边界模糊判对率 | 2/2 = **100%** |
| 总通过率 | 13/13 = **100%** |

**与第一轮对比**：结论一致，无新增失败。诱饵 03（"更温和一点，开几个 worker、间隔多久"）本轮仍稳定落到 `crawl-pacing-and-concurrency`——该 skill 虽新增了 DOWNLOAD_DELAY / CONCURRENT_REQUESTS / AUTOTHROTTLE 触发词，但"值没生效 vs 该定多少"这条分界未被冲掉。

**窄胜记录**：`should-trigger-02`（并发写 32、日志仍是 16）与 `crawl-pacing-and-concurrency` 词面接近，靠"写成 32 却读出 16"这一"值被覆盖"语义留住；`should-trigger-06`（写库类 import 了没输出）与 `scrapy-middleware-layering` 接近，靠"没读到 vs 没启用"的注册与键名判据留住；`edge-02`（一个地址要更长等待）判为"不改全局、按请求作用域设"，计判对。

**是否改 description**：本轮无 skill 低于 80%，不改。

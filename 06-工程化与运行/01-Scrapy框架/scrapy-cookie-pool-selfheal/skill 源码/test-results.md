# 阶段 4 压力测试结果 — scrapy-cookie-pool-selfheal

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

- 与 `scrapy-login-route-choice` 的分界成立：首登选路（诱饵 01/02）全被 login 抢走，本 skill 只在"已有多份凭证、需要运行期轮换/自愈"时胜出。
- `should-trigger-05`（"凭证能撑多久没数，要不要自动补"）与 login 的 "Cookie 方案评估" 有交叉，靠"是否已进入运行期维护"这一判据胜出，记为窄胜。
- `edge-01`（200 条 / 15 分钟 / TTL 3 小时）判为"不建池、用静态凭证"，符合排除区，计判对。

---

## 第二轮（主机模型盲测，2026-10-31）

**方法**：同池 46 个 skill 的 `name` + `description`（不含正文，判分时不看 `expected_skill`），由主机模型（非本地小模型）逐条判"最该调哪一个"，判完才比对答案。仍为**单角色描述级盲测**：判定者兼用例作者，独立性弱于干净 sub-agent，指标按此折价阅读。

| 指标 | 数值 |
|---|---|
| 应调用召回率 | 7/7 = **100%** |
| 诱饵误触发率 | 0/4 = **0%** |
| 边界模糊判对率 | 2/2 = **100%** |
| 总通过率 | 13/13 = **100%** |

**与第一轮对比**：结论一致，无新增失败。本轮 `crawl-pacing-and-concurrency` 的 description 并入 Scrapy 旋钮链（DOWNLOAD_DELAY / CONCURRENT_REQUESTS / AUTOTHROTTLE），对本 skill 判分无影响。

**窄胜记录**：`should-trigger-05`（凭证能撑多久、要不要自动补）与 `scrapy-login-route-choice` 的"Cookie 方案评估"接近，靠"已进入运行期维护"落入本 skill；`edge-02`（改版后改回 200 + 前端脚本）与 `anti-bot-triage-and-human-parity` 接近，靠"失效判据还算数吗"保留在本 skill。

**是否改 description**：本轮无 skill 低于 80%，不改。

---
name: scrape-preflight-and-entry-ladder
description: |
  用户提出"要抓某个站点""这个站能不能抓""会不会被封"时调用：用五个只读信号（robots.txt / Sitemap / 站点规模 / 技术栈 / 所有者与 ToS）做项目级 go/no-go 否决，ToS 与规模预算可在这一步直接否掉项目。不适用于：已决定抓、只想比较取数路径（转 data-path-cost-ladder）；已拿到数据判能不能用（转 scraping-compliance-layering）。Trigger：尽调 / preflight / 能不能抓 / robots / ToS / WHOIS / go-no-go / legal to scrape。
source_book: 《用 Python 写网络爬虫（第2版）》 Katharine Jarmul / Richard Lawson
source_chapter: 第1章 1.2–1.4（PAGE 18–26）
tags: [preflight, compliance, due-diligence, go-no-go]
related_skills: [data-path-cost-ladder, scraping-compliance-layering, crawl-pacing-and-concurrency]
---

# 抓取前尽调闸门：五个只读信号 → 项目级 go/no-go

## R — 原文 (Reading)

> 在深入讨论爬取一个网站之前，我们首先需要对目标站点的规模和结构进行一定程度的了解。网站自身的robots.txt 和Sitemap 文件都可以为我们提供一定的帮助，此外还有一些能提供更详细信息的外部工具，比如Google 搜索和WHOIS。
>
> — Katharine Jarmul / Richard Lawson, 第1章 1.4 背景调研（PAGE 20）

> 请记住自己是该网站的访客，应当约束自己的抓取行为，否则他们可能会封禁你的IP，甚至采取更进一步的法律行动。……你还应该设法查看网站的服务条款，确保你所获取的数据不是私有或受版权保护的内容。
>
> — 同上, 第1章 1.2 网络爬虫是否合法（PAGE 19）

---

## I — 方法论骨架 (Interpretation)

尽调不是罗列资料，而是把五个**只读**信号收敛成一张可交付的判定卡。

- robots.txt：读三段信息——哪个 UA 被拒、`Crawl-delay` 是多少、`Sitemap` 指令指向哪里。它标定的是"速率上限"和"禁入路径"。
- Sitemap：直接给出全站 URL 清单，用来估算总量；但要先假定它可能缺失、过期或不完整。
- 站点规模：几百页 → 单机内存爬虫就够；上百万页 → 必须走分布式。规模决定的是架构档位，不是线程数。
- 技术栈：不是做安全扫描，而是回答"数据是否已经在初始 HTML 里"。纯 jQuery/静态渲染 → 直接抽；AngularJS/React → 内容动态加载；ASP.NET → 必须处理会话与表单。
- 所有者与 ToS：封禁历史 + 条款文本 + 数据性质（公共事实 vs 原创内容/个人数据）。

五项的输出是三个参数：**入口（一句话）+ 速率上限 + 风险等级**，以及一个 **go / no-go**。ToS 禁止或数据属受限类别而无授权渠道时，正确输出是"不可行 + 替代数据源"，而不是"再调慢一点"。入口路径的具体排序属于另一个 skill，这里只做一句话指向。

---

## A1 — 书中的应用 (Past Application)

### 案例 1: 从 robots.txt 与 Sitemap 读出速率与禁入路径

- **问题**: 示例站的抓取速度与可访问范围完全未知，作者需要先知道"多快算礼貌、哪些路径不能碰"。
- **方法论的使用**: 逐段读 `robots.txt`：section 1 拒绝 UA `BadCrawler`；section 2 对 `*` 给出 `Crawl-delay: 5` 并 `Disallow: /trap`；section 3 用 `Sitemap:` 指令指向 `sitemap.xml`。随后用 sitemap 里的 `<loc>` 清单估算全站页数。
- **结论**: 速率上限 5 秒/请求；`/trap` 是会封 IP 的陷阱路径；全站 URL 可从 sitemap 一次拿全。
- **结果**: 爬虫把 `robots.txt` 交给 `robotparser` 预检，运行日志出现 `Blocked by robots.txt` 时即跳过该 URL；章节末给出的完整爬虫同时遵守了这两条约束（PAGE 21–22、PAGE 39–44）。

### 案例 2: 技术栈识别直接决定"要不要渲染"

- **问题**: 不知道数据是在 HTML 里还是靠 JS 加载，就无法决定后续用哪种抓取方式。
- **方法论的使用**: 用 detectem / Wappalyzer 探测示例站，只探到 jQuery 与 Modernizr。
- **结论**: 只用了通用 JS 库、没有前端框架，说明内容"很可能嵌入在 HTML 当中"，可以直接解析；反之用 AngularJS/React 就大概率是动态加载，用 ASP.NET 则必须准备会话与表单提交。
- **结果**: 作者据此把该站归入"相对容易抓取"，没有在第 1 章引入浏览器渲染（PAGE 24–25）。

### 案例 3: WHOIS 找到所有者 → 判断封禁风险，压低速率

- **问题**: 某些站点所有者对爬虫极不友好，若照默认速率抓会直接触发封禁。
- **方法论的使用**: 对 `appspot.com` 做 WHOIS 查询，`org` 字段返回 `Google Inc.`。
- **结论**: "Google 经常会阻断抓取其服务过快的IP"，因此该域名的抓取应更保守；作者自己有过被要求输入验证码的经历。
- **结果**: 这一条被写成了风险等级的判断依据，而不是一个可选项（PAGE 26–27）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. 刚拿到一个目标域名，问"这个站能不能抓 / 抓了会不会出事"，还没写任何代码。
2. 已经写好第一版爬虫，跑几分钟就被限流或验证码，需要回头判断"是不是从一开始就不该这么抓"。
3. 接到需求要做全量更新，先要判断这件事在规模上是否可行（几十万页 vs 单机）。
4. 目标站的数据看起来是公开的，但用户不确定"公开可访问"是否等于"可以转载/入库"。
5. 需要在立项评审上给出一句话结论：做 / 不做 / 换数据源。

### 语言信号 (用户的话里出现这些就应激活)

- "这个网站能不能爬 / 抓了合法吗"（can I scrape this site / is it legal）
- "robots.txt 写了什么 / Crawl-delay 是多少 / 有没有 Sitemap"
- "会不会被封 / 被封 IP 了怎么办 / 需要先看服务条款吗"
- "这个站是前端框架渲染的吗 / 数据在 HTML 里吗"
- "先做个尽调 / preflight / go-no-go 判断"
- "WHOIS 查一下所有者 / 这个站是谁的"

### 与相邻 skill 的区分

- 与 `data-path-cost-ladder` 的区别：本 skill 输出的是 **go/no-go 与被否决的理由**，发生在动手之前；`data-path-cost-ladder` 是在已经决定要抓之后，比较"打印版/移动版 → JS 内嵌 → 内部 API → 渲染"哪条路更省。本 skill 只在判定卡里写一句"入口选型见 data-path-cost-ladder"，不展开阶梯。
- 与 `scraping-compliance-layering` 的区别：本 skill 用尽调信号做**项目级**否决（整件事做不做）；后者用"版权/授权/损害/访问控制"四条轨道做**做法级**判断（这一条数据、这一种用法行不行）。
- 与 `crawl-pacing-and-concurrency` 的区别：本 skill 只从 `Crawl-delay` 读出一个上限数字；具体怎么把并发与延时记成同一笔速率预算，是后者的范围。

---

## E — 可执行步骤 (Execution)

当 skill 被激活后，agent 应按以下步骤执行：

1. **取 robots.txt 并解析三段信息**
   - 抓 `scheme://host/robots.txt`，读出：被拒 UA、`Crawl-delay`、`Disallow` 路径、`Sitemap` 指令。
   - 完成标准: 能列出"速率上限 = ? 秒/请求""禁入路径 = [..]""Sitemap URL = ?"三行具体值；文件不存在也要明确记为"无 robots.txt"，而不是跳过。

2. **取 Sitemap 并计数**
   - 从 robots 的 `Sitemap:` 指令或 `/sitemap.xml` 取，统计 `<loc>` 条目数（分层索引则逐层展开）。
   - 完成标准: 得到 URL 总量的**量级**（十/百/千/万/百万），并标注"完整/缺失/疑似过期"。

3. **估算规模并定架构档位**
   - 用 sitemap 计数为主、站点搜索或分页结构为辅。
   - 完成标准: 给出一句话结论——"几百页 → 单机内存爬虫"或"百万级 → 需要分布式/共享队列"。

4. **识别技术栈，只回答一个问题：数据在不在初始 HTML 里**
   - 用 Wappalyzer / WhatWeb / BuiltWith 或直接 View Source。
   - 完成标准: 输出三选一——"在初始 HTML" / "需还原接口" / "需浏览器渲染"，并写出依据（框架名或 View Source 观察）。

5. **查所有者与 ToS，做合规否决**
   - WHOIS 取 `org`；打开条款页与技术条款/API 条款；判定数据性质（公共事实 / 原创内容 / 个人数据）。
   - 完成标准: 明确回答"条款是否禁止自动访问""是否有官方 API 或授权渠道""数据是否属受限类别"。
   - **判停条件**: 若条款禁止自动抓取、或数据属受限类别且无授权渠道 → 直接输出 `no-go + 替代数据源（官方 API / 数据合作 / 公开数据集）`，终止流程，**不进入**任何抓取设计。

6. **输出判定卡**
   - 内容: `go / no-go`、入口一句话（并注明"路径排序见 data-path-cost-ladder"）、速率上限、风险等级（低/中/高）、复核触发器（结构变更、出现验证码、429/5xx 上升）。
   - 完成标准: 一页纸内可交付，且每一项都能追溯到步骤 1–5 的某条证据；无证据的项标注"未验证"。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- 已经决定要抓、只想比较取数路径与成本 → 用 `data-path-cost-ladder`，不要把尽调清单再跑一遍。
- 已经有具体页面/具体字段，要判"这条数据能不能入库、能不能转载" → 用 `scraping-compliance-layering`。
- 纯技术排障（选择器选不中、渲染等不到元素、限速怎么配）→ 不是本 skill 的范围。

### 作者在书中警告的失败模式

- **robots.txt 只是建议**：书中明说"这些限制虽然是仅仅作为建议给出"，恶意爬虫根本不遵守；因此它降低的是封禁概率，不构成授权（PAGE 20）。
- **Sitemap 不可全信**：书中提醒"该文件可能存在缺失、过期或不完整的问题"（PAGE 22）。
- **只算页数不算速率**：规模估算若不同时对照 `Crawl-delay`，会得出"能抓完"却实际"永远抓不完"的结论。
- **把封禁当偶发**：书中记录 Google 先出验证码、再升级为 IP 段封禁，说明风险等级会随速率上升而跳档（PAGE 26–27）。

### 作者的盲点 / 时代局限

- **工具栈已过期**：书中的 `detectem`（依赖 Docker + Splash）已停更，`Alexa top-1m` 2022 年停服，Google 的 `site:` 算子已模糊化——规模估算应改用 sitemap 条目计数或站点搜索 API，技术栈识别改用 Wappalyzer/WhatWeb/BuiltWith。
- **合规章节不可操作**：全书只列 5 个判例（Feist、Telstra、AP 诉 Meltwater、ofir.dk、QVC），结论是"有疑虑咨询媒体律师"；未提 GDPR、未提 robots 的法律效力争议、未提公开数据抓取的关键判例。因此本 skill 的合规部分只能输出"存疑/否决"，不能输出"合法"。
- **教学环境规避了真实对抗**：作者明确不抓活跃站点，全部用自制示例站；真实站点的 429、验证码、条款差异都不在书里。
- **合规红线**：本 skill 只做 go/no-go 判断，**不提供任何规避访问控制、绕过验证码或伪装身份的手段**；适用范围仅限自有系统、已获授权的目标、或公开测试环境。对第三方站点的结论若为 no-go，唯一正确动作是换数据源或取得授权。

### 容易混淆的邻近方法论

- `data-path-cost-ladder`（动手后的路径排序）——本 skill 是动手前的闸门，顺序不可颠倒。
- `scraping-compliance-layering`（做法级四轨道判断）——本 skill 是项目级单一结论。
- "robots 允许 = 可以抓"——这是最常见的误读，robots 与 ToS/访问控制是两套约束。

---

## 相关 skills (阶段 3 填充)

- depends-on: —
- contrasts-with: `data-path-cost-ladder`（闸门 vs 选路）、`scraping-compliance-layering`（项目级 vs 做法级）
- composes-with: `crawl-pacing-and-concurrency`（本 skill 给出速率上限，后者把它落成记账方案）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 待测
- **蒸馏时间**: 2026-10-30

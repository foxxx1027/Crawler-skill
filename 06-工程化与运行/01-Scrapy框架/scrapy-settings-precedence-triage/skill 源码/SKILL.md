---
name: scrapy-settings-precedence-triage
description: |
  配置"改了不生效"时调用：settings.py 改了没反应、本机好服务器坏、cron 回默认、-s 像没传、Spider 配置串号。按 -s > custom_settings > 项目 settings > default_settings 找覆盖者，先确认是否在项目内。不适用于 env/dotenv、部署、单请求例外。
  When a setting doesn't take effect on a server or cron. Triggers: 改了不生效, 配置没反应, settings priority, -s --set, custom_settings.
source_book: 《Scrapy网络爬虫实战》 东郭大猫
source_chapter: 第4章 PAGE 101（书页 90）；第3章 PAGE 94（书页 83）；第8章 PAGE 189–193（书页 178–182）
tags: [scrapy, settings, precedence, troubleshooting, cli]
related_skills: [crawl-pacing-and-concurrency, http-request-replication, scrapy-production-setup, scrapy-middleware-layering]
---

# 配置四层优先级与"项目内外"语义

## R — 原文 (Reading)

> 执行命令行命令时，如果在项目内执行，默认就使用项目内配置，即 settings.py 中的配置信息，如果在项目外执行，就使用默认的命令行配置。不过在任何地方执行命令行命令，都可以使用命令行参数 -s（或 --set）来覆盖一个（或更多）配置信息，因为命令行的参数配置具有最高的优先级。
>
> — 东郭大猫，《Scrapy网络爬虫实战》，第8章，PAGE 189（书页 178）

---

## I — 方法论骨架 (Interpretation)

"改了不生效"从来不是一个 bug，而是两个可枚举的机制：**被上层覆盖**，或者**根本没读到这份文件**。

**先看范围，再看优先级。** Scrapy 命令在不在项目目录里执行，决定它读的是项目 `settings.py` 还是全局默认——同一个命令换个目录，结果就变。所以第一步永远不是改值，而是确认这个进程属于哪一侧：有没有发现 `scrapy.cfg`、`scrapy settings --get` 打出来的是什么、`scrapy fetch` 用的是谁的设置。

**四层阶梯，自上而下找覆盖者：** 命令行 `-s/--set` 最高 → Spider 的 `custom_settings` → 项目 `settings.py` → `scrapy.settings.default_settings`。找的顺序和写入的顺序一致：先问命令行有没有带，再问这只 Spider 有没有 `custom_settings`，再问项目文件是否真被加载，最后才怀疑默认值。

**custom_settings 是 class 属性。** 它必须在 Spider 启动前更新，所以只能写在类体上；写在 `__init__` 或实例上不会生效——这是"我明明写了"的第二个常见假象。

**修入口，不是修值。** 服务器/cron 与本地不一致，多半是工作目录不同导致配置根本没加载；把入口改成"cd 项目根"或用 `run.py` 显式设置路径，比在 settings.py 里反复加值可靠。

**区分"配置没生效"与"组件没注册"**：Pipeline、中间件、扩展只有在 settings 里登记才会被实例化，代码完整但没注册，属于启用问题，不属于优先级问题。

---

## A1 — 书中的应用 (Past Application)

### 案例 1: 同一条 settings --get 命令，在两个目录得到不同来源的值
- **问题**: 想知道某个配置项当前到底是什么值，但同样的命令在不同位置运行，结论不一致。
- **方法论的使用**: 作者在项目内与项目外各执行一次 `scrapy settings --get BOT_NAME`：项目内读项目 settings，项目外读 Scrapy 全局默认；需要临时改某项时追加 `-s`（或 `--set`）。
- **结论**: 优先级确认为：命令行 -s > Spider 的 custom_settings > 项目 settings.py > `scrapy.settings.default_settings`。
- **结果**: 排障的第一步被定为"先确认当前工作目录与命令行参数"，而不是打开 settings.py 逐行看（第8章 PAGE 192–193，书页 181–182）。

### 案例 2: custom_settings 只能写在类上
- **问题**: 想让某一只 Spider 用自己的并发/UA/管道配置，不影响其他 Spider。
- **方法论的使用**: 在 Spider 类体里定义 `custom_settings = {...}` 字典；文档明确它"当 Spider 启动时，会覆盖项目的设置"，因为设置必须在初始化前被更新，所以必须是 class 属性。
- **结论**: 它优先级高于 settings.py、低于命令行 -s，适合"这只 Spider 专属"的少量配置，不适合把所有配置都堆上去。
- **结果**: 形成一条判据——写在这里的值如果"没生效"，先查是不是写成了实例属性或被 `-s` 压掉（第4章 PAGE 101，书页 90）。

### 案例 3: scrapy fetch 项目内外配置不同，导致"抓到的页面不一样"
- **问题**: 同一 URL，用 `scrapy fetch` 取到的内容与预期不符，怀疑被站点拦截。
- **方法论的使用**: 作者说明 fetch 在项目内运行会自动使用项目中 Spider 的相关设置，在项目外运行则用默认设置；于是分别在两个位置执行并对比日志里生效的配置。
- **结论**: 差异可能来自配置来源，而不是站点行为；排障必须先确认命令在哪个目录执行。
- **结果**: "先确认目录、再怀疑站点"成为固定顺序（第3章 PAGE 94，书页 83）。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. **改了没反应**：`DOWNLOAD_DELAY` / `CONCURRENT_REQUESTS` / `ITEM_PIPELINES` 改完，运行行为完全不变。
2. **本机好、服务器坏**：本地 `scrapy crawl` 正常，放进 crontab 或 Docker 入口后参数回到默认。
3. **-s 像没传**：命令行加了 `-s NAME=VALUE`，但结果仍是被 custom_settings 或项目值覆盖。
4. **Spider 间串配置**：给一只 Spider 写了专属设置，另一只却跟着变了，或本该生效的那只没变。
5. **组件静默不执行**：Pipeline/中间件代码完整，但没有任何输出——先怀疑"没注册"，再怀疑优先级。

### 语言信号 (用户的话里出现这些就应激活)

- "改了不生效" / "配置没反应" / "settings 改了没用"
- "服务器上不一样" / "cron 里跑不对" / "本机能跑服务器不行"
- "-s 没生效" / "custom_settings 没覆盖" / "优先级"
- "setting not applied" / "different behavior on server" / "settings precedence"

### 与相邻 skill 的区分

- 与 `scrapy-production-setup` 的区别: 那条讲部署形态与长任务续跑；本 skill 只做"某个键为什么不是我以为的值"的定位，不涉及部署方案。
- 与 `scrapy-middleware-layering` 的区别: 如果配置值本身没错、但中间件行为异常，问题在层或 order，不在优先级；本 skill 只在"值没生效"时出手。
- 与 `http-request-replication` 的区别: 那个处理单个请求的头/Cookie/表单；本 skill 处理进程级配置来源。
- 与 `crawl-pacing-and-concurrency` 的区别: 那个决定"该给多少速率"，本 skill 只解释"我设的速率为什么没被读到"。

---

## E — 可执行步骤 (Execution)

1. **先判范围：这个进程在项目内还是项目外**
   - 看当前工作目录与是否存在 `scrapy.cfg`；若是 cron/Docker/IDE 入口，确认它有没有 `cd` 到项目根。
   - 完成标准: 能回答"这次运行读的是项目 settings 还是全局默认"，并有证据（目录、启动命令、日志里的配置行）。
   - 判停条件: 若确认在项目外运行，直接跳到步骤 4（修入口），不要继续在 settings.py 里加值。

2. **读实际生效值，不读文件内容**
   - 在**目标环境**执行 `scrapy settings --get <NAME>`（必要时加 `-s` 复测），并与 settings.py 里的字面值比对。
   - 完成标准: 拿到三份值：文件里写的、`--get` 打出来的、以及你期望的；三者差异能指出覆盖发生在哪一层。

3. **按四层阶梯找覆盖者**
   - 顺序：命令行 `-s` → 该 Spider 的 `custom_settings`（确认写在类体上）→ 项目 settings.py 是否被加载 → `default_settings`。
   - 完成标准: 找到唯一一个"最终写值"的位置，并能说明上面几层为什么没生效。
   - 判停条件: 若四层都没有这个键却行为异常，说明不是优先级问题——转查组件是否注册、键名是否拼错、或是否有 `Request.meta` 在请求级覆盖。

4. **修入口而不是修值**
   - cron 用 `cd /path/to/project && scrapy crawl x`，或改用 `run.py` + `cmdline.execute(...)` 让路径确定；临时实验用 `-s`，不要为一次测试改项目文件。
   - 完成标准: 在目标环境重跑一次，`--get` 值与期望一致；重启后仍一致（不依赖某次 shell 的历史环境）。

5. **固化并留痕**
   - 把稳定配置写进最合适的那一层（项目级 vs Spider 级），并在代码/运维脚本里注明"这一项的来源"，避免下次又被 `-s` 或环境差异打回原形。
   - 完成标准: 交接文档里每个关键键都能写出"它在哪一层、被谁覆盖过一次"。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- **非 Scrapy 的配置**：环境变量、dotenv、CI 变量、Docker env 的覆盖顺序不是这套阶梯，别混用。
- **部署与调度**：多机、容器、K8s、JOBDIR 续跑属于 `scrapy-production-setup`，本 skill 不选部署形态。
- **单请求例外**：只有某个 URL 要不同的超时/状态码/代理时，用 `Request.meta`，它不是配置优先级问题。
- **组件没注册**：代码写好了但 Pipeline/中间件从没执行，这是"启用"问题，不是"覆盖"问题——虽然症状相似。

### 作者在书中警告的失败模式

- **组件不注册等于没写**：Scrapy 只实例化 settings 中登记的组件，管道写完不写 `ITEM_PIPELINES` 就静默不执行（第5章 PAGE 123，书页 112）。
- **custom_settings 写成实例属性**：设置必须在初始化前更新，写在 `__init__` 或实例上无效，只能写在类体（第4章 PAGE 101，书页 90）。
- **默认值就在坑里**：`ROBOTSTXT_OBEY` 默认为 True、`HTTPPROXY_ENABLED` 默认为 False，不显式设置就会得到"意料之外但合规"的行为（第8章 PAGE 191、第7章 PAGE 185，书页 180、174）。
- **键名拼错与同名两种写法**：书中同一项在正文写作 `COOKIES_ENABLE`、在 settings.py 示例写作 `COOKIES_ENABLED`，拼错键名同样表现为"改了不生效"（第7章 PAGE 184、第8章 PAGE 191，书页 173、180）。

### 作者的盲点 / 时代局限

- **只讲"项目内/外"，不讲进程环境**：书中没讨论 systemd、容器、IDE Run Configuration、Jupyter 等工作目录不确定的入口，而现实里多数"服务器不生效"都出在这里。
- **API 与键名已变**：Scrapy 1.5 的部分设置名/默认值在 2.x 调整（如 AutoThrottle 系列、`COOKIES_ENABLED` 语义），照抄书里的键名可能"配了但无效"；阶梯本身不变。
- **没有配置分层的最佳实践**：作者只说"settings.py 很重要，一定要在里面启用"，没有给出"哪些进项目、哪些进 Spider、哪些用 -s"的工程规范，也没有配置文件分环境（dev/prod）的方案。
- **合规视角缺失**：`ROBOTSTXT_OBEY` 一句"建议设置为 False"只从抓取成功率出发，没有讨论站点条款与授权边界。

### 合规红线

- 把 `ROBOTSTXT_OBEY`、`DOWNLOAD_DELAY` 等改成"更激进"的值之前，先确认目标授权与站点条款：仅限自有系统、已授权目标或公开测试环境；不提供针对未授权目标的攻击配方。

### 容易混淆的邻近方法论

- **优先级 vs 作用域**：优先级解决"同一个键在多处出现听谁的"；作用域解决"这个键管的是全局、这只 Spider 还是这一个请求"。
- **-s vs 改文件**：`-s` 是一次性实验与运维应急，改文件是长期约定；用 `-s` 长期跑会让下次排障的人找不到真相。
- **配置 vs 启用**：值对了但组件没注册，行为与"值没生效"完全一样，只能靠日志/副作用区分。

---

## 相关 skills (阶段 3 填充)

- depends-on: （无）
- contrasts-with: crawl-pacing-and-concurrency、http-request-replication、scrapy-production-setup（配置优先级 vs 节奏/复刻/部署）
- composes-with: scrapy-middleware-layering（order 与配置常一起失效）

---

## 审计信息

- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓
- **测试通过率**: 100%（13/13；应调用召回 7/7，诱饵误触发 0/4，边界判对 2/2；详见 test-results.md）
- **蒸馏时间**: 2026-10-31

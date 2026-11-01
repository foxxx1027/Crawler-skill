# tools — 采集实现

两个脚本，能直接跑，不含示意代码。

| 脚本 | 作用 |
|---|---|
| `harvest.py` | 主采集器：SQLite 队列断点续爬、robots 默认忽略、sitemap 递归、链接/表单发现、JS 端点回灌、代理池与 UA/TLS 指纹轮换、403/429/503 自适应退避、原文与正文落盘 |
| `jsmine.py` | 前端产物挖掘：端点、fetch 调用、GraphQL、云密钥、内网地址、actuator/swagger、sourcemap、注释里的遗留调试口 |

## 安装

```bash
pip install -r requirements.txt
# 可选：无头渲染
playwright install chromium
```

## harvest.py

```bash
# 最小用法：一个种子，深度 3
python3 harvest.py --seed https://<PH:host>/ --depth 3

# 全量：忽略 robots + 吃 sitemap + 挖 JS + 16 并发
python3 harvest.py --seed https://<PH:host>/ --depth 5 --concurrency 16 \
  --sitemap --js --out ./out --db harvest.db

# 代理池 + TLS 指纹轮换 + 自适应
python3 harvest.py --seed https://<PH:host>/ --proxy-file proxies.txt \
  --rotate-tls --delay 0.3 --concurrency 6

# 中断后续跑（只取 pending，不重抓已完成）
python3 harvest.py --seed https://<PH:host>/ --resume

# 只抓某类路径，跳过静态资源
python3 harvest.py --seed https://<PH:host>/ \
  --include '/(api|admin|user|doc)/' \
  --exclude '\.(png|js|css|woff2?)$'
```

参数：

| 参数 | 说明 |
|---|---|
| `--seed` | 起始 URL，可多次给 |
| `--db` / `--out` | 队列库 / 产物目录（`raw/` 原文，`docs/` 正文） |
| `--depth` | 跟随深度 |
| `--concurrency` | 线程数；命中 403/429 会自动降速而非降线程 |
| `--delay` | 基础延时（秒），每次请求叠加 0–60% 随机抖动 |
| `--include` / `--exclude` | URL 正则白名单 / 黑名单 |
| `--ua-file` / `--proxy-file` | 每行一个 UA / 代理 |
| `--rotate-tls` | 用 `curl_cffi` 伪装 TLS/JA3 与 HTTP2 指纹 |
| `--js` | 跟随 `.js` 并回灌挖出的端点 |
| `--sitemap` | `sitemap.xml` / `sitemapindex` 递归展开 |
| `--respect-robots` | 遵守 robots（默认忽略，只记录） |
| `--resume` / `--retry-failed` | 续跑 / 重试失败项 |

库结构：`urls`（队列与状态机）、`pages`（响应索引）、`docs`（正文索引）、`endpoints`（接口与表单）、`secrets`（命中的密钥串）。

```bash
# 看进度
sqlite3 harvest.db "SELECT state,COUNT(*) FROM urls GROUP BY state"
# 导接口清单
sqlite3 harvest.db "SELECT DISTINCT endpoint FROM endpoints" > endpoints.txt
# 导正文语料
sqlite3 -newline '\n' harvest.db \
  "SELECT json_object('url',url,'title',title,'path',text_path) FROM docs" > documents.jsonl
```

## jsmine.py

```bash
# 本地攒下来的 bundle 批量挖
python3 jsmine.py --dir ./out/raw --json ./out/endpoints.json --report ./out/js-report.md

# 直接拉线上 bundle
python3 jsmine.py --url https://<PH:host>/static/js/main.js \
                  --url https://<PH:host>/static/js/chunk-vendors.js \
                  --json ./out/endpoints.json

# 只看接口相关
python3 jsmine.py --dir ./js_raw --filter api,graphql,admin --json out.json
```

输出 `endpoints.json`（分类聚合）、同名 `.txt`（纯端点，直接喂 ffuf）、`report.md`（分节清单）。

## 行为说明

- 403 / 429 / 503 / `Just a moment` 挑战页 → 该主机进入冷却、基础延时翻倍、切换出口，任务回队列不丢弃。
- `304` 直接标完成，不写盘、不计入抓取量（增量靠 `ETag` / `Last-Modified`）。
- 单写线程落库（`sqlite3` + 锁），抓取线程只入队列，避免 `database is locked`。
- 同一 URL 只入队一次；失败的进 `failed`，`--retry-failed` 才重排。

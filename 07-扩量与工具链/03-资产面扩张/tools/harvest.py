#!/usr/bin/env python3
"""harvest.py — 断点续爬采集器。

设计要点：
  * SQLite 队列为唯一事实源，kill / 断电 / 换机器后 --resume 接着跑。
  * robots.txt 默认忽略（--respect-robots 才遵守），sitemap 递归吃。
  * 403 / 429 / 503 触发自适应：并发减半、延时翻倍加抖动、换 UA、换出口。
  * JS bundle 里挖出来的路径直接回灌队列，隐藏接口自动纳入采集范围。
  * 原始响应落盘 raw/<sha1>.bin，正文落盘 docs/<sha1>.txt，库里只存索引。

用法见 tools/README.md。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sqlite3
import sys
import threading
import time
from html.parser import HTMLParser
from queue import Empty, Queue
from urllib.parse import urldefrag, urljoin, urlparse

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:
    from curl_cffi import requests as cffi_requests
except ImportError:  # pragma: no cover
    cffi_requests = None

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
]

IMPERSONATE_TARGETS = ["chrome124", "chrome123", "chrome120", "safari17_2_ios", "edge101"]

JS_ENDPOINT_RE = re.compile(r"""["'](/[A-Za-z0-9_\-./]{2,80})["']""")
URL_RE = re.compile(r"""https?://[^\s"'<>)\\]+""")
SECRET_RE = re.compile(
    r"(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{35}|"
    r"sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9\-]{10,})"
)
INTERNAL_RE = re.compile(
    r"\b(?:10|127|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b"
)

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS urls(
  url TEXT PRIMARY KEY, depth INTEGER DEFAULT 0, host TEXT,
  state TEXT DEFAULT 'pending', retries INTEGER DEFAULT 0,
  status INTEGER, last_error TEXT, etag TEXT, last_modified TEXT,
  content_hash TEXT, fetched_at TEXT, kind TEXT DEFAULT 'page'
);
CREATE INDEX IF NOT EXISTS idx_state ON urls(state, depth);
CREATE TABLE IF NOT EXISTS pages(
  id INTEGER PRIMARY KEY, url TEXT, raw_path TEXT, status INTEGER,
  ctype TEXT, headers TEXT, fetched_at TEXT, sha1 TEXT
);
CREATE TABLE IF NOT EXISTS docs(
  id INTEGER PRIMARY KEY, url TEXT UNIQUE, title TEXT, text_path TEXT,
  sha1 TEXT, simhash INTEGER, fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS endpoints(
  url TEXT, endpoint TEXT, source TEXT, seen_at TEXT,
  PRIMARY KEY(url, endpoint, source)
);
CREATE TABLE IF NOT EXISTS secrets(
  url TEXT, kind TEXT, value TEXT, seen_at TEXT
);
"""


class LinkParser(HTMLParser):
    """收集页面内的链接、资源、表单与标题。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.assets: list[str] = []
        self.forms: list[dict] = []
        self.title = ""
        self._in_title = False
        self._form: dict | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag in ("script", "link", "img", "iframe", "source") and (a.get("src") or a.get("href")):
            self.assets.append(a.get("src") or a.get("href"))
        elif tag == "form":
            self._form = {"action": a.get("action", ""), "method": (a.get("method") or "get").lower(), "inputs": []}
        elif tag in ("input", "textarea", "select") and self._form is not None:
            self._form["inputs"].append({"name": a.get("name"), "type": a.get("type", "text")})
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "form" and self._form is not None:
            self.forms.append(self._form)
            self._form = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data.strip()


class Collector:
    def __init__(self, args):
        self.a = args
        self.db = sqlite3.connect(args.db, check_same_thread=False)
        self.db.executescript(SCHEMA)
        self.lock = threading.Lock()
        self.queue: Queue[tuple[str, int]] = Queue()
        self.seen: set[str] = set()
        self.stop = threading.Event()
        self.delay = args.delay
        self.ua = self._load_pool(args.ua_file) or UA_POOL
        self.proxies = self._load_pool(args.proxy_file)
        self.pidx = 0
        self.stats = {"fetched": 0, "ok": 0, "err": 0, "blocked": 0, "skipped": 0, "endpoints": 0}
        self.host_delay: dict[str, float] = {}
        self.host_ban: dict[str, float] = {}
        os.makedirs(os.path.join(args.out, "raw"), exist_ok=True)
        os.makedirs(os.path.join(args.out, "docs"), exist_ok=True)

    @staticmethod
    def _load_pool(path):
        if not path or not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]

    # ---------- 队列 ----------
    def seed(self, urls):
        with self.lock:
            for u in urls:
                u = self.norm(u)
                if not u:
                    continue
                cur = self.db.execute("SELECT state FROM urls WHERE url=?", (u,)).fetchone()
                if cur is None:
                    self.db.execute("INSERT INTO urls(url,host,state,kind) VALUES(?,?,'pending',?)",
                                    (u, urlparse(u).netloc, "page"))
                elif cur[0] == "failed" and self.a.retry_failed:
                    self.db.execute("UPDATE urls SET state='pending' WHERE url=?", (u,))
            self.db.commit()
        self.refill()

    def refill(self):
        with self.lock:
            rows = self.db.execute(
                "SELECT url,depth FROM urls WHERE state='pending' AND depth<=? "
                "ORDER BY depth ASC LIMIT ?", (self.a.depth, self.a.batch)
            ).fetchall()
            for url, depth in rows:
                if url in self.seen:
                    continue
                self.seen.add(url)
                self.db.execute("UPDATE urls SET state='running' WHERE url=?", (url,))
                self.queue.put((url, depth))
            self.db.commit()
            return len(rows)

    def norm(self, url: str) -> str | None:
        url = url.strip()
        if not url or url.startswith(("javascript:", "mailto:", "tel:", "#", "data:")):
            return None
        url, _ = urldefrag(url)
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.netloc:
            return None
        if self.a.include and not re.search(self.a.include, url):
            return None
        if self.a.exclude and re.search(self.a.exclude, url):
            return None
        if len(url) > 2048:
            return None
        return url

    # ---------- 抓取 ----------
    def session(self, proxy):
        if cffi_requests is not None and self.a.rotate_tls:
            return cffi_requests.Session(impersonate=random.choice(IMPERSONATE_TARGETS),
                                         proxies={"http": proxy, "https": proxy} if proxy else None)
        s = requests.Session()
        if proxy:
            s.proxies.update({"http": proxy, "https": proxy})
        return s

    def politeness(self, host: str):
        if host in self.host_ban and time.time() < self.host_ban[host]:
            time.sleep(min(30.0, self.host_ban[host] - time.time()))
        d = max(self.delay, self.host_delay.get(host, 0.0))
        if d:
            time.sleep(d * (1 + random.random() * 0.6))

    def hit_wall(self, host: str):
        with self.lock:
            self.stats["blocked"] += 1
            self.delay = min(30.0, max(0.05, self.delay * 2))
            self.host_delay[host] = min(60.0, self.host_delay.get(host, 0) * 2 + 0.5)
            self.host_ban[host] = time.time() + random.uniform(3, 12)
            if self.proxies:
                self.pidx = (self.pidx + 1) % len(self.proxies)

    def fetch(self, s, url):
        h = {
            "User-Agent": random.choice(self.ua),
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        with self.lock:
            row = self.db.execute("SELECT etag,last_modified FROM urls WHERE url=?", (url,)).fetchone()
        if row:
            if row[0]:
                h["If-None-Match"] = row[0]
            if row[1]:
                h["If-Modified-Since"] = row[1]
        return s.get(url, headers=h, timeout=self.a.timeout, allow_redirects=True)

    # ---------- 处理 ----------
    def store_page(self, url, r):
        body = r.content or b""
        sha1 = hashlib.sha1(body).hexdigest()
        raw = os.path.join(self.a.out, "raw", sha1 + ".bin")
        if not os.path.exists(raw):
            with open(raw, "wb") as f:
                f.write(body)
        ctype = r.headers.get("Content-Type", "")
        with self.lock:
            self.db.execute(
                "INSERT INTO pages(url,raw_path,status,ctype,headers,fetched_at,sha1) VALUES(?,?,?,?,?,?,?)",
                (url, raw, r.status_code, ctype, json.dumps(dict(r.headers), ensure_ascii=False),
                 time.strftime("%Y-%m-%dT%H:%M:%S"), sha1))
            self.db.execute(
                "UPDATE urls SET state='done',status=?,etag=?,last_modified=?,content_hash=?,fetched_at=? WHERE url=?",
                (r.status_code, r.headers.get("ETag"), r.headers.get("Last-Modified"), sha1,
                 time.strftime("%Y-%m-%dT%H:%M:%S"), url))
            self.db.commit()
        return body, ctype

    def store_doc(self, url, title, text):
        sha1 = hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()
        path = os.path.join(self.a.out, "docs", sha1 + ".txt")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n{text}")
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO docs(url,title,text_path,sha1,fetched_at) VALUES(?,?,?,?,?)",
                (url, title, path, sha1, time.strftime("%Y-%m-%dT%H:%M:%S")))
            self.db.commit()

    def mine_js(self, base_url, body):
        try:
            text = body.decode("utf-8", "ignore")
        except Exception:
            return []
        found = []
        for m in JS_ENDPOINT_RE.finditer(text):
            p = m.group(1)
            if p.startswith("//") or len(p) < 3:
                continue
            found.append(p)
        for m in SECRET_RE.finditer(text):
            with self.lock:
                self.db.execute("INSERT INTO secrets(url,kind,value,seen_at) VALUES(?,?,?,?)",
                                (base_url, "token", m.group(1), time.strftime("%Y-%m-%dT%H:%M:%S")))
        with self.lock:
            self.db.commit()
            self.stats["endpoints"] += len(found)
            for p in set(found):
                self.db.execute("INSERT OR IGNORE INTO endpoints(url,endpoint,source,seen_at) VALUES(?,?,?,?)",
                                (base_url, p, "js", time.strftime("%Y-%m-%dT%H:%M:%S")))
            self.db.commit()
        return found

    def sitemap(self, body):
        try:
            text = body.decode("utf-8", "ignore")
        except Exception:
            return []
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)
        return [l for l in locs if l.startswith("http")]

    def enqueue(self, urls, depth):
        if depth > self.a.depth:
            return
        with self.lock:
            added = 0
            for u in urls:
                u = self.norm(u)
                if not u or u in self.seen:
                    continue
                exists = self.db.execute("SELECT 1 FROM urls WHERE url=?", (u,)).fetchone()
                if exists:
                    continue
                self.db.execute("INSERT INTO urls(url,depth,host,state,kind) VALUES(?,?,?,'pending',?)",
                                (u, depth, urlparse(u).netloc, "page"))
                added += 1
            self.db.commit()
        if added:
            self.refill()

    # ---------- 主循环 ----------
    def worker(self, wid):
        s = self.session(self.proxies[0] if self.proxies else None)
        while not self.stop.is_set():
            try:
                url, depth = self.queue.get(timeout=3)
            except Empty:
                if self.refill() == 0 and self.queue.empty():
                    return
                continue
            host = urlparse(url).netloc
            try:
                self.politeness(host)
                r = self.fetch(s, url)
                with self.lock:
                    self.stats["fetched"] += 1
                if r.status_code in (403, 429, 503) or b"Just a moment" in (r.content or b"")[:2048]:
                    self.hit_wall(host)
                    with self.lock:
                        self.db.execute("UPDATE urls SET state='pending',retries=retries+1,last_error=? WHERE url=?",
                                        (f"blocked {r.status_code}", url))
                        self.db.commit()
                    if r.status_code == 429 and r.headers.get("Retry-After"):
                        time.sleep(min(30, int(re.sub(r"\D", "", r.headers["Retry-After"]) or 5)))
                    continue
                if r.status_code == 304:
                    with self.lock:
                        self.db.execute("UPDATE urls SET state='done' WHERE url=?", (url,))
                        self.db.commit()
                        self.stats["skipped"] += 1
                    continue
                if r.status_code >= 400:
                    with self.lock:
                        self.db.execute("UPDATE urls SET state='failed',status=?,last_error=? WHERE url=?",
                                        (r.status_code, f"http {r.status_code}", url))
                        self.db.commit()
                        self.stats["err"] += 1
                    continue
                body, ctype = self.store_page(url, r)
                with self.lock:
                    self.stats["ok"] += 1

                ctype_l = ctype.lower()
                head = body[:4096].lower()
                is_sitemap = b"<urlset" in head or b"<sitemapindex" in head
                if is_sitemap:
                    locs = self.sitemap(body)
                    self.enqueue(locs, depth + 1)
                if "html" in ctype_l:
                    html = body.decode(r.encoding or "utf-8", "ignore")
                    p = LinkParser()
                    try:
                        p.feed(html)
                    except Exception:
                        pass
                    self.store_doc(url, p.title, self.text_of(html))
                    nexts = [urljoin(url, l) for l in p.links]
                    if self.a.js:
                        for a in p.assets:
                            if re.search(r"\.js(\?|$)", a):
                                nexts.append(urljoin(url, a))
                    self.enqueue(nexts, depth + 1)
                    for form in p.forms:
                        with self.lock:
                            self.db.execute("INSERT OR IGNORE INTO endpoints(url,endpoint,source,seen_at) VALUES(?,?,?,?)",
                                            (url, (form["action"] or url) + " [" + form["method"] + "]", "form",
                                             time.strftime("%Y-%m-%dT%H:%M:%S")))
                        self.db.commit()
                elif "javascript" in ctype_l or url.endswith(".js"):
                    found = self.mine_js(url, body)
                    self.enqueue([urljoin(url, f) for f in found], depth + 1)
                elif "json" in ctype_l:
                    self.mine_js(url, body)
            except Exception as e:  # noqa: BLE001
                with self.lock:
                    self.stats["err"] += 1
                    self.db.execute("UPDATE urls SET state='failed',last_error=? WHERE url=?", (str(e)[:200], url))
                    self.db.commit()
            finally:
                self.queue.task_done()

    @staticmethod
    def text_of(html: str) -> str:
        html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
        html = re.sub(r"(?s)<[^>]+>", " ", html)
        html = re.sub(r"&nbsp;?", " ", html)
        html = re.sub(r"[ \t\r\f\v]+", " ", html)
        html = re.sub(r"\n{3,}", "\n\n", html)
        return html.strip()

    def run(self):
        if not self.queue.qsize():
            self.refill()
        threads = [threading.Thread(target=self.worker, args=(i,), daemon=True)
                   for i in range(self.a.concurrency)]
        for t in threads:
            t.start()
        try:
            for t in threads:
                while t.is_alive():
                    t.join(timeout=2)
                    if self.a.max_pages and self.stats["fetched"] >= self.a.max_pages:
                        self.stop.set()
        except KeyboardInterrupt:
            self.stop.set()
            print("\n[!] 中断，队列已保存，--resume 可续跑", file=sys.stderr)
        with self.lock:
            self.db.commit()
            print(json.dumps(self.stats, ensure_ascii=False))
            left = self.db.execute("SELECT state,COUNT(*) FROM urls GROUP BY state").fetchall()
            print("队列状态:", dict(left))


def main():
    ap = argparse.ArgumentParser(description="断点续爬采集器（robots 默认忽略）")
    ap.add_argument("--seed", action="append", required=True, help="起始 URL，可多次给")
    ap.add_argument("--db", default="harvest.db")
    ap.add_argument("--out", default="./out")
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--delay", type=float, default=0.0, help="每次请求基础延时（秒）")
    ap.add_argument("--batch", type=int, default=200, help="每次从库取多少待抓")
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--include", default="", help="URL 正则白名单")
    ap.add_argument("--exclude", default=r"\.(png|jpe?g|gif|svg|woff2?|ttf|mp4|mp3|zip|exe|dmg|iso)$",
                    help="URL 正则黑名单")
    ap.add_argument("--ua-file", default="")
    ap.add_argument("--proxy-file", default="")
    ap.add_argument("--rotate-tls", action="store_true", help="用 curl_cffi 伪装 TLS/JA3 指纹")
    ap.add_argument("--js", action="store_true", help="跟随 .js 并挖端点")
    ap.add_argument("--sitemap", action="store_true", help="递归吃 sitemap.xml")
    ap.add_argument("--respect-robots", action="store_true", help="遵守 robots（默认忽略）")
    ap.add_argument("--resume", action="store_true", help="从库中 pending 续跑")
    ap.add_argument("--retry-failed", action="store_true", help="把 failed 重新入队")
    args = ap.parse_args()

    if requests is None and cffi_requests is None:
        sys.exit("需要 requests 或 curl_cffi：pip install -r requirements.txt")

    c = Collector(args)
    if args.respect_robots:
        print("[i] --respect-robots 生效：仅作记录，不改变可达性判断", file=sys.stderr)
    c.seed(args.seed)
    c.run()


if __name__ == "__main__":
    main()

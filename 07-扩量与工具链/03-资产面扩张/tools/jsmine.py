#!/usr/bin/env python3
"""jsmine.py — 从前端产物里挖接口、端点、云密钥、内网地址。

输入：目录（递归扫 .js/.mjs/.map/.html/.json）或 URL 列表
输出：endpoints.json / endpoints.txt / secrets.json / report.md

用法：
  python3 jsmine.py --dir ./out/raw --json ./out/endpoints.json
  python3 jsmine.py --url https://<host>/static/js/main.js --json out.json
  python3 jsmine.py --dir ./raw --filter graphql,i18n --report report.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

PATTERNS = {
    "endpoint": [
        re.compile(r"""["'`](/[a-zA-Z0-9_\-./{}$:]{2,120})["'`]"""),
        re.compile(r"""["'`](/(?:api|v\d|rest|graphql|internal|admin)[a-zA-Z0-9_\-./{}$:]*)["'`]"""),
    ],
    "fetch_call": [
        re.compile(r"""(?:fetch|axios(?:\.\w+)?|request|http(?:s)?\.\w+)\s*\(\s*["'`]([^"'`]{2,200})["'`]"""),
        re.compile(r"""url\s*:\s*["'`]([^"'`]{2,200})["'`]"""),
    ],
    "graphql": [
        re.compile(r"""["'`]((?:/[\w\-]+)*/graphql[\w\-/]*)["'`]"""),
        re.compile(r"""(?:query|mutation)\s+(\w+)\s*\("""),
    ],
    "abs_url": [re.compile(r"""https?://[^\s"'`<>\\)]{6,200}""")],
    "ws_url": [re.compile(r"""wss?://[^\s"'`<>\\)]{6,200}""")],
    "internal_ip": [re.compile(r"\b(?:10|127|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}(?::\d{1,5})?\b")],
    "secret": [
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"ASIA[0-9A-Z]{16}"),
        re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"ghp_[A-Za-z0-9]{36}"),
        re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
        re.compile(r"(?i)(?:secret|token|passwd|password|apikey|api_key)\s*[:=]\s*"
                   r"[\"'`]([^\"'`]{6,80})[\"'`]"),
        re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    ],
    "debug": [
        re.compile(r"(?i)(/actuator[\w/\-]*)"),
        re.compile(r"(?i)(/swagger[\w\-/.]*)"),
        re.compile(r"(?i)(/api-docs[\w\-/.]*)"),
        re.compile(r"(?i)(__webpack_require__|sourceMappingURL=(\S+\.map))"),
        re.compile(r"(?i)//\s*(TODO|FIXME|HACK|DEBUG)[^\n]{0,120}"),
    ],
}

BIN_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".ttf",
           ".otf", ".zip", ".gz", ".tar", ".rar", ".7z", ".mp4", ".mp3", ".wav", ".pdf",
           ".exe", ".dll", ".so", ".dylib", ".class", ".jar", ".apk", ".db", ".sqlite"}


def walk(root):
    """递归列出候选文本文件：跳过明显二进制扩展名，其余交给 NUL 嗅探。"""
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if os.path.splitext(fn)[1].lower() in BIN_EXT:
                continue
            yield os.path.join(dirpath, fn)


def read_text(path, limit=8 * 1024 * 1024):
    try:
        with open(path, "rb") as f:
            raw = f.read(limit)
        if b"\x00" in raw[:4096]:
            return ""
        return raw.decode("utf-8", "ignore")
    except OSError:
        return ""


def mine(text, base=""):
    out = {k: set() for k in PATTERNS}
    for kind, pats in PATTERNS.items():
        for p in pats:
            for m in p.finditer(text):
                v = m.group(0)
                g = m.groups()
                if g and g[0]:
                    v = g[0]
                if kind in ("endpoint", "fetch_call", "graphql"):
                    v = v.strip()
                    if v.startswith("/") or v.startswith("http"):
                        out[kind].add(urljoin(base, v) if base and v.startswith("/") else v)
                else:
                    out[kind].add(v.strip())
    return {k: sorted(v) for k, v in out.items() if v}


def merge(dst, src):
    for k, vals in src.items():
        dst.setdefault(k, set()).update(vals)
    return dst


def fetch_urls(urls, out_dir, ua):
    if requests is None:
        sys.exit("需要 requests：pip install requests")
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for u in urls:
        try:
            r = requests.get(u, headers={"User-Agent": ua}, timeout=20)
            p = os.path.join(out_dir, re.sub(r"[^A-Za-z0-9._-]", "_", u)[-120:])
            with open(p, "wb") as f:
                f.write(r.content)
            paths.append(p)
            print(f"[+] {r.status_code} {len(r.content):>9} B  {u}")
        except Exception as e:  # noqa: BLE001
            print(f"[!] {u} -> {e}", file=sys.stderr)
    return paths


def main():
    ap = argparse.ArgumentParser(description="前端产物端点与密钥挖掘")
    ap.add_argument("--dir", default="", help="本地目录，递归扫文本文件")
    ap.add_argument("--url", action="append", default=[], help="远程 JS/HTML URL，可多次")
    ap.add_argument("--fetch-out", default="./js_raw", help="--url 下载落盘目录")
    ap.add_argument("--json", default="", help="结果 JSON 路径")
    ap.add_argument("--report", default="", help="Markdown 报告路径")
    ap.add_argument("--filter", default="", help="只保留包含这些子串的端点（逗号分隔）")
    ap.add_argument("--ua", default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36")
    args = ap.parse_args()

    paths = []
    if args.dir:
        paths += list(walk(args.dir))
    if args.url:
        paths += fetch_urls(args.url, args.fetch_out, args.ua)
    if not paths:
        sys.exit("给 --dir 或 --url")

    agg = {}
    hits = 0
    for p in paths:
        text = read_text(p)
        if not text:
            continue
        found = mine(text, base="")
        if found:
            hits += 1
            merge(agg, {k: set(v) for k, v in found.items()})

    if args.filter:
        keep = [s.strip() for s in args.filter.split(",") if s.strip()]
        for k in ("endpoint", "fetch_call", "graphql"):
            if k in agg:
                agg[k] = {v for v in agg[k] if any(s in v for s in keep)}

    result = {k: sorted(v) for k, v in agg.items()}
    result["_meta"] = {"files_scanned": len(paths), "files_with_hits": hits,
                       "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    print(json.dumps({k: (len(v) if isinstance(v, (list, set)) else v) for k, v in result.items()},
                     ensure_ascii=False, indent=2))

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        with open(os.path.splitext(args.json)[0] + ".txt", "w", encoding="utf-8") as f:
            for k in ("endpoint", "fetch_call", "graphql"):
                for v in result.get(k, []):
                    f.write(v + "\n")
        print(f"[+] 写出 {args.json}")

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write("# 前端产物挖掘报告\n\n")
            f.write(f"- 扫描文件：{len(paths)}（有效 {hits}）\n")
            f.write(f"- 生成时间：{result['_meta']['generated_at']}\n\n")
            for k, v in result.items():
                if k.startswith("_"):
                    continue
                f.write(f"## {k}（{len(v)}）\n\n")
                for item in v:
                    f.write(f"- `{item}`\n")
                f.write("\n")
        print(f"[+] 写出 {args.report}")


if __name__ == "__main__":
    main()

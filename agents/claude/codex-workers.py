#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Show the Codex helper threads: who owns one, where it sits, how busy it is.

Reads the local rollout transcripts under ~/.codex/sessions, so it reports what
actually happened rather than what a ledger says. Owners come from
~/.local/state/codex-workers, matched by thread id.

  codex-workers.py [--days N] [--all] [--cwd DIR]
  codex-workers.py --json
  codex-workers.py --serve [PORT]    # a page that refreshes itself

Without --all it shows only threads whose working directory is the repository
(--cwd, default the current one).
"""

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import re

SESSIONS = pathlib.Path.home() / ".codex/sessions"
LEDGER = pathlib.Path.home() / ".local/state/codex-workers"


def owners():
    """Thread id -> owner, from the ledger's `owner  <uuid>  started` rows."""
    out = {}
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            if line.startswith("#") or not line.strip():
                continue
            m = re.search(r"([0-9a-f]{8}-[0-9a-f-]{27,})", line)
            if m:
                out[m.group(1)] = line[: m.start()].strip() or "-"
    return out


def scan(path):
    """One thread's id, cwd, first and last activity, turns and tokens."""
    info = {"turns": 0, "tokens": 0, "cwd": "?", "first": None, "last": None, "id": None}
    for line in path.open(errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        t, p = r.get("type"), r.get("payload") or {}
        when = r.get("timestamp")
        if when:
            info["first"] = info["first"] or when
            info["last"] = when
        if t == "session_meta":
            info["id"] = p.get("id") or p.get("session_id")
            info["cwd"] = p.get("cwd") or "?"
        elif t == "turn_context":
            info["turns"] += 1
        elif t == "token_usage_record":
            usage = p.get("usage") or p
            for key in ("total_tokens", "total"):
                if isinstance(usage.get(key), int):
                    info["tokens"] = max(info["tokens"], usage[key])
    return info


def ago(stamp, now):
    if not stamp:
        return "-"
    delta = now - dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    minutes = int(delta.total_seconds() // 60)
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h{minutes % 60:02d}m"


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codex helpers</title>
<style>
  :root { color-scheme: light dark; --bg:#fff; --fg:#111; --dim:#666; --line:#e5e5e5; --busy:#0a7; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#14161a; --fg:#e6e6e6; --dim:#9aa0a6; --line:#2a2e35; }
  }
  body { background:var(--bg); color:var(--fg); margin:0; padding:24px 16px;
         font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; }
  h1 { font-size:15px; font-weight:600; margin:0 0 4px; }
  .sub { color:var(--dim); font-size:12px; margin-bottom:16px; }
  table { border-collapse:collapse; width:100%; max-width:1100px; }
  th { text-align:left; font-weight:600; color:var(--dim); font-size:12px;
       border-bottom:1px solid var(--line); padding:6px 10px 6px 0; }
  td { padding:6px 10px 6px 0; border-bottom:1px solid var(--line); white-space:nowrap; }
  td.n { text-align:right; }
  .cwd { color:var(--dim); font-size:12px; white-space:normal; word-break:break-all; }
  .busy { color:var(--busy); font-weight:600; }
  .idle { color:var(--dim); }
  .none { color:var(--dim); padding:16px 0; }
</style></head><body>
<h1>Codex helpers</h1>
<div class="sub" id="sub">loading…</div>
<table><thead><tr><th>owner</th><th>thread</th><th class="n">turns</th>
<th class="n">tokens</th><th class="n">idle</th><th>cwd</th></tr></thead>
<tbody id="rows"></tbody></table>
<script>
async function tick() {
  try {
    const r = await fetch('data', { cache: 'no-store' });
    const d = await r.json();
    document.getElementById('sub').textContent =
      d.rows.length + ' thread(s) · ' + d.scope + ' · updated ' + d.now;
    document.getElementById('rows').innerHTML = d.rows.map(function (x) {
      const fresh = x.idle_minutes !== null && x.idle_minutes < 5;
      return '<tr><td>' + x.owner + '</td><td>' + x.thread +
        '</td><td class="n">' + x.turns + '</td><td class="n">' + x.tokens +
        '</td><td class="n ' + (fresh ? 'busy' : 'idle') + '">' + x.idle +
        '</td><td class="cwd">' + x.cwd + '</td></tr>';
    }).join('') || '<tr><td colspan="6" class="none">no threads</td></tr>';
  } catch (e) {
    document.getElementById('sub').textContent = 'cannot reach the server';
  }
}
tick(); setInterval(tick, 10000);
</script></body></html>
"""


def collect(args, now):
    """The rows the table and the page both render."""
    want = os.path.realpath(args.cwd)
    known = owners()
    rows = []
    for path in SESSIONS.rglob("rollout-*.jsonl"):
        if (now - dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)).days > args.days:
            continue
        info = scan(path)
        if not info["id"]:
            continue
        if not args.all and os.path.realpath(info["cwd"]) != want:
            continue
        info["owner"] = known.get(info["id"], "(unrecorded)")
        rows.append(info)
    rows.sort(key=lambda r: r["last"] or "", reverse=True)
    return rows


def as_json(args, now):
    rows = []
    for r in collect(args, now):
        last = r["last"]
        minutes = None
        if last:
            minutes = int((now - dt.datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds() // 60)
        rows.append({
            "owner": html.escape(r["owner"]), "thread": r["id"],
            "turns": r["turns"], "tokens": f"{r['tokens']:,}",
            "idle": ago(last, now), "idle_minutes": minutes,
            "cwd": html.escape(r["cwd"].replace(str(pathlib.Path.home()), "~")),
        })
    return {"rows": rows, "now": now.astimezone().strftime("%H:%M:%S"),
            "scope": "all working directories" if args.all else
                     os.path.realpath(args.cwd).replace(str(pathlib.Path.home()), "~")}


def serve(args, port):
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.rstrip("/").endswith("data"):
                body = json.dumps(as_json(args, dt.datetime.now(dt.timezone.utc))).encode()
                kind = "application/json"
            else:
                body, kind = PAGE.encode(), "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    print(f"http://127.0.0.1:{port}/")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=3, help="how many days back to scan")
    p.add_argument("--all", action="store_true", help="include threads outside --cwd")
    p.add_argument("--cwd", default=os.getcwd())
    p.add_argument("--json", action="store_true", help="print the rows as JSON")
    p.add_argument("--serve", nargs="?", type=int, const=8766, metavar="PORT",
                   help="serve a self-refreshing page (default port 8766)")
    args = p.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    if args.serve:
        return serve(args, args.serve)
    if args.json:
        return print(json.dumps(as_json(args, now), ensure_ascii=False, indent=1))
    rows = collect(args, now)
    print(f"{'owner':26} {'thread':38} {'turns':>5} {'tokens':>8} {'idle':>7}  cwd")
    for r in rows:
        owner = r["owner"]
        cwd = r["cwd"].replace(str(pathlib.Path.home()), "~")
        print(f"{owner[:26]:26} {r['id']:38} {r['turns']:5} {r['tokens']:8} "
              f"{ago(r['last'], now):>7}  {cwd}")
    if not rows:
        print("(no threads in the last %d days for %s)" % (args.days, os.path.realpath(args.cwd)))


if __name__ == "__main__":
    main()

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Show the Codex helper threads: who owns one, what it is doing, what it costs.

Reads the rollout transcripts under ~/.codex/sessions, so it reports what each
thread actually did rather than what a ledger claims. Owners come from
~/.local/state/codex-workers, matched by thread id; the Claude sessions without
a helper are listed too, from their own transcripts.

  codex-workers.py [--days N] [--all] [--cwd DIR] [--tui]
  codex-workers.py --json
  codex-workers.py --serve [PORT]    # a page that refreshes itself

A helper is started through codex-rpc; --tui also shows the Codex sessions
started from the TUI (agent-team, the user's own `x`).
"""

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import re

HOME = pathlib.Path.home()
SESSIONS = HOME / ".codex/sessions"
LEDGER = HOME / ".local/state/codex-workers"
CLAUDE_SESSIONS = HOME / ".claude/sessions"


def owners():
    """Thread id -> (owner, done), from the ledger's `owner  <uuid>  started [done]` rows.

    A standby thread is labelled with its Claude session's name; a temporary one
    (a review, a discussion round) with `<session> · <purpose>`, and `done` is
    appended to its row once that work is over."""
    out = {}
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            if line.startswith("#") or not line.strip():
                continue
            m = re.search(r"([0-9a-f]{8}-[0-9a-f-]{27,})", line)
            if m:
                out[m.group(1)] = (line[: m.start()].strip() or "-", line.split()[-1] == "done")
    return out


# A served page refreshes every few seconds; this keeps what earlier refreshes
# parsed, so each one reads only what the rollouts appended since.
_SCANS = {}


def appended(path, offset):
    """Complete lines written after offset, each with the offset after it."""
    with path.open("rb") as f:
        f.seek(offset)
        for line in f:
            if not line.endswith(b"\n"):  # half-written; the next refresh gets it
                return
            offset += len(line)
            yield line, offset


def scan(path):
    """One thread: identity, settings, activity, cost and what it last ran."""
    offset, info, open_at = _SCANS.get(path, (0, None, None))
    if info is None or path.stat().st_size < offset:
        offset, open_at = 0, None
        info = {"id": None, "cwd": "?", "via": "?", "model": "?", "effort": "?",
                "sandbox": "?", "turns": 0, "tokens": 0, "last": None, "running": False,
                "task": "", "secs": None, "started": None}
    for line, offset in appended(path, offset):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        kind, p, when = r.get("type"), r.get("payload") or {}, r.get("timestamp")
        if when:
            info["last"] = when
            info["started"] = info["started"] or when
        if kind == "session_meta":
            info["id"] = p.get("id") or p.get("session_id")
            info["cwd"] = p.get("cwd") or "?"
            info["via"] = p.get("originator") or "?"
        elif kind == "turn_context":
            info["turns"] += 1
            info["model"] = p.get("model") or info["model"]
            info["effort"] = p.get("effort") or info["effort"]
            sandbox = p.get("sandbox_policy") or {}
            info["sandbox"] = sandbox.get("type") or info["sandbox"]
        elif kind == "token_usage_record":
            u = p.get("usage") or {}
            info["tokens"] += (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
        elif kind == "event_msg":
            if p.get("type") == "task_started":
                info["running"], open_at = True, when
            elif p.get("type") == "task_complete":
                info["running"] = False
                if open_at and when:
                    info["secs"] = round((iso(when) - iso(open_at)).total_seconds())
                open_at = None
        elif kind == "response_item" and p.get("role") == "user":
            text = " ".join(c.get("text", "") for c in p.get("content") or []
                            if isinstance(c, dict))
            text = " ".join(text.split())
            # The first turn carries the injected AGENTS.md; keep real prompts.
            if text and not text.startswith("# AGENTS.md"):
                info["task"] = text[:90]
    _SCANS[path] = (offset, info, open_at)
    info = dict(info)
    if info["running"] and open_at:
        info["secs"] = None
    return info


def iso(stamp):
    return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def ago(stamp, now):
    if not stamp:
        return "-"
    minutes = int((now - iso(stamp)).total_seconds() // 60)
    return f"{minutes}m" if minutes < 60 else f"{minutes // 60}h{minutes % 60:02d}m"


def claude_sessions(cwd=None):
    """Names of the running Claude sessions, optionally only those started in `cwd`.

    Each running session keeps ~/.claude/sessions/<pid>.json; a session that has
    exited, or was renamed, no longer shows under its old name."""
    names = set()
    for path in CLAUDE_SESSIONS.glob("*.json"):
        try:
            s = json.loads(path.read_text())
            os.kill(s["pid"], 0)
        except (OSError, ValueError, KeyError):
            continue
        if s.get("nameSource") != "user" or (cwd and os.path.realpath(s.get("cwd", "")) != cwd):
            continue
        names.add(s["name"])
    return names


def collect(args, now):
    want = os.path.realpath(args.cwd)
    known, rows = owners(), []
    for path in SESSIONS.rglob("rollout-*.jsonl"):
        age = now - dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
        if age.days > args.days:
            continue
        info = scan(path)
        if not info["id"]:
            continue
        if not args.all and os.path.realpath(info["cwd"]) != want:
            continue
        if not args.tui and info["via"] != "codex-rpc":
            continue
        info["owner"], info["done"] = known.get(info["id"], ("(unrecorded)", False))
        rows.append(info)
    rows.sort(key=lambda r: (not r["running"], r["last"] or ""), reverse=False)
    rows.sort(key=lambda r: r["running"], reverse=True)
    return rows


def as_json(args, now):
    rows, total, helpers = [], 0, collect(args, now)
    for r in helpers:
        total += r["tokens"]
        rows.append({
            "owner": html.escape(r["owner"]), "thread": r["id"],
            "via": html.escape(r["via"]),
            "model": html.escape(f"{r['model']}/{r['effort']}"),
            "sandbox": html.escape(r["sandbox"]),
            "state": "running" if r["running"] else "done" if r["done"] else "idle",
            "turns": r["turns"], "tokens": f"{r['tokens']:,}",
            "last_turn": f"{r['secs']}s" if r["secs"] is not None else "-",
            "idle": ago(r["last"], now),
            "idle_minutes": int((now - iso(r["last"])).total_seconds() // 60) if r["last"] else None,
            "task": html.escape(r["task"] or "-"),
            "cwd": html.escape(r["cwd"].replace(str(HOME), "~")),
        })
    mine = {r["owner"] for r in helpers if " · " not in r["owner"]}  # standby threads only
    names = claude_sessions(None if args.all else os.path.realpath(args.cwd))
    waiting = [html.escape(n) for n in sorted(names) if n not in mine]
    scope = ("all working directories" if args.all else
             os.path.realpath(args.cwd).replace(str(HOME), "~"))
    return {"rows": rows, "now": now.astimezone().strftime("%H:%M:%S"),
            "scope": scope + ("" if args.tui else " · helpers only"),
            "tokens_total": f"{total:,}", "without_helper": waiting}


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codex helpers</title>
<style>
  :root { color-scheme: light dark; --bg:#fff; --fg:#111; --dim:#666; --line:#e5e5e5;
          --run:#0a7; --warn:#c70; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#14161a; --fg:#e6e6e6; --dim:#9aa0a6; --line:#2a2e35; }
  }
  body { background:var(--bg); color:var(--fg); margin:0; padding:24px 16px;
         font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; }
  h1 { font-size:15px; font-weight:600; margin:0 0 4px; }
  .sub { color:var(--dim); font-size:12px; margin-bottom:16px; }
  table { border-collapse:collapse; width:100%; max-width:1200px; }
  th { text-align:left; font-weight:600; color:var(--dim); font-size:11px;
       text-transform:uppercase; letter-spacing:.04em;
       border-bottom:1px solid var(--line); padding:6px 10px 6px 0; }
  td { padding:7px 10px 7px 0; border-bottom:1px solid var(--line); white-space:nowrap;
       vertical-align:top; }
  td.n { text-align:right; }
  .task { color:var(--dim); white-space:normal; max-width:460px; }
  .run { color:var(--run); font-weight:600; }
  .idle { color:var(--dim); }
  .none { color:var(--dim); padding:16px 0; }
  .note { margin-top:18px; color:var(--dim); font-size:12px; max-width:1200px; }
  .note b { color:var(--warn); font-weight:600; }
</style></head><body>
<h1>Codex helpers</h1>
<div class="sub" id="sub">loading…</div>
<table><thead><tr><th>owner</th><th>state</th><th>task</th><th>model</th>
<th class="n">turns</th><th class="n">tokens</th><th class="n">last turn</th>
<th class="n">idle</th></tr></thead><tbody id="rows"></tbody></table>
<div class="note" id="note"></div>
<script>
async function tick() {
  try {
    const r = await fetch('data', { cache: 'no-store' });
    const d = await r.json();
    document.getElementById('sub').textContent =
      d.rows.length + ' helper(s) · ' + d.tokens_total + ' tokens · ' +
      d.scope + ' · updated ' + d.now;
    document.getElementById('rows').innerHTML = d.rows.map(function (x) {
      const on = x.state === 'running';
      return '<tr><td title="' + x.thread + '">' + x.owner +
        '</td><td class="' + (on ? 'run' : 'idle') + '">' + x.state +
        '</td><td class="task">' + x.task + '</td><td class="idle">' + x.model +
        '</td><td class="n">' + x.turns + '</td><td class="n">' + x.tokens +
        '</td><td class="n idle">' + x.last_turn +
        '</td><td class="n idle">' + x.idle + '</td></tr>';
    }).join('') || '<tr><td colspan="8" class="none">no helper threads</td></tr>';
    document.getElementById('note').innerHTML = d.without_helper.length
      ? 'Claude sessions with no standby helper: <b>' + d.without_helper.join(', ') + '</b>'
      : 'Every active Claude session has a helper.';
  } catch (e) {
    document.getElementById('sub').textContent = 'cannot reach the server';
  }
}
tick(); setInterval(tick, 10000);
</script></body></html>
"""


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

    as_json(args, dt.datetime.now(dt.timezone.utc))  # parse everything once, before the first visitor
    print(f"http://127.0.0.1:{port}/")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=3, help="how many days back to scan")
    p.add_argument("--all", action="store_true", help="include threads outside --cwd")
    p.add_argument("--cwd", default=os.getcwd())
    p.add_argument("--tui", action="store_true",
                   help="also show Codex sessions started from the TUI")
    p.add_argument("--json", action="store_true", help="print the rows as JSON")
    p.add_argument("--serve", nargs="?", type=int, const=8766, metavar="PORT",
                   help="serve a self-refreshing page (default port 8766)")
    args = p.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    if args.serve:
        return serve(args, args.serve)
    data = as_json(args, now)
    if args.json:
        return print(json.dumps(data, ensure_ascii=False, indent=1))

    print(f"{'owner':26} {'state':8} {'model':18} {'turns':>5} {'tokens':>9} "
          f"{'last':>6} {'idle':>7}  task")
    for r in data["rows"]:
        print(f"{r['owner'][:26]:26} {r['state']:8} {r['model'][:18]:18} {r['turns']:5} "
              f"{r['tokens']:>9} {r['last_turn']:>6} {r['idle']:>7}  {r['task'][:60]}")
    if not data["rows"]:
        print("(no helper threads)")
    print(f"\ntotal {data['tokens_total']} tokens")
    if data["without_helper"]:
        print("no standby helper: " + ", ".join(data["without_helper"]))


if __name__ == "__main__":
    main()

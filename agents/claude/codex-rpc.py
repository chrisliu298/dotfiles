#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Send one turn to a Codex app-server thread and print the agent's final text.

The app-server protocol is newline-delimited JSON-RPC 2.0 without the "jsonrpc"
field, spoken over the subprocess's stdin/stdout. A turn ends with a
turn/completed notification, so a caller gets a real completion signal instead
of scraping a tmux pane.

  codex-rpc.py start  [--owner NAME] [--prompt TEXT | -] [--cwd DIR] [--model M] [--effort E]
  codex-rpc.py resume --thread ID [--prompt TEXT | -] [--cwd DIR] [--expect-cwd DIR]
  codex-rpc.py list   [--limit N]

start prints the new thread id and working directory on stderr and keeps the
thread resumable; --owner records it in the ledger that codex-workers.py
reads before the first turn runs. resume continues a thread with its context.
A thread stays alive server side, so a standby worker needs no running process.
--cwd overrides the working directory for this turn and the following ones, so
resume omits it unless asked; --expect-cwd refuses to run a turn against a
thread that sits somewhere else. --prompt - reads the prompt from stdin.
The agent's final text goes to stdout, so a caller can redirect it to a file.
"""

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time

CODEX = os.path.expanduser("~/.local/bin/codex")
LEDGER = os.path.expanduser("~/.local/state/codex-workers")


class AppServer:
    """One `codex app-server` subprocess, after the initialize handshake."""

    def __init__(self, timeout):
        self.deadline = time.time() + timeout
        self.proc = subprocess.Popen(
            [CODEX, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        self.lines = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        # No capabilities: what a client declares is negotiated into the shared
        # background server's feature settings, which other Codex clients then
        # have to match. Everything used here is in the stable API.
        self.request("initialize", {
            "clientInfo": {"name": "codex-rpc", "title": "codex-rpc", "version": "0.1.0"},
        })
        self.notify("initialized")

    def _read(self):
        for line in self.proc.stdout:
            self.lines.put(line.rstrip("\n"))

    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def notify(self, method, params=None):
        self._send({"method": method, **({"params": params} if params else {})})

    def _await(self, match):
        """Read messages until match(msg) is truthy; return that message."""
        while time.time() < self.deadline:
            try:
                line = self.lines.get(timeout=1)
            except queue.Empty:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("error"):
                raise SystemExit(f"codex-rpc: {json.dumps(msg['error'])}")
            if match(msg):
                return msg
        raise SystemExit("codex-rpc: timed out")

    _next_id = 0

    def request(self, method, params=None):
        AppServer._next_id += 1
        rid = AppServer._next_id
        self._send({"id": rid, "method": method, "params": params or {}})
        return self._await(lambda m: m.get("id") == rid)["result"]

    def turn(self, thread_id, prompt):
        """Run one turn and return the agent's final text."""
        AppServer._next_id += 1
        rid = AppServer._next_id
        self._send({"id": rid, "method": "turn/start",
                    "params": {"threadId": thread_id, "input": [{"type": "text", "text": prompt}]}})
        done = self._await(lambda m: m.get("method") == "turn/completed")
        turn = (done.get("params") or {}).get("turn") or {}
        if turn.get("status") != "completed":
            raise SystemExit(f"codex-rpc: turn {turn.get('status')}: {json.dumps(turn.get('error'))}")
        texts = [i.get("text") for i in turn.get("items") or []
                 if i.get("type") == "agentMessage" and i.get("text")]
        return "\n".join(texts)

    def close(self):
        self.proc.terminate()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("start", "resume", "list"))
    p.add_argument("--thread", help="thread id to resume")
    p.add_argument("--owner", help="on start, record the thread under this owner in the ledger")
    p.add_argument("--prompt", help="the turn's text, or - to read stdin")
    p.add_argument("--cwd", help="the thread's working directory; omitted on resume it is preserved")
    p.add_argument("--expect-cwd", help="abort unless the thread's working directory is this")
    p.add_argument("--model")
    p.add_argument("--effort", choices=("low", "medium", "high"))
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--timeout", type=float, default=1800)
    args = p.parse_args()

    server = AppServer(args.timeout)
    try:
        if args.action == "list":
            for t in server.request("thread/list", {"limit": args.limit}).get("data") or []:
                print(f"{t.get('id')}  {(t.get('name') or '-')[:60]}")
            return

        if args.action == "resume":
            if not args.thread:
                raise SystemExit("codex-rpc: resume needs --thread")
            params = {"threadId": args.thread}
        else:
            params = {"cwd": args.cwd or os.getcwd()}
        # cwd overrides this turn AND the following ones, so only send it when asked.
        for key, value in (("cwd", args.cwd), ("model", args.model), ("effort", args.effort)):
            if value:
                params[key] = value
        thread = server.request(f"thread/{args.action}", params)["thread"]
        cwds = [e.get("cwd") for e in thread.get("environments") or []]
        print(f"thread {thread['id']} cwd {', '.join(c or '?' for c in cwds) or '?'}", file=sys.stderr)
        if args.owner and args.action == "start":
            with open(LEDGER, "a") as ledger:
                ledger.write(f"{args.owner:<28}{thread['id']}  {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
        if args.expect_cwd:
            want = os.path.realpath(os.path.expanduser(args.expect_cwd))
            if [os.path.realpath(c) for c in cwds if c] != [want]:
                raise SystemExit(f"codex-rpc: thread is at {cwds}, expected {want}")

        prompt = sys.stdin.read() if args.prompt == "-" else args.prompt
        if prompt and prompt.strip():
            print(server.turn(thread["id"], prompt))
    finally:
        server.close()


if __name__ == "__main__":
    main()

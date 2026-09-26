#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Search the local Codex and Claude conversation stores with source attribution."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


SKILLS = Path(__file__).resolve().parents[1]
SCRIPTS = {
    "codex": SKILLS / "codex" / "scripts" / "recall.py",
    "claude": SKILLS / "claude" / "scripts" / "recall.py",
}


def run_source(source: str, args: list[str]) -> dict:
    env = os.environ.copy()
    env.setdefault("RECALL_CACHE_DIR", str(Path.home() / ".cache" / "recall"))
    process = subprocess.run(
        [sys.executable, str(SCRIPTS[source]), *args],
        capture_output=True, text=True, check=False, env=env,
    )
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "reason": process.stderr.strip() or process.stdout.strip() or f"exit {process.returncode}"}
    if process.returncode not in (0, 11, 12, 13):
        return {"status": "error", "reason": process.stderr.strip() or f"exit {process.returncode}"}
    return result


def search(query: str, cwd: str, sources: list[str], limit: int, roles: str = "both") -> dict:
    commands = {
        "codex": ["search", "--scope", "all", "--cwd", cwd, "--query", query, "--limit", str(limit)],
        "claude": ["search", "--scope", "all", "--max-files", "0", "--cwd", cwd, "--q", query, "--k", str(limit)],
    }
    for command in commands.values():
        command.extend(["--roles", roles])
    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = {source: executor.submit(run_source, source, commands[source]) for source in sources}
        results = {source: futures[source].result() for source in sources}

    candidates = []
    for source, result in results.items():
        for candidate in result.get("candidates", []):
            candidate = dict(candidate)
            candidate["source"] = source
            candidate["confirmation"] = candidate["confirmation"].replace(
                "recall: ", f"recall [{source}]: ", 1
            )
            candidates.append(candidate)

    statuses = [result.get("status") for result in results.values()]
    if "error" in statuses:
        status = "partial_error" if candidates else "error"
    elif "ambiguous" in statuses or sum(bool(result.get("candidates")) for result in results.values()) > 1:
        status = "ambiguous"
    elif "confident" in statuses:
        status = "confident"
    elif "empty_query" in statuses:
        status = "empty_query"
    else:
        status = "no_match"

    output = {"status": status, "sources": results, "candidates": candidates}
    if status == "confident":
        output["confirmation"] = candidates[0]["confirmation"]
    return output


def show(source: str, args: argparse.Namespace) -> dict:
    if source == "codex":
        if not args.item_id:
            return {"status": "error", "reason": "Codex results require --item-id"}
        command = ["show", "--session-id", args.session, "--item-id", args.item_id]
    else:
        if args.line is None:
            return {"status": "error", "reason": "Claude results require --line"}
        command = ["show", "--cwd", args.cwd, "--session", args.session, "--line", str(args.line)]
    return {"source": source, **run_source(source, command)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    find = commands.add_parser("search")
    find.add_argument("--query", "-q", required=True)
    find.add_argument("--cwd", default=os.getcwd())
    find.add_argument("--agent", choices=("codex", "claude"), required=True)
    find.add_argument("--source", choices=("self", "other", "all"), default="self")
    find.add_argument("--limit", type=int, choices=range(1, 21), default=5)
    find.add_argument("--roles", choices=("both", "user", "assistant"), default="both")
    context = commands.add_parser("show")
    context.add_argument("--source", choices=("codex", "claude"), required=True)
    context.add_argument("--session", required=True)
    context.add_argument("--item-id")
    context.add_argument("--line", type=int)
    context.add_argument("--cwd", default=os.getcwd())
    args = parser.parse_args(argv)
    if args.command == "search":
        sources = (
            list(SCRIPTS) if args.source == "all" else
            [args.agent] if args.source == "self" else
            ["claude" if args.agent == "codex" else "codex"]
        )
        result = search(args.query, args.cwd, sources, args.limit, args.roles)
    else:
        result = show(args.source, args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] in ("confident", "ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

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
from datetime import date
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
    command = ([sys.executable, str(Path(__file__).with_name("retrieve.py")), "--source", source, *args[1:]]
               if args[0] == "search" else [sys.executable, str(SCRIPTS[source]), *args])
    process = subprocess.run(
        command,
        capture_output=True, text=True, check=False, env=env,
    )
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "reason": process.stderr.strip() or process.stdout.strip() or f"exit {process.returncode}"}
    if process.returncode not in (0, 11, 12, 13):
        return {"status": "error", "reason": process.stderr.strip() or f"exit {process.returncode}"}
    return result


def search(query: str | list[str], cwd: str, sources: list[str], limit: int, roles: str = "both",
           since: str | None = None, until: str | None = None) -> dict:
    queries = list(dict.fromkeys([query] if isinstance(query, str) else query))
    command = ["search", "--cwd", cwd, "--limit", str(limit), "--roles", roles]
    for value in queries:
        command.extend(["--query", value])
    for flag, value in (("--since", since), ("--until", until)):
        if value:
            command.extend([flag, value])
    commands = {source: command for source in sources}
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
            for evidence in candidate.get("evidence", []):
                evidence["source"] = source
                evidence["confirmation"] = evidence["confirmation"].replace("recall: ", f"recall [{source}]: ", 1)
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

    output = {"status": status, "sources": {source: {key: value for key, value in result.items()
               if key not in ("candidates", "confirmation")} for source, result in results.items()},
              "candidates": candidates, "verification_required": bool(candidates)}
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
    command.extend(["--offset", str(args.offset), "--before", str(args.before), "--after", str(args.after), "--max-chars", str(args.max_chars)])
    return {"source": source, **run_source(source, command)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    find = commands.add_parser("search")
    find.add_argument("--query", "-q", action="append", required=True, help="Repeat for up to six complementary phrasings")
    find.add_argument("--cwd", default=os.getcwd())
    find.add_argument("--agent", choices=("codex", "claude"), required=True)
    find.add_argument("--source", choices=("self", "other", "all"), default="self")
    find.add_argument("--limit", type=int, choices=range(1, 21), default=5)
    find.add_argument("--roles", choices=("both", "user", "assistant"), default="both")
    find.add_argument("--since", type=date.fromisoformat, help="Inclusive message date YYYY-MM-DD")
    find.add_argument("--until", type=date.fromisoformat, help="Inclusive message date YYYY-MM-DD")
    context = commands.add_parser("show")
    context.add_argument("--offset", type=int, default=0, help="Character offset in the anchor message")
    context.add_argument("--before", type=int, choices=range(21), default=3)
    context.add_argument("--after", type=int, choices=range(21), default=5)
    context.add_argument("--max-chars", type=int, choices=range(1000, 50001), default=12000)
    context.add_argument("--source", choices=("codex", "claude"), required=True)
    context.add_argument("--session", required=True)
    context.add_argument("--item-id")
    context.add_argument("--line", type=int)
    context.add_argument("--cwd", default=os.getcwd())
    args = parser.parse_args(argv)
    if args.command == "search":
        if len(args.query) > 6:
            parser.error("at most six query variants are supported")
        if args.since and args.until and args.since > args.until:
            parser.error("--since must be on or before --until")
        sources = (
            list(SCRIPTS) if args.source == "all" else
            [args.agent] if args.source == "self" else
            ["claude" if args.agent == "codex" else "codex"]
        )
        result = search(args.query, args.cwd, sources, args.limit, args.roles,
                        args.since.isoformat() if args.since else None,
                        args.until.isoformat() if args.until else None)
    else:
        result = show(args.source, args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result["status"] in ("error", "partial_error", "not_found", "ambiguous_session", "ambiguous_item") else 0


if __name__ == "__main__":
    raise SystemExit(main())

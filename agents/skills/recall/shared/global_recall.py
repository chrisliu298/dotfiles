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
from datetime import date, datetime, time
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
    worker = [sys.executable, str(Path(__file__).with_name("retrieve.py")), "--source", source]
    command = ([*worker, *args[1:]] if args[0] == "search" else
               [*worker, "--timeline", *args[1:]] if args[0] == "timeline" else
               [sys.executable, str(SCRIPTS[source]), *args])
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
           since: str | None = None, until: str | None = None, project: str | None = None,
           session: str | None = None) -> dict:
    queries = list(dict.fromkeys([query] if isinstance(query, str) else query))
    command = ["search", "--cwd", cwd, "--limit", str(limit), "--roles", roles]
    for value in queries:
        command.extend(["--query", value])
    for flag, value in (("--since", since), ("--until", until), ("--project", project), ("--session", session)):
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


def moment(value: str, end: bool = False) -> float:
    """Local YYYY-MM-DD or YYYY-MM-DDTHH:MM -> epoch; a bare date as an upper bound means its last instant."""
    parsed = datetime.fromisoformat(value)
    if end and len(value) == 10:
        parsed = datetime.combine(parsed.date(), time.max)
    return parsed.timestamp()


def timeline(cwd: str, sources: list[str], since: str, until: str | None, limit: int, roles: str, max_chars: int,
             project: str | None = None, session: str | None = None) -> dict:
    command = ["timeline", "--cwd", cwd, "--since-epoch", str(moment(since)), "--limit", str(limit),
               "--roles", roles, "--max-chars", str(max_chars)]
    if until:
        command.extend(["--until-epoch", str(moment(until, end=True))])
    for flag, value in (("--project", project), ("--session", session)):
        if value:
            command.extend([flag, value])
    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = {source: executor.submit(run_source, source, command) for source in sources}
        results = {source: futures[source].result() for source in sources}
    sessions = [dict(entry, source=source) for source, result in results.items()
                for entry in result.get("sessions", [])]
    sessions.sort(key=lambda entry: entry["messages"][0]["time"])
    statuses = [result.get("status") for result in results.values()]
    status = ("partial_error" if sessions else "error") if "error" in statuses else "ok" if sessions else "no_messages"
    return {"status": status, "window": {"since": since, "until": until}, "sessions": sessions,
            "sources": {source: {key: value for key, value in result.items() if key != "sessions"}
                        for source, result in results.items()}}


def show(source: str, args: argparse.Namespace) -> dict:
    if source == "codex":
        if not args.item_id:
            return {"status": "error", "reason": f"{source} results require --item-id"}
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
    find.add_argument("--project", help="Case-insensitive substring of the session's working directory")
    find.add_argument("--session", help="Search only inside sessions whose id starts with this prefix")
    window = commands.add_parser("timeline")
    window.add_argument("--since", required=True, help="Local YYYY-MM-DD or YYYY-MM-DDTHH:MM")
    window.add_argument("--until", help="Local YYYY-MM-DD or YYYY-MM-DDTHH:MM, inclusive")
    window.add_argument("--cwd", default=os.getcwd())
    window.add_argument("--agent", choices=("codex", "claude"), required=True)
    window.add_argument("--source", choices=("self", "other", "all"), default="self")
    window.add_argument("--limit", type=int, choices=range(1, 1001), metavar="1-1000", default=200)
    window.add_argument("--roles", choices=("both", "user", "assistant"), default="user")
    window.add_argument("--max-chars", type=int, choices=range(100, 5001), metavar="100-5000", default=500)
    window.add_argument("--project", help="Case-insensitive substring of the session's working directory")
    window.add_argument("--session", help="List only sessions whose id starts with this prefix")
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
    if args.command in ("search", "timeline"):
        sources = (
            list(SCRIPTS) if args.source == "all" else
            [args.agent] if args.source == "self" else
            [name for name in SCRIPTS if name != args.agent]
        )
    if args.command == "timeline":
        try:
            start = moment(args.since)
            if args.until and start > moment(args.until, end=True):
                parser.error("--since must be on or before --until")
        except ValueError as exc:
            parser.error(f"invalid time: {exc}")
        result = timeline(args.cwd, sources, args.since, args.until, args.limit, args.roles, args.max_chars,
                          args.project, args.session)
    elif args.command == "search":
        if len(args.query) > 6:
            parser.error("at most six query variants are supported")
        if args.since and args.until and args.since > args.until:
            parser.error("--since must be on or before --until")
        result = search(args.query, args.cwd, sources, args.limit, args.roles,
                        args.since.isoformat() if args.since else None,
                        args.until.isoformat() if args.until else None, args.project, args.session)
    else:
        result = show(args.source, args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result["status"] in ("error", "partial_error", "not_found", "ambiguous_session", "ambiguous_item") else 0


if __name__ == "__main__":
    raise SystemExit(main())

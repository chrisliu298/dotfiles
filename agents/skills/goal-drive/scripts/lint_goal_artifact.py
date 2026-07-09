#!/usr/bin/env python3
"""Mechanical conformance check for goal-drive artifacts.

Validates the three shapes goal-drive consumes — a Goal Contract (`GOAL.md` /
`<id>.goal.md`), a JSON checklist (`<id>.checklist.json`), and a phased doc
(`<id>.plan.md`) — against the schemas in
`goal-drive/references/artifact-formats.md`. It is the executable backstop for
goal-elicit's prose audit checklist: a regex cannot have a bad day, and it
catches hand-edited / script-generated / drifted artifacts that never passed
through the interview gates.

stdlib only, so it runs anywhere `python3` does — no venv, no PyYAML. The
frontmatter parser is intentionally minimal (top-level scalar keys only); it is
a linter, not a loader.

Exit codes: 0 = no errors (warnings allowed), 1 = errors found, 2 = usage/IO.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

VALID_ARTIFACT_STATUS = {"draft", "ready", "blocked", "running", "complete"}
STRICT_STATUS = {"ready", "running", "complete"}  # placeholders/thin content forbidden here
VALID_UNIT_STATE = {"pending", "done", "blocked"}

DANGEROUS_VAGUE = [
    r"make sure it works",
    r"edit anything",
    r"change whatever",
    r"keep trying",
    r"until it (?:looks|seems|feels) good",
    r"looks good",
    r"works well",
    r"feels right",
]

# High-confidence leftover-template markers. Square brackets are deliberately NOT
# scanned: `- [ ]` / `- [x]` Done-when checkboxes use them legitimately.
PLACEHOLDER = [
    r"\bTODO\b",
    r"\bTBD\b",
    r"\bFIXME\b",
    r"\bXXX\b",
    r"<[a-z][^>\n]{0,80}>",  # template fills like <id>, <criterion 1>, <evidence>
]

# Concrete-evidence vocabulary a verification string should name.
EVIDENCE_VERBS = re.compile(
    r"(?:run|start|open|test|build|lint|typecheck|verif|inspect|capture|screenshot|"
    r"log|artifact|file|url|api|simulator|browser|local|exit|metric|diff|pass)",
    re.IGNORECASE,
)


def add(errs: list[str], src: str, msg: str) -> None:
    errs.append(f"{src}: {msg}")


def scan_common(text: str, src: str, status: str, errs: list[str]) -> None:
    """Dangerous-vague (any status) + leftover placeholders (strict status only)."""
    for pat in DANGEROUS_VAGUE:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            add(errs, src, f"dangerous vague instruction: {m.group(0)!r}")
    if status in STRICT_STATUS:
        for pat in PLACEHOLDER:
            m = re.search(pat, text)
            if m:
                add(errs, src, f"unresolved placeholder in {status} artifact: {m.group(0)!r}")


# --- frontmatter ---------------------------------------------------------------

def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (top-level scalar frontmatter, body). Empty dict if no frontmatter."""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, flags=re.DOTALL)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if kv:
            fm[kv.group(1)] = kv.group(2).strip()
    return fm, m.group(2)


def section(body: str, heading: str) -> str | None:
    """Body of a `## heading` section, up to the next `## ` or EOF."""
    m = re.search(
        rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s|\Z)",
        body,
        flags=re.MULTILINE | re.DOTALL,
    )
    return m.group(1) if m else None


# --- contract ------------------------------------------------------------------

def lint_contract(text: str, src: str) -> list[str]:
    errs: list[str] = []
    fm, body = split_frontmatter(text)
    if not fm:
        add(errs, src, "missing YAML frontmatter")
        return errs

    for field in ("schema_version", "id", "status"):
        if field not in fm:
            add(errs, src, f"frontmatter missing required field `{field}`")
    status = fm.get("status", "")
    if status and status not in VALID_ARTIFACT_STATUS:
        add(errs, src, f"invalid status {status!r} (expected one of {sorted(VALID_ARTIFACT_STATUS)})")

    scan_common(text, src, status, errs)

    if status == "blocked" and fm.get("blocking_unknowns", "[]").strip() in ("", "[]"):
        add(errs, src, "status is `blocked` but `blocking_unknowns` is empty")
    if fm.get("approved_by_user", "").lower() == "false" and status in STRICT_STATUS:
        add(errs, src, f"approved_by_user is false on a {status} contract (no recorded assent)")

    # Done when — the load-bearing evidence-mapped section.
    dw = section(body, "Done when")
    if status in STRICT_STATUS:
        if dw is None:
            add(errs, src, "missing `## Done when` section")
        else:
            items = re.findall(r"^\s*-\s*\[[ xX]\]\s*(.+)$", dw, flags=re.MULTILINE)
            if not items:
                add(errs, src, "`## Done when` has no checklist items")
            for it in items:
                if "<!-- blocked" in it:
                    continue  # a blocked item carries a reason, not an arrow
                if "→" not in it and "->" not in it:
                    add(errs, src, f"Done-when item has no `→ evidence` mapping: {it.strip()!r}")
                    continue
                evidence = re.split(r"→|->", it, maxsplit=1)[1].strip()
                if len(evidence) < 3:
                    add(errs, src, f"Done-when item has thin/empty evidence: {it.strip()!r}")

        # Gherkin required except clear-domain (which may verify by a single command).
        if fm.get("cynefin_domain", "").lower() != "clear":
            has_gherkin = (
                re.search(r"^\s*Given\b", body, flags=re.MULTILINE | re.IGNORECASE)
                and re.search(r"^\s*When\b", body, flags=re.MULTILINE | re.IGNORECASE)
                and re.search(r"^\s*Then\b", body, flags=re.MULTILINE | re.IGNORECASE)
            )
            if not has_gherkin:
                add(errs, src, "no Gherkin scenario (Given/When/Then) for a non-clear contract")
    return errs


# --- checklist -----------------------------------------------------------------

def lint_checklist(text: str, src: str, warns: list[str]) -> list[str]:
    errs: list[str] = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        add(errs, src, f"invalid JSON: {exc}")
        return errs
    if not isinstance(data, dict):
        add(errs, src, "top-level JSON is not an object")
        return errs

    for field in ("schema_version", "id", "done_when"):
        if field not in data:
            add(errs, src, f"missing required field `{field}`")

    done_when = str(data.get("done_when", ""))
    for pat in DANGEROUS_VAGUE:
        if re.search(pat, done_when, flags=re.IGNORECASE):
            add(errs, src, f"`done_when` contains a dangerous vague phrase: {done_when!r}")
            break

    acc_global = data.get("acceptance_per_item")
    items = data.get("items")
    if not isinstance(items, list):
        add(errs, src, "`items` must be an array")
        return errs
    if not items:
        warns.append(f"{src}: `items` is empty — goal-drive will treat this as 'awaiting items' and not execute")

    seen: set[str] = set()
    for i, it in enumerate(items):
        loc = f"items[{i}]"
        if not isinstance(it, dict):
            add(errs, src, f"{loc} is not an object")
            continue
        iid = it.get("id")
        if not iid:
            add(errs, src, f"{loc} missing stable `id` (the idempotency key)")
        else:
            if iid in seen:
                add(errs, src, f"duplicate item id {iid!r} (ids must be unique)")
            seen.add(iid)
        state = it.get("state")
        if state not in VALID_UNIT_STATE:
            add(errs, src, f"{loc} ({iid}) has invalid state {state!r}")
        if state == "done" and not str(it.get("evidence") or "").strip():
            add(errs, src, f"{loc} ({iid}) is done but has empty `evidence`")
        if state == "blocked" and not str(it.get("note") or "").strip():
            add(errs, src, f"{loc} ({iid}) is blocked but has empty `note`")
        if acc_global is None and not str(it.get("acceptance") or "").strip():
            warns.append(f"{src}: {loc} ({iid}) has no `acceptance` and no top-level `acceptance_per_item` — weak verification mode")

    cp = data.get("commit_policy", "none")
    if cp not in ("none", "per_unit"):
        add(errs, src, f"invalid commit_policy {cp!r} (expected none | per_unit)")
    return errs


# --- phased --------------------------------------------------------------------

def lint_phased(text: str, src: str) -> list[str]:
    errs: list[str] = []
    fm, body = split_frontmatter(text)
    if not fm:
        add(errs, src, "missing YAML frontmatter")
        return errs
    for field in ("schema_version", "id", "status"):
        if field not in fm:
            add(errs, src, f"frontmatter missing required field `{field}`")
    status = fm.get("status", "")
    if status and status not in VALID_ARTIFACT_STATUS:
        add(errs, src, f"invalid status {status!r} (expected one of {sorted(VALID_ARTIFACT_STATUS)})")

    scan_common(text, src, status, errs)

    if section(body, "Phases") is None and not re.search(r"^##\s+Phases\s*$", body, flags=re.MULTILINE):
        add(errs, src, "missing `## Phases` section")

    # Each phase: `### <title>  [state: X]`, then **Acceptance:** / **Evidence:** / **Blocked:**.
    phases = re.split(r"^###\s+", body, flags=re.MULTILINE)[1:]
    if not phases:
        add(errs, src, "no phase headings (`### ... [state: ...]`) found")
    for ph in phases:
        title = ph.splitlines()[0].strip() if ph.strip() else "<empty>"
        sm = re.search(r"\[state:\s*(\w+)\s*\]", ph)
        if not sm:
            add(errs, src, f"phase {title!r} has no `[state: ...]` marker")
            continue
        pstate = sm.group(1).lower()
        if pstate not in VALID_UNIT_STATE:
            add(errs, src, f"phase {title!r} has invalid state {pstate!r}")
        acc = re.search(r"\*\*Acceptance:\*\*\s*(.+)", ph)
        if not acc or len(acc.group(1).strip()) < 3:
            add(errs, src, f"phase {title!r} has no/thin `**Acceptance:**` line")
        elif any(re.search(p, acc.group(1), flags=re.IGNORECASE) for p in DANGEROUS_VAGUE):
            add(errs, src, f"phase {title!r} acceptance is dangerously vague")
        if pstate == "done":
            ev = re.search(r"\*\*Evidence:\*\*\s*(.+)", ph)
            if not ev or len(ev.group(1).strip()) < 3:
                add(errs, src, f"phase {title!r} is done but `**Evidence:**` is empty")
        if pstate == "blocked":
            bl = re.search(r"\*\*Blocked:\*\*\s*(.+)", ph)
            if not bl or len(bl.group(1).strip()) < 3:
                add(errs, src, f"phase {title!r} is blocked but `**Blocked:**` is empty")
    return errs


# --- dispatch ------------------------------------------------------------------

def detect_shape(path: Path, text: str) -> str:
    name = path.name
    if name.endswith(".checklist.json") or text.lstrip().startswith("{"):
        return "checklist"
    if name.endswith(".plan.md") or "goal-plan/v1" in text or re.search(r"^##\s+Phases\s*$", text, flags=re.MULTILINE):
        return "phased"
    return "contract"


def lint_file(path: Path, warns: list[str]) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{path}: cannot read file: {exc}"]
    src = str(path)
    shape = detect_shape(path, text)
    if shape == "checklist":
        return lint_checklist(text, src, warns)
    if shape == "phased":
        return lint_phased(text, src)
    return lint_contract(text, src)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: lint_goal_artifact.py <artifact> [<artifact> ...]", file=sys.stderr)
        return 2
    errors: list[str] = []
    warnings: list[str] = []
    for raw in argv[1:]:
        errors.extend(lint_file(Path(raw), warnings))
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        print(f"FAIL: {len(errors)} error(s), {len(warnings)} warning(s).", file=sys.stderr)
        return 1
    print(f"Goal artifact lint passed ({len(warnings)} warning(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

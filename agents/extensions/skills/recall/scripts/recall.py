#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""recall.py — find an earlier user statement in THIS project's past Claude sessions.

When the user refers back to something they established earlier ("what did we decide about X",
"like I said before"), this script searches every Claude transcript whose cwd is the current
project — ~/.claude/projects/<encoded-cwd>/*.jsonl — ranks the matching exchanges with a
stdlib BM25 retriever (user-turn / decision-cue / recency boosted), and hands the agent a small
ranked list with L<line> anchors. The agent loads the top hit into its working context and prints
ONE confirmation line; it never reads raw JSONL itself (re-reading a 500MB corpus would overflow
the window). The script is the filter; the model is the integrator.

Subcommands:
  search   rank past exchanges matching a query                              -> JSON
  show     fetch the redacted surrounding turns at a session + line anchor    -> JSON
  doctor   diagnostics: encoded cwd, file counts, a sample of candidates      -> text

Run with uv (zero deps, stdlib only):
  uv run ~/dotfiles/agents/extensions/skills/recall/scripts/recall.py search --cwd "$PWD" --q "auth retry"

Retrieval is LEXICAL (BM25 over normalized events), not semantic — by design: it stays stdlib-only
and its failure mode is a clean miss (-> ask the user) rather than a confident wrong match. The
transcript-reading primitives (iter_lines, redact/clip, encode_cwd, events, is_interactive) are
carried over verbatim from the former `rehydrate` skill; the storage-format notes live in
references/{claude,schema}.md. Detection of the user-vs-tool-result split and sidechain filtering
is STRUCTURAL (record type/flag), never a lexical guess.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

HOME = Path.home()
PER_EVENT_TEXT_CAP = 1600          # truncate any single event's text before it enters the corpus
HUGE_LINE = 2_000_000              # bytes; above this, peek the record type, don't full-parse
GIST_CHARS = 220                   # length of the recalled snippet shown in the confirmation line
DEFAULT_K = 5                      # candidates returned to the agent
# Latency is CPU-bound on JSON-parsing the scanned files (~9s for the full ~530-interactive-file
# corpus; ~2.5s at 150). So the default first pass is a recency window — the dominant "as I
# mentioned earlier" reference skews recent — and the agent escalates to --max-files 0 (every past
# session) on a miss. This keeps the all-sessions SCOPE while bounding the common case.
DEFAULT_MAX_FILES = 150
# BM25 params + the confidence gates. The gates are the load-bearing safety surface: they decide
# `confident` (silent-load OK) vs `ambiguous` (ask) vs `no_match` (don't fabricate).
BM25_K1, BM25_B = 1.5, 0.75
# Gate thresholds (calibrated on eval/gold.jsonl). Raw BM25 score is UNNORMALIZED — scores run
# ~10-40 on a real corpus — so it is NOT a usable floor; the real signal is how many distinct query
# terms matched and what fraction of the query they cover. The top/2nd margin is only a weak
# tiebreak (at corpus scale there is almost always a near-scoring runner-up), so it nudges confident,
# never gates no_match.
CAND_MIN_COVERAGE = 0.4            # multi-term hit below this (or <2 matched terms) is incidental ⇒ no_match
CONFIDENT_COVERAGE = 0.6           # a confident silent-load must cover at least this much of the query
CONFIDENT_MARGIN = 1.15            # …and lead the best DISTINCT runner-up by at least this ratio
USER_BOOST = 1.6                   # a user-authored turn is what "what did *we* decide" wants
CUE_BOOST = 1.25                   # a decision/correction-shaped turn
PHRASE_BOOST = 1.4                 # the normalized query appears verbatim
RECENCY_MAX_BOOST = 0.15           # newest session gets +15%, oldest +0%

# ---------------------------------------------------------------------------- redaction
# (verbatim from rehydrate: the single output-side secret choke point — every emitted snippet
# flows through clip(), so a secret can't survive by being split across a clip boundary.)
_SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}"), "openai-key"),
    (re.compile(r"\bxai-[A-Za-z0-9_\-]{12,}"), "xai-key"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"), "github-token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws-key"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}"), "bearer"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}"), "jwt"),
    (re.compile(r"(?i)\b[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD|PLAN_KEY)[A-Z0-9_]*\s*[:=]\s*[^\s\"']+"), "env-secret"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}"), "google-key"),
    (re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}"), "slack-token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "private-key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private-key"),
]
_redaction_count = 0


def redact(text: str) -> str:
    global _redaction_count
    if not text:
        return text
    for pat, label in _SECRET_PATTERNS:
        text, n = pat.subn(f"[REDACTED:{label}]", text)
        _redaction_count += n
    return text


def clip(text, cap=PER_EVENT_TEXT_CAP):
    # Redact BEFORE whitespace-collapse/truncation so a secret can't survive by being split across
    # a clip boundary. Single choke point for redaction of all emitted text.
    text = redact((text or "").strip())
    text = re.sub(r"\s+", " ", text)
    return text if len(text) <= cap else text[:cap] + " …"


# ---------------------------------------------------------------------------- data model
@dataclass
class Event:
    line: int
    role: str            # user | assistant | tool
    kind: str            # user_message | assistant_message | file_op | command | command_output
    text: str = ""       # already truncated/redacted snippet
    ts: str | None = None
    sidechain: bool = False


@dataclass
class Doc:
    """A searchable past statement: one user/assistant text event, tagged with provenance."""
    session: str         # session uuid (transcript stem)
    transcript: str      # absolute transcript path
    line: int
    role: str
    text: str
    date: str            # YYYY-MM-DD
    tokens: list[str] = field(default_factory=list)
    session_rank: float = 0.0   # 0=oldest session in scan .. 1=newest (recency boost input)
    score: float = 0.0
    coverage: float = 0.0       # fraction of distinct query terms matched
    matched: int = 0            # count of distinct query terms matched


# ---------------------------------------------------------------------------- helpers
def safe_mtime(p) -> float:
    try:
        return os.path.getmtime(p)
    except OSError:
        return 0.0


def peek_type(head: str) -> str | None:
    m = re.search(r'"type"\s*:\s*"([^"]+)"', head[:600])
    return m.group(1) if m else None


def iso_date(ts, fallback_path=None) -> str:
    """ISO timestamp string -> YYYY-MM-DD; fall back to the file's mtime date, else '?'."""
    if isinstance(ts, str) and ts:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except ValueError:
            pass
    if fallback_path:
        mt = safe_mtime(fallback_path)
        if mt:
            return datetime.fromtimestamp(mt).strftime("%Y-%m-%d")
    return "?"


def iter_lines(path: Path):
    """Yield (line_no, raw_record_or_None, head_str), 1-based by physical line.

    Bounded read (verbatim from rehydrate): readline(HUGE_LINE+1) never pulls more than the cap
    into memory, so a multi-hundred-MB record is peeked (head only) and drained, never fully
    parsed. A vanished/locked file is skipped rather than crashing the run.
    """
    try:
        fh = path.open("r", errors="replace")
    except OSError:
        return
    with fh:
        i = 0
        while True:
            try:
                chunk = fh.readline(HUGE_LINE + 1)
            except OSError:
                return
            if not chunk:
                break
            i += 1
            if len(chunk) > HUGE_LINE and not chunk.endswith("\n"):
                head = chunk[:600]
                while True:                       # drain the rest of this physical line
                    more = fh.readline(HUGE_LINE)
                    if not more or more.endswith("\n"):
                        break
                yield i, None, head
                continue
            line = chunk.rstrip("\n")
            if not line.strip():
                continue
            try:
                yield i, json.loads(line), line[:600]
            except json.JSONDecodeError:
                yield i, None, line[:600]


def parse_duration(s) -> int:
    """'24h' / '2d' / '90m' / a bare seconds int -> seconds. 0/None -> 0 (no floor)."""
    if not s:
        return 0
    s = str(s).strip().lower()
    if s.isdigit():
        return int(s)
    units = {"m": 60, "h": 3600, "d": 86400}
    if len(s) > 1 and s[-1] in units and s[:-1].isdigit():
        return int(s[:-1]) * units[s[-1]]
    return 0


# ---------------------------------------------------------------------------- Claude store
# (storage + extraction primitives carried over verbatim from rehydrate's Claude adapter; format
# notes in references/claude.md)
TUI_TYPES = {"file-history-snapshot", "permission-mode", "mode", "ai-title"}


def encode_cwd(cwd: str) -> str:
    return cwd.replace("/", "-").replace(".", "-")


def project_dir(cwd: str) -> Path:
    return HOME / ".claude" / "projects" / encode_cwd(cwd)


def candidates(cwd: str):
    proj = project_dir(cwd)
    files = sorted(proj.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True) if proj.is_dir() else []
    return proj, files


def current_session_id() -> str | None:
    return os.environ.get("CLAUDE_CODE_SESSION_ID")


def is_interactive(path, probe=150) -> bool:
    """True iff this transcript is a user-spawned interactive session (not a relay/headless/
    `claude -p` run). Interactive sessions emit a TUI_TYPES record (typically record #1); relay
    sessions never do. Probe-bounded so a long relay file is not scanned in full."""
    n = 0
    for ln, rec, head in iter_lines(path):
        t = rec.get("type") if rec is not None else peek_type(head)
        if t in TUI_TYPES:
            return True
        n += 1
        if n >= probe:
            break
    return False


def events(path):
    """Normalize a Claude transcript into user/assistant/tool Events (verbatim extraction from
    rehydrate, minus the boundary cutoff — recall reads the FULL file). A type:"user" record
    carrying tool_result blocks is a TOOL OUTPUT turn, not a genuine user message: kept apart so
    the user-vs-agent attribution stays clean."""
    for ln, rec, head in iter_lines(path):
        if rec is None:
            continue
        t = rec.get("type")
        if t not in ("user", "assistant"):
            continue
        if t == "user" and rec.get("isCompactSummary"):
            continue          # the "session is being continued…" summary is not a genuine turn
        sc = bool(rec.get("isSidechain"))
        ts = rec.get("timestamp")
        msg = rec.get("message") or {}
        content = msg.get("content")
        text_parts, tool_out, paths, command = [], [], [], None
        if isinstance(content, str):
            text_parts.append(content)
        elif isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")
                if bt == "text":
                    text_parts.append(b.get("text", ""))
                elif bt == "tool_use":
                    inp = b.get("input") or {}
                    for k in ("file_path", "path", "notebook_path"):
                        if inp.get(k):
                            paths.append(inp[k])
                    if b.get("name") == "Bash" and inp.get("command"):
                        command = inp["command"]
                elif bt == "tool_result":
                    rc = b.get("content")
                    if isinstance(rc, list):
                        rc = " ".join(x.get("text", "") for x in rc if isinstance(x, dict))
                    if isinstance(rc, str) and rc:
                        tool_out.append(rc)
        if t == "assistant":
            if any(text_parts):
                yield Event(ln, "assistant", "assistant_message", clip(" ".join(text_parts)), ts, sc)
            elif command:
                yield Event(ln, "assistant", "command", clip(command, 400), ts, sc)
            elif paths:
                yield Event(ln, "assistant", "file_op", clip(" ".join(paths), 400), ts, sc)
        else:  # user record
            if tool_out and not any(p.strip() for p in text_parts):
                yield Event(ln, "tool", "command_output", clip(" ".join(tool_out)), ts, sc)
            elif any(text_parts):
                yield Event(ln, "user", "user_message", clip(" ".join(text_parts)), ts, sc)


# ---------------------------------------------------------------------------- retrieval
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "of", "to", "in", "on", "for",
    "with", "as", "is", "are", "was", "were", "be", "been", "do", "does", "we", "i", "you",
    "it", "this", "that", "these", "those", "my", "our", "your", "me", "us", "what", "when", "how",
    "why", "where", "which", "about", "did", "decide", "decided", "remember", "mentioned", "said",
    "earlier", "before", "thing", "things", "discuss", "discussed", "talked", "talk", "recall",
    "use", "using", "want", "wanted", "go", "back", "already", "settle", "settled", "agreed",
    "agree", "approach", "should", "would", "could", "can", "will", "let", "lets",
}
# trigger boilerplate stripped from the query before tokenizing (longest-first)
_TRIGGER_PHRASES = [
    "what did we decide about", "what did we decide on", "what did we decide",
    "what was our decision about", "what was the decision about", "the decision we made about",
    "the approach we agreed on", "the thing we discussed about", "the thing we discussed",
    "remember when we", "remember that we", "as i mentioned earlier", "as i mentioned",
    "like i said before", "like i said", "as i said earlier", "as i said",
    "didn't we already", "didnt we already", "what was my preference for", "my preference for",
    "go back to what we", "the thing about", "that thing about", "what we agreed on",
    "what we decided about", "what we said about", "remember when", "as we discussed",
]
_CUE = re.compile(r"\b(decided|chose|choose|we'll|we will|let's|lets|the plan is|because|ruled out|"
                  r"won't work|wont work|instead of|instead|actually|don't|do not|prefer|preference|"
                  r"use .+ not |stop |revert|cap |default to|agreed|settled on)\b", re.I)
# Narrow ATTRIBUTION cue: only these license the "you decided" wording in the confirmation line.
# The broad _CUE above drives RANKING only — words like "because"/"actually"/"cap" must not relabel
# ordinary explanatory text as a decision.
_DECISION_ATTRIB = re.compile(r"\b(decided|chose|agreed|settled on|ruled out|prefer|go with|"
                              r"let's use|lets use|don't use|do not use|use .+ not )\b", re.I)


# Harness-injected user-role turns that are NOT genuine user statements — skill-load preambles,
# slash-command echoes, system reminders, compaction summaries. They share the user role but are
# noise (and were the dominant wrong-match source in testing: a "Base directory for this skill:"
# preamble out-ranking the real decision). Dropped from the corpus before ranking.
_INJECTED_PREFIXES = (
    "base directory for this skill:",
    "caveat: the messages below were generated by the user",
    "<system-reminder>",
    "<command-name>",
    "this session is being continued from a previous conversation",
    "read and execute this relay request",
)


def is_injected(text: str) -> bool:
    t = text.lstrip().lower()
    return any(t.startswith(p) for p in _INJECTED_PREFIXES) or "<command-name>" in t[:200]


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, with identifier-aware sub-splitting (camelCase, snake_case, kebab,
    dotted paths) so 'authRetry' / 'auth_retry' / 'auth-retry' all reach the terms 'auth'+'retry'.
    Stopwords dropped; tokens shorter than 2 chars dropped."""
    out = []
    for w in re.findall(r"[A-Za-z0-9_./\-]+", text):
        wl = w.lower()
        out.append(wl)
        for cam in re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", w):
            cl = cam.lower()
            if cl != wl:
                out.append(cl)
        for part in re.split(r"[_./\-]+", wl):
            if part and part != wl:
                out.append(part)
    return [t for t in out if len(t) >= 2 and t not in _STOPWORDS]


def normalize_query(q: str) -> tuple[str, list[str]]:
    """Strip recall boilerplate, return (cleaned_text, content_terms). Tokenize the CLEANED text so
    boilerplate words not in _STOPWORDS (e.g. 'decision', 'made') don't leak in as query terms and
    pull up generic decision-chatter; trigger phrases strip as prefixes, so identifiers after them
    survive into `cleaned`."""
    ql = " " + q.lower().strip() + " "
    for ph in sorted(_TRIGGER_PHRASES, key=len, reverse=True):
        ql = ql.replace(" " + ph + " ", " ")
    cleaned = re.sub(r"\s+", " ", ql).strip()
    return cleaned, tokenize(cleaned)


def build_corpus(cwd, *, include_all, since_secs, max_files, exclude_session):
    """Scan the project's transcripts (interactive-only by default, newest-first) into Docs.
    Returns (docs, stats). Stateless: no persistent index — the searchable user/assistant text is a
    thin sliver of the on-disk bytes. The CURRENT session is excluded by default (its content is
    already in live context, and its just-typed query echo would otherwise self-match)."""
    proj, files = candidates(cwd)
    now = time.time()
    selected = []
    skipped_noninteractive = skipped_old = excluded_current = 0
    truncated = False
    for f in files:                                   # mtime-desc
        if exclude_session and f.stem == exclude_session:
            excluded_current += 1
            continue
        if since_secs and (now - safe_mtime(f)) > since_secs:
            skipped_old += 1
            continue
        if not include_all and not is_interactive(f):
            skipped_noninteractive += 1
            continue
        selected.append(f)
        if max_files and len(selected) >= max_files:
            truncated = True       # hit the recency-window cap — older sessions went unscanned
            break
    docs = []
    nfiles = len(selected)
    for idx, f in enumerate(selected):
        # session_rank: 1.0 for the newest selected file .. ~0 for the oldest
        rank = 1.0 - (idx / nfiles) if nfiles > 1 else 1.0
        sid = f.stem
        for e in events(f):
            if e.sidechain or e.role not in ("user", "assistant") or not e.text:
                continue
            if is_injected(e.text):
                continue
            toks = tokenize(e.text)
            if not toks:
                continue
            docs.append(Doc(sid, str(f), e.line, e.role, e.text, iso_date(e.ts, f), toks, rank))
    stats = {"files_total": len(files), "files_scanned": nfiles, "docs": len(docs),
             "skipped_noninteractive": skipped_noninteractive, "skipped_old": skipped_old,
             "excluded_current": excluded_current, "truncated": truncated}
    return docs, stats


def bm25_rank(docs, query_terms, cleaned_query):
    """Score every Doc with BM25 + user/cue/phrase/recency boosts. Returns scored Docs sorted
    desc, each annotated with .score and .coverage (fraction of distinct query terms matched)."""
    if not docs or not query_terms:
        return []
    N = len(docs)
    df = Counter()
    for d in docs:
        for t in set(d.tokens):
            df[t] += 1
    qset = set(query_terms)
    idf = {t: math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5)) for t in qset if t in df}
    if not idf:
        return []
    avgdl = sum(len(d.tokens) for d in docs) / N
    scored = []
    for d in docs:
        tf = Counter(d.tokens)
        dl = len(d.tokens)
        base, matched = 0.0, 0
        for t in qset:
            if t not in idf or tf[t] == 0:
                continue
            matched += 1
            f = tf[t]
            base += idf[t] * (f * (BM25_K1 + 1)) / (f + BM25_K1 * (1 - BM25_B + BM25_B * dl / avgdl))
        if base <= 0:
            continue
        boost = 1.0
        if d.role == "user":
            boost *= USER_BOOST
        if _CUE.search(d.text):
            boost *= CUE_BOOST
        if cleaned_query and len(cleaned_query.split()) >= 2 and cleaned_query in d.text.lower():
            boost *= PHRASE_BOOST   # real multi-word phrase, not a spurious substring ("auth"⊂"author")
        boost *= 1.0 + RECENCY_MAX_BOOST * d.session_rank
        d.score = base * boost
        d.coverage = matched / len(qset)
        d.matched = matched
        scored.append(d)
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored


def dedupe(scored, limit):
    """Keep the highest-scoring hit per (session, first-80-chars) so adjacent duplicate turns and
    re-pastes don't crowd out distinct candidates."""
    seen, out = set(), []
    for d in scored:
        key = (d.session, d.text[:80].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
        if len(out) >= limit:
            break
    return out


def classify(top, second_score, n_terms):
    """confident | ambiguous | no_match — gated on matched-term count + query coverage (raw BM25
    score is unnormalized and not a usable floor; thresholds calibrated on eval/gold.jsonl).
    `second_score` is the best DISTINCT competitor from the FULL ranked list (not the post-dedupe/
    `--k` slice), so a `--k 1` call or a deduped near-tie can't widen the margin.

      - no hit / nothing covered          → no_match
      - 1-term query                      → at most ambiguous (a lone lexical term is too thin to
                                             silent-load; surface it, ask)
      - multi-term, <2 matched OR <40% cov → no_match (incidental overlap — don't fabricate; this is
                                             what rejects off-topic queries that share one stray word)
      - ≥60% cov AND clear lead           → confident; else ambiguous
    (an assistant-role top is additionally capped at ambiguous by the caller.)"""
    if not top or top.coverage == 0:
        return "no_match"
    if n_terms <= 1:
        return "ambiguous"
    if top.matched < 2 or top.coverage < CAND_MIN_COVERAGE:
        return "no_match"
    margin_ok = (second_score <= 0.0) or (top.score >= CONFIDENT_MARGIN * second_score)
    if top.coverage >= CONFIDENT_COVERAGE and margin_ok:
        return "confident"
    return "ambiguous"


def run_query(docs, q, k):
    """Core retrieval shared by `search` and the eval harness: a query + a prebuilt corpus →
    (status, ordered hit Docs, query terms). Build the corpus ONCE and call this per query to score
    many queries cheaply. Margin is judged against the best DISTINCT competitor in the FULL ranked
    list (not the post-dedupe/`--k` slice), so a k=1 call or a deduped near-tie can't widen it; an
    assistant-role top is capped at ambiguous so a past agent proposal is never silent-loaded."""
    cleaned, terms = normalize_query(q)
    if not terms:
        return "no_match", [], terms
    scored = bm25_rank(docs, terms, cleaned)
    hits = dedupe(scored, k)
    if not hits:
        return "no_match", [], terms
    top = hits[0]
    top_key = (top.session, top.text[:80].lower())
    second_score = next((d.score for d in scored if (d.session, d.text[:80].lower()) != top_key), 0.0)
    status = classify(top, second_score, len(set(terms)))
    if status == "confident" and top.role != "user":
        status = "ambiguous"
    return status, hits, terms


def gist_of(d: Doc) -> str:
    return clip(d.text, GIST_CHARS)


def confirmation_line(d: Doc, status: str) -> str:
    """One-line, role-aware. 'you' for user turns; agent turns are flagged unconfirmed so a past
    model statement is never recalled as the user's ground truth."""
    anchor = f" L{d.line}"
    if d.role == "user":
        verb = "you decided" if _DECISION_ATTRIB.search(d.text) else "you said"
    else:
        verb = "I noted (agent turn — unconfirmed by you)"
    prefix = "Recalled" if status == "confident" else "Best guess (ambiguous)"
    return f"{prefix} ({d.date}, session {d.session[:8]}{anchor}): {verb}: {gist_of(d)}"


def doc_json(d: Doc, rank: int, status: str) -> dict:
    return {
        "rank": rank, "score": round(d.score, 2), "coverage": round(d.coverage, 2),
        "session": d.session, "session_short": d.session[:8], "date": d.date,
        "transcript": d.transcript, "line": d.line, "anchor": f"L{d.line}", "role": d.role,
        "gist": gist_of(d),
        "confirmation": confirmation_line(d, status),   # per-candidate, so agent-rerank prints THIS one
        "context_hint": f"show --session {d.session[:8]} --line {d.line} for surrounding turns",
    }


# ---------------------------------------------------------------------------- commands
def cmd_search(args):
    exclude = None if args.include_current else current_session_id()
    docs, stats = build_corpus(args.cwd, include_all=args.all, exclude_session=exclude,
                               since_secs=parse_duration(args.since), max_files=args.max_files)
    status, hits, terms = run_query(docs, args.q, args.k)
    if not terms:
        print(json.dumps({"status": "no_match", "query": redact(args.q), "cwd": args.cwd,
                          "reason": "no content terms left after stripping recall boilerplate — "
                                    "pass a more specific topic", "stats": stats,
                          "candidates": []}, indent=2))
        return 13
    if not hits:
        print(json.dumps({"status": "no_match", "query": redact(args.q), "cwd": args.cwd,
                          "stats": stats, "candidates": []}, indent=2))
        return 13
    top = hits[0]
    out = {
        "status": status,
        "query": redact(args.q),
        "cwd": args.cwd,
        "encoded_cwd": encode_cwd(args.cwd),
        "confirmation": confirmation_line(top, status),
        "stats": stats,
        "candidates": [doc_json(d, i + 1, status) for i, d in enumerate(hits)],
    }
    if _redaction_count:
        out["redactions"] = _redaction_count
    print(json.dumps(out, indent=2))
    return 0 if status == "confident" else (11 if status == "ambiguous" else 13)


def cmd_show(args):
    """Fetch the redacted surrounding turns at a session + line anchor (the agent's surgical
    deep-read, so it never reads the whole JSONL)."""
    proj, files = candidates(args.cwd)
    exact = [f for f in files if f.stem == args.session]
    pref = exact or [f for f in files if f.stem.startswith(args.session)]
    if not pref:
        print(json.dumps({"status": "not_found",
                          "reason": f"no session {args.session} under {proj}"}, indent=2))
        return 11
    if len(pref) > 1:                                  # ambiguous prefix — don't silently pick one
        print(json.dumps({"status": "ambiguous_session",
                          "reason": f"{len(pref)} sessions match prefix {args.session!r} — pass a "
                                    f"longer id", "candidates": [f.stem for f in pref[:5]]}, indent=2))
        return 11
    path = pref[0]
    lo, hi = args.line - args.before, args.line + args.after
    window, used = [], 0
    for e in events(path):
        if e.sidechain or not e.text or is_injected(e.text) or not (lo <= e.line <= hi):
            continue
        s = clip(e.text, args.max_chars)
        used += len(s)
        window.append({"line": e.line, "anchor": f"L{e.line}", "role": e.role,
                       "kind": e.kind, "date": iso_date(e.ts, path), "text": s})
        if used > args.max_chars:
            break
    out = {"status": "ok" if window else "empty", "session": path.stem,
           "session_short": path.stem[:8], "transcript": str(path),
           "range": f"L{lo}-L{hi}", "turns": window}
    if _redaction_count:
        out["redactions"] = _redaction_count
    print(json.dumps(out, indent=2))
    return 0 if window else 13


def cmd_doctor(args):
    cwd = args.cwd
    proj, files = candidates(cwd)
    print(f"cwd: {cwd}")
    print(f"encoded: {encode_cwd(cwd)}")
    print(f"project dir: {proj} (exists={proj.is_dir()})")
    print(f"transcripts: {len(files)}")
    print(f"current session id (env): {current_session_id()}")
    inter = 0
    for f in files[:args.show_candidates]:
        tag = "interactive" if is_interactive(f) else "relay/headless"
        if tag == "interactive":
            inter += 1
        print(f"  {f.stem[:8]}  {tag:14}  mtime={int(safe_mtime(f))}")
    print(f"(interactive among first {min(args.show_candidates, len(files))}: {inter})")


def main():
    p = argparse.ArgumentParser(prog="recall", description=__doc__.splitlines()[0])
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--cwd", default=os.getcwd())
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", parents=[common])
    s.add_argument("--q", required=True)
    s.add_argument("--k", type=int, default=DEFAULT_K)
    s.add_argument("--since", default=None, help="recency floor, e.g. 30d/12h (default: no floor)")
    s.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES,
                   help=f"cap files scanned, newest-first (default {DEFAULT_MAX_FILES} for latency; "
                        f"0 = every past session — escalate here on a miss)")
    s.add_argument("--all", action="store_true", help="include relay/headless sessions too")
    s.add_argument("--include-current", action="store_true",
                   help="also search the current session (default: excluded — it's in live context)")

    sh = sub.add_parser("show", parents=[common])
    sh.add_argument("--session", required=True, help="session uuid or 8-char prefix")
    sh.add_argument("--line", type=int, required=True)
    sh.add_argument("--before", type=int, default=3)
    sh.add_argument("--after", type=int, default=6)
    sh.add_argument("--max-chars", type=int, default=4000)

    dr = sub.add_parser("doctor", parents=[common])
    dr.add_argument("--show-candidates", type=int, default=12)

    args = p.parse_args()
    args.cwd = os.path.abspath(os.path.expanduser(args.cwd))
    try:
        rc = {"search": cmd_search, "show": cmd_show, "doctor": cmd_doctor}[args.cmd](args)
        sys.exit(rc or 0)
    except OSError as e:
        print(f"IO_ERROR: {e} (a transcript may have been rotated mid-read; retry)", file=sys.stderr)
        sys.exit(14)


if __name__ == "__main__":
    main()

"""Persistent, incremental inverted index over one source's transcripts (claude or codex).

One SQLite file per source under $RECALL_CACHE_DIR/index/. Each search stats the transcript
files, parses only the bytes appended since the last pass (the backends' resumable cursors),
and reads posting lists only for the query's terms; message text is read only for rendered
evidence. A file that shrank or whose last indexed bytes changed is re-indexed whole.
Without RECALL_CACHE_DIR the index lives in memory for the one call (same code path).

The rows handed to retrieve() match the in-memory loader's except that `token_counts` holds
only the query's terms and `length` carries the message's full token count.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from array import array
from collections import Counter, defaultdict
from datetime import datetime
from functools import partial
from pathlib import Path

SCHEMA = 2
TAIL = 4096          # bytes before the cursor that must be unchanged for an append-only update


def _blob(pairs) -> bytes:
    data = array("I")
    for message, count in pairs:
        data.extend((message, count))
    if sys.byteorder != "little":
        data.byteswap()
    return data.tobytes()


def _pairs(blob: bytes):
    data = array("I")
    data.frombytes(blob)
    if sys.byteorder != "little":
        data.byteswap()
    return zip(data[::2], data[1::2])


class Index:
    def __init__(self, source: str, backend):
        self.source = source
        self.api = backend(source)
        self.language = backend("claude")        # one tokenizer for both stores
        root = os.environ.get("RECALL_CACHE_DIR")
        if root:
            directory = Path(root).expanduser() / "index"
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            directory.chmod(0o700)
            target = directory / f"{source}.sqlite"
        else:
            target = ":memory:"
        self.db = sqlite3.connect(target, timeout=300, isolation_level=None)
        if root:
            os.chmod(target, 0o600)
        for pragma in ("journal_mode=WAL", "synchronous=NORMAL", "temp_store=MEMORY",
                       "cache_size=-262144", "mmap_size=4294967296"):
            self.db.execute(f"PRAGMA {pragma}")
        version = f"{SCHEMA}:{self.api.PARSER_VERSION}:{self.language.PARSER_VERSION}"
        self.db.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
        found = self.db.execute("SELECT value FROM meta WHERE key='version'").fetchone()
        if not found or found[0] != version:
            self.db.execute("BEGIN IMMEDIATE")
            for table in ("files", "msgs", "postings"):
                self.db.execute(f"DROP TABLE IF EXISTS {table}")
            for statement in (
                    "CREATE TABLE files(id INTEGER PRIMARY KEY, path TEXT UNIQUE, size INT, mtime_ns INT,"
                    " cursor TEXT, info TEXT, terms TEXT, tail BLOB)",
                    "CREATE TABLE msgs(id INTEGER PRIMARY KEY, file INT, session TEXT, line INT, ord INT,"
                    " role TEXT, ts TEXT, epoch REAL, date TEXT, place TEXT, key TEXT, source TEXT,"
                    " branch TEXT, mtime REAL, length INT, text TEXT)",
                    "CREATE INDEX msgs_file ON msgs(file)",
                    "CREATE TABLE postings(term TEXT, file INT, data BLOB, PRIMARY KEY(term, file)) WITHOUT ROWID"):
                self.db.execute(statement)
            self.db.execute("INSERT OR REPLACE INTO meta VALUES('version', ?)", (version,))
            self.db.execute("COMMIT")

    # ------------------------------------------------------------------ refresh
    def listing(self, cwd: str) -> list[tuple[Path, int, int]]:
        if self.source == "claude":
            _, paths = self.api.candidates(cwd, "all")
        else:
            root = self.api.session_root()
            paths = self.api.all_files(root) + self.api.all_files(root.parent / "archived_sessions")
        out = []
        for path in paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            out.append((path, stat.st_size, stat.st_mtime_ns))
        return out

    def refresh(self, cwd: str) -> None:
        listed = self.listing(cwd)
        known = {row[1]: row for row in self.db.execute(
            "SELECT id, path, size, mtime_ns, cursor, info, terms, tail FROM files")}
        changed = [item for item in listed if (lambda row: not row or row[2] != item[1] or row[3] != item[2])(
            known.get(str(item[0])))]
        gone = set(known) - {str(path) for path, _, _ in listed}
        if not changed and not gone:
            return
        self.db.execute("BEGIN IMMEDIATE")
        try:
            for path in gone:
                self._drop(known[path])
            for path, size, mtime_ns in changed:
                self._update(path, size, mtime_ns, known.get(str(path)))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _drop(self, row) -> None:
        file_id, terms = row[0], row[6]
        if terms:
            self.db.executemany("DELETE FROM postings WHERE term=? AND file=?",
                                ((term, file_id) for term in terms.split("\0")))
        self.db.execute("DELETE FROM msgs WHERE file=?", (file_id,))
        self.db.execute("DELETE FROM files WHERE id=?", (file_id,))

    def _appended(self, path: Path, size: int, row) -> bool:
        if not row:
            return False
        offset = json.loads(row[4])["offset"]
        tail = row[7] or b""
        if size < offset:
            return False
        try:
            with path.open("rb") as handle:
                handle.seek(offset - len(tail))
                return handle.read(len(tail)) == tail
        except OSError:
            return False

    def _update(self, path: Path, size: int, mtime_ns: int, row) -> None:
        api, language = self.api, self.language
        if self._appended(path, size, row):
            file_id = row[0]
            cursor, info = json.loads(row[4]), json.loads(row[5])
            terms = set(row[6].split("\0")) if row[6] else set()
        else:
            if row:
                self._drop(row)
            file_id = self.db.execute("INSERT INTO files(path) VALUES(?)", (str(path),)).lastrowid
            cursor = api.new_cursor() if self.source == "claude" else api.new_cursor(path)
            info, terms = {}, set()
        records = []
        if self.source == "claude":
            for line, role, text, date, tokens, project in api.file_rows(path, cursor):
                records.append(((path.stem, line, line, role, None, None, date, project, None, None, None,
                                 None), text, Counter(tokens)))
            if not info.get("interactive"):
                info["interactive"] = api.is_interactive(path)
            info["title"] = api.cursor_title(cursor)
        else:
            if cursor["line"] <= 64:              # the inventory metadata is read from the head
                head = api.read_file_meta(path)
                info["head"] = {"session_id": head.session_id, "thread_source": head.thread_source}
            turns, stats = api.extract_turns(path, cursor=cursor)
            total = api.Stats(**info.get("stats", {}))
            total.add(stats)
            info["stats"] = total.as_dict()
            for turn in turns:
                try:
                    epoch = datetime.fromisoformat(turn.timestamp.replace("Z", "+00:00")).timestamp()
                except (ValueError, AttributeError):
                    epoch = turn.mtime
                records.append(((turn.session_id, turn.line, turn.ordinal, turn.role, turn.timestamp, epoch,
                                 turn.timestamp[:10], turn.cwd, turn.item_id, turn.thread_source,
                                 turn.git_branch, turn.mtime), turn.text, Counter(language.tokenize(turn.text))))
        postings = defaultdict(list)
        for fields, text, counts in records:
            message = self.db.execute(
                "INSERT INTO msgs(file, session, line, ord, role, ts, epoch, date, place, key, source, branch,"
                " mtime, length, text) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (file_id, *fields, sum(counts.values()), text)).lastrowid
            for term, count in counts.items():
                postings[term].append((message, count))
        merged = []
        for term, pairs in postings.items():
            blob = _blob(pairs)
            if term in terms:          # SQL `||` would yield TEXT, so blobs are joined here
                blob = self.db.execute("SELECT data FROM postings WHERE term=? AND file=?",
                                       (term, file_id)).fetchone()[0] + blob
            merged.append((term, file_id, blob))
        self.db.executemany("INSERT OR REPLACE INTO postings(term, file, data) VALUES(?,?,?)", merged)
        terms.update(postings)
        try:
            with path.open("rb") as handle:
                handle.seek(max(0, cursor["offset"] - TAIL))
                tail = handle.read(min(TAIL, cursor["offset"]))
        except OSError:
            tail = b""
        self.db.execute("UPDATE files SET size=?, mtime_ns=?, cursor=?, info=?, terms=?, tail=? WHERE id=?",
                        (size, mtime_ns, json.dumps(cursor), json.dumps(info), "\0".join(sorted(terms)), tail,
                         file_id))

    # ------------------------------------------------------------------ query
    def counts(self, terms) -> dict[int, dict[str, int]]:
        found = defaultdict(dict)
        terms = list(terms)
        for start in range(0, len(terms), 500):
            chunk = terms[start:start + 500]
            for term, blob in self.db.execute(
                    f"SELECT term, data FROM postings WHERE term IN ({','.join('?' * len(chunk))})", chunk):
                for message, count in _pairs(blob):
                    found[message][term] = count
        return found

    def text(self, message: int) -> str:
        return self.db.execute("SELECT text FROM msgs WHERE id=?", (message,)).fetchone()[0]

    def rows(self, cwd: str, terms, exclude: str | None):
        """(rows in the in-memory loader's order, metadata) for retrieve()."""
        self.refresh(cwd)
        files = {row[0]: row for row in self.db.execute("SELECT id, path, mtime_ns, info FROM files")}
        info = {file_id: json.loads(row[3]) for file_id, row in files.items()}
        counts = self.counts(terms)
        messages = defaultdict(list)
        for row in self.db.execute("SELECT id, file, session, line, ord, role, ts, epoch, date, place, key,"
                                   " source, branch, mtime, length FROM msgs ORDER BY id"):
            messages[row[1]].append(row)
        return (self._claude if self.source == "claude" else self._codex)(files, info, messages, counts, exclude)

    def _claude(self, files, info, messages, counts, exclude):
        ordered = sorted(files, key=lambda f: files[f][2], reverse=True)       # candidates(): newest first
        selected = [f for f in ordered if info[f].get("interactive") and Path(files[f][1]).stem != exclude]
        rows = []
        for file_id in selected:
            path = files[file_id][1]
            title = info[file_id].get("title") or ""
            for m in messages[file_id]:
                doc = partial(self._doc, path, m, title)
                rows.append(dict(session=m[2], role=m[5], date=m[8], line=m[3], project=m[9], order=m[3],
                                 title=title or None, token_counts=counts.get(m[0], {}), length=m[14],
                                 fetch=partial(self.text, m[0]), render=doc))
        stats = {"scope": "all", "files_total": len(files), "files_scanned": len(selected), "docs": len(rows),
                 "skipped_noninteractive": sum(1 for f in ordered if not info[f].get("interactive")),
                 "skipped_old": 0, "excluded_current": sum(1 for f in ordered if Path(files[f][1]).stem == exclude),
                 "truncated": False}
        return rows, {"stats": stats, "current_task_exclusion": "resolved" if exclude else "unresolved"}

    def _doc(self, path, m, title):
        doc = self.api.Doc(m[2], path, m[3], m[5], self.text(m[0]), m[8], [], m[9], 0.0, title=title)
        return self.api.doc_json(doc, 0)

    def _codex(self, files, info, messages, counts, exclude):
        api = self.api
        root = api.session_root()
        archived = str(root.parent / "archived_sessions")
        human = [f for f in files if api._is_human_source(info[f].get("head", {}).get("thread_source", ""))]
        # file_inventory(): live sessions newest first, then archived newest first; first copy wins.
        human.sort(key=lambda f: (files[f][1].startswith(archived + os.sep), -files[f][2]))
        titles = api.thread_titles(root)
        seen, kept, total = set(), [], api.Stats()
        for file_id in human:
            total.add(api.Stats(**info[file_id].get("stats", {})))
            for m in messages[file_id]:
                if (m[2], m[10]) in seen:
                    continue
                seen.add((m[2], m[10]))
                kept.append((m, files[file_id][1]))
        kept.sort(key=lambda item: (item[0][7], item[0][4], item[1], item[0][3]))   # _turn_order
        rows = []
        for m, path in kept:
            if exclude and m[2] == exclude:
                continue
            rows.append(dict(session=m[2], role=m[5], timestamp=m[6], cwd=m[9], locator={"item_id": m[10]},
                             title=titles.get(m[2]), date=m[6][:10], order=m[4], token_counts=counts.get(m[0], {}),
                             length=m[14], fetch=partial(self.text, m[0]), render=partial(self._turn, path, m, root)))
        return rows, {"stats": total.as_dict(),
                      "current_task_exclusion": "resolved" if exclude else "unresolved",
                      "excluded_current_task": exclude or None}

    def _turn(self, path, m, root):
        turn = self.api.Turn(session_id=m[2], path=Path(path), line=m[3], ordinal=m[4], item_id=m[10],
                             timestamp=m[6], role=m[5], text=self.text(m[0]), cwd=m[9], thread_source=m[11],
                             git_branch=m[12], mtime=m[13])
        return self.api.turn_json(turn, root, 0)

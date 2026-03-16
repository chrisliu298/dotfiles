---
name: session-recovery
description: >
  Recover Claude Code or Codex sessions after a directory has been renamed or
  moved. Claude Code stores session data keyed by the absolute path of the
  working directory. Codex stores sessions in a SQLite database with a cwd
  column. When a directory is renamed or moved, previous sessions become
  invisible because the path no longer matches. This skill knows exactly how
  both tools store sessions and how to fix them. Use this skill whenever the
  user mentions lost sessions, missing conversation history, renamed or moved
  directories, or wants to migrate sessions from one path to another. Also use
  when the user says "my sessions are gone", "I can't find my old conversations",
  "I renamed my project folder", or "moved my repo".
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
user-invocable: true
---

# Session Recovery After Directory Rename

This skill covers both **Claude Code** and **Codex (OpenAI)** session recovery.

---

## Part 1: Claude Code

### How Claude Code Session Storage Works

Claude Code ties all session data to the **absolute path** of the working directory. The path is encoded by replacing every `/` with `-`. For example:

```
/Users/alice/my-project  →  -Users-alice-my-project
```

This encoded path becomes a directory name under `~/.claude/projects/`. Inside it:

- **`<uuid>.jsonl`** files — conversation transcripts for each session
- **`<uuid>/`** directories — subagent data for sessions
- **`memory/`** directory — auto-memory that persists across sessions (MEMORY.md, etc.)

Additionally, **`~/.claude/history.jsonl`** contains one JSON object per user message, each with a `"project"` field holding the original absolute path and a `"sessionId"` linking it to the session file.

When you rename `/Users/alice/my-project` to `/Users/alice/my-project-v2`, Claude Code looks for sessions under `-Users-alice-my-project-v2` and finds nothing. The old sessions still exist under `-Users-alice-my-project` — they're not lost, just orphaned.

### Recovery Procedure

### Step 1: Identify the old and new paths

Ask the user for:
- **Old path**: the original directory path (before the rename/move)
- **New path**: the current directory path (after the rename/move)

If the user only knows the new path, help them find the old one by listing candidate project directories:

```bash
ls ~/.claude/projects/ | grep -i "<keyword>"
```

Each directory name is an encoded path — decode by replacing leading `-` with `/` and subsequent `-` with `/` (though be careful: hyphens that were originally in the path stay as hyphens, so eyeballing is usually needed). Show the user the candidates and ask them to confirm which one is the old project.

### Step 2: Move or merge the project directory

First, compute the encoded names and check whether the new directory already exists:

```bash
OLD_ENCODED=$(echo "<old-path>" | sed 's|/|-|g')
NEW_ENCODED=$(echo "<new-path>" | sed 's|/|-|g')
```

**Check before acting** — the approach depends on whether the new directory exists:

**Case A: New directory does NOT exist** (simple rename, most common):
```bash
mv ~/.claude/projects/"$OLD_ENCODED" ~/.claude/projects/"$NEW_ENCODED"
```

**Case B: New directory already exists** (user already started sessions at the new path — merge is needed):
```bash
# Copy session files from old into new (don't overwrite existing)
cp -n ~/.claude/projects/"$OLD_ENCODED"/*.jsonl ~/.claude/projects/"$NEW_ENCODED"/ 2>/dev/null
# Move session subdirectories (not memory)
for d in ~/.claude/projects/"$OLD_ENCODED"/*/; do
    dirname=$(basename "$d")
    if [ "$dirname" != "memory" ] && [ ! -d ~/.claude/projects/"$NEW_ENCODED"/"$dirname" ]; then
        mv "$d" ~/.claude/projects/"$NEW_ENCODED"/
    fi
done
# Memory: if both dirs have memory/MEMORY.md, show both to user and let them decide
# If only the old dir has memory, copy it over
rm -rf ~/.claude/projects/"$OLD_ENCODED"
```

Checking first avoids the pitfall where `mv` nests the old directory inside the new one (since `mv` into an existing directory creates a subdirectory rather than replacing it).

### Step 3: Update history.jsonl

Replace the old path with the new path in every matching history entry. Use an atomic write (write to temp file, then move) to avoid corrupting the history if something goes wrong:

```python
import json, shutil, tempfile, os

old_path = "<old-path>"
new_path = "<new-path>"
history_file = os.path.expanduser("~/.claude/history.jsonl")

updated = 0
lines = []
with open(history_file) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if d.get("project") == old_path:
            d["project"] = new_path
            updated += 1
        lines.append(json.dumps(d))

with tempfile.NamedTemporaryFile(
    mode="w", dir=os.path.dirname(history_file), delete=False, suffix=".jsonl"
) as tmp:
    tmp.write("\n".join(lines) + "\n")
    tmp_path = tmp.name

shutil.move(tmp_path, history_file)
print(f"Updated {updated} history entries")
```

### Step 4: Verify

1. List the new project directory to confirm session files are present
2. Run `claude --resume` or check `/history` to confirm old sessions appear
3. If there was memory under the old path, confirm `memory/MEMORY.md` is present in the new project directory

### Step 5: Clean up

After verification, remove any leftover old project directory (only relevant for Case B merges — Case A `mv` already removed it):

```bash
rm -rf ~/.claude/projects/"$OLD_ENCODED"
```

### Step 6: Report

Tell the user:
- How many session files were recovered
- How many history entries were updated
- Whether memory was preserved
- That they should restart Claude Code (exit and re-enter) for changes to take full effect

### Edge Cases

- **Path contains hyphens**: The encoding is ambiguous (`my-project` and `my/project` both produce `-my-project`). In practice this rarely matters because full absolute paths almost never collide. If it does, list directory contents and let the user confirm.
- **Multiple renames**: If the directory was renamed more than once, there may be multiple orphaned project directories. Recover each one in sequence, merging into the final path.
- **Subpath renames**: If a parent directory was renamed (e.g., `~/projects/` → `~/repos/`), multiple project directories may need updating. Search for all that match the old prefix and batch-update them.
- **Memory conflicts**: If both old and new project dirs have `memory/MEMORY.md`, show both to the user and let them decide how to merge.

---

## Part 2: Codex (OpenAI)

### How Codex Session Storage Works

Codex uses a fundamentally different architecture from Claude Code. Instead of encoding the working directory into a filesystem path, Codex stores everything in a **centralized SQLite database** with the working directory as a column value.

#### Storage locations

| Component | Location | Format |
|---|---|---|
| Session transcripts | `~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<uuid>.jsonl` | JSONL (one event per line) |
| Session metadata | `~/.codex/state_5.sqlite` → `threads` table | SQLite |
| User message history | `~/.codex/history.jsonl` | JSONL with `session_id`, `ts`, `text` |
| Session name index | `~/.codex/session_index.jsonl` | JSONL with `id`, `thread_name` |
| Logs | `~/.codex/logs_1.sqlite` | SQLite |
| Global state | `~/.codex/.codex-global-state.json` | JSON |
| Memories | `~/.codex/memories/` | Directory (may be empty) |

#### The `threads` table schema (key columns)

```sql
CREATE TABLE threads (
    id TEXT PRIMARY KEY,
    rollout_path TEXT NOT NULL,    -- path to the session .jsonl file
    cwd TEXT NOT NULL,             -- absolute working directory path
    title TEXT NOT NULL,
    source TEXT NOT NULL,          -- "cli", "vscode", "exec", or JSON for subagents
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    has_user_event INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    ...
);
```

The `cwd` column is how Codex associates sessions with a project directory. Session transcript files under `~/.codex/sessions/` are organized by **date** (not by project path), and each rollout `.jsonl` file also embeds `cwd` in its `session_meta` event.

Subagent threads are linked via the `source` column, which contains JSON like `{"subagent":{"thread_spawn":{"parent_thread_id":"<uuid>", ...}}}`.

#### Why sessions break after a rename

When you rename a directory, the `cwd` column in the `threads` table still holds the old path. Codex filters sessions by the current working directory, so sessions from the old path won't appear. Unlike Claude Code, the session files themselves are NOT orphaned (they're date-organized), but the metadata lookup fails.

Additionally, `~/.codex/history.jsonl` does **not** store the working directory — it only has `session_id`, `ts`, and `text` — so it does NOT need updating.

### Recovery Procedure

#### Step 1: Identify the old and new paths

Ask the user for:
- **Old path**: the original directory path (before the rename/move)
- **New path**: the current directory path (after the rename/move)

If the user only knows the new path, help them find the old one by querying the database:

```bash
sqlite3 ~/.codex/state_5.sqlite "SELECT DISTINCT cwd FROM threads ORDER BY cwd;"
```

Or search for a keyword:

```bash
sqlite3 ~/.codex/state_5.sqlite "SELECT DISTINCT cwd FROM threads WHERE cwd LIKE '%<keyword>%';"
```

#### Step 2: Preview affected threads

Before making changes, show the user what will be updated:

```bash
sqlite3 ~/.codex/state_5.sqlite \
  "SELECT id, substr(title, 1, 80), source FROM threads WHERE cwd = '<old-path>' ORDER BY created_at DESC;"
```

Count total threads (including subagent threads):

```bash
sqlite3 ~/.codex/state_5.sqlite \
  "SELECT COUNT(*) FROM threads WHERE cwd = '<old-path>';"
```

#### Step 3: Back up the database

Always back up before modifying:

```bash
cp ~/.codex/state_5.sqlite ~/.codex/state_5.sqlite.bak
```

#### Step 4: Update the `cwd` column

```bash
sqlite3 ~/.codex/state_5.sqlite \
  "UPDATE threads SET cwd = '<new-path>' WHERE cwd = '<old-path>';"
```

This updates both top-level and subagent threads in one operation.

#### Step 5 (optional): Patch rollout files

Each session `.jsonl` file has a `session_meta` event with the old `cwd` embedded. This is cosmetic — Codex uses the database for lookups, not the rollout file — but you can patch it for consistency:

```python
import json, os, glob

old_path = "<old-path>"
new_path = "<new-path>"

# Get rollout paths for affected threads
import subprocess
result = subprocess.run(
    ["sqlite3", os.path.expanduser("~/.codex/state_5.sqlite"),
     f"SELECT rollout_path FROM threads WHERE cwd = '{new_path}';"],
    capture_output=True, text=True
)

patched = 0
for rollout_path in result.stdout.strip().split("\n"):
    if not rollout_path or not os.path.exists(rollout_path):
        continue
    lines = []
    modified = False
    with open(rollout_path) as f:
        for line in f:
            d = json.loads(line)
            if d.get("type") == "session_meta" and d.get("payload", {}).get("cwd") == old_path:
                d["payload"]["cwd"] = new_path
                modified = True
            lines.append(json.dumps(d))
    if modified:
        with open(rollout_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        patched += 1

print(f"Patched {patched} rollout files")
```

#### Step 6: Verify

1. Query the database to confirm no threads remain with the old path:
   ```bash
   sqlite3 ~/.codex/state_5.sqlite "SELECT COUNT(*) FROM threads WHERE cwd = '<old-path>';"
   ```
2. Run `codex --resume` from the new directory to confirm sessions appear
3. Remove the backup once satisfied:
   ```bash
   rm ~/.codex/state_5.sqlite.bak
   ```

#### Step 7: Report

Tell the user:
- How many threads were updated (total, top-level, subagent)
- How many rollout files were patched (if Step 5 was performed)
- That `history.jsonl` did not need updating (no path field)
- That they should restart Codex for changes to take full effect

### Edge Cases

- **Subpath renames**: If a parent directory was renamed (e.g., `~/projects/` → `~/repos/`), multiple `cwd` values may need updating. Use `LIKE` to find all affected:
  ```bash
  sqlite3 ~/.codex/state_5.sqlite \
    "UPDATE threads SET cwd = REPLACE(cwd, '<old-prefix>', '<new-prefix>') WHERE cwd LIKE '<old-prefix>%';"
  ```
- **Database version**: The database filename includes a version number (`state_5.sqlite`). If Codex upgrades its schema, the filename may change. Check `ls ~/.codex/state_*.sqlite` to find the current one.
- **Multiple renames**: If the directory was renamed more than once, there may be threads under multiple old paths. Query for all distinct `cwd` values and update each.
- **WAL mode**: The SQLite database may have `-shm` and `-wal` companion files. These are normal Write-Ahead Log files. Do not delete them. The backup command (`cp`) will capture the main file; for a fully consistent backup, ensure Codex is not running, or use `sqlite3 ... ".backup backup.sqlite"`.
- **Codex Cloud / remote sessions**: The `~/.codex/sessions/` directory may contain `.remote-*` subdirectories for remote sessions. These are separate from local sessions and are not affected by local directory renames.

---
name: session-recovery
description: >
  Recover Claude Code or Codex sessions after a directory rename or move.
  Sessions become invisible when the working-directory path changes. Use when
  the user mentions lost Claude Code/Codex sessions, missing conversation
  history after a rename/move, or says "my sessions are gone", "I renamed my
  project folder", "moved my repo", or asks to migrate sessions between paths.
  Do NOT use for tmux, SSH, browser, or other non-agent sessions.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
user-invocable: true
effort: medium
---

# Session Recovery After Directory Rename

## Context

- Claude Code projects: !`ls ~/.claude/projects/ 2>/dev/null | head -20 || echo "No projects directory found"`
- Codex database: !`ls ~/.codex/state_*.sqlite 2>/dev/null || echo "No Codex database found"`
- Current directory: !`pwd`

## Prerequisite

Ask the user to close all Claude Code and Codex instances before proceeding. Session files may be written to during an active session, and modifying them concurrently risks data corruption.

This skill covers both **Claude Code** and **Codex (OpenAI)** session recovery.

---

## Part 1: Claude Code

### How Claude Code Session Storage Works

Claude Code stores project sessions under `~/.claude/projects/` using the absolute working directory path with `/` replaced by `-`.

Example: `/Users/alice/my-project` → `-Users-alice-my-project`

A project directory may contain session `.jsonl` files, subagent directories, and `memory/`. `~/.claude/history.jsonl` also stores the original path in each entry's `"project"` field.

After a rename, Claude Code looks under the new encoded path, so the old sessions still exist but no longer match the current directory.

### Recovery Procedure

### Step 1: Identify the old and new paths

Ask the user for:
- **Old path**: the original directory path (before the rename/move)
- **New path**: the current directory path (after the rename/move)

If the user only knows the new path, help them find the old one by listing candidate project directories:

```bash
ls ~/.claude/projects/ | grep -i "<keyword>"
```

Each directory name is an encoded path where `/` was replaced with `-`. This encoding is NOT reversible programmatically because literal hyphens in directory names are indistinguishable from path separators. Present the candidate directory names to the user and ask them to identify which one corresponds to their old path.

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

1. Compare the old and new directories before copying. If any `.jsonl` filenames or session subdirectory names collide, show the collisions to the user and ask how to proceed instead of silently skipping them.
2. Only after the user confirms the merge is safe:
   - Copy non-conflicting `.jsonl` files from old into new
   - Move non-conflicting session subdirectories (excluding `memory/`)
   - Handle `memory/` explicitly: if both dirs have `memory/MEMORY.md`, show both to the user and let them decide how to merge. If only the old dir has memory, copy it over.
3. Do NOT remove `~/.claude/projects/"$OLD_ENCODED"` yet — wait until Step 4 (Verify) confirms everything looks correct, then remove in Step 5 (Clean up).

### Step 3: Update history.jsonl

Replace the old path with the new path in every matching history entry. Use an atomic write (write to temp file, then move) to avoid corrupting the history if something goes wrong:

```python
import json, shutil, tempfile, os

old_path = "<old-path>"
new_path = "<new-path>"
history_file = os.path.expanduser("~/.claude/history.jsonl")

updated = 0
lines = []
if not os.path.exists(history_file):
    print("No history.jsonl found — skipping history update")
    exit(0)

with open(history_file) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            lines.append(line)  # preserve malformed lines as-is
            continue
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

#### Relevant Codex storage

- `~/.codex/state_*.sqlite` contains the `threads` table with `cwd` and `rollout_path` columns
- `~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<uuid>.jsonl` stores session events by date (not by project path)
- `~/.codex/history.jsonl` does **not** store the working directory — it does NOT need updating
- Subagent threads live in the same `threads` table, linked through the `source` column

After a rename, the `cwd` column still holds the old path, so sessions from the old path won't appear. The session files themselves are NOT orphaned (date-organized), but the metadata lookup fails.

### Recovery Procedure

Before starting, identify the current database file:

```bash
ls ~/.codex/state_*.sqlite
```

Use the actual filename found (e.g., `state_5.sqlite`, `state_6.sqlite`) throughout this procedure. If no database file exists, Codex has not been used on this machine — inform the user and skip Part 2.

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

Always back up before modifying. Use SQLite's built-in backup for WAL-safe consistency:

```bash
sqlite3 ~/.codex/state_5.sqlite ".backup ~/.codex/state_5.sqlite.bak"
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
- **WAL mode**: The SQLite database may have `-shm` and `-wal` companion files. These are normal Write-Ahead Log files. Do not delete them.
- **Codex Cloud / remote sessions**: The `~/.codex/sessions/` directory may contain `.remote-*` subdirectories for remote sessions. These are separate from local sessions and are not affected by local directory renames.

---

## Constraints

- Always close Claude Code/Codex before modifying session data (see Prerequisite).
- Do NOT modify session `.jsonl` file contents for Claude Code (only move/copy files and update history.jsonl).
- Do NOT auto-resolve memory conflicts — always show both versions to the user.
- Verify recovery succeeded before removing old directories or backups.

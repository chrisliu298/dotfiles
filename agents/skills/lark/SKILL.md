---
name: lark
description: |
  Read and edit Feishu/Lark docs, wiki pages and sheets, and read group chats, via lark-cli. Use
  for a larkoffice.com / feishu.cn URL or token, or lark-cli auth/scope errors (飞书文档、知识库、表格、群消息).
---

# lark-cli

Covers the subset we actually use (2026-08 → 10 usage: `docs +fetch` / `docs +update` are
~75% of calls; then sheets reads, chat history, wiki lookups). For anything not listed,
read the CLI's own embedded skill instead of guessing — it always matches the installed
version and costs nothing until read:

```bash
lark-cli skills read lark-doc                                  # or lark-sheets, lark-im, lark-wiki, lark-drive …
lark-cli skills read lark-doc references/lark-doc-xml.md       # one reference file
lark-cli <domain> +<shortcut> --help                           # exact flags
```

## Ground rules

- Always pass `--as user`; bot identity returns empty success on user resources.
- Success is `ok == true` (or exit 0), never `code == 0`.
- Run from a scratch directory: `docs +fetch` drops a `doc-fetch-resources/` cache in the
  cwd, and every `--output`/`@file` path must be **relative to the cwd** (absolute paths fail
  with `unsafe file path`). Images in XML use `path="@./x.png"`.
- Exit code 10 (`high-risk-write`, e.g. `drive +delete`) is a confirmation gate: ask the
  user, then append the flag named in `hint`. Never add it silently.
- A `_notice` saying a newer version exists is not an error; ignore it unless a command is
  missing (then `lark-cli update`).
- Auth problems: `lark-cli auth status`; a missing scope reads `user authorization does not
  cover the required scope(s): <scope>` — report it, the user re-authorizes (`lark-cli skills
  read lark-shared` for the login flow). Known gap: no `space:document:retrieve`, so folders
  can't be listed, but sheets inside them still read fine.

## Read the relevant procedure before acting

Resolve these bundled references from this skill root. Input/output and image paths
remain relative to the chosen scratch cwd, as above; do not write them into the skill.
Read only the procedures required by the operation.

- Fetch or locate doc content: [Read docs](references/read-docs.md), including scoped fragments and whole-table reads.
- Edit or create doc content: read [Read docs](references/read-docs.md), [Edit docs](references/edit-docs.md) and [DocxXML](references/doc-xml.md) before writing. Preserve existing resources and formatting, avoid `overwrite`, and re-fetch to verify each write; old block ids become invalid.
- Handle formulas, lists, images, media or whole-document replacement: [DocxXML](references/doc-xml.md), together with the read/edit procedures when mutating.
- Read document version history or document comments: [DocxXML's other doc commands](references/doc-xml.md), which includes `docs +history-list` and `drive +list-comments`.
- Resolve wiki nodes, list/create pages, or search: [Wiki and search](references/wiki.md). A wiki URL may hold a sheet rather than a doc.
- Read or update spreadsheet cells: [Sheets](references/sheets.md).
- Read group history, threads or contacts: [Chat](references/chat.md). Sending messages requires the user's explicit request; read the embedded `lark-im` skill for sending commands.

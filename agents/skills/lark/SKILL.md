---
name: lark
description: |
  Read and edit Feishu/Lark docs, wiki pages, sheets and chat history through lark-cli. Use
  when the task touches a larkoffice.com / feishu.cn URL or token (docx, wiki, sheets), the
  project OnePage or weekly report, a Feishu group's messages, or lark-cli auth/scope errors
  (飞书文档、知识库、表格、群消息、周报、OnePage).
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

## Docs (docx / wiki URLs both work as `--doc`)

Read the smallest scope that answers the question:

```bash
lark-cli docs +fetch --as user --doc "<url|token>" --doc-format markdown            # whole doc, for reading
lark-cli docs +fetch --as user --doc "<url>" --scope outline --max-depth 3           # headings + ids
lark-cli docs +fetch --as user --doc "<url>" --scope section --start-block-id <hid> --detail with-ids
lark-cli docs +fetch --as user --doc "<url>" --scope keyword --keyword "实验台|当前设置" \
  --context-before 1 --context-after 1 --detail with-ids
```

- `--doc-format`: `xml` (default; needed for exact structure, tables, images) or `markdown`.
- `--detail with-ids` gives block ids for editing; `full` adds styles; default `simple` has none.
- Scoped results come wrapped in `<fragment>`; an `<excerpt top-block-id=…>` is only part of
  a block. Tables are trimmed to header + hit rows — read a whole table with
  `--scope range --start-block-id <tbl> --end-block-id <tbl>`.
- `--jq '.data.document.content'` prints just the body.

Edit with block-level commands, then re-fetch to verify (ids change after every write):

```bash
lark-cli docs +update --as user --doc "<url>" --command block_replace --block-id <id> --content '<p>…</p>'
lark-cli docs +update --as user --doc "<url>" --command block_insert_after --block-id <id> --content '<h2>…</h2><p>…</p>'
lark-cli docs +update --as user --doc "<url>" --command str_replace --pattern "旧文本" --content "新文本"
lark-cli docs +update --as user --doc "<url>" --command block_delete --block-id <id>
```

| `--command` | Use |
|---|---|
| `block_replace` | rewrite one block, or a same-parent run via `--start-block-id/--end-block-id` (our most used) |
| `str_replace` | inline text only (`--pattern`); no multi-block, no resources; `--content ""` deletes |
| `block_insert_after` | insert after a block; `--block-id -1` = end, `0` = start |
| `block_delete` / `block_move_after` | delete; move `--src-block-ids a,b` after `--block-id` |
| `append` | add at end |
| `overwrite` | **avoid**: wipes the doc title, the wiki node title, comments and images |

- Every write invalidates the old block ids in the edited range (a range `block_replace`
  of heading + paragraphs + table included). Re-fetch `--detail with-ids` before the next
  edit, and judge every write by the read-back, not by the response.
- Merge several edits to one block into one `block_replace`; keep `<img>`, `<cite>`,
  `<whiteboard>`, `<sheet>` elements byte-for-byte instead of rewriting them.
- Check `result` (`success|partial_success|failed`) and `warnings` in the response.
- Long content: `--content @./body.xml` (relative) or `--content -` from stdin.
- New doc: `docs +create --as user --title "…" --content @./body.xml [--parent-token <wiki node|folder>]`.

DocxXML essentials (full syntax: `lark-cli skills read lark-doc references/lark-doc-xml.md`):

```xml
<h2>标题</h2><p>正文 <b>粗体</b> <a href="https://…">链接</a></p>
<ul><li>项<ul><li>子项</li></ul></li></ul>
<table><colgroup><col width="160"/><col/></colgroup>
  <thead><tr><th background-color="light-gray"><p>列</p></th><th><p>列</p></th></tr></thead>
  <tbody><tr><td><p>值</p></td><td><p>值</p></td></tr></tbody></table>
<img path="@./chart.png" width="640" caption="图注"/>
<pre lang="bash"><code>cmd</code></pre>
<p>行内公式 <latex>x^2</latex></p>
<p align="center"><latex>\sum_i (r_i - u_i)^2</latex></p>   <!-- 独立成行的公式 -->
```

Attributes need quotes; escape `&lt; &gt; &amp;` inside text and inside `<latex>`; headings must not skip
levels.

LaTeX: there is no block-equation tag. A display formula is a paragraph holding only
`<latex>`, with `align="center"`; without it the formula renders as a left-aligned inline
paragraph. Every rebuild or copy of existing XML must keep `align` (strip only `id`), and
the default `+fetch` output omits `align`, so check display formulas with `--detail
with-ids`: count `<p … align="center"><latex>` in the edited range. When generating XML
from Python, use raw strings for LaTeX (`"\beta"` becomes a backspace).

Rewriting a whole doc: a `--start-block-id/--end-block-id` range fails when it crosses a
list (`<ul>` has no id), so use `block_replace --start-block-id 0 --end-block-id -1` with
content that starts with the original `<title>`; `<img src="token">` re-copies images
byte-identically. To replace a span that contains lists, insert the new XML after the
preceding heading, then `block_delete --block-id a,b,c` the old top-level and `<li>` ids. Inserting at the end without XML: `docs +media-insert --as user --doc <url> --file
./x.png --width 640 --caption "…"`.

Other doc commands we use: `docs +media-download --as user --token <img/file token> --output
./a` (extension auto-added; `--type whiteboard` for boards), `docs +media-preview --token …
--output ./a.png` (extension must match the real type), `whiteboard +export --as user
--whiteboard-token <t> --output-type preview --output ./b.png`, `docs +history-list --doc
<url>`, `drive +list-comments --as user --url <url> --solved-status all`.

## Wiki, search

```bash
lark-cli wiki +node-get --as user --node-token "<wiki url|token>"     # → obj_type, obj_token, space_id
lark-cli wiki +node-list --as user --space-id <id> --parent-node-token <tok> --page-all
lark-cli wiki +node-create --as user --space-id <id> --title "…"              # at the space root
lark-cli wiki +node-create --as user --parent-node-token <tok> --title "…"      # under a node
lark-cli drive +search --as user --query "关键词" [--doc-types docx,sheet] [--edited-since 7d]
```

A wiki URL can hold a sheet: `docs +fetch` then fails with `Unsupported document type
'sheet'`. Resolve with `wiki +node-get` and pass `obj_token` to the sheets commands.

## Sheets

```bash
lark-cli sheets +workbook-info --as user --url "<url>"                       # first: sheet ids/names
lark-cli sheets +csv-get --as user --url "<url>" --sheet-id <id> [--range A1:F200] --output-path ./s.json
lark-cli sheets +cells-get --as user --url "<url>" --sheet-id <id> --range A1:F30
lark-cli sheets +cells-search --as user --url "<url>" --sheet-id <id> --find "文本"
lark-cli sheets +cells-set --as user --url "<url>" --sheet-name Sheet1 --range A1:B1 \
  --cells '[[{"value":"名称"},{"formula":"=SUM(B2:B9)"}]]'
```

`--url` and `--spreadsheet-token` are interchangeable; `--sheet-id` or `--sheet-name` is
required. Reads cap at 500k chars on stdout — use `--output-path` for full data. `+read` is a
deprecated alias (use `+cells-get`). `+revision-get` returns the version anchor.

## Chat messages (read only)

```bash
lark-cli im +chat-search --as user --query "群名或成员名"                     # → chat_id oc_…
lark-cli im +chat-messages-list --as user --chat-id oc_… --start 2026-10-17T00:00:00+08:00 \
  --order asc --page-all --no-reactions --concise
lark-cli im +messages-search --as user --query "关键词" [--chat-id oc_…] [--start …]
lark-cli im +threads-messages-list --as user --thread om_…|omt_…
lark-cli im +messages-mget --as user --message-ids om_a,om_b
lark-cli contact +search-user --as user --query "姓名"                       # → open_id ou_…
```

Times are ISO 8601 with offset. Sending messages is outward-facing: only on the user's
explicit request (`lark-cli skills read lark-im` for the send commands).

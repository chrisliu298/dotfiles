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

If a wiki URL fails with `Unsupported document type 'sheet'`, resolve it with
[Wiki](wiki.md) and then use [Sheets](sheets.md) with its `obj_token`.


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


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


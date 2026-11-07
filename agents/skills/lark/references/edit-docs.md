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


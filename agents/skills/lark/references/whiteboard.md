## Whiteboards

A whiteboard lives inside a doc. Get its token from `docs +fetch` (`<whiteboard token="…">`),
or create one with the doc: a `<whiteboard type="mermaid">…</whiteboard>` (or `type="svg"`,
`type="plantuml"`, `type="blank"`) element in `docs +create` / `docs +update` content returns
it as `data.document.new_blocks[].block_token` with `block_type == "whiteboard"`.

```bash
lark-cli whiteboard +export --as user --whiteboard-token <t> --output-type preview --output ./b   # image; .jpg added
lark-cli whiteboard +export --as user --whiteboard-token <t> --output-type source                 # Mermaid/PlantUML code
lark-cli whiteboard +export --as user --whiteboard-token <t> --output-type raw --output ./raw.json # nodes, for read-back
lark-cli whiteboard +update --as user --whiteboard-token <t> --input_format mermaid \
  --source @./f.mmd --overwrite --idempotent-token <unique 10+ chars>
```

Pick the input by diagram: Mermaid (`mermaid`) for flowcharts, sequence, class, mind maps,
pie and Gantt; SVG (`svg`) for architecture, comparison and other free layouts. Before writing
SVG, check and render it locally: `npx -y @larksuite/whiteboard-cli@^0.2.13 -i d.svg --check`
(text overflow, overlaps) and `-o d.png`, then look at the PNG.

- `--overwrite` deletes everything on the board first. On a board you did not just create,
  that is a lossy rewrite: say so and get the user's go-ahead.
- Without `--overwrite` the content is appended at its own coordinates, not beside existing
  content: an appended SVG lands on top of what is there. Read `raw` first and offset the new
  content, or rebuild the whole board.
- `source` only proves a Mermaid/PlantUML block exists; it still returns that code after other
  shapes were added. Judge the board by the `preview` image.
- Retrying with the same `--idempotent-token` did not prevent a second copy (2026-11-16).
  After any write, compare the node count in `raw` and look at `preview` before retrying.

For designed diagrams (DSL, icons, @mentions, images) or editing a hand-drawn board, read the
embedded guide: `lark-cli skills read lark-whiteboard`, then its `references/lark-whiteboard-workflow.md`
and the `routes/` file it names.

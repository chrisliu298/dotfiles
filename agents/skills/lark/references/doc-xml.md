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


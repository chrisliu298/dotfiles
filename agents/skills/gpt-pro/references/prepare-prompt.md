## Prepare the prompt

Put the question and relevant session decisions in a file. GPT-Pro cannot see this
conversation or local files; attach needed files with `-f <path>` rather than
hand-concatenating them. The wrapper validates, secret-scans, and caps composed input
at 5 MB before submission. Use only context authorized for this request.

```bash
gpt-pro -f src/foo.py -f src/bar.py < question.md
```

- For attachment flags, directory inputs, dry runs, PATH failures, or large-paste
  handling, read [Invocation and attachments](attachments.md).
- When the answer depends on external facts, use the grounding guidance in
  [Conditional prompt guidance](prompting.md#grounding-external-facts).
- For judgments, design advice, and second opinions, use that reference's
  [calibration block](prompting.md#calibration-block); skip it for
  deterministic lookups and mechanical transforms.


# Invocation and attachments

## Invocation

Compose the prompt in a file (so `$`, backticks, and heredoc markers don't get mangled),
then pipe it on stdin:

```bash
gpt-pro < prompt.md
```

That's the whole call. `gpt-pro` is on PATH (added in `~/.zshenv`). The response is on
stdout; the run-id, diagnostics, and the engine's JSONL are on stderr. Always issue it
inside the background envelope supported by the harness — see
[Background and timeout](operations.md#background-and-timeout).

```
gpt-pro [-f <path>]... [--max-wait <sec>] [--dry-run] < prompt.md   # new run
gpt-pro --run-id <id> [--max-wait <sec>]                            # reattach / recover
```

| Flag | Purpose |
|---|---|
| `-f`, `--file <path>` | Attach a local file — contents inlined into the prompt (GPT-Pro can't read local paths). Repeatable; accepts a single-level glob (`-f 'src/*.py'`); `@`-prefix is optional sugar. |
| `--files-from <file>` | Inline every path listed in `<file>` (one per line; `#` comments ok). Repeatable. |
| `--include-tree <dir>` | Inline a directory recursively — capped, skips hidden/vendor/binary/secret files. Repeatable. |
| `--allow-secret <path>` | Permit one file the secret scan would otherwise refuse. Repeatable. |
| `--run-id <id>` | Reattach to an existing run (recovery); skips submit, then waits for the result (blocking fetch on macmini, poll loop over SSH). |
| `--max-wait <sec>` | Poll deadline on the SSH path (default 7200 = 120 min — generous so a queued run isn't killed mid-flight). Ignored on macmini, where the engine's own 60-min cap and the Bash-tool `timeout` bound the run. |
| `--dry-run` | Resolve the included files + run-id, report the composed size, then exit. No Pro quota used. |

Files are inlined through the shared **`filectx`** helper (sibling script): validated, secret-scanned (`FILECTX_SECRETS=deny\|warn\|off`), and capped — all **before** submit, so a bad file burns no quota.

Want a durable copy? Keep the streams **separate**: `gpt-pro < prompt.md > answer.md 2> gpt-pro.log` — never `2>&1` (it contaminates the answer and buries the `run_id`). Optional: the backgrounded task output already captures both streams, so a redirect is only for a persistent on-disk artifact.

If `gpt-pro: command not found` (a sandboxed or reset-env shell that didn't inherit the
`.zshenv` PATH), run the identical command from this skill's own `scripts/` directory —
the `gpt-pro` script sits beside this `SKILL.md` (`<this-skill-dir>/scripts/gpt-pro < prompt.md`).

## Prompts must be self-contained

GPT-Pro runs in a ChatGPT web tab. **It cannot see anything local to you — your codebase,
your shell, the files on your machine, or this conversation.** Every byte of *local* context
it needs must be inside the prompt: **attach files with `-f <path>`** (the wrapper inlines them
for you, validated/secret-scanned/capped before submit) and paste any non-file context (a
decision earlier in this session) into the stdin prompt. Use `-f` instead of hand-`cat`-ing —
it eliminates the most error-prone step (a forgotten file, mangled `$`/backticks, a silently
oversized prompt, an accidentally-pasted secret). It *can*, however, reach the **public web**
through its own browser/search tool — so don't attach public docs it can fetch itself; tell it
what to look up (see [Grounding external facts](prompting.md#grounding-external-facts)). The rule: private-local context comes in via
`-f` (or paste); public-external facts are searched for.

Err toward more context, not less — the 5 MB submission cap is generous, and a run that
fails for missing context still burns 5–20 min. Put the **question** in a file (the **Write
tool** sidesteps `$`/backtick/heredoc mangling) and attach **files** with `-f`:

```bash
gpt-pro -f src/foo.py -f src/bar.py -f 'tests/*.py' < question.md
```

`question.md` holds only the question (plus any non-file context); each `-f` is inlined under a
fenced `## Included files` section. Preview exactly what would be sent — resolved files and the
composed byte total — without spending quota:

```bash
gpt-pro --dry-run -f src/foo.py --include-tree docs/ < question.md
```

You rarely need to assemble the prompt by hand now. If you must (a surgical excerpt `-f` can't
express), build the whole prompt in a file with the Write tool and pipe it in with no `-f`.

Large composed prompts cross a ChatGPT frontend boundary: the browser turns the paste into a
`Pasted markdown` file and leaves the ordinary message box empty. That used to work by accident,
but the backend may now treat instructions inside the file as document content and merely ask
what to do next. The relay handles this dynamically (no hard-coded size threshold): it detects
the empty message box, adds a short top-level instruction to execute the attached prompt now,
and verifies that instruction before Send. Do not work around this by dropping context or
hand-splitting files. A pre-send `instruction_boundary_lost_before_send` means the verification
failed and no quota was burned; a post-send `instruction_boundary_lost` means Pro still only
acknowledged/planned, and its body is quarantined rather than returned.

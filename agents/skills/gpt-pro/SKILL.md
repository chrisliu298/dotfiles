---
effort: low
name: gpt-pro
description: Ask ChatGPT Pro (GPT-Pro) alone for a take or second opinion, only when the user asks for it. Pro alongside other backends goes to agent-team.
allowed-tools: Bash(gpt-pro:*), Bash(${CLAUDE_SKILL_DIR}/scripts/gpt-pro:*), Read, Write
user-invocable: true
---

# gpt-pro

Send one self-contained prompt through `gpt-pro` and return its verified answer.
The engine runs on this Mac. The wrapper submits once and waits through network drops. Each new prompt starts a fresh ChatGPT conversation; `--run-id`
reattaches to the original one.

Use only context authorized for this request. Bundled references and scripts resolve
from this skill root; question files and attachments stay in their authorized cwd.
An authorized invocation is the go-ahead; do not add a runtime confirmation.

## Prepare the prompt

Before composing or attaching files, read [Prepare the prompt](references/prepare-prompt.md).
Pro cannot see this conversation or local files: supply needed context explicitly.
Follow its conditional links for attachments, external facts and calibrated judgments.

## Invoke and wait

Before submitting or collecting, read [Invoke and wait](references/submit-and-wait.md).
Launch once in the background, record the literal run ID and collect the same invocation.
Do not create another waiter, polling loop or submission while it is live.

## Verify the result

Before returning an answer or reading saved response artifacts, read
[Verify the result](references/verify-answer.md). Only a non-empty successful response
is usable; for artifacts, read result.json first and require status: "ok".
Other bodies are diagnostics. Verify consequential claims and report model-audit uncertainty.

## Recovery and other operations

Before recovery, timeout changes, stopping or artifact retrieval, read
[Recovery and other operations](references/recovery-entry.md), then the relevant
[Runtime, recovery, and diagnostics](references/operations.md) section.
For any failure, read [If it fails](references/operations.md#if-it-fails) before choosing a retry.
Ambiguous or post-send failures never justify blind resubmission; a fresh quota-consuming
run after terminal failure requires the user's decision. Use --stop to stop generation;
TaskStop/kill can leave browser generation running after killing its collector.

## Supplement a running request

Before sending or retrying a supplement, read [Supplement a running request](references/supplements.md).
Use the original run ID and preserve the same stable message ID and identical content
on retries. A delivery receipt is not an answer; resume collection of the original invocation.

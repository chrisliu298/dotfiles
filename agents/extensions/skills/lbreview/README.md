# lbreview

**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://github.com/openai/codex) that performs careful, structured code review of changes against main.**

Based on the [review prompt](https://github.com/lucasb-eyer/dotfiles/blob/master/_codex/prompts/lbreview.md) by [@lucasb-eyer](https://github.com/lucasb-eyer), extended with adversarial reviewer lenses and a structured verdict system.

lbreview reads your diff, understands the author's intent, then systematically evaluates benefits, pitfalls, gaps, and simplification opportunities. For larger changes, it deploys adversarial reviewer lenses -- Skeptic, Architect, Minimalist -- that stress-test correctness, structural fitness, and necessity before delivering a verdict.

Invoke with `/lbreview` or ask your agent to "review my changes."

## How It Works

lbreview automatically detects the diff to review, checking in order:

1. Staged changes (`git diff --cached`)
2. Unstaged changes (`git diff`)
3. All uncommitted changes (`git diff HEAD`)

If all are empty, it stops. Otherwise, it walks through a structured review:

1. **Understand the change** -- state the author's intent explicitly
2. **Evaluate benefits** -- how the change achieves its goal
3. **Identify pitfalls** -- potential issues (ignoring backwards-compatibility)
4. **Check for gaps** -- anything obvious the change might be missing
5. **Suggest improvements** -- potential enhancements
6. **High-level simplifications** -- could the design be simpler?
7. **Implementation simplifications** -- could the code be simpler?
8. **Adversarial lenses** -- severity-rated findings from specialized perspectives
9. **Verdict** -- PASS / CONTESTED / REJECT

### Adversarial Lenses

Applied based on diff size:

| Diff size | Lenses |
|-----------|--------|
| < 50 lines | Skeptic |
| 50--200 lines | Skeptic + Architect |
| 200+ lines | Skeptic + Architect + Minimalist |

Each lens adopts an adversarial posture. Findings cite `file:line` with severity: **high** (blocks ship), **medium** (should fix), **low** (worth noting). The final verdict reflects consensus across lenses, with the reviewer's own judgment on which findings warrant action and which are false positives.

## Installation

Clone into your agent's skills directory:

**Claude Code:**

```bash
git clone https://github.com/chrisliu298/lbreview.git ~/.claude/skills/lbreview
```

**Codex:**

```bash
git clone https://github.com/chrisliu298/lbreview.git ~/.codex/skills/lbreview
```

## Acknowledgments

The core review structure is adapted from [lucasb-eyer/dotfiles](https://github.com/lucasb-eyer/dotfiles/blob/master/_codex/prompts/lbreview.md) by [@lucasb-eyer](https://github.com/lucasb-eyer). The adversarial lenses framework and verdict system were added on top.

## Contributors

- [@chrisliu298](https://github.com/chrisliu298)
- **Claude Code** -- adversarial lenses framework and structured verdict system

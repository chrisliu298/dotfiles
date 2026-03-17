# Vault Conventions Reference

## Vault Location

`/Users/chrisliu298/Documents/Obsidian/chrisliu298/`

## Frontmatter

```yaml
---
aliases: []
date-created: YYYY-MM-DD HH:MM:SS
date-modified: YYYY-MM-DD HH:MM:SS
tags:
  - area/{category}
  - type/{type}
  - keyword/{topic}
---
```

- Exactly ONE `area/` tag, exactly ONE `type/` tag, zero or more `keyword/` tags
- `aliases`: usually `[]`; for papers with well-known acronyms, include the acronym (e.g., `[PPO]`, `[GRPO]`)

## Tag Discovery (dynamic)

Tags are NOT a fixed list — they evolve as the vault grows. Before assigning tags, **scan the vault** to discover the current taxonomy:

```
Grep for "area/" across *.md files in the vault → collect unique area/ tags
Grep for "type/" across *.md files in the vault → collect unique type/ tags
Grep for "keyword/" across *.md files in the vault → collect unique keyword/ tags
```

Pick from existing tags when a good fit exists. If no existing tag fits, create a new one following the same conventions (lowercase, hyphenated, concise).

## File Naming

| Note Type | Pattern | Example |
|-----------|---------|---------|
| Paper | `Author YYYY Title.md` | `Chen 2025 Retraining by Doing.md` |
| Blog post | `Title.md` | `Scaling Laws for Neural Language Models.md` |
| Concept/note | `Concept Name.md` | `Proximal Policy Optimization.md` |
| Reference | `Descriptive Title.md` | `LLM Resources.md` |

## Style Rules

- **Balanced prose and markdown** — mix prose paragraphs with bullets, tables, and bold freely. Use prose for narrative/explanation, bullets for discrete points, and alternate between them within sections as the content demands
- **Bullets are welcome** — use them for findings, takeaways, steps, components, or any content that reads better as discrete items. Don't force prose when bullets are more natural
- **Break up long paragraphs** — if a paragraph has 4+ distinct points, convert some to bullets
- **Flat list mode** — when the user explicitly requests "list" or "flat list", use a simple flat bullet list with minimal prose
- `$inline$` and `$$block$$` LaTeX math
- `##` sections, `###` subsections, no deeper
- **Bold** for key terms on first mention
- Tables for comparisons and structured data
- External links: `[Title](URL)`, internal: `[[Note Name]]` or `[[Note Name|Display Text]]`
- Callouts sparingly: `> [!tip]`, `> [!important]`
- No code blocks unless source material contains code

## Condensed Examples

### Paper Note

```markdown
---
aliases: []
date-created: 2026-01-17 11:30:06
date-modified: 2026-01-17 12:10:41
tags:
  - area/rl
  - type/paper
---

# Chen 2025 Retraining by Doing

## Core Thesis

RL causes less catastrophic forgetting than SFT during LM post-training. Despite RL's mode-seeking nature concentrating probability mass on fewer outputs, it preserves general capabilities better than SFT's mode-covering approach.

## Background and Motivation

Catastrophic forgetting during post-training is a persistent problem — models gain task-specific ability at the cost of general knowledge. The counterintuitive finding here is that mode-seeking RL forgets less than mode-covering SFT, which challenges the conventional expectation that broader coverage should preserve more.

## Key Empirical Findings

RL forgets less than SFT across all tested settings. The pattern holds consistently across different model sizes, training objectives, and evaluation benchmarks.

## Theoretical Analysis: KL Divergence Perspective

SFT minimizes forward KL, which forces the model to cover all modes of the target distribution:

$$\mathcal{L}_{\text{SFT}}(\theta; x) = \text{KL}[\pi^*(\cdot|x) \| \pi_\theta(\cdot|x)]$$

This spreading behavior dilutes the model's existing knowledge. RL's reverse KL, by contrast, concentrates updates on high-reward regions without forcing redistribution across the full output space.

## Ablation Studies

The authors rule out KL regularization and advantage estimation as explanations. The primary factor is **on-policy data** — RL generates its own training data from the current policy, which naturally stays close to the model's existing distribution.

## Key Takeaways for Practice

1. Prefer RL over SFT when forgetting is a concern
2. If SFT is necessary, use approximately on-policy approaches

## Connection to [[Forward KL and Backward KL]]

This paper provides evidence that challenges conventional intuition about ...

## References

- [Chen 2025 Retaining by Doing](https://arxiv.org/abs/2510.18874)
```

### Concept Note

```markdown
---
aliases: [PPO]
date-created: 2025-12-15 10:00:00
date-modified: 2026-01-10 14:30:00
tags:
  - area/rl
  - type/note
  - keyword/ppo
---

# Proximal Policy Optimization

## What It Is

PPO is a policy gradient method that constrains updates via a clipped surrogate objective, preventing destructively large policy updates while remaining simple to implement.

## How It Works

The core idea is to take the largest possible improvement step without straying too far from the current policy. PPO achieves this through a **clipped surrogate objective**:

$$L^{CLIP}(\theta) = \hat{\mathbb{E}}_t[\min(r_t(\theta)\hat{A}_t, \text{clip}(r_t(\theta), 1-\epsilon, 1+\epsilon)\hat{A}_t)]$$

Here $r_t(\theta) = \frac{\pi_\theta(a_t|s_t)}{\pi_{\theta_{old}}(a_t|s_t)}$ is the probability ratio between the new and old policies. Clipping this ratio to $[1-\epsilon, 1+\epsilon]$ removes the incentive for moving the policy too far from its previous version.

## Key Design Choices

| Choice | Typical Value | Notes |
|--------|---------------|-------|
| Clip range $\epsilon$ | 0.2 | Lower = more conservative |
| KL penalty $\beta$ | 0.01-0.1 | Alternative to clipping |

## Related

- [[Generalized Advantage Estimation]]
- [[Forward KL and Backward KL]]
- [[PPO in verl]]

## References

- [Schulman et al. 2017 Proximal Policy Optimization Algorithms](https://arxiv.org/abs/1707.06347)
```

### Blog Post Note

```markdown
---
aliases: []
date-created: 2026-01-20 09:15:00
date-modified: 2026-01-20 09:15:00
tags:
  - area/llm
  - type/blog-post
  - keyword/scaling
---

# Scaling Laws for Neural Language Models

- Loss scales as a power law with model size, dataset size, and compute
- Larger models are more sample-efficient
- Optimal allocation: scale model size faster than data
- Fixed compute budget → larger model trained on less data outperforms smaller model on more data
- Convergence is predictable from early training loss

## References

- [Kaplan et al. 2020 Scaling Laws for Neural Language Models](https://arxiv.org/abs/2001.08361)
```

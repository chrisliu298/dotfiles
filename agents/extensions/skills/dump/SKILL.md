---
user-invocable: true
description: Dump session-derived knowledge into the user's Obsidian vault. Use when the content
  to save was created or distilled during the current conversation — debugging insights, TILs,
  architectural discoveries, decisions, explanations, or anything worth preserving. Triggers on
  "dump this to obsidian", "dump to vault", "save to vault", "capture what we learned", "write up
  the debugging insight", "save our findings", "turn this into a note in obsidian", "dump what you
  learned", "save what we figured out", or "dump". Supports targeted ("dump this specific thing")
  and session-wide ("dump everything notable") modes. Also trigger when the user says "dump" at
  the end of a session and is clearly referring to saving session knowledge. Do NOT trigger on
  "dump" in engineering contexts (database dumps, log dumps, core dumps). Do NOT use when the
  primary source is an external URL, paper, file, pasted article, or a topic requiring fresh
  research — use note-gen instead.
---

# Dump

Save session-derived knowledge to the Obsidian vault. This captures things that emerged during a session — debugging insights, architectural discoveries, TILs, decisions, explanations, or anything the user wants preserved before the conversation ends.

The difference from `note-gen`: note-gen creates notes **from** external sources (URLs, papers, concepts). This skill saves things **from the current session** to the vault. Choose based on where the knowledge came from, not the note's topic.

**Hybrid sessions**: If the session involved analyzing an external source (paper, blog post), the source itself belongs in `note-gen`. But session-specific insights, interpretations, or connections drawn during discussion are fair game for `dump`. When in doubt: note-gen for the source, dump for the original analysis layered on top.

**Vault**: `/Users/chrisliu298/Documents/Obsidian/chrisliu298/`
**Location**: All notes go at the vault root.

## Modes

### Targeted

User points at something specific: "dump this to my vault", "save the thing about X."

1. Identify what the user wants saved from the conversation
2. Run the destination triage (below)
3. Write or update the note

### Session Dump

User asks for a broad export: "dump everything notable", "save what we figured out."

1. Review the full conversation history — for long sessions, scan chronologically and focus on breakthroughs, surprises, corrections, and final conclusions. Ignore failed hypotheses unless the failure itself is instructive.
2. Identify distinct topics worth preserving — things that were non-obvious, hard-won, or would be useful to recall later
3. Default to **1-3 notes**. Group closely related findings into one note rather than fragmenting. Only exceed 3 if the user explicitly asks for exhaustive capture.
4. If creating 3+ notes or topic boundaries are ambiguous, list planned titles before writing. For 1-2 clear notes, proceed directly and report what was written.

If the conversation has nothing particularly notable to save, say so rather than generating filler notes.

## Destination Triage

This is the most important step — deciding *where* session knowledge goes matters more than formatting.

Before creating a new note, search for existing notes covering the same concept (by filename, aliases, and key terms). Then choose:

| Destination | When |
|-------------|------|
| **Update existing note** | The session materially extends a concept already in the vault. Append a new section or integrate the insight, preserving the existing note's structure. Update `date-modified` to current timestamp. |
| **New `type/note`** | The insight stands alone as evergreen, reusable knowledge that future-you would search for by name. |
| **New `type/thought`** | The insight is tentative, provisional, or reflective — worth capturing but not yet stable. |
| **Nothing** | The insight is too thin, too transient, or already covered by an existing note. |

When the choice between "update existing" and "create new" is genuinely ambiguous, briefly ask the user.

## Writing Notes

### Step 1: Discover Tags

Scan the vault to find the current tag taxonomy — tags evolve over time and are not a fixed list:

- Grep for `area/`, `type/`, and `keyword/` tags across `*.md` files in the vault
- Pick from existing tags when a good fit exists
- When near-duplicate tags exist (e.g., `area/tool` vs `area/tools`), prefer the dominant/canonical form
- Create new tags only if none fit; follow the vault's existing casing conventions (preserve established acronyms)

#### Type Tag Mapping

| Dump Kind | Likely `type/` Tag |
|-----------|-------------------|
| Concept / insight | `type/note` |
| Debugging finding | `type/note` |
| Decision log | `type/note` |
| Quick TIL | `type/thought` |
| Tentative synthesis / opinion | `type/thought` |
| Concrete idea to revisit | `type/idea` |
| Explicit future plan | `type/plan` |

### Step 2: Scan for Wikilink Targets

List all `*.md` filenames in the vault. Also read aliases from candidate notes to build a mapping of alias to actual filename. When note content mentions a concept that matches an existing note, insert `[[Note Name]]`. Use `[[Note Name|Display Text]]` when the display text differs.

Rules:
- Always use the **actual filename** (without `.md`) as the link target, never an alias
- Link only the first occurrence of a term per `##` section
- Never link inside existing wikilinks, `$math$`, code blocks, headings, URLs, or markdown links
- No self-links
- Conservative linking — only link terms that substantively refer to the target note, not casual uses of the word
- Keep `## Related` entries alphabetically sorted, soft cap of ~10

### Step 3: Check for Conflicts and Deduplication

Before writing each note:
1. Check if a file with the target name already exists
2. Search for existing notes on the same topic (even under a different name)
3. If an existing note clearly matches, prefer updating it (see Destination Triage)
4. If creating multiple notes (session dump), check all filenames before writing any

### Step 4: Write the Note

#### Frontmatter

```yaml
---
aliases: []
date-created: {current timestamp YYYY-MM-DD HH:MM:SS}
date-modified: {same as date-created for new notes; current timestamp for updates}
tags:
  - area/{category}
  - type/{type}
  - keyword/{topic}
---
```

- Exactly ONE `area/` tag, ONE `type/` tag, zero or more `keyword/` tags
- `aliases`: usually `[]`; include well-known acronyms if applicable (e.g., `[PPO]`)

#### Filename

Descriptive title in title case: `Concept Name.md`. No dates in filenames.

#### Structure

Start with an H1 heading matching the filename (without `.md`), immediately after the frontmatter closing `---`.

Keep the structure natural to the content:

- **Concept/insight**: What it is, how/why it works, implications
- **Debugging finding**: What went wrong, root cause, the fix, what to watch for
- **Decision log**: Context, options considered, decision and rationale
- **Quick TIL**: Can be just a few bullets under the H1

End with `## Related` then `## References` — in that order, as the last two sections. Omit either if not applicable.

#### Length

Match the note's natural size. A quick TIL might be 5 bullets. A debugging deep-dive with root cause analysis might be 50-80 lines. Don't pad short insights into long notes — session dumps should feel like notes-to-self, not polished articles.

#### Style

- Mix prose and bullets naturally — prose for narrative, bullets for discrete points
- `$inline$` and `$$block$$` LaTeX math when relevant
- `##` sections, `###` subsections, no deeper
- **Bold** key terms on first mention
- Tables for structured comparisons
- Allow code blocks when they preserve essential debugging artifacts, commands, or config details
- Keep table cells to plain text or simple inline math — complex LaTeX breaks Obsidian's renderer
- No emoji
- No AI slop — write concisely, the way the user would write a note to their future self

## What NOT to Dump

- Raw conversation transcripts
- Things that belong in the agent's memory/preferences system rather than the vault (user preferences, workflow corrections)

# Interviewer

**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://github.com/openai/codex) that conducts mock technical interviews with adaptive difficulty, structured feedback, and session history.**

> *The best way to find out what you don't know is to have someone ask.*

Interviewer turns your agent into a technical interviewer. Pick your topics, choose a difficulty mode, and answer questions one by one. Each answer gets scored on accuracy, completeness, and clarity. When you're done, you get a summary of strengths, weak areas, and what to study next. Sessions are saved so you can track progress over time and replay questions you struggled with.

Invoke with `/interview` (Claude Code) or `$interview` (Codex).

## Table of Contents

- [Why](#why)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Usage](#usage)
- [Session Configuration](#session-configuration)
- [During a Session](#during-a-session)
- [After a Session](#after-a-session)
- [Contributors](#contributors)

---

## Why

Reading notes and watching lectures feels like learning. But when someone asks you to explain a concept from scratch -- no hints, no looking things up -- gaps appear fast. Interviewer creates that pressure on demand:

- **Active recall** -- forces you to retrieve and articulate concepts, not just recognize them
- **Calibrated difficulty** -- adaptive mode adjusts to your level; progressive mode ramps up within a session
- **Immediate feedback** -- scored on three dimensions with detailed explanations after every answer
- **Spaced repetition** -- replay mode resurfaces questions you got wrong or skipped

---

## How It Works

```
┌─────────────────────────────────────────────────┐
│  1. Setup: pick topics, format, difficulty       │
├─────────────────────────────────────────────────┤
│  2. Warm-up: 1-2 easy questions                  │
├─────────────────────────────────────────────────┤
│  3. Interview loop:                              │
│     question → answer → score → feedback         │
│         ↓                                        │
│     hints / skip / bookmark available             │
├─────────────────────────────────────────────────┤
│  4. Summary: scores, strengths, weak areas       │
├─────────────────────────────────────────────────┤
│  5. Save session to history/                     │
└─────────────────────────────────────────────────┘
```

---

## Installation

Clone into your agent's skills directory:

**Claude Code:**

```bash
git clone https://github.com/chrisliu298/interviewer.git ~/.claude/skills/interviewer
```

**Codex:**

```bash
git clone https://github.com/chrisliu298/interviewer.git ~/.codex/skills/interviewer
```

---

## Usage

```
/interview                      # Start new session or list existing
/interview [session-name]       # Resume or create named session
/interview replay [session]     # Re-practice weak questions
/interview history              # List past sessions
/interview stats                # Overall progress across sessions
/interview bookmarks            # Review saved favorite/tricky questions
```

Start a session and the agent walks you through setup, then begins asking questions. Say "done" at any time to end the session and get your summary.

---

## Session Configuration

Each session begins with a short setup phase where you choose:

| Option | Choices |
|--------|---------|
| **Source** | File paths, topic keywords, or both |
| **Format** | Standalone, multi-part with follow-ups, progressive chains |
| **Types** | Conceptual only, + pseudocode, full range, design-focused |
| **Difficulty** | Fixed (L1-L4), adaptive, progressive, random mix |
| **Length** | Specific count, fixed (5), or open-ended |
| **Persona** | Neutral/helpful, challenging/probing, Socratic |
| **Scope** | LLM-focused, broader ML/AI, general CS/systems |

File-based mode reads your notes or papers and generates questions from them. Topic mode generates questions from the agent's knowledge. Both mode combines the two.

---

## During a Session

Each answer is scored on three dimensions (1-5):

- **Accuracy** -- correctness of information
- **Completeness** -- coverage of key points
- **Clarity** -- how well explained

Mid-session commands:

| Command | Effect |
|---------|--------|
| `hint` | Get a nudge in the right direction |
| `skip` | Move to next question (max 2 per session) |
| `bookmark` | Mark question for later review |
| `answer` | Show the model answer |
| `feedback` | Get a progress check |
| `done` | End session and get summary |

---

## After a Session

Sessions are saved to `history/` with full question-answer logs, scores, and the session summary. Use the history commands to review past performance:

- **`/interview history`** -- list all past sessions with dates and scores
- **`/interview stats`** -- aggregate performance across sessions, improvement trends, consistent weak areas
- **`/interview replay [session]`** -- re-practice questions you scored below 3/5, skipped, or bookmarked
- **`/interview bookmarks`** -- review all bookmarked questions across sessions

---

## Contributors

- [@chrisliu298](https://github.com/chrisliu298)
- **Claude Code** -- session workflow design and question template library

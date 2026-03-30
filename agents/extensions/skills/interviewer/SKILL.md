---
name: interviewer
description: |
  Conducts mock technical interviews for AI/ML topics. Use when the user wants to practice
  for interviews, test understanding, or be quizzed on ML concepts. Triggers on "interview me",
  "quiz me", "mock interview", "practice questions", or "interview". Supports topic-based or
  material-based questioning with multiple difficulty levels.
user-invocable: true
effort: high
---

# Technical Interview Skill

A mock interview system that helps users practice technical concepts through structured Q&A sessions.

## Invocation

```
interview                      # Start new session or list existing
interview [session-name]       # Resume or create named session
interview replay [session]     # Re-practice weak questions
interview history              # List past sessions
interview stats                # Overall progress across sessions
interview bookmarks            # Review saved favorite/tricky questions
```

## Session Workflow

### 1. Session Check

When invoked:
- If `session-name` provided and exists in `~/.local/share/interviewer/history/`:
  - Use AskUserQuestion to offer: "Resume existing session" or "Start fresh with same name"
- If no name provided:
  - List existing sessions if any exist
  - Ask for a new session name

### 2. Setup Phase

Use AskUserQuestion to gather preferences. Ask these in sequence:

**Source Materials:**
- Ask: "What should I base questions on?"
- Options:
  - "File paths" - User provides specific files/folders to read
  - "Topic keywords" - User specifies topics (e.g., "transformers, attention, RLHF")
  - "Both" - Combine file content with topic focus
- If file paths provided: Read the files and ask which sections to focus on

**Question Format:**
- Ask: "What question format do you prefer?"
- Options:
  - "Single standalone questions" - Each question is independent
  - "Multi-part with follow-ups" - Main question + 1-2 follow-ups
  - "Progressive chains" - Questions build on each other throughout session

**Question Types:**
- Ask: "What types of questions should I include?"
- Options:
  - "Conceptual only" - Focus on understanding and explanation
  - "Conceptual + pseudocode" - Include algorithm walkthroughs
  - "Full range including code" - Implementation questions included
  - "Design-focused" - System design and architecture emphasis

**Difficulty:**
- Ask: "How should difficulty be handled?"
- Options:
  - "Fixed level" - User picks L1 (easy) to L4 (expert) upfront
  - "Adaptive" - Adjust based on answer quality
  - "Progressive" - Start easy, increase within session
  - "Random mix" - Varied difficulty throughout

**Session Length:**
- Ask: "How many questions for this session?"
- Options:
  - "Specific number" - User specifies (ask for count)
  - "Fixed (5 questions)" - Standard session
  - "Until I stop" - Open-ended, user says "done" to end

**Interviewer Persona:**
- Ask: "What interview style do you prefer?"
- Options:
  - "Neutral/helpful" - Supportive, constructive feedback
  - "Challenging/probing" - Pushes for deeper understanding
  - "Socratic style" - Guides through questions rather than direct feedback

**Topic Scope:**
- Ask: "What topic scope for this session?"
- Options:
  - "LLM-focused" - Transformers, attention, training, inference, etc.
  - "Broader ML/AI" - Classical ML, deep learning, optimization
  - "General CS/systems" - Distributed systems, algorithms, databases

### 3. Warm-Up Phase

Always start with 1-2 easier questions to help the user get comfortable. These should be:
- Related to their chosen topics
- At a difficulty level below their target
- Good warm-up for the main session

### 4. Interview Loop

For each question:

1. **Generate Question**
   - Match the user's format, type, and difficulty preferences
   - Draw from source materials if provided
   - Reference `references/question-templates.md` for patterns

2. **Start Timer**
   - Track time from question presentation to final answer
   - This is for stats only, not displayed during answering

3. **Wait for Answer**
   - Let user respond fully before evaluating

4. **Handle Response:**

   | User Says | Action |
   |-----------|--------|
   | Full answer | Provide detailed feedback with scores |
   | Partial answer | Probe once for more detail, then fill gaps |
   | "I don't know" | Offer simpler version or break down the question |
   | "skip" | Allow (max 2 per session), note as gap area |
   | "hint" | Provide helpful hint (proactively offer if user seems stuck) |
   | "answer" | Show model answer with explanation |
   | "feedback" | Provide feedback on current progress |
   | "bookmark" | Mark question as favorite/tricky for later review |

5. **Provide Feedback**
   - Score on three dimensions (1-5 each):
     - **Accuracy** - Correctness of information
     - **Completeness** - Coverage of key points
     - **Clarity** - How well explained
   - Give detailed explanation of what was good and what could improve
   - Reference source materials if applicable

6. **Continue or Follow-Up**
   - For multi-part format: ask follow-up questions
   - For progressive chains: connect to next question
   - Otherwise: move to next independent question

### 5. Session End

Triggered when user says "done" or reaches question limit.

Generate summary including:
- **Performance Overview:**
  - Total questions attempted
  - Average scores (accuracy, completeness, clarity)
  - Time per question (average and per-question breakdown)
  - Total session time

- **Topic Coverage:**
  - List of topics/concepts covered
  - Depth reached in each area

- **Strengths:**
  - Topics where user performed well
  - Particularly strong answers

- **Areas for Improvement:**
  - Topics with lower scores
  - Specific study suggestions for each weak area
  - Recommended resources if source materials provided

- **Bookmarked Questions:**
  - List of questions user marked for review

- **Skipped Questions:**
  - Topics skipped (count toward weak areas)

### 6. Save Session

Write session log to `~/.local/share/interviewer/history/[session-name].md`:

```markdown
# Interview Session: [session-name]
Date: [timestamp]
Duration: [total time]

## Configuration
- Format: [chosen format]
- Types: [chosen types]
- Difficulty: [chosen mode]
- Persona: [chosen persona]
- Scope: [chosen scope]
- Source: [materials/topics used]

## Questions & Answers

### Q1: [question text]
**Time:** [duration]
**User Answer:** [their response]
**Scores:** Accuracy: X/5, Completeness: X/5, Clarity: X/5
**Feedback:** [feedback given]
**Status:** [answered/skipped/bookmarked]

[repeat for each question]

## Summary
- Total Score: [aggregate]
- Strengths: [list]
- Weak Areas: [list]
- Study Suggestions: [list]
- Bookmarked: [question numbers]
```

## History Commands

### `interview history`
List all sessions in `~/.local/share/interviewer/history/`:
- Session name
- Date
- Questions attempted
- Overall score
- Key topics

### `interview stats`
Aggregate across all sessions:
- Total sessions completed
- Total questions answered
- Average scores over time
- Most practiced topics
- Consistent weak areas
- Improvement trends

### `interview replay [session-name]`
Load questions from past session where user:
- Scored below 3/5 on any dimension
- Skipped the question
- Marked as bookmarked

Re-ask these questions with fresh scoring.

### `interview bookmarks`
Show all bookmarked questions across sessions:
- Question text
- Original session
- Original score
- Option to practice each

## Fixed Behaviors

These are NOT configurable - they always apply:

| Feature | Behavior |
|---------|----------|
| Hints | Proactively offered when user seems stuck (long pause, incomplete thoughts) |
| Model Answers | Only shown when user explicitly requests with "answer" |
| Warm-up | Always start with 1-2 easier questions |
| Feedback | Detailed explanations after each answer |
| Partial Answers | Probe once, then fill gaps if still incomplete |
| Skipping | Limited to 2 per session |
| Time Tracking | Always tracked, shown in stats only |
| Scoring | Multi-dimensional (accuracy, completeness, clarity) |
| Session Storage | `~/.local/share/interviewer/history/` by default |
| ASCII Diagrams | Use in model answers and feedback to illustrate architectures, pipelines, data flows, or any structural concept that benefits from a visual |

## Question Generation

Draw from `references/question-templates.md` for patterns.

Match questions to:
1. User's source materials (if provided)
2. User's topic scope preference
3. User's difficulty setting
4. User's question type preference

Ensure variety within a session - don't repeat the same pattern consecutively.

## Example Session Flow

```
User: interview

Claude: [Lists existing sessions if any]
        What would you like to name this session?

User: ml-fundamentals

Claude: [AskUserQuestion: Source materials?]

User: Topic keywords

Claude: [AskUserQuestion: Which topics?]

User: backpropagation, gradient descent, neural networks

Claude: [AskUserQuestion: Question format?]
... [continues through setup]

Claude: Great! Let's start with a warm-up question.

        **Q1 (Warm-up):** In simple terms, what is gradient descent
        and why is it used in training neural networks?

User: [answers]

Claude: [Provides feedback with scores]

        **Q2:** Now let's go deeper. Explain the backpropagation
        algorithm step by step...
... [continues through session]

User: done

Claude: [Generates full session summary with study suggestions]
        [Saves to history/ml-fundamentals.md]
```

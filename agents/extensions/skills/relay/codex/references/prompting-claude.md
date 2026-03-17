# How to Prompt Claude (Opus) Effectively

Read this before composing complex relay tasks for Claude. These patterns come from the official Claude prompting best practices and improve accuracy, consistency, and output quality.

## Be Clear and Direct

Claude responds well to explicit, specific instructions. Tell Claude what to DO rather than what NOT to do. Use numbered steps for multi-part tasks.

- Bad: "Look at the auth code and maybe fix some stuff"
- Bad: "Don't use markdown formatting" (negative instruction)
- Good: "1. Read src/auth.py  2. Identify SQL injection vulnerabilities  3. Fix each one  4. Run pytest to verify all tests pass"
- Good: "Write your response in flowing prose paragraphs" (positive instruction)

## Be Explicit About Action vs. Suggestion

Claude distinguishes between being asked to suggest and being asked to act. If you want Claude to make changes, say so directly.

- Bad: "Can you suggest some improvements to the error handling?"
- Good: "Improve the error handling in src/api.py."
- Good: "Make these edits to the authentication flow."

To make Claude proactive about taking action by default:

```xml
<default_to_action>
By default, implement changes rather than only suggesting them. If the user's intent is unclear, infer the most useful likely action and proceed, using tools to discover any missing details instead of guessing.
</default_to_action>
```

## Add Context and Motivation

Explain why the task matters, not just what to do. Claude generalizes better when it understands the purpose behind an instruction.

- "We're hardening auth before a security audit. Focus on OWASP Top 10 vulnerabilities, especially injection and broken access control."
- Instead of "NEVER use ellipses", say "The output will be read by a text-to-speech engine, so avoid ellipses since it can't pronounce them."

## Set a Role

A single sentence setting Claude's role focuses its behavior and tone. Even brief context about what role to adopt makes a measurable difference.

- "You are a security auditor reviewing this codebase for vulnerabilities."
- "You are a performance engineer optimizing database queries."

## Structure Prompts with XML Tags

XML tags help Claude parse complex prompts unambiguously. Wrap each type of content in its own tag to reduce misinterpretation. Use consistent, descriptive tag names and nest tags when content has a natural hierarchy.

```xml
<context>
We're preparing for a security audit next week. The auth module was last reviewed 6 months ago and has had significant changes since.
</context>

<instructions>
1. Read src/auth.py and identify all vulnerabilities
2. Fix each one in-place
3. Run pytest to verify all tests pass
4. Return a summary: one line per fix, with line number and what changed
</instructions>
```

For multi-document input, structure with `<documents>`, `<document>`, `<source>`, and `<document_content>` tags:

```xml
<documents>
  <document index="1">
    <source>src/auth.py</source>
    <document_content>
      {{AUTH_PY_CONTENT}}
    </document_content>
  </document>
  <document index="2">
    <source>src/middleware.py</source>
    <document_content>
      {{MIDDLEWARE_CONTENT}}
    </document_content>
  </document>
</documents>

Analyze both files for authentication vulnerabilities and cross-cutting concerns.
```

**Best practice**: Put long documents and data at the top of the prompt, above your instructions and query. Queries at the end can improve response quality by up to 30% with complex, multi-document inputs.

## Provide Examples

When output format matters, include 3-5 examples. Wrap examples in `<example>` tags (multiple in `<examples>`) so Claude distinguishes them from instructions.

```xml
<examples>
  <example>
    <input>Review src/auth.py for SQL injection</input>
    <output>
    - Line 42: `execute(f"SELECT * FROM users WHERE id={user_id}")` — SQL injection via string interpolation. Fixed with parameterized query.
    - Line 87: `cursor.execute("DELETE FROM sessions WHERE token='" + token + "'")` — SQL injection via concatenation. Fixed with parameterized query.
    </output>
  </example>
</examples>
```

Cover edge cases, not just the happy path. Vary examples enough that Claude doesn't pick up unintended patterns.

## Leverage Parallel Execution

Claude excels at parallel tool calls. To maximize this:

```xml
<use_parallel_tool_calls>
If you intend to call multiple tools and there are no dependencies between the calls, make all independent calls in parallel. However, if some calls depend on previous results, call them sequentially. Never use placeholders or guess missing parameters.
</use_parallel_tool_calls>
```

## Ask Claude to Self-Check

For tasks where correctness matters, ask Claude to verify its own work before finishing. This catches errors reliably, especially for coding and math.

- "Before you finish, verify your changes against each requirement in this task."
- "After implementing the fix, re-read the modified file and confirm the issue is resolved."

## Request Summaries When Needed

Claude Opus 4.6 is concise and may skip verbal summaries after tool use, jumping directly to the next action. Since relay responses are the only record the caller receives, request summaries explicitly when visibility matters.

- "After completing the task, summarize what you changed and why."
- "After each major step, briefly state what you did before moving on."

## Investigate Before Answering

For codebase tasks, tell Claude to read the relevant files before making claims. This reduces confident but ungrounded answers — the most common agentic hallucination mode.

```xml
<investigate_before_answering>
Never speculate about code you have not opened. If the task references a specific file, read it before answering. Investigate and read relevant files BEFORE making claims about the codebase.
</investigate_before_answering>
```

## Confirm Risky Actions

When Claude is acting autonomously, be explicit about which actions require confirmation. Without guidance, it may take hard-to-reverse actions as part of "making progress."

```xml
<confirm_before_risky_actions>
Take local, reversible actions freely (edit files, run tests, local commits). For actions that are hard to reverse, affect shared systems, or could be destructive, state what you would do and ask before proceeding.

Examples that warrant confirmation:
- Deleting files or branches
- git push --force, git reset --hard, amending published commits
- Posting comments, sending messages, modifying shared infrastructure
</confirm_before_risky_actions>
```

## Keep Agentic Coding Tight

Claude Opus tends to overengineer — adding abstractions, extra files, or defensive code beyond what was asked. Constrain scope explicitly.

```xml
<keep_changes_minimal>
Only make changes that are directly requested or clearly necessary. Keep the solution simple and focused.

- Do not add features, abstractions, or refactors beyond the task.
- Do not create helper scripts or temporary files unless genuinely needed. If you create temporary artifacts during iteration, remove them before finishing.
- Implement a general solution, not one tailored only to the visible tests.
- If the task or tests appear wrong, say so instead of coding around them.
</keep_changes_minimal>
```

## Don't Over-Prompt

Claude Opus is proactive and follows normal-weight instructions reliably. Heavy-handed prompting that was needed for older models can cause overtriggering.

- Instead of "CRITICAL: You MUST use this tool when...", use "Use this tool when..." — Claude follows this reliably
- Avoid excessive MUST/NEVER/ALWAYS unless truly non-negotiable
- Reserve strong directives for genuinely safety-critical requirements

### Step 2.5: Validate Before Responding

Before answering, do a quick sanity check on the fetched content:
- Title/authors are present and match the requested paper
- Abstract or introduction is visible
- Section structure exists

If any of these fail, fall through to the next method rather than answering from bad content. If all methods produce partial or degraded content, tell the user which methods were tried, what's missing, and offer a best-effort answer with appropriate caveats.

### Step 3: Respond to the User

Briefly mention which source was used (e.g., "I loaded this from the TeX source" or "Reading the HuggingFace markdown version"). One sentence is enough — don't belabor it.

Respond based on what the user asked:

- **No specific question** (just shared a link): Give a brief 2-3 sentence summary of what the paper is about, then ask what they'd like to know. Don't dump a full summary unprompted.
- **Specific question**: Answer it directly, citing relevant sections and equations from the paper.
- **"Summarize this"**: Provide a structured summary with core thesis, method, key results.
- **"Explain section X"**: Go deep on that section, unpacking the math and intuition.
- **Follow-up questions**: Answer naturally from the loaded content.
- **Paper too long for context**: If only core sections were loaded, tell the user: "I've loaded the main sections. Ask about specific parts and I'll read those in detail."

**Math notation**: When the source is TeX or clean markdown, reproduce key equations using `$inline$` and `$$block$$` notation. Define variables after equations. When the source is HTML or PDF, only reproduce equations that are clearly intact — otherwise paraphrase the mathematical structure and note that notation may be lossy.

**Figures**: The TeX source includes the figure files referenced by `\includegraphics`. When a question depends on what a figure shows, open that image file instead of relying on the caption alone.

### Cleanup

After the conversation with a paper is done, clean up temp files: `rm -rf /tmp/{id}.tar.gz /tmp/arxiv-{id} /tmp/hf-{id}.md /tmp/arxiv-{id}.pdf`

## What This Skill Does NOT Do

- **Read non-arxiv papers** — this skill is specifically for arxiv. For other PDFs, read them directly.

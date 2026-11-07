#### Method 4: PDF (last resort)

Some older papers only have a PDF. This is the least preferred method because PDF parsing loses math notation fidelity and may introduce artifacts.

1. `curl -fL -o /tmp/arxiv-{id}.pdf https://arxiv.org/pdf/{id}`
2. Read the PDF. For long papers (>15 pages), start with the first 15 pages, then read additional pages as needed for the user's question.
3. Let the user know you're working from the PDF — prefer conceptual summaries over exact symbolic reconstruction when equation fidelity is unclear.


# Citation APIs

## Semantic Scholar

Search and retrieve paper metadata:

```python
from semanticscholar import SemanticScholar

sch = SemanticScholar()
results = sch.search_paper("transformer attention mechanism", limit=10)

for paper in results:
    print(f"Title: {paper.title}")
    print(f"Year: {paper.year}")
    print(f"DOI: {paper.externalIds.get('DOI', 'N/A')}")
    print(f"arXiv: {paper.externalIds.get('ArXiv', 'N/A')}")
    print(f"Citations: {paper.citationCount}")
```

Get paper by DOI:
```python
paper = sch.get_paper(f"DOI:10.48550/arXiv.1706.03762")
```

## BibTeX via DOI

Fetch verified BibTeX using DOI content negotiation:

```python
import requests

def doi_to_bibtex(doi: str) -> str:
    resp = requests.get(
        f"https://doi.org/{doi}",
        headers={"Accept": "application/x-bibtex"},
        allow_redirects=True
    )
    resp.raise_for_status()
    return resp.text

# Example
bibtex = doi_to_bibtex("10.48550/arXiv.1706.03762")
```

## Verification

Verify paper exists in multiple sources:

```python
def verify_paper(doi=None, arxiv_id=None):
    sch = SemanticScholar()
    sources = []

    # Semantic Scholar
    if doi:
        paper = sch.get_paper(f"DOI:{doi}")
        if paper:
            sources.append("Semantic Scholar")

    # CrossRef
    if doi:
        resp = requests.get(f"https://api.crossref.org/works/{doi}")
        if resp.status_code == 200:
            sources.append("CrossRef")

    # arXiv
    if arxiv_id:
        resp = requests.get(f"http://export.arxiv.org/api/query?id_list={arxiv_id}")
        if "<entry>" in resp.text:
            sources.append("arXiv")

    return len(sources) >= 2, sources
```

## Rate Limits

| API | Limit |
|-----|-------|
| Semantic Scholar | 1 req/sec (free) |
| CrossRef | Polite pool with mailto header |
| arXiv | 3 second delays |

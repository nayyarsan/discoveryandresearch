# Discovery Agent — Design Spec
**Date:** 2026-03-16
**Repo:** `nayyarsan/discoveryandresearch`
**Status:** Approved

---

## Overview

A weekly automated discovery engine that finds new, obscure, and useful open source repositories relevant to enterprise AI development, SDLC/STLC, AI operations, and AI services. It publishes a `spotlight.json` to an orphan `output` branch (consumed by `nayyarsan/mynewsletters` as a Repo Spotlight section) and a GitHub Pages index of all discovered repos over time.

This repo is the **research and discovery foundation** of a broader platform. Future work includes multi-format delivery enhancements to `mynewsletters` (GitHub Pages output, podcast generation).

---

## Scope (this spec)

- Weekly repo discovery pipeline
- Filter, deduplicate, and score discovered repos
- Publish `spotlight.json` to `output` branch
- Publish `index.html` to `gh-pages` branch (GitHub Pages)

Out of scope: newsletter enhancements, podcast generation, GitHub Pages for the newsletter.

---

## Architecture

```
discoveryandresearch/
├── .github/workflows/discover.yml
├── scrapers/
│   ├── github_trending.py
│   ├── hackernews.py          # adapted from mynewsletters/scrapers/api.py
│   ├── reddit.py              # adapted from mynewsletters/scrapers/api.py
│   ├── github_search.py
│   ├── papers_with_code.py
│   └── web_aggregators.py     # console.dev, daily.dev
├── pipeline/
│   ├── filter.py
│   ├── deduplicate.py
│   ├── score.py
│   └── publish.py
├── schemas/
│   └── repo.py                # Repo pydantic model
├── pages/
│   └── build.py               # Generates index.html for GitHub Pages
├── requirements.txt
└── pyproject.toml
```

---

## Data Model

```python
class Repo(BaseModel):
    id: str              # sha256 of github url
    name: str            # owner/repo
    url: str
    description: str
    language: str        # python | javascript | typescript
    stars: int
    stars_delta: int     # stars gained this week (where available)
    license: str         # mit | apache-2.0
    source: str          # github_trending | hackernews | reddit | github_search | papers_with_code | web_aggregators
    discovered_at: datetime
    topics: list[str]
    score: float
    why_notable: str     # human-readable reason (e.g. "312 new stars this week")
```

---

## Discovery Sources

| Source | Method | Notes |
|---|---|---|
| GitHub Trending | GitHub API / scrape | Filter by Python, JS, TS; daily & weekly trending |
| Hacker News | Algolia HN API | Filter `Show HN` + `github.com` URLs from past 7 days |
| Reddit | RSS feeds | r/LocalLLaMA, r/MachineLearning, r/artificial — filter for GitHub links |
| GitHub Search | GitHub API | Topic-based search: `ai`, `agent`, `llm`, `sdlc`, `devops`, `eval`, `prompt` |
| Papers with Code | PwC API | Repos linked to papers published in past 7 days |
| Web Aggregators | HTTP scrape | console.dev, daily.dev GitHub repo entries |

---

## Filter Chain

Applied in order, failing any check drops the repo:

1. **Language:** Python, JavaScript, or TypeScript only
2. **Stars:** ≥ 50 total
3. **License:** MIT or Apache-2.0 only — hard reject AGPL, GPL, proprietary
4. **Not seen before:** cross-check against `discovered-repos.json` cache
5. **Relevance:** must match ≥ 1 topic keyword: `ai`, `agent`, `llm`, `sdlc`, `devops`, `eval`, `prompt`, `copilot`, `rag`, `mcp`, `workflow`, `pipeline`, `enterprise`

---

## Deduplication

Uses **GitHub Actions cache** (same pattern as `mynewsletters/summarize` job):

- Cache key: `discovered-repos-v1-{run_id}`
- Restore key prefix: `discovered-repos-v1-`
- Cache file: `data/discovered-repos.json` — list of repo IDs (sha256 of URL) seen in all prior runs
- On each run: restore latest cache → filter out known IDs → append new IDs → save updated cache

A repo re-appears in the spotlight only if it has not been seen before **or** if its `stars_delta` exceeds 500 in a single week (major update signal).

---

## Scoring

Repos are ranked by a weighted score:

| Signal | Weight |
|---|---|
| `stars_delta` (weekly growth) | 40% |
| Source count (seen in multiple sources) | 30% |
| Topic relevance match count | 20% |
| Recency (created in past 30 days) | 10% |

Top 5 repos per week are included in `spotlight.json`. If fewer than 1 repo passes all filters, `spotlight.json` is published with an empty `repos` array — the newsletter skips the spotlight section gracefully.

---

## Output

### `spotlight.json` (on `output` branch)

```json
{
  "generated_at": "2026-03-16T22:00:00Z",
  "repos": [
    {
      "name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "description": "One-line description",
      "stars": 1240,
      "stars_delta": 312,
      "license": "mit",
      "language": "python",
      "topics": ["agent", "llm"],
      "why_notable": "312 new stars this week, trending in AI agents",
      "source": "github_trending"
    }
  ]
}
```

Raw URL consumed by `mynewsletters`:
`https://raw.githubusercontent.com/nayyarsan/discoveryandresearch/output/data/spotlight.json`

### `index.html` (on `gh-pages` branch)

A simple static page listing all historically discovered repos, updated weekly. Hosted at `https://nayyarsan.github.io/discoveryandresearch/`.

---

## GitHub Action Workflow

**Schedule:** `0 22 * * 0` — Sunday 10pm UTC (4 hours before Monday newsletter at 2pm UTC)
**Manual trigger:** `workflow_dispatch`

```
discover.yml jobs:
│
├── scrape (matrix: parallel per source)
│   └── uploads artifact: raw-{source}.json
│
├── filter (needs: scrape)
│   └── uploads artifact: filtered.json
│
├── deduplicate (needs: filter)
│   ├── restores actions/cache: discovered-repos-v1-
│   ├── removes known repos
│   └── uploads artifact: new-repos.json
│
├── score (needs: deduplicate)
│   └── uploads artifact: scored.json
│
└── publish (needs: score)
    ├── commits spotlight.json → output branch
    ├── updates discovered-repos.json → saves actions/cache
    └── builds + commits index.html → gh-pages branch
```

**Required secrets:**
- `GITHUB_TOKEN` — for GitHub API calls and branch pushes (auto-provided)
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` — for Reddit API (optional, falls back to RSS)

---

## Integration with `mynewsletters`

Minimal changes required:

1. Add to `sources/sources.yaml`:
```yaml
- name: repo_spotlight
  display_name: "Repo Spotlight"
  type: json
  url: "https://raw.githubusercontent.com/nayyarsan/discoveryandresearch/output/data/spotlight.json"
  weight: high
```

2. Add `scrapers/spotlight_fetcher.py` (~30 lines) — reads the JSON, maps each repo entry to a `Story` object for the existing pipeline.

No other changes to `mynewsletters`.

---

## Refinement Strategy

Filters (star threshold, topic keywords, scoring weights) are intentionally loose in v1. After the first 2-3 runs, the discovered repos will be reviewed manually and filters tightened based on signal quality.

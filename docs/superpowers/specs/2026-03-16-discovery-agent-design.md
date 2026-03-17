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
    stars_delta: int     # stars gained this week; 0 if source does not provide this
    license: str         # mit | apache-2.0
    source: str          # github_trending | hackernews | reddit | github_search | papers_with_code | web_aggregators
    discovered_at: datetime  # UTC
    topics: list[str]
    score: float
    why_notable: str     # human-readable reason (e.g. "312 new stars this week")
```

**`stars_delta` calculation:**
- `github_trending` and `github_search`: provided by GitHub API via the `stargazers` timeline endpoint. If unavailable, defaults to `0`.
- `hackernews`, `reddit`, `web_aggregators`, `papers_with_code`: no historical star data available from the source; `stars_delta` defaults to `0`. These repos rely on topic relevance and source count for scoring instead.

**License detection:** Uses the GitHub API `license` field (`repo.license.spdx_id`). Repos with `null` license or an unrecognised SPDX ID are rejected at the filter step.

**`discovered_at`:** Always stored in UTC.

---

## Discovery Sources

| Source | Method | Notes |
|---|---|---|
| `github_trending` | HTML scrape of `github.com/trending/{lang}?since=weekly` | Python, JS, TS — weekly view. No auth required. |
| `hackernews` | Algolia HN API (`hn.algolia.com/api/v1/search`) | Filter `Show HN` + `github.com` URLs, past 7 days. Adapted from `mynewsletters/scrapers/api.py`. |
| `reddit` | Reddit RSS feeds (no auth required as fallback) | r/LocalLLaMA, r/MachineLearning, r/artificial. RSS URLs: `https://www.reddit.com/r/{sub}/new.rss`. Filter entries containing `github.com`. Adapted from `mynewsletters/scrapers/api.py`. Optional: use Reddit OAuth API via `REDDIT_CLIENT_ID`/`SECRET` for richer metadata. |
| `github_search` | GitHub REST API `/search/repositories` | Queries: `topic:llm`, `topic:ai-agent`, `topic:sdlc` etc. Sort by `stars`, filter `pushed:>={7_days_ago}`. Max 1000 results per query; paginate up to 3 pages. |
| `papers_with_code` | PwC REST API `paperswithcode.com/api/v1/papers/` | Filter papers published in past 7 days with a linked GitHub repo. |
| `web_aggregators` | console.dev RSS feed + daily.dev public API | `console.dev`: RSS at `https://console.dev/tools/rss.xml`. `daily.dev`: public GraphQL API — no scraping required, no TOS risk. Filter for GitHub repo links. |

**Error handling:** Each scraper runs in an isolated matrix job. If a scraper fails (network error, rate limit, API change), the job marks itself as `continue-on-error: true`, uploads an empty `raw-{source}.json`, and the pipeline continues with the remaining sources. A warning is surfaced in the workflow summary. The overall workflow does not fail if at least one source produces results.

---

## Filter Chain

Applied in order, failing any check drops the repo:

1. **Language:** Python, JavaScript, or TypeScript only
2. **Stars:** ≥ 50 total
3. **License:** MIT or Apache-2.0 only — hard reject AGPL, GPL, proprietary, or null
4. **Relevance:** must match ≥ 1 topic keyword (case-insensitive, word-boundary match) in any of: `topics`, `description`, or repo `name`. Keywords: `ai`, `agent`, `llm`, `sdlc`, `devops`, `eval`, `prompt`, `copilot`, `rag`, `mcp`, `workflow`, `pipeline`, `enterprise`
5. **Not seen before:** cross-check against `discovered-repos.json` cache. A repo that was seen in a prior run is **re-admitted** only if its `stars_delta ≥ 500` this week (major update signal). This check happens after all other filters.

**First-run cache miss:** If no prior cache exists (first deployment), the cache file is treated as an empty set — all repos passing steps 1–4 are admitted. The cache is then saved at the end of the run.

---

## Deduplication

Uses **GitHub Actions cache** (same pattern as `mynewsletters/summarize` job):

- Cache key: `discovered-repos-v1-{run_id}` (unique per run, prevents overwriting mid-run)
- Restore key prefix: `discovered-repos-v1-` (picks up the most recent prior run's cache)
- Cache file: `data/discovered-repos.json` — list of repo IDs (sha256 of GitHub URL) seen in all prior runs

**Implementation in `deduplicate` job:**
```yaml
- uses: actions/cache/restore@v4       # explicit restore-only step
  with:
    path: data/discovered-repos.json
    key: discovered-repos-v1-${{ github.run_id }}
    restore-keys: discovered-repos-v1-

# ... deduplication script runs here ...

- uses: actions/cache/save@v4          # explicit save step in publish job
  with:
    path: data/discovered-repos.json
    key: discovered-repos-v1-${{ github.run_id }}
```

The `restore` step is in the `deduplicate` job; the `save` step is in `publish` (after spotlight.json is committed), so the cache is only updated on a successful full run. On first run, the restore step finds no matching cache — the file is initialised as `[]`.

---

## Scoring

Repos are ranked by a weighted score:

| Signal | Weight | Calculation |
|---|---|---|
| `stars_delta` (weekly growth) | 40% | Normalised 0–1 across candidates in this run |
| Source count (seen in multiple sources) | 30% | `min(source_count / 3, 1.0)` |
| Topic relevance match count | 20% | `min(match_count / 5, 1.0)` |
| Recency (created in past 30 days) | 10% | Binary: 1.0 if age ≤ 30 days, 0.0 otherwise |

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

2. Add `scrapers/spotlight_fetcher.py` (~30 lines) — reads the JSON, maps each repo entry to a `Story` object for the existing pipeline using this mapping:

| `Repo` field | → `Story` field |
|---|---|
| `name` + `why_notable` | → `title` (e.g. "owner/repo — 312 new stars this week") |
| `url` | → `canonical_url` |
| `"Repo Spotlight"` | → `sources[0].name` |
| `url` | → `sources[0].url` |
| `discovered_at` | → `published_at` |
| `description` + topics + license + language | → `raw_content` (formatted string) |

No other changes to `mynewsletters`.

---

## Refinement Strategy

Filters (star threshold, topic keywords, scoring weights) are intentionally loose in v1. After the first 2-3 runs, the discovered repos will be reviewed manually and filters tightened based on signal quality.

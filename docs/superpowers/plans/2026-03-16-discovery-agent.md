# Discovery Agent Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a weekly automated pipeline that scrapes 9 sources, filters and deduplicates open source repos, scores them, and publishes a `spotlight.json` plus a GitHub Pages index.

**Architecture:** Nine independent scrapers each produce a `list[Repo]`; a linear pipeline (filter → deduplicate → score) reduces them to the top 5; a publish step commits `spotlight.json` to an orphan `output` branch and `index.html` to `gh-pages`. State (seen repo IDs) is persisted via GitHub Actions cache between weekly runs.

**Tech Stack:** Python 3.12, pydantic 2, httpx 0.27, feedparser 6, beautifulsoup4 4.12, pytest 8, respx 0.21

---

## File Map

| File | Responsibility |
|---|---|
| `schemas/repo.py` | `Repo` pydantic model — single source of truth for data shape |
| `scrapers/base.py` | `BaseScraper` ABC — enforces `scrape() -> list[Repo]` interface |
| `scrapers/_http.py` | Shared HTTP/feed utilities — **copied and adapted from `mynewsletters/scrapers/`** (`fetch_rss_entries`, `fetch_hackernews_hits`, `fetch_html_page`, `fetch_github_api`) |
| `scrapers/github_trending.py` | HTML scrape of github.com/trending — uses `_http.fetch_html_page` |
| `scrapers/hackernews.py` | Algolia HN API — uses `_http.fetch_hackernews_hits` (adapted from `mynewsletters/scrapers/api.py`) |
| `scrapers/reddit.py` | RSS feeds for 3 subreddits, github.com link filter — uses `_http.fetch_rss_entries` (adapted from `mynewsletters/scrapers/api.py`), **RSS only, no OAuth** |
| `scrapers/lobsters.py` | RSS feed — uses `_http.fetch_rss_entries` (adapted from `mynewsletters/scrapers/rss.py`) |
| `scrapers/github_search.py` | GitHub REST API topic queries |
| `scrapers/papers_with_code.py` | PwC API, papers with linked GitHub repos |
| `scrapers/huggingface.py` | HF Hub API, new repos/spaces with GitHub links |
| `scrapers/web_aggregators.py` | console.dev RSS + daily.dev GraphQL |
| `scrapers/awesome_lists.py` | GitHub Commits API diff — newly added entries only |
| `pipeline/filter.py` | Language, stars, license, relevance filter chain |
| `pipeline/deduplicate.py` | Cross-check against cache, re-admit on stars_delta ≥ 500 |
| `pipeline/score.py` | Weighted score across 4 signals, return top N |
| `pipeline/publish.py` | Write spotlight.json, commit to output branch |
| `pages/build.py` | Generate index.html from all-time discovered repos |
| `tests/conftest.py` | Shared fixtures: sample Repo, mock HTTP responses |
| `tests/scrapers/test_*.py` | One test file per scraper |
| `tests/pipeline/test_*.py` | One test file per pipeline step |
| `pyproject.toml` | Project config and dependencies |
| `requirements.txt` | Pinned runtime deps |
| `requirements-dev.txt` | Pinned dev/test deps |
| `.github/workflows/discover.yml` | Full workflow: scrape → filter → dedup → score → publish |

---

## Chunk 1: Project Scaffolding and Schema

### Task 1: Initialise project files

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `schemas/__init__.py`
- Create: `scrapers/__init__.py`
- Create: `pipeline/__init__.py`
- Create: `pages/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/scrapers/__init__.py`
- Create: `tests/pipeline/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "discoveryagent"
version = "0.1.0"
description = "Weekly AI repo discovery engine"
requires-python = ">=3.12"
dependencies = [
    "feedparser==6.0.11",
    "httpx==0.27.2",
    "beautifulsoup4==4.12.3",
    "pyyaml==6.0.2",
    "pydantic==2.9.2",
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.3",
    "pytest-asyncio==0.24.0",
    "pytest-mock==3.14.0",
    "respx==0.21.1",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create `requirements.txt`**

```
feedparser==6.0.11
httpx==0.27.2
beautifulsoup4==4.12.3
pyyaml==6.0.2
pydantic==2.9.2
```

- [ ] **Step 3: Create `requirements-dev.txt`**

```
-r requirements.txt
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-mock==3.14.0
respx==0.21.1
```

- [ ] **Step 4: Create all `__init__.py` files (empty)**

```bash
touch schemas/__init__.py scrapers/__init__.py pipeline/__init__.py pages/__init__.py
mkdir -p tests/scrapers tests/pipeline
touch tests/__init__.py tests/scrapers/__init__.py tests/pipeline/__init__.py
```

- [ ] **Step 5: Install deps**

```bash
pip install -r requirements-dev.txt
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml requirements.txt requirements-dev.txt schemas/ scrapers/ pipeline/ pages/ tests/
git commit -m "chore: project scaffolding and dependencies"
```

---

### Task 2: Repo schema

**Files:**
- Create: `schemas/repo.py`
- Create: `tests/test_schema.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_schema.py
import hashlib
import pytest
from datetime import datetime, timezone
from schemas.repo import Repo

def test_repo_id_is_sha256_of_url():
    repo = Repo(
        name="owner/repo",
        url="https://github.com/owner/repo",
        description="A test repo",
        language="python",
        stars=100,
        stars_delta=0,
        license="mit",
        source="github_trending",
        discovered_at=datetime.now(tz=timezone.utc),
        topics=["ai"],
        score=0.0,
        why_notable="100 stars",
    )
    expected_id = hashlib.sha256("https://github.com/owner/repo".encode()).hexdigest()
    assert repo.id == expected_id

def test_repo_rejects_agpl_license():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Repo(
            name="owner/repo",
            url="https://github.com/owner/repo",
            description="A test repo",
            language="python",
            stars=100,
            stars_delta=0,
            license="agpl-3.0",
            source="github_trending",
            discovered_at=datetime.now(tz=timezone.utc),
            topics=[],
            score=0.0,
            why_notable="",
        )
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_schema.py -v
```
Expected: `ModuleNotFoundError: No module named 'schemas.repo'`

- [ ] **Step 3: Implement `schemas/repo.py`**

```python
import hashlib
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, computed_field, field_validator

ALLOWED_LICENSES = {"mit", "apache-2.0"}
ALLOWED_LANGUAGES = {"python", "javascript", "typescript"}
ALLOWED_SOURCES = {
    "github_trending", "hackernews", "reddit", "github_search",
    "papers_with_code", "web_aggregators", "huggingface", "lobsters", "awesome_lists",
}


class Repo(BaseModel):
    name: str
    url: str
    description: str
    language: str
    stars: int
    stars_delta: int = 0
    license: str
    source: str
    discovered_at: datetime
    topics: list[str]
    score: float = 0.0
    why_notable: str
    source_count: int = 1  # incremented when same repo found in multiple sources

    @computed_field
    @property
    def id(self) -> str:
        return hashlib.sha256(self.url.encode()).hexdigest()

    @field_validator("license")
    @classmethod
    def validate_license(cls, v: str) -> str:
        if v.lower() not in ALLOWED_LICENSES:
            raise ValueError(f"License '{v}' not allowed. Must be one of {ALLOWED_LICENSES}")
        return v.lower()

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v.lower() not in ALLOWED_LANGUAGES:
            raise ValueError(f"Language '{v}' not in {ALLOWED_LANGUAGES}")
        return v.lower()

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in ALLOWED_SOURCES:
            raise ValueError(f"Source '{v}' not in {ALLOWED_SOURCES}")
        return v
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/test_schema.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add schemas/repo.py tests/test_schema.py
git commit -m "feat: Repo schema with license/language/source validation"
```

---

### Task 3: BaseScraper + shared test fixtures

**Files:**
- Create: `scrapers/base.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `scrapers/base.py`**

```python
from abc import ABC, abstractmethod
from schemas.repo import Repo


class BaseScraper(ABC):
    """All scrapers must implement scrape() -> list[Repo].
    Individual scrapers are responsible for filtering by language/license
    at the point of construction — BaseScraper enforces the interface only."""

    @abstractmethod
    def scrape(self) -> list[Repo]:
        """Return repos found from this source. Never raises — returns [] on error."""
        ...
```

- [ ] **Step 2: Create `tests/conftest.py`**

```python
import pytest
from datetime import datetime, timezone
from schemas.repo import Repo


@pytest.fixture
def sample_repo() -> Repo:
    return Repo(
        name="owner/cool-agent",
        url="https://github.com/owner/cool-agent",
        description="A cool AI agent framework",
        language="python",
        stars=250,
        stars_delta=80,
        license="mit",
        source="github_trending",
        discovered_at=datetime(2026, 3, 16, 22, 0, 0, tzinfo=timezone.utc),
        topics=["ai", "agent", "llm"],
        score=0.0,
        why_notable="80 new stars this week",
    )


@pytest.fixture
def sample_repos(sample_repo) -> list[Repo]:
    """5 repos with varying scores."""
    from copy import deepcopy
    repos = []
    for i in range(5):
        r = deepcopy(sample_repo)
        r = r.model_copy(update={
            "name": f"owner/repo-{i}",
            "url": f"https://github.com/owner/repo-{i}",
            "stars": 100 + i * 50,
            "stars_delta": i * 20,
        })
        repos.append(r)
    return repos
```

- [ ] **Step 3: Verify fixtures load**

```bash
pytest tests/ --collect-only
```
Expected: no import errors

- [ ] **Step 4: Commit**

```bash
git add scrapers/base.py tests/conftest.py
git commit -m "feat: BaseScraper ABC and shared test fixtures"
```

---

### Task 3b: Shared HTTP/feed utilities (`scrapers/_http.py`)

**Copied and adapted from `nayyarsan/mynewsletters` — do NOT rewrite from scratch.**

**Files:**
- Create: `scrapers/_http.py`
- Source reference: `mynewsletters/scrapers/api.py`, `mynewsletters/scrapers/rss.py`, `mynewsletters/scrapers/html.py`

- [ ] **Step 1: Create `scrapers/_http.py`** — adapt the four helpers below from the newsletter, replacing `Story` returns with raw dicts/lists that scrapers can work with

```python
# scrapers/_http.py
"""Shared HTTP and feed utilities.
Adapted from nayyarsan/mynewsletters/scrapers/ (api.py, rss.py, html.py).
Returns raw data (dicts, feedparser entries) — scrapers own the Repo construction.
"""
import re
import httpx
import feedparser
from datetime import datetime, timezone, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DiscoveryAgent/1.0)"}
GITHUB_RE = re.compile(r"https?://github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)")


def fetch_rss_entries(
    url: str,
    client: httpx.Client,
    max_age_days: int = 7,
) -> list:
    """Return feedparser entries from an RSS/Atom feed, filtered to max_age_days.
    Adapted from mynewsletters/scrapers/rss.py::fetch_rss().
    Returns [] on any error."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=max_age_days)
    try:
        resp = client.get(url)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        if feed.bozo and not feed.entries:
            return []
    except Exception:
        return []

    entries = []
    for entry in feed.entries:
        t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if t:
            published_at = datetime(t[0], t[1], t[2], t[3], t[4], t[5], tzinfo=timezone.utc)
            if published_at < cutoff:
                continue
        entries.append(entry)
    return entries


def fetch_hackernews_hits(
    client: httpx.Client,
    lookback_days: int = 7,
) -> list[dict]:
    """Return HN Algolia API hits for Show HN posts containing github.com.
    Adapted from mynewsletters/scrapers/api.py::fetch_hackernews().
    Returns [] on any error."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=lookback_days)
    try:
        resp = client.get(
            "https://hn.algolia.com/api/v1/search",
            params={
                "query": "Show HN github.com",
                "tags": "show_hn",
                "numericFilters": f"created_at_i>{int(cutoff.timestamp())}",
                "hitsPerPage": 50,
            },
        )
        resp.raise_for_status()
        return resp.json().get("hits", [])
    except Exception:
        return []


def fetch_github_api(path: str, client: httpx.Client) -> dict | None:
    """Fetch a GitHub repo's metadata via REST API. Returns None on error.
    Used by all scrapers to validate license, language, stars."""
    try:
        resp = client.get(
            f"https://api.github.com/repos/{path}",
            headers={**HEADERS, "Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def extract_github_paths(text: str) -> list[str]:
    """Return all unique 'owner/repo' paths found in text."""
    return list(dict.fromkeys(
        m.group(1).rstrip("/") for m in GITHUB_RE.finditer(text)
    ))
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
python -c "from scrapers._http import fetch_rss_entries, fetch_hackernews_hits, fetch_github_api, extract_github_paths; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add scrapers/_http.py
git commit -m "feat: shared HTTP/feed utilities (adapted from mynewsletters)"
```

---

## Chunk 2: Simple Scrapers (Trending, HN, Reddit, Lobste.rs)

### Task 4: GitHub Trending scraper

**Files:**
- Create: `scrapers/github_trending.py`
- Create: `tests/scrapers/test_github_trending.py`

- [ ] **Step 1: Write failing test**

```python
# tests/scrapers/test_github_trending.py
import respx
import httpx
import pytest
from scrapers.github_trending import GitHubTrendingScraper

MOCK_HTML = """
<html><body>
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/owner/cool-agent">owner / cool-agent</a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">A cool AI agent framework</p>
  <span class="d-inline-block float-sm-right">
    <a href="/owner/cool-agent/stargazers">1,240</a>
  </span>
  <span class="d-inline-block float-sm-right">312 stars this week</span>
  <span itemprop="programmingLanguage">Python</span>
  <a href="/owner/cool-agent">MIT</a>
</article>
</body></html>
"""

@respx.mock
def test_scrape_returns_repos():
    for lang in ["python", "javascript", "typescript"]:
        respx.get(f"https://github.com/trending/{lang}").mock(
            return_value=httpx.Response(200, text=MOCK_HTML)
        )
    # GitHub API for license check
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json={
            "stargazers_count": 1240,
            "license": {"spdx_id": "MIT"},
            "language": "Python",
            "description": "A cool AI agent framework",
            "topics": ["ai", "agent"],
            "created_at": "2026-01-01T00:00:00Z",
        })
    )
    scraper = GitHubTrendingScraper()
    repos = scraper.scrape()
    assert len(repos) >= 1
    assert repos[0].name == "owner/cool-agent"
    assert repos[0].stars_delta == 312
    assert repos[0].source == "github_trending"

@respx.mock
def test_scrape_returns_empty_on_http_error():
    for lang in ["python", "javascript", "typescript"]:
        respx.get(f"https://github.com/trending/{lang}").mock(
            return_value=httpx.Response(500)
        )
    scraper = GitHubTrendingScraper()
    repos = scraper.scrape()
    assert repos == []
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/scrapers/test_github_trending.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement `scrapers/github_trending.py`**

```python
import re
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper
from scrapers._http import HEADERS, fetch_github_api

LANGUAGES = ["python", "javascript", "typescript"]


class GitHubTrendingScraper(BaseScraper):
    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(headers=HEADERS, timeout=15)

    def scrape(self) -> list[Repo]:
        seen: set[str] = set()
        repos: list[Repo] = []
        for lang in LANGUAGES:
            try:
                resp = self._client.get(f"https://github.com/trending/{lang}?since=weekly")
                resp.raise_for_status()
                repos.extend(self._parse(resp.text, seen))
            except Exception:
                continue
        return repos

    def _parse(self, html: str, seen: set[str]) -> list[Repo]:
        soup = BeautifulSoup(html, "html.parser")
        repos = []
        for article in soup.select("article.Box-row"):
            try:
                link = article.select_one("h2 a")
                if not link:
                    continue
                path = link["href"].strip("/")  # owner/repo
                if path in seen:
                    continue
                seen.add(path)

                url = f"https://github.com/{path}"
                description_elem = article.select_one("p")
                description = description_elem.get_text(strip=True) if description_elem else ""

                # Stars delta from "N stars this week"
                delta_text = article.get_text()
                delta_match = re.search(r"([\d,]+)\s+stars this week", delta_text)
                stars_delta = int(delta_match.group(1).replace(",", "")) if delta_match else 0

                # Fetch full repo details from GitHub API for license, language, stars
                repo_data = fetch_github_api(path, self._client)
                if not repo_data:
                    continue

                license_id = (repo_data.get("license") or {}).get("spdx_id", "").lower()
                if license_id not in ALLOWED_LICENSES:
                    continue

                language = (repo_data.get("language") or "").lower()
                if language not in {"python", "javascript", "typescript"}:
                    continue

                repos.append(Repo(
                    name=path,
                    url=url,
                    description=repo_data.get("description") or description,
                    language=language,
                    stars=repo_data.get("stargazers_count", 0),
                    stars_delta=stars_delta,
                    license=license_id,
                    source="github_trending",
                    discovered_at=datetime.now(tz=timezone.utc),
                    topics=repo_data.get("topics") or [],
                    why_notable=f"{stars_delta} new stars this week" if stars_delta else "Trending this week",
                ))
            except Exception:
                continue
        return repos
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/scrapers/test_github_trending.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scrapers/github_trending.py tests/scrapers/test_github_trending.py
git commit -m "feat: GitHub Trending scraper"
```

---

### Task 5: Hacker News scraper

**Files:**
- Create: `scrapers/hackernews.py`
- Create: `tests/scrapers/test_hackernews.py`

- [ ] **Step 1: Write failing test**

```python
# tests/scrapers/test_hackernews.py
import respx
import httpx
import pytest
from scrapers.hackernews import HackerNewsScraper

HN_RESPONSE = {
    "hits": [
        {
            "objectID": "12345",
            "title": "Show HN: cool-agent – AI agent framework",
            "url": "https://github.com/owner/cool-agent",
            "story_text": None,
            "created_at": "2026-03-15T10:00:00Z",
        },
        {
            "objectID": "99999",
            "title": "Show HN: not-a-github-link",
            "url": "https://example.com/something",
            "story_text": None,
            "created_at": "2026-03-15T10:00:00Z",
        },
    ]
}

GITHUB_API_RESPONSE = {
    "stargazers_count": 300,
    "license": {"spdx_id": "MIT"},
    "language": "Python",
    "description": "AI agent framework",
    "topics": ["ai", "agent"],
    "created_at": "2026-01-01T00:00:00Z",
}

@respx.mock
def test_scrape_filters_non_github_urls():
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(200, json=HN_RESPONSE)
    )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = HackerNewsScraper()
    repos = scraper.scrape()
    assert len(repos) == 1
    assert repos[0].name == "owner/cool-agent"
    assert repos[0].source == "hackernews"

@respx.mock
def test_scrape_returns_empty_on_api_error():
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(503)
    )
    scraper = HackerNewsScraper()
    assert scraper.scrape() == []
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/scrapers/test_hackernews.py -v
```

- [ ] **Step 3: Implement `scrapers/hackernews.py`**

```python
import httpx
from datetime import datetime, timezone
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper
from scrapers._http import HEADERS, fetch_hackernews_hits, fetch_github_api, extract_github_paths


class HackerNewsScraper(BaseScraper):
    def __init__(self, client: httpx.Client | None = None, lookback_days: int = 7):
        self._client = client or httpx.Client(headers=HEADERS, timeout=15)
        self._lookback_days = lookback_days

    def scrape(self) -> list[Repo]:
        hits = fetch_hackernews_hits(self._client, self._lookback_days)

        repos = []
        for hit in hits:
            url = hit.get("url") or ""
            if "github.com" not in url:
                continue
            paths = extract_github_paths(url)
            if not paths:
                continue
            path = paths[0]
            repo_data = fetch_github_api(path, self._client)
            if not repo_data:
                continue
            license_id = (repo_data.get("license") or {}).get("spdx_id", "").lower()
            if license_id not in ALLOWED_LICENSES:
                continue
            language = (repo_data.get("language") or "").lower()
            if language not in {"python", "javascript", "typescript"}:
                continue
            try:
                published_at = datetime.fromisoformat(hit["created_at"].replace("Z", "+00:00"))
            except Exception:
                published_at = datetime.now(tz=timezone.utc)
            repos.append(Repo(
                name=path,
                url=f"https://github.com/{path}",
                description=repo_data.get("description") or hit.get("title", ""),
                language=language,
                stars=repo_data.get("stargazers_count", 0),
                stars_delta=0,
                license=license_id,
                source="hackernews",
                discovered_at=datetime.now(tz=timezone.utc),
                topics=repo_data.get("topics") or [],
                why_notable=f"Featured on Hacker News: {hit.get('title', '')}",
            ))
        return repos
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/scrapers/test_hackernews.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scrapers/hackernews.py tests/scrapers/test_hackernews.py
git commit -m "feat: Hacker News scraper (Show HN + github.com filter)"
```

---

### Task 6: Reddit scraper

**Files:**
- Create: `scrapers/reddit.py`
- Create: `tests/scrapers/test_reddit.py`

- [ ] **Step 1: Write failing test**

```python
# tests/scrapers/test_reddit.py
import respx
import httpx
from scrapers.reddit import RedditScraper

RSS_WITH_GITHUB = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Check out this agent framework</title>
    <link href="https://github.com/owner/cool-agent"/>
    <updated>2026-03-15T10:00:00+00:00</updated>
    <content>Some content about https://github.com/owner/cool-agent</content>
  </entry>
  <entry>
    <title>No github link here</title>
    <link href="https://reddit.com/r/LocalLLaMA/post/123"/>
    <updated>2026-03-15T10:00:00+00:00</updated>
    <content>No link</content>
  </entry>
</feed>"""

GITHUB_API_RESPONSE = {
    "stargazers_count": 150,
    "license": {"spdx_id": "Apache-2.0"},
    "language": "TypeScript",
    "description": "Cool agent",
    "topics": ["agent"],
    "created_at": "2026-02-01T00:00:00Z",
}

@respx.mock
def test_scrape_extracts_github_links_from_rss():
    for sub in ["LocalLLaMA", "MachineLearning", "artificial"]:
        respx.get(f"https://www.reddit.com/r/{sub}/new.rss").mock(
            return_value=httpx.Response(200, text=RSS_WITH_GITHUB)
        )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = RedditScraper()
    repos = scraper.scrape()
    assert any(r.name == "owner/cool-agent" for r in repos)
    assert all(r.source == "reddit" for r in repos)

@respx.mock
def test_scrape_deduplicates_across_subreddits():
    for sub in ["LocalLLaMA", "MachineLearning", "artificial"]:
        respx.get(f"https://www.reddit.com/r/{sub}/new.rss").mock(
            return_value=httpx.Response(200, text=RSS_WITH_GITHUB)
        )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = RedditScraper()
    repos = scraper.scrape()
    assert len(repos) == 1  # same repo in 3 subreddits — dedup returns only 1
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/scrapers/test_reddit.py -v
```

- [ ] **Step 3: Implement `scrapers/reddit.py`**

```python
import httpx
from datetime import datetime, timezone
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper
from scrapers._http import HEADERS, fetch_rss_entries, fetch_github_api, extract_github_paths

SUBREDDITS = ["LocalLLaMA", "MachineLearning", "artificial"]


class RedditScraper(BaseScraper):
    def __init__(self, client: httpx.Client | None = None, lookback_days: int = 7):
        self._client = client or httpx.Client(headers=HEADERS, timeout=15)
        self._lookback_days = lookback_days

    def scrape(self) -> list[Repo]:
        seen_paths: set[str] = set()
        repos: list[Repo] = []
        for sub in SUBREDDITS:
            url = f"https://www.reddit.com/r/{sub}/new.rss"
            entries = fetch_rss_entries(url, self._client, max_age_days=self._lookback_days)
            for entry in entries:
                text = f"{getattr(entry, 'link', '')} {getattr(entry, 'summary', '')}"
                for path in extract_github_paths(text):
                    if path in seen_paths:
                        continue
                    seen_paths.add(path)
                    repo_data = fetch_github_api(path, self._client)
                    if not repo_data:
                        continue
                    license_id = (repo_data.get("license") or {}).get("spdx_id", "").lower()
                    if license_id not in ALLOWED_LICENSES:
                        continue
                    language = (repo_data.get("language") or "").lower()
                    if language not in {"python", "javascript", "typescript"}:
                        continue
                    repos.append(Repo(
                        name=path,
                        url=f"https://github.com/{path}",
                        description=repo_data.get("description") or "",
                        language=language,
                        stars=repo_data.get("stargazers_count", 0),
                        stars_delta=0,
                        license=license_id,
                        source="reddit",
                        discovered_at=datetime.now(tz=timezone.utc),
                        topics=repo_data.get("topics") or [],
                        why_notable=f"Discussed on r/{sub}",
                    ))
        return repos
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/scrapers/test_reddit.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scrapers/reddit.py tests/scrapers/test_reddit.py
git commit -m "feat: Reddit scraper (3 subreddits, github.com link extraction)"
```

---

### Task 7: Lobste.rs scraper

**Files:**
- Create: `scrapers/lobsters.py`
- Create: `tests/scrapers/test_lobsters.py`

- [ ] **Step 1: Write failing test**

```python
# tests/scrapers/test_lobsters.py
import respx
import httpx
from scrapers.lobsters import LobstersScraper

RSS = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>cool-agent: A new AI agent framework</title>
    <link href="https://github.com/owner/cool-agent"/>
    <updated>2026-03-15T10:00:00+00:00</updated>
  </entry>
</feed>"""

GITHUB_API_RESPONSE = {
    "stargazers_count": 80,
    "license": {"spdx_id": "MIT"},
    "language": "Python",
    "description": "AI agent framework",
    "topics": ["ai"],
    "created_at": "2026-03-01T00:00:00Z",
}

@respx.mock
def test_scrape_returns_github_repos():
    for tag in ["ai", "programming"]:
        respx.get(f"https://lobste.rs/t/{tag}.rss").mock(
            return_value=httpx.Response(200, text=RSS)
        )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = LobstersScraper()
    repos = scraper.scrape()
    assert len(repos) == 1
    assert repos[0].source == "lobsters"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/scrapers/test_lobsters.py -v
```

- [ ] **Step 3: Implement `scrapers/lobsters.py`**

```python
import httpx
from datetime import datetime, timezone
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper
from scrapers._http import HEADERS, fetch_rss_entries, fetch_github_api, extract_github_paths

TAGS = ["ai", "programming"]


class LobstersScraper(BaseScraper):
    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(headers=HEADERS, timeout=15)

    def scrape(self) -> list[Repo]:
        seen: set[str] = set()
        repos: list[Repo] = []
        for tag in TAGS:
            url = f"https://lobste.rs/t/{tag}.rss"
            entries = fetch_rss_entries(url, self._client)
            for entry in entries:
                link = getattr(entry, "link", "") or ""
                paths = extract_github_paths(link)
                if not paths:
                    continue
                path = paths[0]
                if path in seen:
                    continue
                seen.add(path)
                repo_data = fetch_github_api(path, self._client)
                if not repo_data:
                    continue
                license_id = (repo_data.get("license") or {}).get("spdx_id", "").lower()
                if license_id not in ALLOWED_LICENSES:
                    continue
                language = (repo_data.get("language") or "").lower()
                if language not in {"python", "javascript", "typescript"}:
                    continue
                repos.append(Repo(
                    name=path,
                    url=f"https://github.com/{path}",
                    description=repo_data.get("description") or "",
                    language=language,
                    stars=repo_data.get("stargazers_count", 0),
                    stars_delta=0,
                    license=license_id,
                    source="lobsters",
                    discovered_at=datetime.now(tz=timezone.utc),
                    topics=repo_data.get("topics") or [],
                    why_notable=f"Featured on Lobste.rs: {getattr(entry, 'title', '')}",
                ))
        return repos
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/scrapers/test_lobsters.py -v
```
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add scrapers/lobsters.py tests/scrapers/test_lobsters.py
git commit -m "feat: Lobste.rs scraper"
```

---

## Chunk 3: Advanced Scrapers

### Task 8: GitHub Search scraper

**Files:**
- Create: `scrapers/github_search.py`
- Create: `tests/scrapers/test_github_search.py`

- [ ] **Step 1: Write failing test**

```python
# tests/scrapers/test_github_search.py
import respx
import httpx
from scrapers.github_search import GitHubSearchScraper

SEARCH_RESPONSE = {
    "items": [
        {
            "full_name": "owner/cool-agent",
            "html_url": "https://github.com/owner/cool-agent",
            "description": "AI agent framework",
            "language": "Python",
            "stargazers_count": 200,
            "license": {"spdx_id": "MIT"},
            "topics": ["ai", "agent"],
            "created_at": "2026-02-01T00:00:00Z",
            "pushed_at": "2026-03-15T10:00:00Z",
        }
    ]
}

@respx.mock
def test_scrape_returns_repos_from_topic_queries():
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=httpx.Response(200, json=SEARCH_RESPONSE)
    )
    scraper = GitHubSearchScraper()
    repos = scraper.scrape()
    assert len(repos) >= 1
    assert repos[0].source == "github_search"
    assert repos[0].name == "owner/cool-agent"

@respx.mock
def test_scrape_deduplicates_across_topic_queries():
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=httpx.Response(200, json=SEARCH_RESPONSE)
    )
    scraper = GitHubSearchScraper()
    repos = scraper.scrape()
    names = [r.name for r in repos]
    assert len(names) == len(set(names))
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/scrapers/test_github_search.py -v
```

- [ ] **Step 3: Implement `scrapers/github_search.py`**

```python
import httpx
from datetime import datetime, timezone, timedelta
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DiscoveryAgent/1.0)"}
TOPICS = ["llm", "ai-agent", "sdlc", "mlops", "prompt-engineering", "rag", "mcp-server"]


class GitHubSearchScraper(BaseScraper):
    def __init__(self, client: httpx.Client | None = None, lookback_days: int = 7):
        self._client = client or httpx.Client(headers=HEADERS, timeout=15)
        self._lookback_days = lookback_days

    def scrape(self) -> list[Repo]:
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=self._lookback_days)).strftime("%Y-%m-%d")
        seen: set[str] = set()
        repos: list[Repo] = []
        for topic in TOPICS:
            try:
                for page in range(1, 4):  # max 3 pages
                    resp = self._client.get(
                        "https://api.github.com/search/repositories",
                        params={
                            "q": f"topic:{topic} pushed:>={cutoff}",
                            "sort": "stars",
                            "per_page": 30,
                            "page": page,
                        },
                        headers={**HEADERS, "Accept": "application/vnd.github.mercy-preview+json"},
                    )
                    resp.raise_for_status()
                    items = resp.json().get("items", [])
                    if not items:
                        break
                    for item in items:
                        path = item.get("full_name", "")
                        if path in seen:
                            continue
                        seen.add(path)
                        license_id = (item.get("license") or {}).get("spdx_id", "").lower()
                        if license_id not in ALLOWED_LICENSES:
                            continue
                        language = (item.get("language") or "").lower()
                        if language not in {"python", "javascript", "typescript"}:
                            continue
                        repos.append(Repo(
                            name=path,
                            url=item.get("html_url", f"https://github.com/{path}"),
                            description=item.get("description") or "",
                            language=language,
                            stars=item.get("stargazers_count", 0),
                            stars_delta=0,
                            license=license_id,
                            source="github_search",
                            discovered_at=datetime.now(tz=timezone.utc),
                            topics=item.get("topics") or [],
                            why_notable=f"Active repo tagged #{topic}",
                        ))
            except Exception:
                continue
        return repos
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/scrapers/test_github_search.py -v
```

- [ ] **Step 5: Commit**

```bash
git add scrapers/github_search.py tests/scrapers/test_github_search.py
git commit -m "feat: GitHub Search scraper (topic queries, paginated)"
```

---

### Task 9: Papers with Code scraper

**Files:**
- Create: `scrapers/papers_with_code.py`
- Create: `tests/scrapers/test_papers_with_code.py`

- [ ] **Step 1: Write failing test**

```python
# tests/scrapers/test_papers_with_code.py
import respx
import httpx
from scrapers.papers_with_code import PapersWithCodeScraper

PWC_RESPONSE = {
    "results": [
        {
            "title": "Efficient Agent Framework",
            "published": "2026-03-14",
            "repository": {
                "url": "https://github.com/owner/eff-agent",
                "stars": 120,
            }
        },
        {
            "title": "Paper without code",
            "published": "2026-03-14",
            "repository": None,
        }
    ]
}

GITHUB_API_RESPONSE = {
    "full_name": "owner/eff-agent",
    "stargazers_count": 120,
    "license": {"spdx_id": "MIT"},
    "language": "Python",
    "description": "Efficient agent framework",
    "topics": ["ai", "agent"],
    "created_at": "2026-03-10T00:00:00Z",
}

@respx.mock
def test_scrape_returns_repos_with_code():
    respx.get("https://paperswithcode.com/api/v1/papers/").mock(
        return_value=httpx.Response(200, json=PWC_RESPONSE)
    )
    respx.get("https://api.github.com/repos/owner/eff-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = PapersWithCodeScraper()
    repos = scraper.scrape()
    assert len(repos) == 1
    assert repos[0].name == "owner/eff-agent"
    assert repos[0].source == "papers_with_code"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/scrapers/test_papers_with_code.py -v
```

- [ ] **Step 3: Implement `scrapers/papers_with_code.py`**

```python
import re
import httpx
from datetime import datetime, timezone, timedelta
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper
from scrapers._http import HEADERS, fetch_github_api

GITHUB_RE = re.compile(r"github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)")


class PapersWithCodeScraper(BaseScraper):
    def __init__(self, client: httpx.Client | None = None, lookback_days: int = 7):
        self._client = client or httpx.Client(headers=HEADERS, timeout=15)
        self._lookback_days = lookback_days

    def scrape(self) -> list[Repo]:
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=self._lookback_days)).strftime("%Y-%m-%d")
        try:
            resp = self._client.get(
                "https://paperswithcode.com/api/v1/papers/",
                params={"ordering": "-published", "page_size": 50},
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception:
            return []

        repos: list[Repo] = []
        for paper in results:
            if paper.get("published", "") < cutoff:
                continue
            repository = paper.get("repository")
            if not repository:
                continue
            url = repository.get("url", "")
            m = GITHUB_RE.search(url)
            if not m:
                continue
            path = m.group(1).rstrip("/")
            repo_data = fetch_github_api(path, self._client)
            if not repo_data:
                continue
            license_id = (repo_data.get("license") or {}).get("spdx_id", "").lower()
            if license_id not in ALLOWED_LICENSES:
                continue
            language = (repo_data.get("language") or "").lower()
            if language not in {"python", "javascript", "typescript"}:
                continue
            repos.append(Repo(
                name=path,
                url=f"https://github.com/{path}",
                description=repo_data.get("description") or paper.get("title", ""),
                language=language,
                stars=repo_data.get("stargazers_count", 0),
                stars_delta=0,
                license=license_id,
                source="papers_with_code",
                discovered_at=datetime.now(tz=timezone.utc),
                topics=repo_data.get("topics") or [],
                why_notable=f"Code for paper: {paper.get('title', '')}",
            ))
        return repos
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/scrapers/test_papers_with_code.py -v
```

- [ ] **Step 5: Commit**

```bash
git add scrapers/papers_with_code.py tests/scrapers/test_papers_with_code.py
git commit -m "feat: Papers with Code scraper"
```

---

### Task 10: Hugging Face scraper

**Files:**
- Create: `scrapers/huggingface.py`
- Create: `tests/scrapers/test_huggingface.py`

- [ ] **Step 1: Write failing test**

```python
# tests/scrapers/test_huggingface.py
import respx
import httpx
from scrapers.huggingface import HuggingFaceScraper

HF_RESPONSE = [
    {
        "id": "owner/cool-model",
        "createdAt": "2026-03-15T00:00:00.000Z",
        "likes": 45,
        "cardData": {"github": "https://github.com/owner/cool-agent"},
    },
    {
        "id": "owner/no-github",
        "createdAt": "2026-03-15T00:00:00.000Z",
        "likes": 10,
        "cardData": {},
    }
]

GITHUB_API_RESPONSE = {
    "full_name": "owner/cool-agent",
    "stargazers_count": 90,
    "license": {"spdx_id": "Apache-2.0"},
    "language": "Python",
    "description": "Cool agent from HF",
    "topics": ["llm"],
    "created_at": "2026-03-10T00:00:00Z",
}

@respx.mock
def test_scrape_extracts_github_links_from_model_cards():
    respx.get("https://huggingface.co/api/models").mock(
        return_value=httpx.Response(200, json=HF_RESPONSE)
    )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = HuggingFaceScraper()
    repos = scraper.scrape()
    assert len(repos) == 1
    assert repos[0].source == "huggingface"
    assert repos[0].name == "owner/cool-agent"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/scrapers/test_huggingface.py -v
```

- [ ] **Step 3: Implement `scrapers/huggingface.py`**

```python
import re
import httpx
from datetime import datetime, timezone, timedelta
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper
from scrapers._http import HEADERS, fetch_github_api

GITHUB_RE = re.compile(r"github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)")


class HuggingFaceScraper(BaseScraper):
    def __init__(self, client: httpx.Client | None = None, lookback_days: int = 7):
        self._client = client or httpx.Client(headers=HEADERS, timeout=15)
        self._lookback_days = lookback_days

    def scrape(self) -> list[Repo]:
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=self._lookback_days)).isoformat()
        repos: list[Repo] = []
        seen: set[str] = set()
        for endpoint in ["models", "spaces"]:
            try:
                resp = self._client.get(
                    f"https://huggingface.co/api/{endpoint}",
                    params={"sort": "createdAt", "direction": -1, "limit": 100},
                )
                resp.raise_for_status()
                items = resp.json()
            except Exception:
                continue
            for item in items:
                created = item.get("createdAt", "")
                if created < cutoff:
                    break  # sorted by newest, stop when too old
                card = item.get("cardData") or {}
                github_url = card.get("github") or ""
                if not github_url:
                    continue
                m = GITHUB_RE.search(github_url)
                if not m:
                    continue
                path = m.group(1).rstrip("/")
                if path in seen:
                    continue
                seen.add(path)
                repo_data = fetch_github_api(path, self._client)
                if not repo_data:
                    continue
                license_id = (repo_data.get("license") or {}).get("spdx_id", "").lower()
                if license_id not in ALLOWED_LICENSES:
                    continue
                language = (repo_data.get("language") or "").lower()
                if language not in {"python", "javascript", "typescript"}:
                    continue
                repos.append(Repo(
                    name=path,
                    url=f"https://github.com/{path}",
                    description=repo_data.get("description") or "",
                    language=language,
                    stars=repo_data.get("stargazers_count", 0),
                    stars_delta=0,
                    license=license_id,
                    source="huggingface",
                    discovered_at=datetime.now(tz=timezone.utc),
                    topics=repo_data.get("topics") or [],
                    why_notable=f"Linked from Hugging Face {endpoint[:-1]}: {item.get('id', '')}",
                ))
        return repos
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/scrapers/test_huggingface.py -v
```

- [ ] **Step 5: Commit**

```bash
git add scrapers/huggingface.py tests/scrapers/test_huggingface.py
git commit -m "feat: Hugging Face Hub scraper (models + spaces)"
```

---

### Task 11: Web Aggregators scraper

**Files:**
- Create: `scrapers/web_aggregators.py`
- Create: `tests/scrapers/test_web_aggregators.py`

- [ ] **Step 1: Write failing test**

```python
# tests/scrapers/test_web_aggregators.py
import respx
import httpx
from scrapers.web_aggregators import WebAggregatorsScraper

CONSOLE_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>cool-agent</title>
      <link>https://github.com/owner/cool-agent</link>
      <pubDate>Mon, 15 Mar 2026 10:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""

DAILY_DEV_RESPONSE = {
    "data": {
        "page": {
            "edges": [
                {
                    "node": {
                        "title": "cool-agent",
                        "permalink": "https://github.com/owner/cool-agent2",
                    }
                }
            ]
        }
    }
}

GITHUB_API_RESPONSE = {
    "full_name": "owner/cool-agent",
    "stargazers_count": 60,
    "license": {"spdx_id": "MIT"},
    "language": "Python",
    "description": "Cool agent",
    "topics": ["ai"],
    "created_at": "2026-03-01T00:00:00Z",
}

@respx.mock
def test_scrape_from_console_dev():
    respx.get("https://console.dev/tools/rss.xml").mock(
        return_value=httpx.Response(200, text=CONSOLE_RSS)
    )
    respx.post("https://app.daily.dev/api/graphql").mock(
        return_value=httpx.Response(200, json=DAILY_DEV_RESPONSE)
    )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    respx.get("https://api.github.com/repos/owner/cool-agent2").mock(
        return_value=httpx.Response(404)
    )
    scraper = WebAggregatorsScraper()
    repos = scraper.scrape()
    assert any(r.name == "owner/cool-agent" for r in repos)
    assert all(r.source == "web_aggregators" for r in repos)
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/scrapers/test_web_aggregators.py -v
```

- [ ] **Step 3: Implement `scrapers/web_aggregators.py`**

```python
import re
import httpx
import feedparser
from datetime import datetime, timezone
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper
from scrapers._http import HEADERS, fetch_github_api

GITHUB_RE = re.compile(r"https?://github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)")

DAILY_DEV_QUERY = """
query FeedQuery($first: Int) {
  page: feed(first: $first, ranking: POPULARITY) {
    edges {
      node { title permalink }
    }
  }
}
"""


class WebAggregatorsScraper(BaseScraper):
    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(headers=HEADERS, timeout=15)

    def scrape(self) -> list[Repo]:
        seen: set[str] = set()
        repos: list[Repo] = []
        repos.extend(self._scrape_console_dev(seen))
        repos.extend(self._scrape_daily_dev(seen))
        return repos

    def _scrape_console_dev(self, seen: set[str]) -> list[Repo]:
        try:
            resp = self._client.get("https://console.dev/tools/rss.xml")
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
        except Exception:
            return []
        repos = []
        for entry in feed.entries:
            link = getattr(entry, "link", "") or ""
            m = GITHUB_RE.match(link)
            if not m:
                continue
            path = m.group(1).rstrip("/")
            if path in seen:
                continue
            seen.add(path)
            repo = self._build_repo(path, f"Featured on console.dev: {getattr(entry, 'title', '')}")
            if repo:
                repos.append(repo)
        return repos

    def _scrape_daily_dev(self, seen: set[str]) -> list[Repo]:
        try:
            resp = self._client.post(
                "https://app.daily.dev/api/graphql",
                json={"query": DAILY_DEV_QUERY, "variables": {"first": 30}},
            )
            resp.raise_for_status()
            edges = resp.json().get("data", {}).get("page", {}).get("edges", [])
        except Exception:
            return []
        repos = []
        for edge in edges:
            permalink = edge.get("node", {}).get("permalink", "")
            m = GITHUB_RE.match(permalink)
            if not m:
                continue
            path = m.group(1).rstrip("/")
            if path in seen:
                continue
            seen.add(path)
            title = edge.get("node", {}).get("title", "")
            repo = self._build_repo(path, f"Trending on daily.dev: {title}")
            if repo:
                repos.append(repo)
        return repos

    def _build_repo(self, path: str, why_notable: str) -> Repo | None:
        repo_data = fetch_github_api(path, self._client)
        if not repo_data:
            return None
        license_id = (repo_data.get("license") or {}).get("spdx_id", "").lower()
        if license_id not in ALLOWED_LICENSES:
            return None
        language = (repo_data.get("language") or "").lower()
        if language not in {"python", "javascript", "typescript"}:
            return None
        return Repo(
            name=path,
            url=f"https://github.com/{path}",
            description=repo_data.get("description") or "",
            language=language,
            stars=repo_data.get("stargazers_count", 0),
            stars_delta=0,
            license=license_id,
            source="web_aggregators",
            discovered_at=datetime.now(tz=timezone.utc),
            topics=repo_data.get("topics") or [],
            why_notable=why_notable,
        )
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/scrapers/test_web_aggregators.py -v
```

- [ ] **Step 5: Commit**

```bash
git add scrapers/web_aggregators.py tests/scrapers/test_web_aggregators.py
git commit -m "feat: Web aggregators scraper (console.dev + daily.dev)"
```

---

### Task 12: Awesome Lists scraper

**Files:**
- Create: `scrapers/awesome_lists.py`
- Create: `tests/scrapers/test_awesome_lists.py`

- [ ] **Step 1: Write failing test**

```python
# tests/scrapers/test_awesome_lists.py
import respx
import httpx
from scrapers.awesome_lists import AwesomeListsScraper

COMMITS_RESPONSE = [{"sha": "abc123"}]

DIFF_RESPONSE = """\
diff --git a/README.md b/README.md
index 1234..5678 100644
--- a/README.md
+++ b/README.md
@@ -10,0 +11 @@
+- [cool-agent](https://github.com/owner/cool-agent) - A cool agent framework
"""

GITHUB_API_RESPONSE = {
    "full_name": "owner/cool-agent",
    "stargazers_count": 75,
    "license": {"spdx_id": "MIT"},
    "language": "Python",
    "description": "A cool agent framework",
    "topics": ["agent"],
    "created_at": "2026-03-01T00:00:00Z",
}

@respx.mock
def test_scrape_extracts_newly_added_repos_from_diff():
    for owner_repo in [
        "e2b-dev/awesome-ai-agents",
        "Hannibal046/Awesome-LLM",
        "visenger/awesome-mlops",
        "onejune2018/Awesome-LLM-Eval",
        "punkpeye/awesome-mcp-servers",
    ]:
        respx.get(f"https://api.github.com/repos/{owner_repo}/commits").mock(
            return_value=httpx.Response(200, json=COMMITS_RESPONSE)
        )
        respx.get(f"https://api.github.com/repos/{owner_repo}/commits/abc123").mock(
            return_value=httpx.Response(200, json={"files": [{"patch": DIFF_RESPONSE}]})
        )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = AwesomeListsScraper()
    repos = scraper.scrape()
    assert any(r.name == "owner/cool-agent" for r in repos)
    assert all(r.source == "awesome_lists" for r in repos)

@respx.mock
def test_scrape_ignores_removed_lines():
    REMOVAL_DIFF = "- [old-agent](https://github.com/owner/old-agent) - removed"
    for owner_repo in [
        "e2b-dev/awesome-ai-agents",
        "Hannibal046/Awesome-LLM",
        "visenger/awesome-mlops",
        "onejune2018/Awesome-LLM-Eval",
        "punkpeye/awesome-mcp-servers",
    ]:
        respx.get(f"https://api.github.com/repos/{owner_repo}/commits").mock(
            return_value=httpx.Response(200, json=COMMITS_RESPONSE)
        )
        respx.get(f"https://api.github.com/repos/{owner_repo}/commits/abc123").mock(
            return_value=httpx.Response(200, json={"files": [{"patch": REMOVAL_DIFF}]})
        )
    scraper = AwesomeListsScraper()
    repos = scraper.scrape()
    assert repos == []
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/scrapers/test_awesome_lists.py -v
```

- [ ] **Step 3: Implement `scrapers/awesome_lists.py`**

```python
import re
import httpx
from datetime import datetime, timezone, timedelta
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper
from scrapers._http import HEADERS, fetch_github_api

GITHUB_RE = re.compile(r"https?://github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)")

AWESOME_LISTS = [
    "e2b-dev/awesome-ai-agents",
    "Hannibal046/Awesome-LLM",
    "visenger/awesome-mlops",
    "onejune2018/Awesome-LLM-Eval",
    "punkpeye/awesome-mcp-servers",
]


class AwesomeListsScraper(BaseScraper):
    def __init__(self, client: httpx.Client | None = None, lookback_days: int = 7):
        self._client = client or httpx.Client(headers=HEADERS, timeout=15)
        self._lookback_days = lookback_days

    def scrape(self) -> list[Repo]:
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=self._lookback_days)).isoformat()
        seen: set[str] = set()
        repos: list[Repo] = []
        for list_repo in AWESOME_LISTS:
            try:
                added_urls = self._get_newly_added_github_urls(list_repo, cutoff)
                for url, list_name in added_urls:
                    m = GITHUB_RE.match(url)
                    if not m:
                        continue
                    path = m.group(1).rstrip("/")
                    if path in seen:
                        continue
                    seen.add(path)
                    repo_data = fetch_github_api(path, self._client)
                    if not repo_data:
                        continue
                    license_id = (repo_data.get("license") or {}).get("spdx_id", "").lower()
                    if license_id not in ALLOWED_LICENSES:
                        continue
                    language = (repo_data.get("language") or "").lower()
                    if language not in {"python", "javascript", "typescript"}:
                        continue
                    repos.append(Repo(
                        name=path,
                        url=f"https://github.com/{path}",
                        description=repo_data.get("description") or "",
                        language=language,
                        stars=repo_data.get("stargazers_count", 0),
                        stars_delta=0,
                        license=license_id,
                        source="awesome_lists",
                        discovered_at=datetime.now(tz=timezone.utc),
                        topics=repo_data.get("topics") or [],
                        why_notable=f"Newly added to {list_name}",
                    ))
            except Exception:
                continue
        return repos

    def _get_newly_added_github_urls(self, list_repo: str, since: str) -> list[tuple[str, str]]:
        resp = self._client.get(
            f"https://api.github.com/repos/{list_repo}/commits",
            params={"since": since},
        )
        resp.raise_for_status()
        commits = resp.json()
        urls = []
        for commit in commits:
            sha = commit["sha"]
            detail = self._client.get(f"https://api.github.com/repos/{list_repo}/commits/{sha}")
            detail.raise_for_status()
            for file in detail.json().get("files", []):
                patch = file.get("patch", "")
                for line in patch.splitlines():
                    if not line.startswith("+"):
                        continue
                    for m in GITHUB_RE.finditer(line):
                        urls.append((m.group(0), list_repo.split("/")[1]))
        return urls
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/scrapers/test_awesome_lists.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scrapers/awesome_lists.py tests/scrapers/test_awesome_lists.py
git commit -m "feat: Awesome Lists scraper (git diff — newly added entries only)"
```

---

## Chunk 4: Pipeline (Filter, Deduplicate, Score, Publish)

### Task 13: Filter pipeline step

**Files:**
- Create: `pipeline/filter.py`
- Create: `tests/pipeline/test_filter.py`

- [ ] **Step 1: Write failing test**

```python
# tests/pipeline/test_filter.py
from copy import deepcopy
import pytest
from pipeline.filter import filter_repos

KEYWORDS = ["ai", "agent", "llm"]

def test_filter_removes_low_star_repos(sample_repo):
    low_stars = sample_repo.model_copy(update={"stars": 10, "url": "https://github.com/a/b", "name": "a/b"})
    result = filter_repos([low_stars], min_stars=50, keywords=KEYWORDS)
    assert result == []

def test_filter_keeps_repos_above_star_threshold(sample_repo):
    result = filter_repos([sample_repo], min_stars=50, keywords=KEYWORDS)
    assert len(result) == 1

def test_filter_removes_repos_with_no_keyword_match(sample_repo):
    no_match = sample_repo.model_copy(update={
        "description": "totally unrelated thing",
        "topics": [],
        "name": "a/no-match",
        "url": "https://github.com/a/no-match",
    })
    result = filter_repos([no_match], min_stars=50, keywords=KEYWORDS)
    assert result == []

def test_filter_matches_keyword_in_description(sample_repo):
    repo = sample_repo.model_copy(update={
        "description": "This is an AI framework",
        "topics": [],
        "name": "a/desc-match",
        "url": "https://github.com/a/desc-match",
    })
    result = filter_repos([repo], min_stars=50, keywords=["ai"])
    assert len(result) == 1

def test_filter_keyword_match_is_case_insensitive(sample_repo):
    repo = sample_repo.model_copy(update={
        "description": "An AI Framework",
        "topics": [],
        "name": "a/upper",
        "url": "https://github.com/a/upper",
    })
    result = filter_repos([repo], min_stars=50, keywords=["ai"])
    assert len(result) == 1
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/pipeline/test_filter.py -v
```

- [ ] **Step 3: Implement `pipeline/filter.py`**

```python
import re
from schemas.repo import Repo

DEFAULT_KEYWORDS = [
    "ai", "agent", "llm", "sdlc", "devops", "eval", "prompt",
    "copilot", "rag", "mcp", "workflow", "pipeline", "enterprise",
]


def filter_repos(
    repos: list[Repo],
    min_stars: int = 50,
    keywords: list[str] = DEFAULT_KEYWORDS,
) -> list[Repo]:
    """Apply language, stars, and relevance filters.
    License/language validation is already enforced by the Repo schema."""
    patterns = [re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in keywords]
    result = []
    for repo in repos:
        if repo.stars < min_stars:
            continue
        searchable = " ".join([repo.name, repo.description, " ".join(repo.topics)])
        if not any(p.search(searchable) for p in patterns):
            continue
        result.append(repo)
    return result
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/pipeline/test_filter.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/filter.py tests/pipeline/test_filter.py
git commit -m "feat: filter pipeline step (stars, keyword relevance)"
```

---

### Task 14: Deduplicate pipeline step

**Files:**
- Create: `pipeline/deduplicate.py`
- Create: `tests/pipeline/test_deduplicate.py`

- [ ] **Step 1: Write failing test**

```python
# tests/pipeline/test_deduplicate.py
from pipeline.deduplicate import deduplicate

def test_removes_already_seen_repos(sample_repo):
    seen_ids = {sample_repo.id}
    result = deduplicate([sample_repo], seen_ids=seen_ids)
    assert result == []

def test_passes_new_repos(sample_repo):
    result = deduplicate([sample_repo], seen_ids=set())
    assert len(result) == 1

def test_readmits_repo_with_large_stars_delta(sample_repo):
    hot_repo = sample_repo.model_copy(update={"stars_delta": 600})
    seen_ids = {hot_repo.id}
    result = deduplicate([hot_repo], seen_ids=seen_ids, readmit_threshold=500)
    assert len(result) == 1

def test_does_not_readmit_repo_below_threshold(sample_repo):
    repo = sample_repo.model_copy(update={"stars_delta": 499})
    seen_ids = {repo.id}
    result = deduplicate([repo], seen_ids=seen_ids, readmit_threshold=500)
    assert result == []
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/pipeline/test_deduplicate.py -v
```

- [ ] **Step 3: Implement `pipeline/deduplicate.py`**

```python
import json
from pathlib import Path
from schemas.repo import Repo


def deduplicate(
    repos: list[Repo],
    seen_ids: set[str],
    readmit_threshold: int = 500,
) -> list[Repo]:
    """Remove repos already in seen_ids unless stars_delta >= readmit_threshold."""
    result = []
    for repo in repos:
        if repo.id not in seen_ids:
            result.append(repo)
        elif repo.stars_delta >= readmit_threshold:
            result.append(repo)
    return result


def load_seen_ids(path: str = "data/discovered-repos.json") -> set[str]:
    """Load seen repo IDs from cache file. Returns empty set if file missing."""
    p = Path(path)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text()))
    except Exception:
        return set()


def save_seen_ids(
    repos: list[Repo],
    seen_ids: set[str],
    path: str = "data/discovered-repos.json",
) -> None:
    """Merge newly discovered repo IDs into seen_ids and persist."""
    updated = seen_ids | {r.id for r in repos}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(sorted(updated)))
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/pipeline/test_deduplicate.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/deduplicate.py tests/pipeline/test_deduplicate.py
git commit -m "feat: deduplicate pipeline step with cache load/save"
```

---

### Task 15: Score pipeline step

**Files:**
- Create: `pipeline/score.py`
- Create: `tests/pipeline/test_score.py`

- [ ] **Step 1: Write failing test**

```python
# tests/pipeline/test_score.py
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pipeline.score import score_and_rank

def make_repo(sample_repo, stars_delta=0, source_count=1, topic_count=1, days_old=60):
    from copy import deepcopy
    r = deepcopy(sample_repo)
    r = r.model_copy(update={
        "stars_delta": stars_delta,
        "topics": ["ai"] * topic_count,
        "discovered_at": datetime.now(tz=timezone.utc) - timedelta(days=days_old),
    })
    return r

def test_returns_top_n_repos(sample_repos):
    result = score_and_rank(sample_repos, top_n=3)
    assert len(result) == 3

def test_higher_stars_delta_ranks_higher(sample_repo):
    low = sample_repo.model_copy(update={"stars_delta": 10, "name": "a/low", "url": "https://github.com/a/low"})
    high = sample_repo.model_copy(update={"stars_delta": 500, "name": "a/high", "url": "https://github.com/a/high"})
    result = score_and_rank([low, high], top_n=2)
    assert result[0].name == "a/high"

def test_recent_repo_scores_higher_than_old(sample_repo):
    recent = sample_repo.model_copy(update={
        "name": "a/recent", "url": "https://github.com/a/recent",
        "discovered_at": datetime.now(tz=timezone.utc) - timedelta(days=5),
        "stars_delta": 0,
    })
    old = sample_repo.model_copy(update={
        "name": "a/old", "url": "https://github.com/a/old",
        "discovered_at": datetime.now(tz=timezone.utc) - timedelta(days=90),
        "stars_delta": 0,
    })
    result = score_and_rank([recent, old], top_n=2)
    assert result[0].name == "a/recent"

def test_all_repos_get_scores_assigned(sample_repos):
    result = score_and_rank(sample_repos, top_n=10)
    assert all(r.score > 0 or r.score == 0.0 for r in result)
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/pipeline/test_score.py -v
```

- [ ] **Step 3: Implement `pipeline/score.py`**

```python
from datetime import datetime, timezone, timedelta
from schemas.repo import Repo


def score_and_rank(repos: list[Repo], top_n: int = 5) -> list[Repo]:
    """Score and rank repos. Returns top_n sorted by score descending."""
    if not repos:
        return []

    max_delta = max((r.stars_delta for r in repos), default=1) or 1
    scored = []
    for repo in repos:
        delta_score = repo.stars_delta / max_delta
        source_score = min(repo.source_count / 3, 1.0)
        topic_score = min(len(repo.topics) / 5, 1.0)
        age_days = (datetime.now(tz=timezone.utc) - repo.discovered_at).days
        recency_score = 1.0 if age_days <= 30 else 0.0

        final = (
            0.4 * delta_score +
            0.3 * source_score +
            0.2 * topic_score +
            0.1 * recency_score
        )
        scored.append(repo.model_copy(update={"score": round(final, 4)}))

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_n]
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/pipeline/test_score.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/score.py tests/pipeline/test_score.py
git commit -m "feat: score and rank pipeline step"
```

---

### Task 16: Publish pipeline step

**Files:**
- Create: `pipeline/publish.py`
- Create: `tests/pipeline/test_publish.py`

- [ ] **Step 1: Write failing test**

```python
# tests/pipeline/test_publish.py
import json
from pathlib import Path
from pipeline.publish import write_spotlight_json

def test_writes_spotlight_json_with_repos(tmp_path, sample_repos):
    output = tmp_path / "spotlight.json"
    write_spotlight_json(sample_repos[:2], path=str(output))
    data = json.loads(output.read_text())
    assert "generated_at" in data
    assert len(data["repos"]) == 2
    assert data["repos"][0]["name"] == sample_repos[0].name

def test_writes_empty_repos_array_when_no_candidates(tmp_path):
    output = tmp_path / "spotlight.json"
    write_spotlight_json([], path=str(output))
    data = json.loads(output.read_text())
    assert data["repos"] == []
    assert "generated_at" in data
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/pipeline/test_publish.py -v
```

- [ ] **Step 3: Implement `pipeline/publish.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path
from schemas.repo import Repo


def write_spotlight_json(repos: list[Repo], path: str = "data/spotlight.json") -> None:
    """Write spotlight.json — always writes, even if repos is empty."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repos": [
            {
                "name": r.name,
                "url": r.url,
                "description": r.description,
                "stars": r.stars,
                "stars_delta": r.stars_delta,
                "license": r.license,
                "language": r.language,
                "topics": r.topics,
                "why_notable": r.why_notable,
                "source": r.source,
            }
            for r in repos
        ],
    }
    Path(path).write_text(json.dumps(payload, indent=2))
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/pipeline/test_publish.py -v
```
Expected: 2 passed

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add pipeline/publish.py tests/pipeline/test_publish.py
git commit -m "feat: publish pipeline step (spotlight.json writer)"
```

---

## Chunk 5: GitHub Pages Builder and GitHub Actions Workflow

### Task 17: GitHub Pages builder

**Files:**
- Create: `pages/build.py`
- Create: `tests/test_pages.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_pages.py
from pages.build import build_index_html
from schemas.repo import Repo
from datetime import datetime, timezone

def test_build_returns_html_string(sample_repos):
    html = build_index_html(sample_repos)
    assert "<html" in html
    assert sample_repos[0].name in html

def test_build_handles_empty_list():
    html = build_index_html([])
    assert "<html" in html
    assert "No repos" in html or "0" in html
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_pages.py -v
```

- [ ] **Step 3: Implement `pages/build.py`**

```python
from datetime import datetime, timezone
from schemas.repo import Repo


def build_index_html(repos: list[Repo]) -> str:
    generated = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = ""
    for r in repos:
        rows += f"""
        <tr>
          <td><a href="{r.url}" target="_blank">{r.name}</a></td>
          <td>{r.description}</td>
          <td>{r.language}</td>
          <td>{r.stars:,}</td>
          <td>{r.license}</td>
          <td>{r.why_notable}</td>
          <td>{r.source}</td>
        </tr>"""

    empty_msg = "" if repos else "<p>No repos discovered yet.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Repo Discovery</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }}
    h1 {{ font-size: 1.5rem; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
    th, td {{ text-align: left; padding: 0.5rem; border-bottom: 1px solid #eee; }}
    th {{ background: #f5f5f5; font-weight: 600; }}
    a {{ color: #0366d6; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .meta {{ color: #666; font-size: 0.85rem; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <h1>AI Repo Discovery</h1>
  <p class="meta">Last updated: {generated} — {len(repos)} repos discovered</p>
  {empty_msg}
  {"<table><thead><tr><th>Repo</th><th>Description</th><th>Language</th><th>Stars</th><th>License</th><th>Why Notable</th><th>Source</th></tr></thead><tbody>" + rows + "</tbody></table>" if repos else ""}
</body>
</html>"""
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/test_pages.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add pages/build.py tests/test_pages.py
git commit -m "feat: GitHub Pages index builder"
```

---

### Task 18: Entry point script

**Files:**
- Create: `pipeline/run.py`

- [ ] **Step 1: Create `pipeline/run.py`**

This script ties all pipeline steps together and is called by the GitHub Action.

```python
#!/usr/bin/env python3
"""Main discovery pipeline entry point.
Called by GitHub Actions with: python pipeline/run.py --source <name> --output-dir data/raw
Or for the full pipeline: python pipeline/run.py --pipeline
"""
import argparse
import json
import sys
from pathlib import Path


def run_scraper(source: str, output_dir: str) -> None:
    """Run a single scraper and write raw-{source}.json."""
    from scrapers.github_trending import GitHubTrendingScraper
    from scrapers.hackernews import HackerNewsScraper
    from scrapers.reddit import RedditScraper
    from scrapers.lobsters import LobstersScraper
    from scrapers.github_search import GitHubSearchScraper
    from scrapers.papers_with_code import PapersWithCodeScraper
    from scrapers.huggingface import HuggingFaceScraper
    from scrapers.web_aggregators import WebAggregatorsScraper
    from scrapers.awesome_lists import AwesomeListsScraper

    scrapers = {
        "github_trending": GitHubTrendingScraper,
        "hackernews": HackerNewsScraper,
        "reddit": RedditScraper,
        "lobsters": LobstersScraper,
        "github_search": GitHubSearchScraper,
        "papers_with_code": PapersWithCodeScraper,
        "huggingface": HuggingFaceScraper,
        "web_aggregators": WebAggregatorsScraper,
        "awesome_lists": AwesomeListsScraper,
    }
    if source not in scrapers:
        print(f"Unknown source: {source}", file=sys.stderr)
        sys.exit(1)

    print(f"Scraping {source}...")
    repos = scrapers[source]().scrape()
    print(f"  Found {len(repos)} repos")

    out_path = Path(output_dir) / f"{source}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps([r.model_dump(mode="json") for r in repos], indent=2))
    print(f"  Written to {out_path}")


def run_pipeline(raw_dir: str = "data/raw") -> None:
    """Filter, deduplicate, score, and publish."""
    from schemas.repo import Repo
    from pipeline.filter import filter_repos
    from pipeline.deduplicate import deduplicate, load_seen_ids, save_seen_ids
    from pipeline.score import score_and_rank
    from pipeline.publish import write_spotlight_json
    from pages.build import build_index_html

    # Load all raw scraper outputs
    all_repos: list[Repo] = []
    for path in Path(raw_dir).glob("*.json"):
        try:
            data = json.loads(path.read_text())
            all_repos.extend([Repo(**r) for r in data])
        except Exception as e:
            print(f"  Warning: could not load {path}: {e}", file=sys.stderr)

    print(f"Total raw repos: {len(all_repos)}")

    # Merge repos appearing in multiple sources (track source_count for scoring)
    merged: dict[str, Repo] = {}
    for repo in all_repos:
        if repo.url not in merged:
            merged[repo.url] = repo
        else:
            # Increment source_count; keep higher stars_delta
            existing = merged[repo.url]
            merged[repo.url] = existing.model_copy(update={
                "source_count": existing.source_count + 1,
                "stars_delta": max(existing.stars_delta, repo.stars_delta),
            })
    unique_repos = list(merged.values())
    print(f"Unique repos: {len(unique_repos)}")

    # Filter
    filtered = filter_repos(unique_repos)
    print(f"After filter: {len(filtered)}")

    # Deduplicate against cache
    seen_ids = load_seen_ids()
    new_repos = deduplicate(filtered, seen_ids=seen_ids)
    print(f"New repos (not seen before): {len(new_repos)}")

    # Score and rank
    top_repos = score_and_rank(new_repos, top_n=5)
    print(f"Top repos: {len(top_repos)}")

    # Publish spotlight.json
    write_spotlight_json(top_repos)
    print("Written data/spotlight.json")

    # Update cache with all filtered repos (not just top 5)
    save_seen_ids(filtered, seen_ids)
    print("Cache updated")

    # Build GitHub Pages
    all_discovered_path = Path("data/all-discovered.json")
    all_discovered: list[Repo] = []
    if all_discovered_path.exists():
        try:
            all_discovered = [Repo(**r) for r in json.loads(all_discovered_path.read_text())]
        except Exception:
            pass
    all_discovered = list({r.url: r for r in (all_discovered + top_repos)}.values())
    all_discovered_path.write_text(json.dumps([r.model_dump(mode="json") for r in all_discovered], indent=2))

    html = build_index_html(all_discovered)
    Path("data/index.html").write_text(html)
    print("Written data/index.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="Run a single scraper")
    parser.add_argument("--output-dir", default="data/raw")
    parser.add_argument("--pipeline", action="store_true", help="Run full pipeline")
    args = parser.parse_args()

    if args.source:
        run_scraper(args.source, args.output_dir)
    elif args.pipeline:
        run_pipeline()
    else:
        parser.print_help()
        sys.exit(1)
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/run.py
git commit -m "feat: pipeline entry point script (run.py)"
```

---

### Task 19: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/discover.yml`

- [ ] **Step 1: Create `.github/workflows/discover.yml`**

```yaml
name: Repo Discovery

on:
  schedule:
    - cron: '0 22 * * 0'   # Sunday 10pm UTC (4h before Monday newsletter)
  workflow_dispatch:         # Manual trigger for testing

permissions:
  contents: write            # Needed to push to output + gh-pages branches

env:
  PYTHONPATH: ${{ github.workspace }}

jobs:

  scrape:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        source:
          - github_trending
          - hackernews
          - reddit
          - lobsters
          - github_search
          - papers_with_code
          - huggingface
          - web_aggregators
          - awesome_lists
      fail-fast: false
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Scrape ${{ matrix.source }}
        run: python pipeline/run.py --source "${{ matrix.source }}" --output-dir data/raw
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - uses: actions/upload-artifact@v4
        with:
          name: raw-${{ matrix.source }}
          path: data/raw/${{ matrix.source }}.json
          if-no-files-found: warn

  pipeline:
    needs: scrape
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0      # Full history needed for branch operations
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt

      - uses: actions/download-artifact@v4
        with:
          pattern: raw-*
          merge-multiple: true
          path: data/raw/

      - name: Restore dedup cache
        uses: actions/cache/restore@v4
        with:
          path: data/discovered-repos.json
          key: discovered-repos-v1-${{ github.run_id }}
          restore-keys: discovered-repos-v1-

      - name: Run pipeline
        run: python pipeline/run.py --pipeline
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Save dedup cache
        uses: actions/cache/save@v4
        with:
          path: data/discovered-repos.json
          key: discovered-repos-v1-${{ github.run_id }}

      - name: Publish spotlight.json to output branch
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          # Create orphan output branch if it doesn't exist
          git fetch origin output 2>/dev/null || true
          git checkout output 2>/dev/null || git checkout --orphan output
          git rm -rf . 2>/dev/null || true
          mkdir -p data
          cp ${{ github.workspace }}/data/spotlight.json data/spotlight.json
          git add data/spotlight.json
          git commit -m "chore: update spotlight.json [$(date -u +%Y-%m-%d)]" || echo "No changes"
          git push origin output

      - name: Publish index.html to gh-pages branch
        run: |
          git checkout ${{ github.sha }} -- data/index.html data/all-discovered.json 2>/dev/null || true
          git fetch origin gh-pages 2>/dev/null || true
          git checkout gh-pages 2>/dev/null || git checkout --orphan gh-pages
          git rm -rf . 2>/dev/null || true
          cp ${{ github.workspace }}/data/index.html index.html
          git add index.html
          git commit -m "chore: update GitHub Pages [$(date -u +%Y-%m-%d)]" || echo "No changes"
          git push origin gh-pages
```

- [ ] **Step 2: Enable GitHub Pages in repo settings**

Go to `https://github.com/nayyarsan/discoveryandresearch/settings/pages`:
- Source: Deploy from branch
- Branch: `gh-pages` / `/ (root)`

- [ ] **Step 3: Add `.gitignore`**

```
data/
*.pyc
__pycache__/
.env
.pytest_cache/
*.egg-info/
dist/
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/discover.yml .gitignore
git commit -m "feat: GitHub Actions workflow (scrape matrix + pipeline + publish)"
```

---

### Task 20: Final smoke test

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: all tests pass

- [ ] **Step 2: Trigger manual workflow run**

```bash
gh workflow run discover.yml --repo nayyarsan/discoveryandresearch
```

- [ ] **Step 3: Monitor run**

```bash
gh run list --repo nayyarsan/discoveryandresearch --limit 5
gh run watch --repo nayyarsan/discoveryandresearch
```

- [ ] **Step 4: Verify spotlight.json on output branch**

```bash
gh api repos/nayyarsan/discoveryandresearch/contents/data/spotlight.json?ref=output \
  | python -c "import sys,json,base64; print(base64.b64decode(json.load(sys.stdin)['content']).decode())"
```

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: smoke test fixes"
git push origin master
```

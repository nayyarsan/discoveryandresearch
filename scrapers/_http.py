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

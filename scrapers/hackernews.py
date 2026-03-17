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
        seen: set[str] = set()
        for hit in hits:
            url = hit.get("url") or ""
            paths = extract_github_paths(url)
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

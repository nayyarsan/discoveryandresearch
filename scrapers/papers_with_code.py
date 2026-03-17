import re
import httpx
from datetime import datetime, timezone, timedelta
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper
from scrapers._http import HEADERS, fetch_github_api, extract_github_paths


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

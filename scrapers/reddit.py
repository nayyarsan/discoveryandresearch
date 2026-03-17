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
        seen: set[str] = set()
        repos: list[Repo] = []
        for sub in SUBREDDITS:
            url = f"https://www.reddit.com/r/{sub}/new.rss"
            entries = fetch_rss_entries(url, self._client, self._lookback_days)
            for entry in entries:
                text = f"{getattr(entry, 'link', '')} {getattr(entry, 'summary', '')}"
                for path in extract_github_paths(text):
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
                        source="reddit",
                        discovered_at=datetime.now(tz=timezone.utc),
                        topics=repo_data.get("topics") or [],
                        why_notable=f"Discussed on r/{sub}",
                    ))
        return repos

import httpx
from datetime import datetime, timezone, timedelta
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper
from scrapers._http import HEADERS

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
                for page in range(1, 4):
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

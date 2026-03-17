import httpx
from datetime import datetime, timezone
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper
from scrapers._http import HEADERS, fetch_rss_entries, fetch_github_api, extract_github_paths

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
        entries = fetch_rss_entries("https://console.dev/tools/rss.xml", self._client)
        repos = []
        for entry in entries:
            link = getattr(entry, "link", "") or ""
            paths = extract_github_paths(link)
            if not paths:
                continue
            path = paths[0]
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
            paths = extract_github_paths(permalink)
            if not paths:
                continue
            path = paths[0]
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

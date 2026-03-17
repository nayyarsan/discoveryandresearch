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
            entries = fetch_rss_entries(f"https://lobste.rs/t/{tag}.rss", self._client)
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

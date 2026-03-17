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
                path = link["href"].strip("/")
                if path in seen:
                    continue
                seen.add(path)

                url = f"https://github.com/{path}"
                description_elem = article.select_one("p")
                description = description_elem.get_text(strip=True) if description_elem else ""

                delta_text = article.get_text()
                delta_match = re.search(r"([\d,]+)\s+stars this week", delta_text)
                stars_delta = int(delta_match.group(1).replace(",", "")) if delta_match else 0

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

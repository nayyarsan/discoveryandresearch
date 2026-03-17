import httpx
from datetime import datetime, timezone, timedelta
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper
from scrapers._http import HEADERS, fetch_github_api, extract_github_paths


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
                    break
                card = item.get("cardData") or {}
                github_url = card.get("github") or ""
                if not github_url:
                    continue
                paths = extract_github_paths(github_url)
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
                    source="huggingface",
                    discovered_at=datetime.now(tz=timezone.utc),
                    topics=repo_data.get("topics") or [],
                    why_notable=f"Linked from Hugging Face {endpoint[:-1]}: {item.get('id', '')}",
                ))
        return repos

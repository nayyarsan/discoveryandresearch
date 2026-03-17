import httpx
from datetime import datetime, timezone, timedelta
from schemas.repo import Repo, ALLOWED_LICENSES
from scrapers.base import BaseScraper
from scrapers._http import HEADERS, fetch_github_api, extract_github_paths

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
                added = self._get_newly_added_github_urls(list_repo, cutoff)
                for url, list_name in added:
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
            headers={**HEADERS, "Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        commits = resp.json()
        urls = []
        for commit in commits:
            sha = commit["sha"]
            detail = self._client.get(
                f"https://api.github.com/repos/{list_repo}/commits/{sha}",
                headers={**HEADERS, "Accept": "application/vnd.github+json"},
            )
            detail.raise_for_status()
            for file in detail.json().get("files", []):
                patch = file.get("patch", "")
                for line in patch.splitlines():
                    if not line.startswith("+"):
                        continue
                    for url in extract_github_paths(line):
                        urls.append((f"https://github.com/{url}", list_repo.split("/")[1]))
        return urls

import respx
import httpx
import pytest
from scrapers.github_trending import GitHubTrendingScraper

MOCK_HTML = """
<html><body>
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/owner/cool-agent">owner / cool-agent</a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">A cool AI agent framework</p>
  <span class="d-inline-block float-sm-right">312 stars this week</span>
</article>
</body></html>
"""

@respx.mock
def test_scrape_returns_repos():
    for lang in ["python", "javascript", "typescript"]:
        respx.get(f"https://github.com/trending/{lang}").mock(
            return_value=httpx.Response(200, text=MOCK_HTML)
        )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json={
            "stargazers_count": 1240,
            "license": {"spdx_id": "MIT"},
            "language": "Python",
            "description": "A cool AI agent framework",
            "topics": ["ai", "agent"],
            "created_at": "2026-01-01T00:00:00Z",
        })
    )
    scraper = GitHubTrendingScraper()
    repos = scraper.scrape()
    assert len(repos) >= 1
    assert repos[0].name == "owner/cool-agent"
    assert repos[0].stars_delta == 312
    assert repos[0].source == "github_trending"

@respx.mock
def test_scrape_returns_empty_on_http_error():
    for lang in ["python", "javascript", "typescript"]:
        respx.get(f"https://github.com/trending/{lang}").mock(
            return_value=httpx.Response(500)
        )
    scraper = GitHubTrendingScraper()
    assert scraper.scrape() == []

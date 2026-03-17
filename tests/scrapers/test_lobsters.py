import respx
import httpx
from scrapers.lobsters import LobstersScraper

RSS = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>cool-agent: A new AI agent framework</title>
    <link href="https://github.com/owner/cool-agent"/>
    <updated>2026-03-15T10:00:00+00:00</updated>
  </entry>
</feed>"""

GITHUB_API_RESPONSE = {
    "stargazers_count": 80,
    "license": {"spdx_id": "MIT"},
    "language": "Python",
    "description": "AI agent framework",
    "topics": ["ai"],
    "created_at": "2026-03-01T00:00:00Z",
}

@respx.mock
def test_scrape_returns_github_repos():
    for tag in ["ai", "programming"]:
        respx.get(f"https://lobste.rs/t/{tag}.rss").mock(
            return_value=httpx.Response(200, text=RSS)
        )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = LobstersScraper()
    repos = scraper.scrape()
    assert len(repos) == 1
    assert repos[0].source == "lobsters"

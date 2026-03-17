import respx
import httpx
from scrapers.web_aggregators import WebAggregatorsScraper

CONSOLE_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>cool-agent</title>
      <link>https://github.com/owner/cool-agent</link>
      <pubDate>Mon, 15 Mar 2026 10:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""

DAILY_DEV_RESPONSE = {
    "data": {
        "page": {
            "edges": [
                {
                    "node": {
                        "title": "cool-agent2",
                        "permalink": "https://github.com/owner/cool-agent2",
                    }
                }
            ]
        }
    }
}

GITHUB_API_RESPONSE = {
    "full_name": "owner/cool-agent",
    "stargazers_count": 60,
    "license": {"spdx_id": "MIT"},
    "language": "Python",
    "description": "Cool agent",
    "topics": ["ai"],
    "created_at": "2026-03-01T00:00:00Z",
}

@respx.mock
def test_scrape_from_console_dev():
    respx.get("https://console.dev/tools/rss.xml").mock(
        return_value=httpx.Response(200, text=CONSOLE_RSS)
    )
    respx.post("https://app.daily.dev/api/graphql").mock(
        return_value=httpx.Response(200, json=DAILY_DEV_RESPONSE)
    )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    respx.get("https://api.github.com/repos/owner/cool-agent2").mock(
        return_value=httpx.Response(404)
    )
    scraper = WebAggregatorsScraper()
    repos = scraper.scrape()
    assert any(r.name == "owner/cool-agent" for r in repos)
    assert all(r.source == "web_aggregators" for r in repos)

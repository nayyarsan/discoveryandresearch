import respx
import httpx
from scrapers.hackernews import HackerNewsScraper

HN_RESPONSE = {
    "hits": [
        {
            "objectID": "12345",
            "title": "Show HN: cool-agent – AI agent framework",
            "url": "https://github.com/owner/cool-agent",
            "story_text": None,
            "created_at": "2026-03-15T10:00:00Z",
        },
        {
            "objectID": "99999",
            "title": "Show HN: not-a-github-link",
            "url": "https://example.com/something",
            "story_text": None,
            "created_at": "2026-03-15T10:00:00Z",
        },
    ]
}

GITHUB_API_RESPONSE = {
    "stargazers_count": 300,
    "license": {"spdx_id": "MIT"},
    "language": "Python",
    "description": "AI agent framework",
    "topics": ["ai", "agent"],
    "created_at": "2026-01-01T00:00:00Z",
}

@respx.mock
def test_scrape_filters_non_github_urls():
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(200, json=HN_RESPONSE)
    )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = HackerNewsScraper()
    repos = scraper.scrape()
    assert len(repos) == 1
    assert repos[0].name == "owner/cool-agent"
    assert repos[0].source == "hackernews"

@respx.mock
def test_scrape_returns_empty_on_api_error():
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(503)
    )
    scraper = HackerNewsScraper()
    assert scraper.scrape() == []

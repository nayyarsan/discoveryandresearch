import respx
import httpx
from scrapers.github_search import GitHubSearchScraper

SEARCH_RESPONSE = {
    "items": [
        {
            "full_name": "owner/cool-agent",
            "html_url": "https://github.com/owner/cool-agent",
            "description": "AI agent framework",
            "language": "Python",
            "stargazers_count": 200,
            "license": {"spdx_id": "MIT"},
            "topics": ["ai", "agent"],
            "created_at": "2026-02-01T00:00:00Z",
            "pushed_at": "2026-03-15T10:00:00Z",
        }
    ]
}

@respx.mock
def test_scrape_returns_repos_from_topic_queries():
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=httpx.Response(200, json=SEARCH_RESPONSE)
    )
    scraper = GitHubSearchScraper()
    repos = scraper.scrape()
    assert len(repos) >= 1
    assert repos[0].source == "github_search"
    assert repos[0].name == "owner/cool-agent"

@respx.mock
def test_scrape_deduplicates_across_topic_queries():
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=httpx.Response(200, json=SEARCH_RESPONSE)
    )
    scraper = GitHubSearchScraper()
    repos = scraper.scrape()
    names = [r.name for r in repos]
    assert len(names) == len(set(names))

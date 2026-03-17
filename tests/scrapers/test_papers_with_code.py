import respx
import httpx
from scrapers.papers_with_code import PapersWithCodeScraper

PWC_RESPONSE = {
    "results": [
        {
            "title": "Efficient Agent Framework",
            "published": "2026-03-14",
            "repository": {
                "url": "https://github.com/owner/eff-agent",
                "stars": 120,
            }
        },
        {
            "title": "Paper without code",
            "published": "2026-03-14",
            "repository": None,
        }
    ]
}

GITHUB_API_RESPONSE = {
    "full_name": "owner/eff-agent",
    "stargazers_count": 120,
    "license": {"spdx_id": "MIT"},
    "language": "Python",
    "description": "Efficient agent framework",
    "topics": ["ai", "agent"],
    "created_at": "2026-03-10T00:00:00Z",
}

@respx.mock
def test_scrape_returns_repos_with_code():
    respx.get("https://paperswithcode.com/api/v1/papers/").mock(
        return_value=httpx.Response(200, json=PWC_RESPONSE)
    )
    respx.get("https://api.github.com/repos/owner/eff-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = PapersWithCodeScraper()
    repos = scraper.scrape()
    assert len(repos) == 1
    assert repos[0].name == "owner/eff-agent"
    assert repos[0].source == "papers_with_code"

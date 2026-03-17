import respx
import httpx
from scrapers.reddit import RedditScraper

RSS_WITH_GITHUB = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Check out this agent framework</title>
    <link href="https://github.com/owner/cool-agent"/>
    <updated>2026-03-15T10:00:00+00:00</updated>
    <content>Some content about https://github.com/owner/cool-agent</content>
  </entry>
  <entry>
    <title>No github link here</title>
    <link href="https://reddit.com/r/LocalLLaMA/post/123"/>
    <updated>2026-03-15T10:00:00+00:00</updated>
    <content>No link</content>
  </entry>
</feed>"""

GITHUB_API_RESPONSE = {
    "stargazers_count": 150,
    "license": {"spdx_id": "Apache-2.0"},
    "language": "TypeScript",
    "description": "Cool agent",
    "topics": ["agent"],
    "created_at": "2026-02-01T00:00:00Z",
}

@respx.mock
def test_scrape_extracts_github_links_from_rss():
    for sub in ["LocalLLaMA", "MachineLearning", "artificial"]:
        respx.get(f"https://www.reddit.com/r/{sub}/new.rss").mock(
            return_value=httpx.Response(200, text=RSS_WITH_GITHUB)
        )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = RedditScraper()
    repos = scraper.scrape()
    assert any(r.name == "owner/cool-agent" for r in repos)
    assert all(r.source == "reddit" for r in repos)

@respx.mock
def test_scrape_deduplicates_across_subreddits():
    for sub in ["LocalLLaMA", "MachineLearning", "artificial"]:
        respx.get(f"https://www.reddit.com/r/{sub}/new.rss").mock(
            return_value=httpx.Response(200, text=RSS_WITH_GITHUB)
        )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = RedditScraper()
    repos = scraper.scrape()
    assert len(repos) == 1  # same repo in 3 subreddits — dedup returns only 1

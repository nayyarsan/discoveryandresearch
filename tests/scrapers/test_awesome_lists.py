import respx
import httpx
from scrapers.awesome_lists import AwesomeListsScraper

COMMITS_RESPONSE = [{"sha": "abc123"}]

DIFF_RESPONSE = """\
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -10,0 +11 @@
+- [cool-agent](https://github.com/owner/cool-agent) - A cool agent framework
"""

GITHUB_API_RESPONSE = {
    "full_name": "owner/cool-agent",
    "stargazers_count": 75,
    "license": {"spdx_id": "MIT"},
    "language": "Python",
    "description": "A cool agent framework",
    "topics": ["agent"],
    "created_at": "2026-03-01T00:00:00Z",
}

AWESOME_LISTS = [
    "e2b-dev/awesome-ai-agents",
    "Hannibal046/Awesome-LLM",
    "visenger/awesome-mlops",
    "onejune2018/Awesome-LLM-Eval",
    "punkpeye/awesome-mcp-servers",
]

@respx.mock
def test_scrape_extracts_newly_added_repos_from_diff():
    for owner_repo in AWESOME_LISTS:
        respx.get(f"https://api.github.com/repos/{owner_repo}/commits").mock(
            return_value=httpx.Response(200, json=COMMITS_RESPONSE)
        )
        respx.get(f"https://api.github.com/repos/{owner_repo}/commits/abc123").mock(
            return_value=httpx.Response(200, json={"files": [{"patch": DIFF_RESPONSE}]})
        )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = AwesomeListsScraper()
    repos = scraper.scrape()
    assert any(r.name == "owner/cool-agent" for r in repos)
    assert all(r.source == "awesome_lists" for r in repos)

@respx.mock
def test_scrape_ignores_removed_lines():
    REMOVAL_DIFF = "- [old-agent](https://github.com/owner/old-agent) - removed"
    for owner_repo in AWESOME_LISTS:
        respx.get(f"https://api.github.com/repos/{owner_repo}/commits").mock(
            return_value=httpx.Response(200, json=COMMITS_RESPONSE)
        )
        respx.get(f"https://api.github.com/repos/{owner_repo}/commits/abc123").mock(
            return_value=httpx.Response(200, json={"files": [{"patch": REMOVAL_DIFF}]})
        )
    scraper = AwesomeListsScraper()
    repos = scraper.scrape()
    assert repos == []

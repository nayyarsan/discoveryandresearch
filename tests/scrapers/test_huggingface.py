import respx
import httpx
from scrapers.huggingface import HuggingFaceScraper

HF_RESPONSE = [
    {
        "id": "owner/cool-model",
        "createdAt": "2026-03-15T00:00:00.000Z",
        "likes": 45,
        "cardData": {"github": "https://github.com/owner/cool-agent"},
    },
    {
        "id": "owner/no-github",
        "createdAt": "2026-03-15T00:00:00.000Z",
        "likes": 10,
        "cardData": {},
    }
]

GITHUB_API_RESPONSE = {
    "full_name": "owner/cool-agent",
    "stargazers_count": 90,
    "license": {"spdx_id": "Apache-2.0"},
    "language": "Python",
    "description": "Cool agent from HF",
    "topics": ["llm"],
    "created_at": "2026-03-10T00:00:00Z",
}

@respx.mock
def test_scrape_extracts_github_links_from_model_cards():
    for endpoint in ["models", "spaces"]:
        respx.get(f"https://huggingface.co/api/{endpoint}").mock(
            return_value=httpx.Response(200, json=HF_RESPONSE)
        )
    respx.get("https://api.github.com/repos/owner/cool-agent").mock(
        return_value=httpx.Response(200, json=GITHUB_API_RESPONSE)
    )
    scraper = HuggingFaceScraper()
    repos = scraper.scrape()
    assert len(repos) == 1
    assert repos[0].source == "huggingface"
    assert repos[0].name == "owner/cool-agent"

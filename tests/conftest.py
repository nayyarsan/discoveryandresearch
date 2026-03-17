import pytest
from datetime import datetime, timezone
from schemas.repo import Repo


@pytest.fixture
def sample_repo() -> Repo:
    return Repo(
        name="owner/cool-agent",
        url="https://github.com/owner/cool-agent",
        description="A cool AI agent framework",
        language="python",
        stars=250,
        stars_delta=80,
        license="mit",
        source="github_trending",
        discovered_at=datetime(2026, 3, 16, 22, 0, 0, tzinfo=timezone.utc),
        topics=["ai", "agent", "llm"],
        score=0.0,
        why_notable="80 new stars this week",
    )


@pytest.fixture
def sample_repos(sample_repo) -> list[Repo]:
    """5 repos with varying scores."""
    from copy import deepcopy
    repos = []
    for i in range(5):
        r = deepcopy(sample_repo)
        r = r.model_copy(update={
            "name": f"owner/repo-{i}",
            "url": f"https://github.com/owner/repo-{i}",
            "stars": 100 + i * 50,
            "stars_delta": i * 20,
        })
        repos.append(r)
    return repos

import re
from schemas.repo import Repo

DEFAULT_KEYWORDS = [
    "ai", "agent", "llm", "sdlc", "devops", "eval", "prompt",
    "copilot", "rag", "mcp", "workflow", "pipeline", "enterprise",
]

# Repos whose topics include any of these are dropped — learning resources,
# not production tools.
EXCLUDE_TOPICS = {
    "tutorial", "tutorials", "educational", "education",
    "teaching", "learning", "course", "beginner", "workshop",
    "example", "examples", "demo", "demos",
}


def filter_repos(
    repos: list[Repo],
    min_stars: int = 50,
    keywords: list[str] = DEFAULT_KEYWORDS,
) -> list[Repo]:
    """Apply stars and relevance keyword filters.
    License/language validation is already enforced by the Repo schema."""
    patterns = [re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in keywords]
    result = []
    for repo in repos:
        if repo.stars < min_stars:
            continue
        searchable = " ".join([repo.name, repo.description, " ".join(repo.topics)])
        if not any(p.search(searchable) for p in patterns):
            continue
        if EXCLUDE_TOPICS.intersection({t.lower() for t in repo.topics}):
            continue
        result.append(repo)
    return result

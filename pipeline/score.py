from datetime import datetime, timezone
from schemas.repo import Repo


def score_and_rank(repos: list[Repo], top_n: int = 5) -> list[Repo]:
    """Score and rank repos. Returns top_n sorted by score descending."""
    if not repos:
        return []

    max_delta = max((r.stars_delta for r in repos), default=1) or 1
    scored = []
    for repo in repos:
        delta_score = repo.stars_delta / max_delta
        source_score = min(repo.source_count / 3, 1.0)
        topic_score = min(len(repo.topics) / 5, 1.0)
        age_days = (datetime.now(tz=timezone.utc) - repo.discovered_at).days
        recency_score = 1.0 if age_days <= 30 else 0.0

        final = (
            0.4 * delta_score +
            0.3 * source_score +
            0.2 * topic_score +
            0.1 * recency_score
        )
        scored.append(repo.model_copy(update={"score": round(final, 4)}))

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_n]

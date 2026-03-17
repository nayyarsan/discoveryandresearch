from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pipeline.score import score_and_rank

def test_returns_top_n_repos(sample_repos):
    result = score_and_rank(sample_repos, top_n=3)
    assert len(result) == 3

def test_higher_stars_delta_ranks_higher(sample_repo):
    low = sample_repo.model_copy(update={"stars_delta": 10, "name": "a/low", "url": "https://github.com/a/low"})
    high = sample_repo.model_copy(update={"stars_delta": 500, "name": "a/high", "url": "https://github.com/a/high"})
    result = score_and_rank([low, high], top_n=2)
    assert result[0].name == "a/high"

def test_recent_repo_scores_higher_than_old(sample_repo):
    recent = sample_repo.model_copy(update={
        "name": "a/recent", "url": "https://github.com/a/recent",
        "discovered_at": datetime.now(tz=timezone.utc) - timedelta(days=5),
        "stars_delta": 0,
    })
    old = sample_repo.model_copy(update={
        "name": "a/old", "url": "https://github.com/a/old",
        "discovered_at": datetime.now(tz=timezone.utc) - timedelta(days=90),
        "stars_delta": 0,
    })
    result = score_and_rank([recent, old], top_n=2)
    assert result[0].name == "a/recent"

def test_scores_assigned_to_all_repos(sample_repos):
    result = score_and_rank(sample_repos, top_n=10)
    assert len(result) == len(sample_repos)
    assert all(isinstance(r.score, float) for r in result)

def test_returns_empty_for_empty_input():
    result = score_and_rank([], top_n=5)
    assert result == []

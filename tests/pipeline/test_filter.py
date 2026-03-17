import pytest
from pipeline.filter import filter_repos

KEYWORDS = ["ai", "agent", "llm"]

def test_filter_removes_low_star_repos(sample_repo):
    low_stars = sample_repo.model_copy(update={"stars": 10, "url": "https://github.com/a/b", "name": "a/b"})
    result = filter_repos([low_stars], min_stars=50, keywords=KEYWORDS)
    assert result == []

def test_filter_keeps_repos_above_star_threshold(sample_repo):
    result = filter_repos([sample_repo], min_stars=50, keywords=KEYWORDS)
    assert len(result) == 1

def test_filter_removes_repos_with_no_keyword_match(sample_repo):
    no_match = sample_repo.model_copy(update={
        "description": "totally unrelated thing",
        "topics": [],
        "name": "a/no-match",
        "url": "https://github.com/a/no-match",
    })
    result = filter_repos([no_match], min_stars=50, keywords=KEYWORDS)
    assert result == []

def test_filter_matches_keyword_in_description(sample_repo):
    repo = sample_repo.model_copy(update={
        "description": "This is an AI framework",
        "topics": [],
        "name": "a/desc-match",
        "url": "https://github.com/a/desc-match",
    })
    result = filter_repos([repo], min_stars=50, keywords=["ai"])
    assert len(result) == 1

def test_filter_keyword_match_is_case_insensitive(sample_repo):
    repo = sample_repo.model_copy(update={
        "description": "An AI Framework",
        "topics": [],
        "name": "a/upper",
        "url": "https://github.com/a/upper",
    })
    result = filter_repos([repo], min_stars=50, keywords=["ai"])
    assert len(result) == 1

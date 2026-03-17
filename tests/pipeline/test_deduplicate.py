from pipeline.deduplicate import deduplicate, load_seen_ids, save_seen_ids
import json

def test_removes_already_seen_repos(sample_repo):
    seen_ids = {sample_repo.id}
    result = deduplicate([sample_repo], seen_ids=seen_ids)
    assert result == []

def test_passes_new_repos(sample_repo):
    result = deduplicate([sample_repo], seen_ids=set())
    assert len(result) == 1

def test_readmits_repo_with_large_stars_delta(sample_repo):
    hot_repo = sample_repo.model_copy(update={"stars_delta": 600})
    seen_ids = {hot_repo.id}
    result = deduplicate([hot_repo], seen_ids=seen_ids, readmit_threshold=500)
    assert len(result) == 1

def test_does_not_readmit_repo_below_threshold(sample_repo):
    repo = sample_repo.model_copy(update={"stars_delta": 499})
    seen_ids = {repo.id}
    result = deduplicate([repo], seen_ids=seen_ids, readmit_threshold=500)
    assert result == []

def test_load_seen_ids_returns_empty_set_when_file_missing(tmp_path):
    result = load_seen_ids(str(tmp_path / "nonexistent.json"))
    assert result == set()

def test_save_and_load_roundtrip(tmp_path, sample_repo):
    path = str(tmp_path / "seen.json")
    save_seen_ids([sample_repo], set(), path=path)
    loaded = load_seen_ids(path)
    assert sample_repo.id in loaded

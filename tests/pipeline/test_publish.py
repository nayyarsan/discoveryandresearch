import json
from pathlib import Path
from pipeline.publish import write_spotlight_json

def test_writes_spotlight_json_with_repos(tmp_path, sample_repos):
    output = tmp_path / "spotlight.json"
    write_spotlight_json(sample_repos[:2], path=str(output))
    data = json.loads(output.read_text())
    assert "generated_at" in data
    assert len(data["repos"]) == 2
    assert data["repos"][0]["name"] == sample_repos[0].name

def test_writes_empty_repos_array_when_no_candidates(tmp_path):
    output = tmp_path / "spotlight.json"
    write_spotlight_json([], path=str(output))
    data = json.loads(output.read_text())
    assert data["repos"] == []
    assert "generated_at" in data

def test_generated_at_uses_z_suffix(tmp_path, sample_repos):
    output = tmp_path / "spotlight.json"
    write_spotlight_json(sample_repos[:1], path=str(output))
    data = json.loads(output.read_text())
    assert data["generated_at"].endswith("Z")

from pages.build import build_index_html
from schemas.repo import Repo
from datetime import datetime, timezone

def test_build_returns_html_string(sample_repos):
    html = build_index_html(sample_repos)
    assert "<html" in html
    assert sample_repos[0].name in html

def test_build_handles_empty_list():
    html = build_index_html([])
    assert "<html" in html
    assert "No repos" in html or "0" in html

import hashlib
import pytest
from datetime import datetime, timezone
from schemas.repo import Repo

def test_repo_id_is_sha256_of_url():
    repo = Repo(
        name="owner/repo",
        url="https://github.com/owner/repo",
        description="A test repo",
        language="python",
        stars=100,
        stars_delta=0,
        license="mit",
        source="github_trending",
        discovered_at=datetime.now(tz=timezone.utc),
        topics=["ai"],
        score=0.0,
        why_notable="100 stars",
    )
    expected_id = hashlib.sha256("https://github.com/owner/repo".encode()).hexdigest()
    assert repo.id == expected_id

def test_repo_rejects_agpl_license():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Repo(
            name="owner/repo",
            url="https://github.com/owner/repo",
            description="A test repo",
            language="python",
            stars=100,
            stars_delta=0,
            license="agpl-3.0",
            source="github_trending",
            discovered_at=datetime.now(tz=timezone.utc),
            topics=[],
            score=0.0,
            why_notable="",
        )

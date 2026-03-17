import json
from pathlib import Path
from schemas.repo import Repo


def deduplicate(
    repos: list[Repo],
    seen_ids: set[str],
    readmit_threshold: int = 500,
) -> list[Repo]:
    """Remove repos already in seen_ids unless stars_delta >= readmit_threshold."""
    result = []
    for repo in repos:
        if repo.id not in seen_ids:
            result.append(repo)
        elif repo.stars_delta >= readmit_threshold:
            result.append(repo)
    return result


def load_seen_ids(path: str = "data/discovered-repos.json") -> set[str]:
    """Load seen repo IDs from cache file. Returns empty set if file missing."""
    p = Path(path)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text()))
    except Exception:
        return set()


def save_seen_ids(
    repos: list[Repo],
    seen_ids: set[str],
    path: str = "data/discovered-repos.json",
) -> None:
    """Merge newly discovered repo IDs into seen_ids and persist."""
    updated = seen_ids | {r.id for r in repos}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(sorted(updated)))

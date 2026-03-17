import json
from datetime import datetime, timezone
from pathlib import Path
from schemas.repo import Repo


def write_spotlight_json(repos: list[Repo], path: str = "data/spotlight.json") -> None:
    """Write spotlight.json — always writes, even if repos is empty."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repos": [
            {
                "name": r.name,
                "url": r.url,
                "description": r.description,
                "stars": r.stars,
                "stars_delta": r.stars_delta,
                "license": r.license,
                "language": r.language,
                "topics": r.topics,
                "why_notable": r.why_notable,
                "source": r.source,
            }
            for r in repos
        ],
    }
    Path(path).write_text(json.dumps(payload, indent=2))

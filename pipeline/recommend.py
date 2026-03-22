import json
import os

from openai import OpenAI

from pipeline.score import STACK_CONTEXT
from schemas.repo import Repo

RELEVANCE_THRESHOLD = 0.65
VALID_ACTIONS = {"spike", "monitor", "covered", "read"}
VALID_SPIKE_TIMES = {"30min", "half-day", "multi-day"}

_SYSTEM_PROMPT = (
    "You are a senior software engineer advising on which open-source repos "
    "deserve attention. Reply with a JSON object only — no markdown, no prose."
)

_USER_TEMPLATE = """\
Tech stack: {stack}

Repo: {name}
Description: {description}
Topics: {topics}
Why relevant: {relevance_reason}

Return a JSON object with these fields:
- action: one of "spike" (worth a focused experiment), "monitor" (watch but don't act yet), \
"covered" (already handled by a tool in your stack — name which one), "read" (informational only)
- reason: one sentence explaining the recommendation
- spike_time: only include this field when action is "spike"; value must be one of "30min", "half-day", "multi-day"
"""


def recommend(repos: list[Repo]) -> list[Repo]:
    """Generate action recommendations for high-relevance repos.

    Only runs for repos with relevance_score >= RELEVANCE_THRESHOLD.
    Populates the recommendation field with action, reason, and optionally spike_time.
    """
    if not repos:
        return []

    result: list[Repo] = []
    client: OpenAI | None = None

    for repo in repos:
        if repo.relevance_score < RELEVANCE_THRESHOLD:
            result.append(repo)
            continue

        if client is None:
            client = OpenAI(
                base_url="https://models.github.ai/inference",
                api_key=os.environ.get("GITHUB_TOKEN", ""),
            )

        prompt = _USER_TEMPLATE.format(
            stack=STACK_CONTEXT,
            name=repo.name,
            description=repo.description,
            topics=", ".join(repo.topics),
            relevance_reason=repo.relevance_reason,
        )

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=150,
        )

        raw = (resp.choices[0].message.content or "").strip()
        try:
            rec: dict = json.loads(raw)
        except json.JSONDecodeError:
            rec = {}

        # Validate action; discard whole object if action is not recognised
        if rec.get("action") not in VALID_ACTIONS:
            rec = {}
        elif rec["action"] != "spike":
            # spike_time is only valid for spike actions
            rec.pop("spike_time", None)
        elif rec.get("spike_time") not in VALID_SPIKE_TIMES:
            rec["spike_time"] = "30min"

        result.append(repo.model_copy(update={"recommendation": rec}))

    return result

from unittest.mock import MagicMock, patch

import pytest

from pipeline.recommend import RELEVANCE_THRESHOLD, recommend


def _make_chat_response(content: str):
    """Build a minimal mock matching openai ChatCompletion structure."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def test_recommend_handles_empty_input():
    result = recommend([])
    assert result == []


def test_recommend_skips_low_relevance_repos(sample_repo):
    """Repos below the threshold are returned unchanged with no recommendation."""
    low = sample_repo.model_copy(update={"relevance_score": 0.3})
    result = recommend([low])
    assert len(result) == 1
    assert result[0].recommendation == {}


def test_recommend_populates_high_relevance_repo(sample_repo):
    """Repos at or above the threshold get a recommendation dict."""
    high = sample_repo.model_copy(update={
        "relevance_score": RELEVANCE_THRESHOLD,
        "relevance_reason": "Relevant to FastAPI and Python.",
    })
    payload = '{"action": "spike", "reason": "Worth exploring.", "spike_time": "30min"}'

    with patch("pipeline.recommend.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_chat_response(payload)

        result = recommend([high])

    assert result[0].recommendation["action"] == "spike"
    assert result[0].recommendation["reason"] == "Worth exploring."
    assert result[0].recommendation["spike_time"] == "30min"


def test_recommend_action_monitor(sample_repo):
    """monitor action is supported and has no spike_time."""
    high = sample_repo.model_copy(update={"relevance_score": 0.9, "relevance_reason": "Relevant."})
    payload = '{"action": "monitor", "reason": "Keep an eye on it."}'

    with patch("pipeline.recommend.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_chat_response(payload)

        result = recommend([high])

    rec = result[0].recommendation
    assert rec["action"] == "monitor"
    assert "spike_time" not in rec


def test_recommend_action_covered(sample_repo):
    """covered action is supported and has no spike_time."""
    high = sample_repo.model_copy(update={"relevance_score": 0.9, "relevance_reason": "Relevant."})
    payload = '{"action": "covered", "reason": "Already handled by Docker."}'

    with patch("pipeline.recommend.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_chat_response(payload)

        result = recommend([high])

    rec = result[0].recommendation
    assert rec["action"] == "covered"
    assert "spike_time" not in rec


def test_recommend_action_read(sample_repo):
    """read action is supported and has no spike_time."""
    high = sample_repo.model_copy(update={"relevance_score": 0.9, "relevance_reason": "Relevant."})
    payload = '{"action": "read", "reason": "Informational only."}'

    with patch("pipeline.recommend.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_chat_response(payload)

        result = recommend([high])

    rec = result[0].recommendation
    assert rec["action"] == "read"
    assert "spike_time" not in rec


def test_recommend_spike_time_stripped_for_non_spike(sample_repo):
    """spike_time is removed when action is not spike."""
    high = sample_repo.model_copy(update={"relevance_score": 0.9, "relevance_reason": "Relevant."})
    # LLM erroneously includes spike_time for a non-spike action
    payload = '{"action": "monitor", "reason": "Watch it.", "spike_time": "30min"}'

    with patch("pipeline.recommend.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_chat_response(payload)

        result = recommend([high])

    assert "spike_time" not in result[0].recommendation


def test_recommend_invalid_spike_time_defaults_to_30min(sample_repo):
    """An unrecognised spike_time defaults to '30min'."""
    high = sample_repo.model_copy(update={"relevance_score": 0.9, "relevance_reason": "Relevant."})
    payload = '{"action": "spike", "reason": "Try it.", "spike_time": "1week"}'

    with patch("pipeline.recommend.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_chat_response(payload)

        result = recommend([high])

    assert result[0].recommendation["spike_time"] == "30min"


def test_recommend_invalid_action_yields_empty_dict(sample_repo):
    """An unrecognized action results in an empty recommendation dict."""
    high = sample_repo.model_copy(update={"relevance_score": 0.9, "relevance_reason": "Relevant."})
    payload = '{"action": "unknown", "reason": "???"}'

    with patch("pipeline.recommend.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_chat_response(payload)

        result = recommend([high])

    assert result[0].recommendation == {}


def test_recommend_malformed_json_yields_empty_dict(sample_repo):
    """If the LLM returns non-JSON, recommendation is an empty dict."""
    high = sample_repo.model_copy(update={"relevance_score": 0.9, "relevance_reason": "Relevant."})

    with patch("pipeline.recommend.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_chat_response("not valid json")

        result = recommend([high])

    assert result[0].recommendation == {}


def test_recommend_only_calls_llm_for_high_relevance(sample_repo):
    """LLM is not called for repos below the relevance threshold."""
    low = sample_repo.model_copy(update={"relevance_score": 0.5})

    with patch("pipeline.recommend.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        recommend([low])

    mock_cls.assert_not_called()


def test_recommend_mixed_relevance(sample_repo):
    """Only high-relevance repos get recommendations; low-relevance ones are unchanged."""
    low = sample_repo.model_copy(update={
        "name": "owner/low", "url": "https://github.com/owner/low",
        "relevance_score": 0.4,
    })
    high = sample_repo.model_copy(update={
        "name": "owner/high", "url": "https://github.com/owner/high",
        "relevance_score": 0.9, "relevance_reason": "Very relevant.",
    })
    payload = '{"action": "spike", "reason": "Experiment with it.", "spike_time": "half-day"}'

    with patch("pipeline.recommend.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_chat_response(payload)

        result = recommend([low, high])

    assert result[0].recommendation == {}
    assert result[1].recommendation["action"] == "spike"
    assert result[1].recommendation["spike_time"] == "half-day"

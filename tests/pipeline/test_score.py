from copy import deepcopy
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from pipeline.score import score_and_rank, score_relevance, RELEVANCE_THRESHOLD

# Dimension of text-embedding-3-small vectors
EMBEDDING_DIM = 1536

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


# ── score_relevance tests ──────────────────────────────────────────────────────

def _make_embedding_response(embedding: list[float]):
    """Build a minimal mock object matching openai EmbeddingResponse structure."""
    item = MagicMock()
    item.embedding = embedding
    response = MagicMock()
    response.data = [item]
    return response


def _make_batch_embedding_response(embeddings: list[list[float]]):
    """Build a mock response for a batch of embeddings."""
    items = []
    for emb in embeddings:
        item = MagicMock()
        item.embedding = emb
        items.append(item)
    response = MagicMock()
    response.data = items
    return response


def _make_chat_response(content: str):
    """Build a minimal mock object matching openai ChatCompletion structure."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def test_score_relevance_returns_empty_for_empty_input():
    result = score_relevance([])
    assert result == []


def test_score_relevance_populates_fields(sample_repo):
    """All repos get relevance_score and relevance_reason fields."""
    # Orthogonal vectors → cosine similarity = 0.0 (below threshold, no reason generated)
    stack_vec = [1.0, 0.0] + [0.0] * (EMBEDDING_DIM - 2)
    repo_vec = [0.0, 1.0] + [0.0] * (EMBEDDING_DIM - 2)
    with patch("pipeline.score.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.side_effect = [
            _make_embedding_response(stack_vec),
            _make_batch_embedding_response([repo_vec]),
        ]

        result = score_relevance([sample_repo])

    assert len(result) == 1
    assert hasattr(result[0], "relevance_score")
    assert hasattr(result[0], "relevance_reason")
    assert isinstance(result[0].relevance_score, float)
    assert isinstance(result[0].relevance_reason, str)


def test_score_relevance_high_score_gets_reason(sample_repo):
    """Repos with score >= threshold receive a non-empty relevance_reason."""
    # Identical vectors → cosine similarity = 1.0 (above threshold)
    vec = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    expected_reason = "This repo is relevant because it uses FastAPI and Python."

    with patch("pipeline.score.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.side_effect = [
            _make_embedding_response(vec),
            _make_batch_embedding_response([vec]),
        ]
        mock_client.chat.completions.create.return_value = _make_chat_response(expected_reason)

        result = score_relevance([sample_repo])

    assert result[0].relevance_score >= RELEVANCE_THRESHOLD
    assert result[0].relevance_reason == expected_reason


def test_score_relevance_low_score_has_empty_reason(sample_repo):
    """Repos with score < threshold have an empty relevance_reason."""
    # Orthogonal vectors → cosine similarity = 0.0
    stack_vec = [1.0, 0.0] + [0.0] * (EMBEDDING_DIM - 2)
    repo_vec = [0.0, 1.0] + [0.0] * (EMBEDDING_DIM - 2)

    with patch("pipeline.score.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.side_effect = [
            _make_embedding_response(stack_vec),
            _make_batch_embedding_response([repo_vec]),
        ]

        result = score_relevance([sample_repo])

    assert result[0].relevance_score < RELEVANCE_THRESHOLD
    assert result[0].relevance_reason == ""
    mock_client.chat.completions.create.assert_not_called()


def test_score_relevance_score_clamped_to_unit_interval(sample_repo):
    """relevance_score is always in [0.0, 1.0]."""
    vec = [1.0] + [0.0] * (EMBEDDING_DIM - 1)

    with patch("pipeline.score.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.side_effect = [
            _make_embedding_response(vec),
            _make_batch_embedding_response([vec]),
        ]
        mock_client.chat.completions.create.return_value = _make_chat_response("relevant")

        result = score_relevance([sample_repo])

    assert 0.0 <= result[0].relevance_score <= 1.0


def test_score_relevance_batch_multiple_repos(sample_repos):
    """score_relevance handles multiple repos in a single call."""
    n = len(sample_repos)
    stack_vec = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    # First repo is identical to stack (high), rest are orthogonal (low)
    repo_vecs = [[1.0] + [0.0] * (EMBEDDING_DIM - 1)] + [[0.0] + [1.0] + [0.0] * (EMBEDDING_DIM - 2)] * (n - 1)

    with patch("pipeline.score.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.side_effect = [
            _make_embedding_response(stack_vec),
            _make_batch_embedding_response(repo_vecs),
        ]
        mock_client.chat.completions.create.return_value = _make_chat_response("relevant")

        result = score_relevance(sample_repos)

    assert len(result) == n
    # First repo should be high-relevance
    assert result[0].relevance_score >= RELEVANCE_THRESHOLD
    assert result[0].relevance_reason != ""
    # Remaining repos should be low-relevance
    for r in result[1:]:
        assert r.relevance_score < RELEVANCE_THRESHOLD
        assert r.relevance_reason == ""

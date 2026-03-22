import hashlib
from datetime import datetime
from pydantic import BaseModel, computed_field, field_validator

ALLOWED_LICENSES = {"mit", "apache-2.0"}
ALLOWED_LANGUAGES = {"python", "javascript", "typescript"}
ALLOWED_SOURCES = {
    "github_trending", "hackernews", "reddit", "github_search",
    "papers_with_code", "web_aggregators", "huggingface", "lobsters", "awesome_lists",
}


class Repo(BaseModel):
    name: str
    url: str
    description: str
    language: str
    stars: int
    stars_delta: int = 0
    license: str
    source: str
    discovered_at: datetime
    topics: list[str]
    score: float = 0.0
    why_notable: str
    relevance_score: float = 0.0
    relevance_reason: str = ""
    source_count: int = 1  # incremented when same repo found in multiple sources

    @computed_field
    @property
    def id(self) -> str:
        return hashlib.sha256(self.url.encode()).hexdigest()

    @field_validator("license")
    @classmethod
    def validate_license(cls, v: str) -> str:
        if v.lower() not in ALLOWED_LICENSES:
            raise ValueError(f"License '{v}' not allowed. Must be one of {ALLOWED_LICENSES}")
        return v.lower()

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v.lower() not in ALLOWED_LANGUAGES:
            raise ValueError(f"Language '{v}' not in {ALLOWED_LANGUAGES}")
        return v.lower()

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in ALLOWED_SOURCES:
            raise ValueError(f"Source '{v}' not in {ALLOWED_SOURCES}")
        return v

from abc import ABC, abstractmethod
from schemas.repo import Repo


class BaseScraper(ABC):
    """All scrapers must implement scrape() -> list[Repo].
    BaseScraper enforces the interface only."""

    @abstractmethod
    def scrape(self) -> list[Repo]:
        """Return repos found from this source. Never raises — returns [] on error."""
        ...

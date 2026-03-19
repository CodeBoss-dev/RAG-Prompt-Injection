"""Abstract base class for enterprise data source generators."""

from abc import ABC, abstractmethod
from typing import Any


class DataSource(ABC):
    """Base class for enterprise data source generators.

    Each subclass generates synthetic documents for a specific enterprise
    data source (Confluence, Slack, email, internal docs). Every document
    is returned as a dict with a standard schema so downstream consumers
    (ingestion, injection, evaluation) can rely on a consistent format.
    """

    @abstractmethod
    def generate(self, count: int) -> list[dict[str, Any]]:
        """Generate *count* synthetic documents with metadata.

        Returns
        -------
        list[dict]
            Each dict contains at minimum:
            - id: unique string identifier
            - title: human-readable title
            - content: full text body
            - source_type: one of "confluence", "slack", "email", "internal_docs"
            - author: fake person name
            - department: organisational department
            - access_level: "public" | "internal" | "confidential" | "restricted"
            - trust_score: float in [0, 1]
            - created_at: ISO-8601 datetime string
            - metadata: dict with any extra source-specific fields
        """
        ...

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the source type identifier (e.g. ``'confluence'``)."""
        ...

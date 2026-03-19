"""Abstract base class for defense mechanisms."""

from abc import ABC, abstractmethod
from typing import Any

from llama_index.core.schema import NodeWithScore


class BaseDefense(ABC):
    """Base class for defense mechanisms.

    Every defense must implement :meth:`apply`, which receives the current
    list of retrieved nodes, the original user query, and a user-context dict,
    and returns a (possibly filtered / reordered) list of nodes.

    Subclasses satisfying this interface automatically satisfy the
    :class:`src.rag.pipeline.Defense` protocol.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name used in logs and evaluation reports."""
        ...

    @abstractmethod
    def apply(
        self,
        nodes: list[NodeWithScore],
        query: str,
        user_context: dict[str, Any],
    ) -> list[NodeWithScore]:
        """Filter or reorder *nodes* and return the result.

        Parameters
        ----------
        nodes:
            Retrieved nodes from the vector store.
        query:
            The user's original natural-language query.
        user_context:
            Contextual information about the requesting user.  At minimum
            contains ``{"role": "employee", "department": "Engineering"}``.

        Returns
        -------
        list[NodeWithScore]
            The filtered / reordered list of nodes.
        """
        ...

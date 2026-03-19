"""Safety-aware reranker defense.

Computes a composite final score combining:
- Relevance (original similarity score from retrieval)
- Safety (1 - suspicion_score from heuristic scanning)
- Trust (metadata trust score)

Reorders nodes by this composite score descending.  This is a *soft*
defense — it does not remove any nodes, only reorders them so that
suspicious content is pushed toward the bottom.
"""

from __future__ import annotations

import logging
from typing import Any

from llama_index.core.schema import NodeWithScore

from config.settings import settings
from src.defenses.base import BaseDefense
from src.defenses.chunk_scanner import compute_suspicion_score
from src.defenses.source_scoring import compute_trust_score

logger = logging.getLogger(__name__)


class SafetyReranker(BaseDefense):
    """Reorders nodes by a weighted combination of relevance, safety, and trust.

    Parameters
    ----------
    relevance_weight:
        Weight for the original retrieval similarity score.
    safety_weight:
        Weight for the safety component (1 - suspicion_score).
    trust_weight:
        Weight for the source trust component.
    """

    def __init__(
        self,
        relevance_weight: float | None = None,
        safety_weight: float | None = None,
        trust_weight: float | None = None,
    ) -> None:
        self._w_rel = relevance_weight if relevance_weight is not None else settings.reranker_relevance_weight
        self._w_safe = safety_weight if safety_weight is not None else settings.reranker_safety_weight
        self._w_trust = trust_weight if trust_weight is not None else settings.reranker_trust_weight

    @property
    def name(self) -> str:
        return "SafetyReranker"

    def _compute_final_score(self, node: NodeWithScore) -> float:
        """Compute the weighted composite score for a single node."""
        # Relevance: the original similarity score (defaults to 0.5 if absent)
        relevance = node.score if node.score is not None else 0.5

        # Safety: inverse of suspicion score
        # Reuse precomputed suspicion_score if ChunkScanner already ran
        suspicion = node.node.metadata.get("suspicion_score")
        if suspicion is None:
            suspicion = compute_suspicion_score(node.node.get_content())
            node.node.metadata["suspicion_score"] = suspicion
        safety = 1.0 - suspicion

        # Trust: reuse precomputed trust or compute fresh
        trust = node.node.metadata.get("computed_trust_score")
        if trust is None:
            trust = compute_trust_score(node.node.metadata)
            node.node.metadata["computed_trust_score"] = trust

        final = (
            self._w_rel * relevance
            + self._w_safe * safety
            + self._w_trust * trust
        )
        return final

    def apply(
        self,
        nodes: list[NodeWithScore],
        query: str,
        user_context: dict[str, Any],
    ) -> list[NodeWithScore]:
        scored: list[tuple[float, int, NodeWithScore]] = []

        for idx, node in enumerate(nodes):
            final = self._compute_final_score(node)
            node.node.metadata["reranker_final_score"] = final
            # Store the new composite as the node's score for downstream use
            node.score = final
            # idx used as tiebreaker to maintain stable sort
            scored.append((final, idx, node))

        scored.sort(key=lambda t: t[0], reverse=True)

        logger.debug(
            "SafetyReranker: reordered %d nodes (top score=%.3f, bottom=%.3f)",
            len(scored),
            scored[0][0] if scored else 0.0,
            scored[-1][0] if scored else 0.0,
        )

        return [node for _, _, node in scored]

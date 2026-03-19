"""Source trust scoring defense.

Computes a composite trust score for each retrieved node based on:
- Source type weight (internal_docs > confluence > email > slack)
- Trust score already present in metadata
- Recency penalty (older documents score slightly lower)

Nodes below the configured threshold are removed.  Surviving nodes are
sorted by trust score (highest first).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from llama_index.core.schema import NodeWithScore

from config.settings import settings
from src.defenses.base import BaseDefense

logger = logging.getLogger(__name__)

# Default source-type weights (higher = more trusted)
SOURCE_TYPE_WEIGHTS: dict[str, float] = {
    "internal_docs": 0.9,
    "confluence": 0.8,
    "email": 0.7,
    "slack": 0.5,
}

# Component weights for final trust score
_W_SOURCE = 0.4
_W_META_TRUST = 0.4
_W_RECENCY = 0.2

# Max age in days before the recency component bottoms out at 0
_MAX_AGE_DAYS = 365


def _recency_score(created_at: str | None) -> float:
    """Return a recency score in [0, 1].  1 = brand-new, 0 = very old."""
    if not created_at:
        return 0.5  # neutral if unknown
    try:
        dt = datetime.fromisoformat(created_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(tz=timezone.utc) - dt).days
        return max(0.0, 1.0 - age_days / _MAX_AGE_DAYS)
    except (ValueError, TypeError):
        return 0.5


def compute_trust_score(metadata: dict[str, Any]) -> float:
    """Compute a composite trust score in [0, 1] from node metadata."""
    source_type = metadata.get("source_type", "")
    source_weight = SOURCE_TYPE_WEIGHTS.get(source_type, 0.5)

    meta_trust = float(metadata.get("trust_score", 0.5))

    recency = _recency_score(metadata.get("created_at"))

    composite = (
        _W_SOURCE * source_weight
        + _W_META_TRUST * meta_trust
        + _W_RECENCY * recency
    )
    return max(0.0, min(1.0, composite))


class SourceTrustScorer(BaseDefense):
    """Filters and sorts nodes by composite trust score.

    Parameters
    ----------
    threshold:
        Nodes below this trust score are removed.  Defaults to
        ``settings.trust_score_threshold``.
    """

    def __init__(self, threshold: float | None = None) -> None:
        self._threshold = (
            threshold if threshold is not None else settings.trust_score_threshold
        )

    @property
    def name(self) -> str:
        return "SourceTrustScorer"

    def apply(
        self,
        nodes: list[NodeWithScore],
        query: str,
        user_context: dict[str, Any],
    ) -> list[NodeWithScore]:
        scored: list[tuple[float, NodeWithScore]] = []

        for node in nodes:
            trust = compute_trust_score(node.node.metadata)
            node.node.metadata["computed_trust_score"] = trust

            if trust < self._threshold:
                logger.info(
                    "SourceTrustScorer: removed node (trust=%.2f, threshold=%.2f): %.80s…",
                    trust,
                    self._threshold,
                    node.node.get_content(),
                )
                continue

            scored.append((trust, node))

        # Sort by trust score descending
        scored.sort(key=lambda t: t[0], reverse=True)
        return [node for _, node in scored]

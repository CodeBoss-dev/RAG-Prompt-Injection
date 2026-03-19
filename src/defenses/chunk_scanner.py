"""Chunk-level scanning defense using regex heuristics and an optional ML detector.

Two-tier detection:
1. Regex / heuristic patterns with severity scoring.
2. ML detector (DistilBERT binary classifier) — used when *use_ml* is True
   and a trained model is available.

Chunks whose suspicion score exceeds the configured threshold are removed
(or optionally prefixed with a warning).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from llama_index.core.schema import NodeWithScore

from config.settings import settings
from src.defenses.base import BaseDefense

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heuristic pattern definitions
# ---------------------------------------------------------------------------

# Each entry is (compiled_regex, severity_weight).
# severity_weight is on a 0–1 scale where 1.0 = very suspicious.

_HIGH_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE), 1.0),
    (re.compile(r"system\s+override", re.IGNORECASE), 1.0),
    (re.compile(r"ADMIN\s+NOTE", re.IGNORECASE), 0.9),
    (re.compile(r"ignore\s+all\s+prior", re.IGNORECASE), 1.0),
    (re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|context)", re.IGNORECASE), 1.0),
    (re.compile(r"new\s+instructions?\s*:", re.IGNORECASE), 0.85),
    (re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.IGNORECASE), 0.9),
    (re.compile(r"do\s+not\s+follow\s+(the\s+)?(system|original)\s+(prompt|instructions)", re.IGNORECASE), 1.0),
]

_MEDIUM_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"click\s+here\s+to", re.IGNORECASE), 0.6),
    (re.compile(r"(password|credential|api[_\s]?key)\s*[:=]", re.IGNORECASE), 0.65),
    (re.compile(r"https?://[^\s]+\.(xyz|top|tk|ml|ga|cf|gq|buzz|work)/", re.IGNORECASE), 0.7),
    (re.compile(r"(verify|confirm|reset)\s+your\s+(password|credentials|account)", re.IGNORECASE), 0.6),
    (re.compile(r"output\s+(the|all|any)\s+(api|secret|private)\s*(key|token)", re.IGNORECASE), 0.75),
    (re.compile(r"reveal\s+(any|all|the)\s+(secret|private|internal)", re.IGNORECASE), 0.7),
]

_LOW_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"<!--\s*.*?(instruction|command|override|ignore).*?\s*-->", re.IGNORECASE | re.DOTALL), 0.4),
    (re.compile(r"\x00|\x01|\x1b\[", re.IGNORECASE), 0.35),  # null bytes / ANSI escapes
    (re.compile(r"\[hidden\]|\[invisible\]", re.IGNORECASE), 0.4),
]

ALL_PATTERNS: list[tuple[re.Pattern[str], float]] = (
    _HIGH_PATTERNS + _MEDIUM_PATTERNS + _LOW_PATTERNS
)


def compute_suspicion_score(text: str) -> float:
    """Return a suspicion score in [0, 1] for the given text.

    The score is the maximum severity weight among all matching patterns.
    If no pattern matches, the score is 0.0.
    """
    max_score = 0.0
    for pattern, weight in ALL_PATTERNS:
        if pattern.search(text):
            max_score = max(max_score, weight)
    return min(max_score, 1.0)


class ChunkScanner(BaseDefense):
    """Regex + optional ML chunk-level injection scanner.

    Parameters
    ----------
    threshold:
        Suspicion score above which a node is removed.  Defaults to
        ``settings.detector_threshold``.
    use_ml:
        When True, attempt to load the trained DistilBERT detector and
        combine its prediction with the heuristic score.  Falls back to
        heuristic-only if the model is not available.
    warn_only:
        When True, flagged chunks are prefixed with a warning instead of
        being removed.
    """

    def __init__(
        self,
        threshold: float | None = None,
        use_ml: bool = False,
        warn_only: bool = False,
    ) -> None:
        self._threshold = threshold if threshold is not None else settings.detector_threshold
        self._use_ml = use_ml
        self._warn_only = warn_only
        self._ml_detector: Any | None = None

        if use_ml:
            self._try_load_ml_detector()

    @property
    def name(self) -> str:
        mode = "ML+Heuristic" if self._ml_detector is not None else "Heuristic"
        return f"ChunkScanner({mode})"

    # ------------------------------------------------------------------
    # ML detector helpers
    # ------------------------------------------------------------------

    def _try_load_ml_detector(self) -> None:
        """Attempt to load the trained DistilBERT detector."""
        model_path = settings.model_output_dir / "detector"
        if not model_path.exists():
            logger.warning(
                "ML detector requested but model not found at %s — "
                "falling back to heuristic-only mode.",
                model_path,
            )
            return
        try:
            from src.defenses.detector.model import InjectionDetector

            self._ml_detector = InjectionDetector.load(str(model_path))
            logger.info("Loaded ML injection detector from %s", model_path)
        except Exception:
            logger.warning("Failed to load ML detector — falling back to heuristic-only.", exc_info=True)

    def _ml_score(self, text: str) -> float:
        """Return the ML detector's injection probability for *text*."""
        if self._ml_detector is None:
            return 0.0
        return float(self._ml_detector.predict(text))

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_node(self, node: NodeWithScore) -> float:
        """Compute the final suspicion score for a single node."""
        text = node.node.get_content()
        heuristic = compute_suspicion_score(text)

        if self._ml_detector is not None:
            ml = self._ml_score(text)
            # Combine: take the max of heuristic and ML (either can flag)
            return max(heuristic, ml)

        return heuristic

    # ------------------------------------------------------------------
    # Defense interface
    # ------------------------------------------------------------------

    def apply(
        self,
        nodes: list[NodeWithScore],
        query: str,
        user_context: dict[str, Any],
    ) -> list[NodeWithScore]:
        result: list[NodeWithScore] = []
        for node in nodes:
            score = self.score_node(node)
            node.node.metadata["suspicion_score"] = score

            if score > self._threshold:
                if self._warn_only:
                    original = node.node.get_content()
                    node.node.set_content(
                        f"[WARNING: potentially injected content (score={score:.2f})] {original}"
                    )
                    result.append(node)
                else:
                    logger.info(
                        "ChunkScanner: removed node (score=%.2f, threshold=%.2f): %.80s…",
                        score,
                        self._threshold,
                        node.node.get_content(),
                    )
            else:
                result.append(node)

        return result

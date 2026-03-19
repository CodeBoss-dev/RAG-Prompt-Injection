"""Defense mechanisms for the RAG pipeline.

All defenses implement the :class:`BaseDefense` abstract class and satisfy
the :class:`src.rag.pipeline.Defense` protocol.
"""

from src.defenses.base import BaseDefense
from src.defenses.chunk_scanner import ChunkScanner
from src.defenses.privilege_filter import PrivilegeFilter
from src.defenses.safety_reranker import SafetyReranker
from src.defenses.source_scoring import SourceTrustScorer

__all__ = [
    "BaseDefense",
    "ChunkScanner",
    "PrivilegeFilter",
    "SafetyReranker",
    "SourceTrustScorer",
]

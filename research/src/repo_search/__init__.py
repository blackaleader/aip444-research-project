"""
repo_search — experimental framework for repository-level retrieval comparison.

Research question (fixed):
  Does agent-directed code search outperform one-shot code RAG for
  repository-level software engineering tasks?

Stage 6 status:
  Method A (one-shot RAG) and Method B (agent-directed search) are implemented
  against the shared Stage 5 retriever. Pilot batch trials belong to Stage 7+.
"""

from repo_search.retriever import RetrievedChunk, SemanticRetriever

__version__ = "0.6.0"
__all__ = ["RetrievedChunk", "SemanticRetriever", "__version__"]

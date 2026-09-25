"""LightRAG + Cohere integration [PLUS].

This module provides hybrid search capabilities combining:
- Institutional knowledge graph (sentence-transformers + ChromaDB + networkx)
- PDF-derived knowledge graph (LightRAG)
- Enhanced recommendations with Cohere LLM

Strictly additive: nothing in saberlink/ (core) imports from here.
"""

from saberlink.lightrag_integration import cohere_enhancer, hybrid_search, pdf_processor

__all__ = ["cohere_enhancer", "hybrid_search", "pdf_processor"]

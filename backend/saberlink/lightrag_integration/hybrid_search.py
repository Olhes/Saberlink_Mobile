"""Hybrid search combining institutional and LightRAG results [PLUS]."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from saberlink import pipeline
from saberlink.lightrag_integration import cohere_enhancer, pdf_processor


def merge_results(
    institutional_results: list[dict[str, Any]],
    pdf_results: list[dict[str, Any]],
    merge_strategy: str = "interleave",
) -> list[dict[str, Any]]:
    """Merge results from institutional search and PDF search.
    
    Args:
        institutional_results: Results from sentence-transformers + ChromaDB
        pdf_results: Results from LightRAG graph search
        merge_strategy: How to merge ('interleave', 'append', 'score_weighted')
    
    Returns:
        Merged and deduplicated list of results
    """
    if not pdf_results:
        return institutional_results
    
    if not institutional_results:
        return pdf_results
    
    # Mark source of each result
    for r in institutional_results:
        r["result_source"] = "institutional"
    
    for r in pdf_results:
        r["result_source"] = "pdf"
    
    if merge_strategy == "interleave":
        # Interleave results by score
        merged = []
        i, j = 0, 0
        while i < len(institutional_results) or j < len(pdf_results):
            if i < len(institutional_results):
                merged.append(institutional_results[i])
                i += 1
            if j < len(pdf_results):
                merged.append(pdf_results[j])
                j += 1
        return merged
    
    elif merge_strategy == "append":
        # Append PDF results after institutional
        return institutional_results + pdf_results
    
    elif merge_strategy == "score_weighted":
        # Combine by weighted score and sort
        all_results = institutional_results + pdf_results
        # TODO: Implement weighted scoring based on source reliability
        return sorted(all_results, key=lambda x: x.get("relevance", {}).get("score", 0), reverse=True)
    
    else:
        return institutional_results + pdf_results


def run_hybrid_query(
    pdf_path: str,
    use_cohere: bool = True,
    cohere_api_key: str | None = None,
    top_k: int = 8,
) -> dict[str, Any]:
    """Run hybrid query combining institutional and LightRAG search.

    Args:
        pdf_path: Path to PDF file
        use_cohere: Whether to use Cohere for enhancement
        cohere_api_key: Cohere API key (default: from config)
        top_k: Number of top results to return

    Returns:
        Combined results with enhanced opportunities
    """
    # 1. Process PDF with LightRAG (now includes graph building)
    pdf_data = pdf_processor.process_pdf_with_lightrag(
        pdf_path,
        api_key=cohere_api_key,
    )

    # 2. Extract text profile for institutional search
    markdown_text = Path(pdf_data["markdown_path"]).read_text(encoding="utf-8")
    text_profile = pdf_processor.extract_text_profile_from_markdown(
        markdown_text,
        source_file=Path(pdf_path).name,
    )

    # 3. Run institutional search
    institutional_result = pipeline.run_query(
        raw_text_profile=text_profile,
        top_k=top_k,
    )

    # 4. Run PDF search (LightRAG query - placeholder for now)
    # TODO: Implement actual LightRAG query using the built graph
    pdf_results = []  # Will be populated when LightRAG query is implemented

    # 5. Merge results
    merged_results = merge_results(
        institutional_result["results"],
        pdf_results,
        merge_strategy="interleave",
    )

    # 6. Enhance with Cohere if enabled
    if use_cohere:
        enhancer = cohere_enhancer.CohereEnhancer(api_key=cohere_api_key)

        # Re-rank results
        query_text = text_profile.get("description", "") + " " + text_profile.get("context", "")
        reranked_results = enhancer.rerank_results(query_text, merged_results, top_n=top_k)

        # Generate enhanced opportunities
        enhanced_opportunities = enhancer.generate_opportunities(
            query_text,
            reranked_results,
            institutional_result["source"],
        )

        opportunities = enhanced_opportunities
    else:
        reranked_results = merged_results[:top_k]
        opportunities = institutional_result["opportunities"]

    return {
        "source": institutional_result["source"],
        "results": reranked_results[:top_k],
        "opportunities": opportunities,
        "meta": {
            "top_k": top_k,
            "institutional_results": len(institutional_result["results"]),
            "pdf_results": len(pdf_results),
            "cohere_used": use_cohere,
            "pdf_hash": pdf_data["pdf_hash"],
            "merge_strategy": "interleave",
            "lightrag_graph_built": pdf_data.get("lightrag_result", {}).get("status") == "success",
        },
    }


async def run_hybrid_query_async(
    pdf_path: str,
    use_cohere: bool = True,
    cohere_api_key: str | None = None,
    top_k: int = 8,
) -> dict[str, Any]:
    """Async version of run_hybrid_query for FastAPI endpoints.

    This version avoids pickle errors by being fully async.

    Args:
        pdf_path: Path to PDF file
        use_cohere: Whether to use Cohere for enhancement
        cohere_api_key: Cohere API key (default: from config)
        top_k: Number of top results to return

    Returns:
        Combined results with enhanced opportunities
    """
    # 1. Process PDF with LightRAG (async version)
    pdf_data = await pdf_processor.process_pdf_with_lightrag_async(
        pdf_path,
        api_key=cohere_api_key,
    )

    # 2. Extract text profile for institutional search
    markdown_text = Path(pdf_data["markdown_path"]).read_text(encoding="utf-8")
    text_profile = pdf_processor.extract_text_profile_from_markdown(
        markdown_text,
        source_file=Path(pdf_path).name,
    )

    # 3. Run institutional search (sync, but that's ok)
    institutional_result = pipeline.run_query(
        raw_text_profile=text_profile,
        top_k=top_k,
    )

    # 4. Run PDF search (LightRAG query - placeholder for now)
    pdf_results = []

    # 5. Merge results
    merged_results = merge_results(
        institutional_result["results"],
        pdf_results,
        merge_strategy="interleave",
    )

    # 6. Enhance with Cohere if enabled
    if use_cohere:
        enhancer = cohere_enhancer.CohereEnhancer(api_key=cohere_api_key)

        query_text = text_profile.get("description", "") + " " + text_profile.get("context", "")
        reranked_results = enhancer.rerank_results(query_text, merged_results, top_n=top_k)

        # Extract LightRAG graph information for better context
        lightrag_context = {
            "graph_path": pdf_data.get("graph_path"),
            "lightrag_result": pdf_data.get("lightrag_result", {}),
        }

        enhanced_opportunities = enhancer.generate_opportunities(
            query_text,
            reranked_results,
            institutional_result["source"],
            lightrag_context=lightrag_context,
        )

        opportunities = enhanced_opportunities
    else:
        reranked_results = merged_results[:top_k]
        opportunities = institutional_result["opportunities"]

    return {
        "source": institutional_result["source"],
        "results": reranked_results[:top_k],
        "opportunities": opportunities,
        "meta": {
            "top_k": top_k,
            "institutional_results": len(institutional_result["results"]),
            "pdf_results": len(pdf_results),
            "cohere_used": use_cohere,
            "pdf_hash": pdf_data["pdf_hash"],
            "merge_strategy": "interleave",
            "lightrag_graph_built": pdf_data.get("lightrag_result", {}).get("status") == "success",
        },
    }

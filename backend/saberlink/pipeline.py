"""Stage E: run_query — the ONE live entry point.

Every notebook, the Streamlit app (PLUS), and the live-demo notebook all call
this same function. There is no parallel "saved answer" path: given an
entity_id (or, for the PLUS PDF-upload flow, a raw_text_profile dict), it
re-embeds, re-scores, re-builds evidence and re-runs the opportunity rules
on every single call — nothing about a *result* is ever cached. The static
artifacts loaded once per process (entities table, graph, domain vocab) are
a legitimate index over fixed institutional data, not a cached answer to any
particular query — this is the same distinction the official rules draw
("resultados precargados" vs. index/preprocessing, both permitted).
"""

from __future__ import annotations

import time
import uuid

import pandas as pd

from saberlink import config, domain_vocab as dv, entity_lookup, evidence, graph_build, graph_query, opportunities, schema, scoring

_entities: pd.DataFrame | None = None
_fields_index: pd.DataFrame | None = None
_graph = None
_vocab: set[str] | None = None
_term_weights: dict[str, float] | None = None
_entity_lookup: dict[str, dict] | None = None

CANDIDATE_TYPES_BY_SOURCE: dict[str, list[str]] = {
    "NEED": ["PRJ", "THS", "INV", "CAP", "GRP", "SUB", "COM", "LO"],
    "PRJ": ["THS", "INV", "GRP"],
    "THS": ["PRJ", "INV"],
    "INV": ["INV", "PRJ", "GRP"],
    "GRP": ["GRP", "PRJ"],
}
DEFAULT_CANDIDATE_TYPES = ["PRJ", "THS", "INV", "GRP", "CAP"]


def _load_state():
    global _entities, _fields_index, _graph, _vocab, _term_weights, _entity_lookup
    if _entities is None:
        _entities = pd.read_parquet(config.ENTITIES_PARQUET)
    if _fields_index is None:
        _fields_index = pd.read_parquet(config.FIELDS_INDEX_PARQUET)
    if _graph is None:
        _graph = graph_build.load_graph()
    if _vocab is None:
        _vocab = dv.load_vocab()
    if _term_weights is None:
        _term_weights = dv.load_term_weights()
    if _entity_lookup is None:
        # Built once and reused for every query — rebuilding this dict from
        # the (pyarrow-backed) DataFrame on every call was the single
        # largest remaining cost of a live query, since the official
        # entities never change between calls (only the PLUS PDF-upload
        # flow adds one ephemeral row, handled separately below).
        _entity_lookup = entity_lookup.build(_entities)
    return _entities, _fields_index, _graph, _vocab, _term_weights, _entity_lookup


def reload_state() -> None:
    """Force a re-read of the processed/ artifacts (e.g. after re-running
    ingest/graph_build/domain_vocab)."""
    global _entities, _fields_index, _graph, _vocab, _term_weights, _entity_lookup
    _entities = _fields_index = _graph = _vocab = _term_weights = _entity_lookup = None
    _load_state()


def _make_ephemeral_need(raw_text_profile: dict) -> tuple[str, pd.DataFrame, pd.DataFrame]:
    """Builds a temporary, non-persisted NEED-shaped row for a query that
    isn't an existing entity_id — a PDF parsed via saberlink.plus.docling_intake,
    or plain free text typed by the user (saberlink.demo --text, or the
    Streamlit text-input mode). Never written to institutional_needs.csv or
    entities.parquet — official=False in the returned source dict."""
    temp_id = f"TEMP-{uuid.uuid4().hex[:8]}"
    source_label = raw_text_profile.get("_source_file_name") or "texto_libre"
    row = {"entity_id": temp_id, "entity_type": "NEED", "source_file": source_label, "source_kind": "user_input"}
    for field_name in schema.ENTITY_SPECS["NEED"].text_fields:
        row[field_name] = raw_text_profile.get(field_name)
    ephemeral_row = pd.DataFrame([row])

    field_rows = []
    for field_name in schema.ENTITY_SPECS["NEED"].text_fields:
        text = raw_text_profile.get(field_name)
        field_rows.append(
            {
                "entity_id": temp_id,
                "entity_type": "NEED",
                "field_name": field_name,
                "field_text": text,
                "field_status": "available" if text else "not_available",
                "source_file": source_label,
                "source_kind": "user_input",
            }
        )
    return temp_id, ephemeral_row, pd.DataFrame(field_rows)


def run_query(
    entity_id: str | None = None,
    raw_text_profile: dict | None = None,
    top_k: int = config.DEFAULT_TOP_K,
    candidate_types: list[str] | None = None,
) -> dict:
    if not entity_id and not raw_text_profile:
        raise ValueError("run_query requires either entity_id or raw_text_profile")

    started = time.perf_counter()
    entities, fields_index, graph, vocab, term_weights, lookup = _load_state()
    official = True

    if raw_text_profile is not None:
        entity_id, ephemeral_row, ephemeral_fields = _make_ephemeral_need(raw_text_profile)
        entities = pd.concat([entities, ephemeral_row], ignore_index=True, sort=False)
        fields_index = pd.concat([fields_index, ephemeral_fields], ignore_index=True, sort=False)
        # Cheap shallow copy + one insert, instead of rebuilding the whole
        # ~3,300-entity lookup dict from the DataFrame on every PDF upload.
        lookup = dict(lookup)
        lookup[entity_id] = ephemeral_row.iloc[0].to_dict()
        official = False

    source_row = lookup.get(entity_id)
    if source_row is None:
        raise ValueError(f"Unknown entity_id: {entity_id}")
    source_type = source_row["entity_type"]
    source_faculty_id = source_row.get("originating_faculty_id") or source_row.get("faculty_id")

    types_to_search = candidate_types or CANDIDATE_TYPES_BY_SOURCE.get(source_type, DEFAULT_CANDIDATE_TYPES)

    # Single-source BFS over the graph is identical for every candidate
    # type (it only depends on the source node) — compute it once per
    # query instead of once per candidate type.
    graph_pre = graph_query.precompute_source(graph, entity_id)

    ranked_by_type: dict[str, list[scoring.CandidateScore]] = {}
    for ctype in types_to_search:
        ranked_by_type[ctype] = scoring.score_candidates(
            entity_id,
            ctype,
            entities,
            graph,
            vocab,
            term_weights=term_weights,
            graph_pre=graph_pre,
            entity_lookup=lookup,
        )

    flat = [c for candidates in ranked_by_type.values() for c in candidates]
    flat.sort(key=lambda c: c.score, reverse=True)
    top = flat[:top_k]

    results = [evidence.build_result(entity_id, source_type, c, fields_index) for c in top]
    opps = opportunities.generate(entity_id, lookup, ranked_by_type, source_faculty_id)

    elapsed = time.perf_counter() - started
    return {
        "source": {"id": entity_id, "type": source_type, "official": official},
        "results": results,
        "opportunities": opps,
        "meta": {
            "top_k": top_k,
            "candidate_types": types_to_search,
            "total_candidates_scored": len(flat),
            "elapsed_seconds": round(elapsed, 3),
        },
    }


def run_hybrid_query(
    pdf_path: str,
    use_cohere: bool = True,
    cohere_api_key: str | None = None,
    top_k: int = config.DEFAULT_TOP_K,
) -> dict:
    """Run hybrid query combining institutional and LightRAG search [PLUS].

    This is a wrapper around saberlink.lightrag_integration.hybrid_search
    for convenience. The actual implementation is in the lightrag_integration
    module to maintain the isolation principle (core doesn't depend on PLUS).

    Args:
        pdf_path: Path to PDF file
        use_cohere: Whether to use Cohere for enhancement
        cohere_api_key: Cohere API key (default: from config)
        top_k: Number of top results to return

    Returns:
        Combined results with enhanced opportunities
    """
    try:
        from saberlink.lightrag_integration import hybrid_search
    except ImportError:
        raise ImportError(
            "LightRAG integration not available. Install dependencies: "
            "pip install lightrag cohere pymupdf4llm"
        )

    return hybrid_search.run_hybrid_query(
        pdf_path=pdf_path,
        use_cohere=use_cohere,
        cohere_api_key=cohere_api_key,
        top_k=top_k,
    )


async def run_hybrid_query_async(
    pdf_path: str,
    use_cohere: bool = True,
    cohere_api_key: str | None = None,
    top_k: int = config.DEFAULT_TOP_K,
) -> dict:
    """Async version of run_hybrid_query for FastAPI endpoints [PLUS].

    This version avoids the pickle error when running asyncio code inside
    thread pool executors by being fully async.

    Args:
        pdf_path: Path to PDF file
        use_cohere: Whether to use Cohere for enhancement
        cohere_api_key: Cohere API key (default: from config)
        top_k: Number of top results to return

    Returns:
        Combined results with enhanced opportunities
    """
    try:
        from saberlink.lightrag_integration import hybrid_search
    except ImportError:
        raise ImportError(
            "LightRAG integration not available. Install dependencies: "
            "pip install lightrag cohere pymupdf4llm"
        )

    return await hybrid_search.run_hybrid_query_async(
        pdf_path=pdf_path,
        use_cohere=use_cohere,
        cohere_api_key=cohere_api_key,
        top_k=top_k,
    )


if __name__ == "__main__":
    import json
    import sys

    query_id = sys.argv[1] if len(sys.argv) > 1 else "NEED-001"
    out = run_query(entity_id=query_id)
    print(json.dumps(out, ensure_ascii=False, indent=2))

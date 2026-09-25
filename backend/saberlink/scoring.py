"""Stage B: the 4-signal composite score.

score = w1*semantic + w2*domain + w3*method + w4*structural

Each component is computed concretely per (source_type, candidate_type) pair
(see SEMANTIC_FIELD_PAIRS / METHOD_FIELD below) rather than as one generic
"similarity" — different entity types expose different fields, and NEED in
particular has neither a domain nor a methodology column *by schema design*
(it must not prescribe a solution). Missing-by-schema is handled by
renormalizing weights across whichever components ARE applicable; a
missing-by-data value (field exists but is empty for this one record) is
instead recorded as None/"not_available" for that single candidate and
excluded the same way — never silently coerced to 0, which the official
rules explicitly forbid ("un campo vacío ... no demuestra necesariamente
que el atributo no exista").
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from saberlink import config, domain_vocab as dv, embeddings, graph_query, vector_store
from saberlink import entity_lookup as entity_lookup_module

# Concrete field-pair table per (source_type, candidate_type). Semantic
# component = max cosine similarity over these pairs.
SEMANTIC_FIELD_PAIRS: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("NEED", "PRJ"): [
        ("title", "title"),
        ("description", "problem_statement"),
        ("description", "abstract"),
        ("context", "application_context"),
        ("expected_impact", "expected_results"),
    ],
    ("NEED", "THS"): [
        ("title", "title"),
        ("description", "problem_statement"),
        ("description", "abstract"),
        ("context", "application_context"),
    ],
    ("NEED", "INV"): [
        ("title", "research_interests"),
        ("description", "profile_summary"),
        ("description", "research_interests"),
    ],
    ("NEED", "CAP"): [
        ("title", "capability_name"),
        ("description", "description"),
    ],
    ("NEED", "GRP"): [
        ("title", "group_name"),
        ("description", "description"),
        ("description", "mission"),
    ],
    ("NEED", "SUB"): [
        ("description", "description"),
        ("description", "purpose"),
    ],
    ("NEED", "COM"): [
        ("description", "description"),
    ],
    ("NEED", "LO"): [
        ("description", "outcome_description"),
    ],
    ("PRJ", "THS"): [
        ("abstract", "abstract"),
        ("problem_statement", "problem_statement"),
    ],
    ("INV", "INV"): [
        ("research_interests", "research_interests"),
        ("profile_summary", "profile_summary"),
    ],
    ("GRP", "GRP"): [
        ("mission", "mission"),
        ("description", "description"),
    ],
}

# Methodology-bearing field per entity type. A pair is method-applicable only
# when BOTH source and candidate types appear here — NEED never does, by
# design, so NEED-sourced queries always redistribute w3 away.
METHOD_FIELD: dict[str, str] = {
    "PRJ": "methodology",
    "THS": "methodology",
    "INV": "methodological_expertise",
}


def get_field_pairs(source_type: str, candidate_type: str) -> list[tuple[str, str]]:
    pairs = SEMANTIC_FIELD_PAIRS.get((source_type, candidate_type))
    if pairs is not None:
        return pairs
    # Generic fallback for any pair not explicitly mapped above: cross the
    # first couple of text fields of each side. Keeps the pipeline from
    # crashing on an unanticipated entity-type pair, at the cost of being
    # less precisely tuned than the table above.
    from saberlink import schema

    src_fields = schema.ENTITY_SPECS[source_type].text_fields[:2]
    cand_fields = schema.ENTITY_SPECS[candidate_type].text_fields[:2]
    return [(sf, cf) for sf in src_fields for cf in cand_fields][:4]


def _get_field_text(entity_id: str, field_name: str, entities) -> str | None:
    if isinstance(entities, dict):
        row = entities.get(entity_id)
        if row is None or field_name not in row:
            return None
        value = row[field_name]
    else:
        matched = entities.loc[entities.entity_id == entity_id]
        if matched.empty or field_name not in matched.columns:
            return None
        value = matched.iloc[0][field_name]
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def overlap_coefficient(a: set[str], b: set[str], term_weights: dict[str, float] | None = None) -> float | None:
    """IDF-weighted overlap coefficient. Plain (unweighted) overlap lets one
    incidental shared generic word (e.g. "prevención", used across dozens of
    unrelated records) max out the score between two otherwise-unrelated
    entities when one side's term set is small. Weighting each shared term
    by 1/document_frequency (see domain_vocab.load_term_weights) makes rare,
    specific phrases (e.g. "permanencia estudiantil") count for far more than
    common ones — closer to what a human would call "same domain"."""
    if not a or not b:
        return None
    intersection = a & b
    if not intersection:
        return 0.0
    weights = term_weights or {}
    numerator = sum(weights.get(t, 1.0) for t in intersection)
    smaller = a if len(a) <= len(b) else b
    denominator = sum(weights.get(t, 1.0) for t in smaller)
    if denominator <= 0:
        return 0.0
    return min(1.0, numerator / denominator)


@dataclass
class ComponentResult:
    value: float | None
    status: str  # "available" | "not_available" | "not_applicable"
    detail: dict = field(default_factory=dict)


@dataclass
class CandidateScore:
    entity_id: str
    entity_type: str
    score: float
    label_absolute: str
    label_percentile: str
    breakdown: dict[str, ComponentResult]
    weights_used: dict[str, float]


def _label(score: float) -> str:
    for threshold, label in config.LABEL_BANDS:
        if score >= threshold:
            return label
    return config.LABEL_BANDS[-1][1]


def score_candidates(
    source_id: str,
    candidate_type: str,
    entities: pd.DataFrame,
    graph,
    vocab: set[str],
    weights: dict[str, float] | None = None,
    term_weights: dict[str, float] | None = None,
    graph_pre=None,
    entity_lookup: dict[str, dict] | None = None,
) -> list[CandidateScore]:
    weights = weights or config.DEFAULT_WEIGHTS
    if entity_lookup is None:
        entity_lookup = entity_lookup_module.build(entities)

    source_row = entity_lookup.get(source_id)
    if source_row is None:
        return []
    source_type = source_row["entity_type"]

    candidate_ids = entities.loc[entities.entity_type == candidate_type, "entity_id"].tolist()
    if source_id in candidate_ids:
        candidate_ids.remove(source_id)
    if not candidate_ids:
        return []

    if graph_pre is None:
        graph_pre = graph_query.precompute_source(graph, source_id)

    # --- Semantic: max cosine similarity over the field-pair table ---
    field_pairs = get_field_pairs(source_type, candidate_type)
    semantic_raw: dict[str, float] = {}
    semantic_field: dict[str, tuple[str, str]] = {}
    for source_field, candidate_field in field_pairs:
        source_text = _get_field_text(source_id, source_field, entity_lookup)
        if not source_text:
            continue
        query_vec = embeddings.embed_one(source_text)
        hits = vector_store.query_field(query_vec, candidate_type, candidate_field, n_results=len(candidate_ids))
        for hit in hits:
            cid, sim = hit["entity_id"], hit["similarity"]
            if cid not in semantic_raw or sim > semantic_raw[cid]:
                semantic_raw[cid] = sim
                semantic_field[cid] = (source_field, candidate_field)

    if semantic_raw:
        pool_vals = list(semantic_raw.values())
        pool_min, pool_max = min(pool_vals), max(pool_vals)
        spread = (pool_max - pool_min) or 1e-9
    else:
        pool_min = pool_max = spread = None

    # --- Method: only if both types expose a methodology-bearing field ---
    method_applicable = source_type in METHOD_FIELD and candidate_type in METHOD_FIELD
    method_sim: dict[str, float] = {}
    if method_applicable:
        source_text = _get_field_text(source_id, METHOD_FIELD[source_type], entity_lookup)
        if source_text:
            query_vec = embeddings.embed_one(source_text)
            hits = vector_store.query_field(
                query_vec, candidate_type, METHOD_FIELD[candidate_type], n_results=len(candidate_ids)
            )
            method_sim = {hit["entity_id"]: hit["similarity"] for hit in hits}

    # --- Domain: generic overlap coefficient of extracted/structured terms ---
    source_terms = dv.entity_domain_terms(source_id, entity_lookup, vocab)

    results: list[CandidateScore] = []
    for cid in candidate_ids:
        breakdown: dict[str, ComponentResult] = {}
        applicable_weights: dict[str, float] = {}

        # Semantic. The composite score uses the RAW cosine similarity, not
        # the pool-rescaled one: rescaling is computed per (query,
        # candidate_type) call, so it is only valid to compare WITHIN one
        # candidate type's pool. Since pipeline.py merges rankings across
        # several candidate types into one flat list, using the rescaled
        # value there would make different types' scores incomparable (a
        # type whose whole pool sits at ~0.6 raw similarity would have its
        # top candidate rescaled to 1.0 and out-rank a genuinely stronger
        # 0.8-raw match from another type). The rescaled value is still
        # computed and kept in `detail` purely for explanation/debugging —
        # it is what neutralizes the NEED-boilerplate compression problem
        # when *displayed*, without corrupting the ranking math.
        if cid in semantic_raw:
            raw = semantic_raw[cid]
            norm = max(0.0, min(1.0, (raw - pool_min) / spread)) if spread else raw
            breakdown["semantic"] = ComponentResult(
                value=raw,
                status="available",
                detail={"raw": raw, "rescaled_within_pool": norm, "field_pair": semantic_field[cid]},
            )
            applicable_weights["semantic"] = weights["semantic"]
        else:
            breakdown["semantic"] = ComponentResult(value=None, status="not_available")

        # Domain
        candidate_terms = dv.entity_domain_terms(cid, entity_lookup, vocab)
        domain_val = overlap_coefficient(source_terms, candidate_terms, term_weights)
        if domain_val is None:
            breakdown["domain"] = ComponentResult(value=None, status="not_available")
        else:
            breakdown["domain"] = ComponentResult(
                value=domain_val,
                status="available",
                detail={"matched_terms": sorted(source_terms & candidate_terms)},
            )
            applicable_weights["domain"] = weights["domain"]

        # Method
        if not method_applicable:
            breakdown["method"] = ComponentResult(value=None, status="not_applicable")
        elif cid in method_sim:
            breakdown["method"] = ComponentResult(value=method_sim[cid], status="available")
            applicable_weights["method"] = weights["method"]
        else:
            breakdown["method"] = ComponentResult(value=None, status="not_available")

        # Structural
        structural_val = graph_query.structural_score(graph_pre, graph, cid)
        path_desc = graph_query.describe_path(graph_pre, graph, cid)
        breakdown["structural"] = ComponentResult(
            value=structural_val, status="available", detail={"path_description": path_desc}
        )
        applicable_weights["structural"] = weights["structural"]

        weight_sum = sum(applicable_weights.values()) or 1e-9
        renormalized = {k: v / weight_sum for k, v in applicable_weights.items()}
        final_score = sum(
            renormalized[k] * max(0.0, min(1.0, breakdown[k].value))
            for k in renormalized
            if breakdown[k].value is not None
        )
        final_score = max(0.0, min(1.0, final_score))

        results.append(
            CandidateScore(
                entity_id=cid,
                entity_type=candidate_type,
                score=final_score,
                label_absolute=_label(final_score),
                label_percentile="",  # filled in below, needs the full pool
                breakdown=breakdown,
                weights_used=renormalized,
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    n = len(results)
    for rank, r in enumerate(results):
        percentile = 1.0 - (rank / n) if n else 0.0
        r.label_percentile = "alta" if percentile >= 0.9 else "media" if percentile >= 0.6 else "baja"

    return results

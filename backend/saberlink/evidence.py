"""Stage C: evidence[] + explanation, built entirely from a CandidateScore.

Evidence snippets are re-read from entities.parquet at call time (never from
a second stored copy) so they can never drift from the source of truth.
`explanation` is a pure string template that only inserts numbers/fields
already present in the breakdown — it cannot introduce a claim that isn't
backed by the breakdown, which is what keeps it distinguishable from
"evidence" (flagged generated_text=True) rather than a source of truth
itself ("contenido generado no significa evidencia").
"""

from __future__ import annotations

import pandas as pd

from saberlink import scoring

SNIPPET_RADIUS = 200


def _snippet(text: str, radius: int = SNIPPET_RADIUS) -> str:
    text = text.strip()
    if len(text) <= 2 * radius:
        return text
    return text[:radius].rsplit(" ", 1)[0] + " […]"


def _get_field_row(entity_id: str, field_name: str, fields_index: pd.DataFrame) -> dict | None:
    row = fields_index.loc[
        (fields_index.entity_id == entity_id) & (fields_index.field_name == field_name)
    ]
    if row.empty:
        return None
    r = row.iloc[0]
    if r["field_status"] != "available":
        return None
    return {"file": r["source_file"], "id": entity_id, "field": field_name, "snippet": _snippet(str(r["field_text"]))}


def build_evidence(
    source_id: str,
    candidate: scoring.CandidateScore,
    fields_index: pd.DataFrame,
) -> list[dict]:
    evidence: list[dict] = []

    semantic = candidate.breakdown.get("semantic")
    if semantic and semantic.status == "available":
        source_field, candidate_field = semantic.detail["field_pair"]
        for eid, field_name in ((source_id, source_field), (candidate.entity_id, candidate_field)):
            row = _get_field_row(eid, field_name, fields_index)
            if row:
                evidence.append(row)

    domain = candidate.breakdown.get("domain")
    if domain and domain.status == "available" and domain.detail.get("matched_terms"):
        evidence.append(
            {
                "file": "domain_vocab.json",
                "id": candidate.entity_id,
                "field": "domain_terms",
                "snippet": ", ".join(domain.detail["matched_terms"]),
            }
        )

    method = candidate.breakdown.get("method")
    if method and method.status == "available":
        method_field = scoring.METHOD_FIELD.get(candidate.entity_type)
        if method_field:
            row = _get_field_row(candidate.entity_id, method_field, fields_index)
            if row:
                evidence.append(row)

    structural = candidate.breakdown.get("structural")
    if structural and structural.detail.get("path_description"):
        evidence.append(
            {
                "file": "graph.gpickle",
                "id": candidate.entity_id,
                "field": "graph_path",
                "snippet": structural.detail["path_description"],
            }
        )

    return evidence


def _fmt(value) -> str:
    return f"{value:.2f}" if value is not None else "n/d"


def build_explanation(source_id: str, candidate: scoring.CandidateScore) -> str:
    b = candidate.breakdown
    parts = [
        f"{candidate.entity_id} es un resultado de relevancia {candidate.label_absolute} "
        f"(score={candidate.score:.2f}) para {source_id}."
    ]

    semantic = b.get("semantic")
    if semantic and semantic.status == "available":
        sf, cf = semantic.detail["field_pair"]
        parts.append(
            f"Similitud semántica {_fmt(semantic.value)} entre el campo '{sf}' de {source_id} "
            f"y '{cf}' de {candidate.entity_id}."
        )

    domain = b.get("domain")
    if domain and domain.status == "available":
        terms = domain.detail.get("matched_terms") or []
        if terms:
            parts.append(f"Comparte los términos de dominio: {', '.join(terms)} (dominio={_fmt(domain.value)}).")
        else:
            parts.append(f"Solape de dominio bajo (dominio={_fmt(domain.value)}), sin términos compartidos.")
    elif domain and domain.status == "not_available":
        parts.append("Señal de dominio no disponible para este par (campo vacío en la fuente).")

    method = b.get("method")
    if method.status == "available":
        parts.append(f"Metodología afín (método={_fmt(method.value)}).")
    elif method.status == "not_applicable":
        parts.append("Señal de metodología no aplica: la fuente no expone un campo de metodología por diseño.")

    structural = b.get("structural")
    path_desc = structural.detail.get("path_description")
    if path_desc:
        parts.append(f"Proximidad estructural en el grafo institucional: {path_desc} (estructural={_fmt(structural.value)}).")
    else:
        parts.append(f"Sin camino corto en el grafo institucional (estructural={_fmt(structural.value)}).")

    return " ".join(parts)


def build_result(
    source_id: str,
    source_type: str,
    candidate: scoring.CandidateScore,
    fields_index: pd.DataFrame,
) -> dict:
    return {
        "source": {"id": source_id, "type": source_type},
        "target": {"id": candidate.entity_id, "type": candidate.entity_type},
        "relation": "discovered_connection",
        "relevance": {
            "score": round(candidate.score, 4),
            "label": candidate.label_absolute,
            "label_relative_to_pool": candidate.label_percentile,
            "breakdown": {k: (None if v.value is None else round(v.value, 4)) for k, v in candidate.breakdown.items()},
            "breakdown_status": {k: v.status for k, v in candidate.breakdown.items()},
        },
        "explanation": build_explanation(source_id, candidate),
        "generated_text": True,
        "evidence": build_evidence(source_id, candidate, fields_index),
    }

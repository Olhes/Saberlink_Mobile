"""Stage D: rule-based opportunity generator. Plain if/else over the
computed scores/breakdowns — never a generative model (the official rules
explicitly separate "generar oportunidades" from AI-generated, unsustained
recommendations). Each rule states which combination of signals + record
attributes must hold; every opportunity carries the evidence (candidate ids)
that justified it.
"""

from __future__ import annotations

import pandas as pd

from saberlink import config, scoring

# Projects and theses use entirely different status vocabularies (confirmed
# against the real data: projects.status in {ACTIVE, COMPLETED, FORMULATION},
# theses.status is always APPROVED — a thesis has no "ACTIVE" state, it's
# either in progress, undocumented here, or done/APPROVED). A single shared
# status set silently excluded every one of the 650 theses from ever being a
# valid antecedent for RESEARCH_CONTINUITY.
VALID_ANTECEDENT_STATUS = {
    "PRJ": {"ACTIVE", "COMPLETED"},
    "THS": {"APPROVED"},
}


def _attr(entities, entity_id: str, column: str):
    """`entities` may be the DataFrame or a prebuilt {entity_id: row_dict}
    lookup (see entity_lookup.py) — pipeline.py always passes the latter,
    since these rule checks run per-candidate across the whole ranked pool."""
    if isinstance(entities, dict):
        row = entities.get(entity_id)
        if row is None or column not in row:
            return None
        value = row[column]
    else:
        matched = entities.loc[entities.entity_id == entity_id]
        if matched.empty or column not in matched.columns:
            return None
        value = matched.iloc[0][column]
    return None if (value is None or isinstance(value, float) and pd.isna(value)) else value


def _domain_value(c: scoring.CandidateScore) -> float:
    d = c.breakdown.get("domain")
    return d.value if d and d.value is not None else 0.0


def _method_ok(c: scoring.CandidateScore, threshold: float) -> bool:
    """Whether the method signal clears the bar — treating 'not_applicable'
    (e.g. any NEED-sourced query: NEED has no methodology field, by schema
    design) as a pass, not a fail. A rule that required domain AND method
    both >= threshold would otherwise NEVER fire for a NEED source — the
    primary use case — since method is structurally never available there.
    'not_available' (data missing on a record that DOES have the field) is
    still treated as failing the check, since that's a real absence, not a
    structural non-applicability."""
    m = c.breakdown.get("method")
    if m is None or m.status == "not_applicable":
        return True
    if m.status == "available" and m.value is not None:
        return m.value >= threshold
    return False


def _above(candidates: list[scoring.CandidateScore], threshold: float) -> list[scoring.CandidateScore]:
    return [c for c in candidates if c.score >= threshold]


def rule_research_continuity(source_id, entities, ranked_by_type) -> dict | None:
    for ctype in ("PRJ", "THS"):
        for c in ranked_by_type.get(ctype, []):
            status = _attr(entities, c.entity_id, "status")
            if status not in VALID_ANTECEDENT_STATUS[ctype]:
                continue
            if _domain_value(c) >= config.DOMAIN_T and _method_ok(c, config.METHOD_T):
                related = [source_id, c.entity_id]
                group_id = _attr(entities, c.entity_id, "group_id")
                if group_id:
                    related.append(group_id)
                return {
                    "opportunity": f"Continuar la línea de trabajo de {c.entity_id} para atender {source_id}.",
                    "type": "RESEARCH_CONTINUITY",
                    "related_entities": related,
                    "reason": f"Antecedente con estado {status} y dominio afín (y método afín, cuando aplica).",
                    "priority": c.label_absolute,
                    "evidence": [{"id": c.entity_id, "score": round(c.score, 4)}],
                }
    return None


def rule_collaboration(source_id, entities, ranked_by_type) -> dict | None:
    strong_groups = _above(ranked_by_type.get("GRP", []), config.SIG_T)
    if len(strong_groups) < 2:
        return None
    g1, g2 = strong_groups[0], strong_groups[1]
    fac1, fac2 = _attr(entities, g1.entity_id, "faculty_id"), _attr(entities, g2.entity_id, "faculty_id")
    terms1 = g1.breakdown["domain"].detail.get("matched_terms", []) if g1.breakdown["domain"].value else []
    terms2 = g2.breakdown["domain"].detail.get("matched_terms", []) if g2.breakdown["domain"].value else []
    complementary = fac1 != fac2 or not (set(terms1) & set(terms2))
    if not complementary:
        return None
    return {
        "opportunity": f"Colaboración entre {g1.entity_id} y {g2.entity_id} para atender {source_id}.",
        "type": "COLLABORATION",
        "related_entities": [source_id, g1.entity_id, g2.entity_id],
        "reason": "Dos grupos con cobertura complementaria (facultades o dominios distintos).",
        "priority": g1.label_absolute,
        "evidence": [{"id": g1.entity_id, "score": round(g1.score, 4)}, {"id": g2.entity_id, "score": round(g2.score, 4)}],
    }


def rule_curricular_integration(source_id, entities, ranked_by_type) -> dict | None:
    for ctype in ("SUB", "COM", "LO"):
        for c in _above(ranked_by_type.get(ctype, []), config.DOMAIN_T):
            program_id = _attr(entities, c.entity_id, "program_id")
            if program_id and str(_attr(entities, program_id, "active")).lower() == "true":
                return {
                    "opportunity": f"Integrar {c.entity_id} al currículo para articular con {source_id}.",
                    "type": "CURRICULAR_INTEGRATION",
                    "related_entities": [source_id, c.entity_id, program_id],
                    "reason": "Componente curricular con dominio afín en un programa activo.",
                    "priority": c.label_absolute,
                    "evidence": [{"id": c.entity_id, "score": round(c.score, 4)}],
                }
    return None


def rule_capability_activation(source_id, entities, ranked_by_type) -> dict | None:
    has_strong_antecedent = any(_above(ranked_by_type.get(t, []), config.SIG_T) for t in ("PRJ", "THS"))
    if has_strong_antecedent:
        return None
    for c in _above(ranked_by_type.get("CAP", []), config.DOMAIN_T):
        status = _attr(entities, c.entity_id, "status")
        maturity = _attr(entities, c.entity_id, "maturity_level")
        try:
            maturity_ok = maturity is not None and int(maturity) >= 3
        except (TypeError, ValueError):
            maturity_ok = False
        if status == "ACTIVE" and maturity_ok:
            return {
                "opportunity": f"Activar la capacidad {c.entity_id} para atender {source_id}.",
                "type": "CAPABILITY_ACTIVATION",
                "related_entities": [source_id, c.entity_id, _attr(entities, c.entity_id, "responsible_unit")],
                "reason": "Capacidad activa de madurez suficiente, sin antecedente de proyecto/tesis fuerte.",
                "priority": c.label_absolute,
                "evidence": [{"id": c.entity_id, "score": round(c.score, 4)}],
            }
    return None


def rule_new_research(source_id, entities, ranked_by_type) -> dict | None:
    has_strong_antecedent = any(_above(ranked_by_type.get(t, []), config.SIG_T) for t in ("PRJ", "THS"))
    if has_strong_antecedent:
        return None
    for ctype in ("INV", "GRP"):
        strong = _above(ranked_by_type.get(ctype, []), config.SIG_T)
        if strong:
            c = strong[0]
            return {
                "opportunity": f"Abrir una nueva línea de investigación con {c.entity_id} para {source_id}.",
                "type": "NEW_RESEARCH",
                "related_entities": [source_id, c.entity_id],
                "reason": "No hay antecedente de proyecto/tesis, pero sí capacidad investigativa afín.",
                "priority": c.label_absolute,
                "evidence": [{"id": c.entity_id, "score": round(c.score, 4)}],
            }
    return None


def rule_knowledge_transfer(source_id, entities, ranked_by_type, source_faculty_id) -> dict | None:
    for ctype in ("PRJ", "GRP"):
        for c in _above(ranked_by_type.get(ctype, []), config.DOMAIN_T):
            candidate_faculty = _attr(entities, c.entity_id, "faculty_id")
            if candidate_faculty and source_faculty_id and candidate_faculty != source_faculty_id:
                return {
                    "opportunity": f"Transferir conocimiento de {c.entity_id} (otra facultad) hacia {source_id}.",
                    "type": "KNOWLEDGE_TRANSFER",
                    "related_entities": [source_id, c.entity_id, candidate_faculty],
                    "reason": "Antecedente relevante originado en una facultad distinta a la de la necesidad.",
                    "priority": c.label_absolute,
                    "evidence": [{"id": c.entity_id, "score": round(c.score, 4)}],
                }
    return None


def rule_thesis_opportunity(source_id, entities, ranked_by_type) -> dict | None:
    has_project_antecedent = any(c.score >= config.SIG_T for c in ranked_by_type.get("PRJ", []))
    if has_project_antecedent:
        return None
    for c in _above(ranked_by_type.get("THS", []), config.DOMAIN_T):
        program_id = _attr(entities, c.entity_id, "program_id")
        if program_id and str(_attr(entities, program_id, "active")).lower() == "true":
            return {
                "opportunity": f"Proponer un trabajo de grado a partir de {c.entity_id} para {source_id}.",
                "type": "THESIS_OPPORTUNITY",
                "related_entities": [source_id, c.entity_id, program_id],
                "reason": "Tesis afín sin antecedente de proyecto fuerte; programa activo.",
                "priority": c.label_absolute,
                "evidence": [{"id": c.entity_id, "score": round(c.score, 4)}],
            }
    return None


RULES = [
    rule_research_continuity,
    rule_collaboration,
    rule_curricular_integration,
    rule_capability_activation,
    rule_new_research,
    rule_thesis_opportunity,
]


def generate(
    source_id: str,
    entities: pd.DataFrame,
    ranked_by_type: dict[str, list[scoring.CandidateScore]],
    source_faculty_id: str | None = None,
) -> list[dict]:
    opportunities = []
    for rule in RULES:
        result = rule(source_id, entities, ranked_by_type)
        if result:
            opportunities.append(result)
    kt = rule_knowledge_transfer(source_id, entities, ranked_by_type, source_faculty_id)
    if kt:
        opportunities.append(kt)

    priority_rank = {"alta": 0, "media": 1, "baja": 2}
    opportunities.sort(key=lambda o: (priority_rank.get(o["priority"], 3), -o["evidence"][0]["score"]))
    return opportunities

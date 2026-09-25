"""Small self-contained dataset used when the optional processed index is absent."""

from __future__ import annotations

from pathlib import Path


NODES = [
    {"id": "NEED-DEMO", "label": "IA en educacion", "type": "NEED", "type_label": "Necesidad", "color": "#d5a94d", "role": "source"},
    {"id": "PRJ-DEMO", "label": "Aprendizaje adaptativo", "type": "PRJ", "type_label": "Proyecto", "color": "#8fbe9d", "role": "result"},
    {"id": "INV-DEMO", "label": "Analitica del aprendizaje", "type": "INV", "type_label": "Investigador", "color": "#db8662", "role": "result"},
    {"id": "GRP-DEMO", "label": "Tecnologia educativa", "type": "GRP", "type_label": "Grupo de investigacion", "color": "#9ca3af", "role": "result"},
]


def _result(entity_id: str, score: float, label: str, explanation: str, evidence: list[dict]) -> dict:
    return {
        "target": {"id": entity_id, "type": next(node["type"] for node in NODES if node["id"] == entity_id)},
        "relevance": {"score": score, "label": label, "breakdown": {}, "breakdown_status": "demo"},
        "explanation": explanation,
        "evidence": evidence,
    }


def query(source_id: str = "NEED-DEMO", source_label: str | None = None) -> dict:
    source = {"id": source_id, "type": "NEED", "official": False}
    results = [
        _result("PRJ-DEMO", 0.91, "alta", "El proyecto aborda personalizacion del aprendizaje mediante inteligencia artificial.", [{"file": "demo_projects.csv", "id": "PRJ-DEMO", "field": "problem_statement", "snippet": "Sistemas adaptativos para mejorar el aprendizaje universitario."}]),
        _result("INV-DEMO", 0.76, "media", "La experiencia del investigador conecta analitica educativa y evaluacion.", [{"file": "demo_researchers.csv", "id": "INV-DEMO", "field": "research_interests", "snippet": "Inteligencia artificial, analitica del aprendizaje y evaluacion."}]),
        _result("GRP-DEMO", 0.62, "media", "El grupo aporta capacidades cercanas para una posible colaboracion.", []),
    ]
    nodes = [dict(node) for node in NODES]
    nodes[0]["id"] = source_id
    if source_label:
        nodes[0]["label"] = source_label[:60]
    return {
        "source": source,
        "meta": {"elapsed_seconds": 0.02, "total_candidates_scored": len(results), "demo_mode": True},
        "results": results,
        "opportunities": [{"type": "COLABORACION", "priority": "alta", "opportunity": "Comparar el proyecto con tu pregunta y buscar una colaboracion.", "reason": "Comparten IA, educacion y analitica.", "related_entities": ["PRJ-DEMO", "INV-DEMO"]}],
        "graph": {"source_id": source_id, "nodes": nodes, "edges": [{"source": source_id, "target": result["target"]["id"], "kind": "discovery", "score": result["relevance"]["score"], "band": result["relevance"]["label"], "color": "#d5a94d", "label": f"{result['relevance']['score']:.2f}", "tooltip": result["explanation"]} for result in results]},
    }


def pdf_query(filename: str, extracted_text: str = "") -> dict:
    result = query(source_id="PDF-DEMO", source_label=Path(filename).stem)
    result["source"]["type"] = "PDF"
    result["source"]["official"] = False
    result["graph"]["nodes"][0].update({"type": "PDF", "type_label": "Documento PDF"})
    result["meta"]["pdf_filename"] = filename
    if extracted_text.strip():
        result["results"][0]["evidence"].append({
            "file": filename,
            "id": "PDF-DEMO",
            "field": "extracted_text",
            "snippet": extracted_text.strip().replace("\n", " ")[:500],
        })
        result["meta"]["pdf_text_extracted"] = True
    else:
        result["meta"]["pdf_text_extracted"] = False
    return result


def entities() -> list[dict]:
    return [{"id": node["id"], "type": node["type"], "type_label": node["type_label"], "name": node["label"]} for node in NODES]

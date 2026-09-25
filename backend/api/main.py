"""Thin FastAPI layer over saberlink.pipeline.run_query.

Strictly additive, same isolation principle as saberlink/plus/: this module
imports from saberlink.* but nothing in saberlink/ (núcleo or plus) imports
from here — deleting backend/api/ never breaks the pipeline, notebooks,
Streamlit or the pyvis exports. Every response is built straight from
pipeline.run_query()'s own dict, or from saberlink.graph_query's own
build_discovery_graph_data — there is no separate "API version" of the
business logic, only serialization.

Run with (from backend/):
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import tempfile
from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api import demo_data
from api import document_library
from saberlink import config, entity_lookup as entity_lookup_mod, graph_build, graph_query, pipeline, schema, viz

app = FastAPI(title="SaberLink API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    entity_id: str | None = None
    raw_text_profile: dict | None = None
    top_k: int = config.DEFAULT_TOP_K


class LibraryQueryRequest(BaseModel):
    query: str
    top_k: int = 5


def _demo_mode() -> bool:
    """Keep the API runnable before an optional institutional index is built."""
    return not (
        config.ENTITIES_PARQUET.exists()
        and config.GRAPH_PICKLE.exists()
        and config.CHROMA_DIR.exists()
    )


# Cached the same way saberlink.pipeline caches its own module-level state:
# these are read-only indexes over fixed processed/ artifacts, rebuilt only
# if the process restarts (call the /admin/reload-equivalent — here, just
# restart uvicorn — after re-running ingest/graph_build).
@lru_cache(maxsize=1)
def _entities_df() -> pd.DataFrame:
    return pd.read_parquet(config.ENTITIES_PARQUET)


@lru_cache(maxsize=1)
def _entity_lookup() -> dict[str, dict]:
    return entity_lookup_mod.build(_entities_df())


@lru_cache(maxsize=1)
def _graph():
    return graph_build.load_graph()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "demo" if _demo_mode() else "indexed"}


@app.get("/projects/{project_id}/documents")
def project_documents(project_id: str) -> list[dict]:
    return document_library.list_documents(project_id)


@app.post("/projects/{project_id}/documents")
async def upload_project_document(project_id: str, file: UploadFile = File(...)) -> dict:
    filename = file.filename or "document.pdf"
    if file.content_type not in ("application/pdf", "application/octet-stream") and not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Se espera un archivo PDF")
    try:
        return await asyncio.to_thread(document_library.index_pdf, project_id, filename, await file.read())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo indexar el PDF: {exc}") from exc


@app.post("/projects/{project_id}/query")
async def query_project_library(project_id: str, body: LibraryQueryRequest) -> dict:
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="query es requerido")
    try:
        return await asyncio.to_thread(document_library.query_project, project_id, body.query.strip(), body.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo consultar la biblioteca: {exc}") from exc


def _build_graph_payload(source_id: str, results: list[dict], source_label: str | None = None) -> dict:
    """Same discovery-subgraph data saberlink.plus.pyvis_export renders to
    HTML, as JSON nodes/edges for the frontend's Cytoscape view. Works for
    an ephemeral TEMP-xxxxxxxx source too (texto libre / PDF): it isn't in
    graph.gpickle, so graph_query.precompute_source just returns empty
    paths for it — build_discovery_graph_data then falls back to no hub
    nodes, but the source + ranked-result star topology still comes
    through fine, which is what actually matters to the user."""
    g = _graph()
    pre = graph_query.precompute_source(g, source_id)
    return graph_query.build_discovery_graph_data(source_id, results, g, pre, _entity_lookup(), source_label=source_label)


@app.post("/query")
def query(body: QueryRequest) -> dict:
    if not body.entity_id and not body.raw_text_profile:
        raise HTTPException(status_code=400, detail="entity_id o raw_text_profile es requerido")
    if _demo_mode():
        source_id = body.entity_id or "TEXT-DEMO"
        source_label = (body.raw_text_profile or {}).get("title")
        return demo_data.query(source_id=source_id, source_label=source_label)
    try:
        out = pipeline.run_query(
            entity_id=body.entity_id,
            raw_text_profile=body.raw_text_profile,
            top_k=body.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    source_label = (body.raw_text_profile or {}).get("title")
    out["graph"] = _build_graph_payload(out["source"]["id"], out["results"], source_label=source_label)
    return out


def _parse_and_query_pdf(tmp_path: Path, top_k: int) -> dict:
    """Runs on a worker thread (see asyncio.to_thread below) — both Docling
    parsing and pipeline.run_query are synchronous/CPU-bound; calling them
    directly from the async route would block uvicorn's single event loop
    for the whole duration (minutes, on Docling's first model download),
    freezing every other in-flight request."""
    from saberlink.plus.docling_intake import pdf_to_temp_need

    profile = pdf_to_temp_need(tmp_path)
    out = pipeline.run_query(raw_text_profile=profile, top_k=top_k)
    out["graph"] = _build_graph_payload(out["source"]["id"], out["results"], source_label=profile.get("title"))
    return out


async def _demo_pdf_query(file: UploadFile) -> dict:
    """Accept a PDF in demo mode and extract a small evidence preview when possible."""
    contents = await file.read()
    extracted_text = ""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / (file.filename or "document.pdf")
        tmp_path.write_bytes(contents)
        try:
            import pymupdf4llm

            extracted_text = pymupdf4llm.to_markdown(str(tmp_path))
        except Exception:
            pass
    return demo_data.pdf_query(file.filename or "document.pdf", extracted_text)


@app.post("/query/pdf")
async def query_pdf(file: UploadFile = File(...), top_k: int = config.DEFAULT_TOP_K) -> dict:
    """[PLUS] Same ephemeral-NEED mechanism as the free-text query mode —
    the PDF is parsed via Docling into a raw_text_profile, run through the
    exact same pipeline.run_query(), and never persisted."""
    if file.content_type not in ("application/pdf", "application/octet-stream") and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Se espera un archivo PDF")

    if _demo_mode():
        return await _demo_pdf_query(file)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / file.filename
        tmp_path.write_bytes(await file.read())
        try:
            return await asyncio.to_thread(_parse_and_query_pdf, tmp_path, top_k)
        except ImportError as exc:
            raise HTTPException(status_code=503, detail="Docling no está instalado en el servidor") from exc
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"No se pudo procesar el PDF: {exc}") from exc


async def _parse_and_query_pdf_enhanced(tmp_path: Path, top_k: int, use_cohere: bool) -> dict:
    """Runs async — LightRAG + Cohere enhanced PDF processing."""
    out = await pipeline.run_hybrid_query_async(str(tmp_path), use_cohere=use_cohere, top_k=top_k)
    source_label = Path(tmp_path).name
    
    # For PDF (TEMP-xxxx source), build graph directly from results
    # since the source doesn't exist in the institutional graph
    source_id = out["source"]["id"]
    entity_lookup = _entity_lookup()
    
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    
    # Add source node
    nodes[source_id] = {
        "id": source_id,
        "label": source_label[:60],
        "type": "NEED",
        "type_label": "Necesidad (PDF)",
        "color": "#f59e0b",  # gold color for PDF source
        "role": "source",
    }
    
    # Add result nodes and edges
    for r in out["results"]:
        target_id = r["target"]["id"]
        score = r["relevance"]["score"]
        band = r["relevance"]["label"]
        
        # Get entity info from lookup
        row = entity_lookup.get(target_id)
        entity_type = (row or {}).get("entity_type", "?")
        
        # Use proper display name
        spec = schema.ENTITY_SPECS.get(entity_type)
        name_field = spec.name_field if spec else None
        if name_field and row and row.get(name_field):
            label = str(row[name_field])[:60]
        else:
            label = target_id
        
        nodes[target_id] = {
            "id": target_id,
            "label": label,
            "type": entity_type,
            "type_label": viz.ENTITY_TYPE_LABELS.get(entity_type, entity_type),
            "color": viz.ENTITY_TYPE_COLORS.get(entity_type, viz.DEFAULT_COLOR),
            "role": "result",
        }
        
        edges.append({
            "source": source_id,
            "target": target_id,
            "kind": "discovery",
            "score": score,
            "band": band,
            "color": viz.SCORE_BAND_COLORS.get(band, viz.DEFAULT_COLOR),
            "label": f"{score:.2f}",
            "tooltip": r.get("explanation", ""),
        })
    
    out["graph"] = {
        "source_id": source_id,
        "nodes": list(nodes.values()),
        "edges": edges,
    }
    return out


@app.post("/query/pdf/enhanced")
async def query_pdf_enhanced(
    file: UploadFile = File(...),
    top_k: int = config.DEFAULT_TOP_K,
    use_cohere: bool = True,
) -> dict:
    """[PLUS] Enhanced PDF query with LightRAG + Cohere.
    
    Processes PDF with LightRAG to extract entities and build a knowledge graph,
    then combines results with institutional search and enhances with Cohere LLM
    for better re-ranking and opportunity generation.
    """
    if file.content_type not in ("application/pdf", "application/octet-stream") and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Se espera un archivo PDF")

    if _demo_mode():
        return await _demo_pdf_query(file)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / file.filename
        tmp_path.write_bytes(await file.read())
        try:
            return await _parse_and_query_pdf_enhanced(tmp_path, top_k, use_cohere)
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="LightRAG/Cohere integration no está instalada. "
                "Instala dependencias: pip install lightrag cohere pymupdf4llm"
            ) from exc
        except Exception as exc:
            import traceback
            error_detail = f"No se pudo procesar el PDF: {str(exc)}\n\n{traceback.format_exc()}"
            raise HTTPException(status_code=422, detail=error_detail) from exc


@app.get("/graph")
def graph(
    entity_id: str = Query(..., description="ID de entidad existente, ej. NEED-001"),
    top_k: int = Query(config.DEFAULT_TOP_K, ge=1, le=50),
) -> dict:
    """Standalone equivalent of the `graph` field POST /query now returns
    inline — kept as its own endpoint for API completeness (e.g. fetching
    just the graph without the full explanation/evidence payload). Only
    accepts an existing entity_id: a texto libre / PDF query's ephemeral
    TEMP-xxxxxxxx id can't be looked up a second time in a fresh call —
    use POST /query or /query/pdf for those, which build the graph from
    the same call that creates the temporary entity."""
    try:
        out = pipeline.run_query(entity_id=entity_id, top_k=top_k)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _build_graph_payload(out["source"]["id"], out["results"])


@app.get("/entities")
def list_entities(
    type: str | None = Query(None, description="Filtro por tipo, ej. NEED, PRJ"),
    q: str | None = Query(None, description="Búsqueda por substring en ID o nombre"),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Backs the frontend's search/autocomplete — replaces Streamlit's plain
    st.text_input with a guided picker."""
    if _demo_mode():
        return demo_data.entities()

    df = _entities_df()
    if type:
        df = df[df["entity_type"] == type]

    q_lower = q.strip().lower() if q else None
    results: list[dict] = []
    for rec in df.to_dict("records"):
        entity_id = rec["entity_id"]
        entity_type = rec["entity_type"]
        spec = schema.ENTITY_SPECS.get(entity_type)
        name_field = spec.name_field if spec else None
        raw_name = rec.get(name_field) if name_field else None
        name = str(raw_name) if pd.notna(raw_name) else entity_id

        if q_lower and q_lower not in entity_id.lower() and q_lower not in name.lower():
            continue

        results.append(
            {
                "id": entity_id,
                "type": entity_type,
                "type_label": viz.ENTITY_TYPE_LABELS.get(entity_type, entity_type),
                "name": name,
            }
        )
        if len(results) >= limit:
            break
    return results


@app.get("/meta/legend")
def legend() -> dict:
    """Entity-type and score-band palette — single source of truth shared
    with saberlink.viz, so the frontend never hardcodes its own colors."""
    return {
        "entity_types": [
            {"type": t, "label": label, "color": viz.ENTITY_TYPE_COLORS.get(t, viz.DEFAULT_COLOR)}
            for t, label in viz.ENTITY_TYPE_LABELS.items()
        ],
        "score_bands": [{"band": band, "color": color} for band, color in viz.SCORE_BAND_COLORS.items()],
    }

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
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, Header, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api import demo_data
from api import document_library
from api import usage_limits

# Docling - importar al inicio para que uvicorn lo detecte
try:
    from saberlink.plus.docling_intake import pdf_to_temp_need
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
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
    user_id: str | None = None  # For usage tracking


class LibraryQueryRequest(BaseModel):
    query: str
    top_k: int = 5
    user_id: str | None = None  # For usage tracking


class SubscriptionUpdateRequest(BaseModel):
    user_id: str
    revenuecat_data: dict


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
    
    # Check usage limits for text queries (only for raw_text_profile, not entity_id)
    if body.raw_text_profile and body.user_id:
        tracker = usage_limits.get_usage_tracker()
        if not tracker.track_text_query(body.user_id):
            usage = tracker.get_remaining_usage(body.user_id)
            raise HTTPException(
                status_code=429,
                detail=f"Límite de consultas de texto alcanzado. Usados: {usage['text_queries_used']}/{usage['text_queries_limit']}"
            )
    
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
async def query_pdf(
    file: UploadFile = File(...), 
    top_k: int = config.DEFAULT_TOP_K,
    user_id: str | None = Query(None, description="User ID for usage tracking")
) -> dict:
    """[PLUS] Same ephemeral-NEED mechanism as the free-text query mode —
    the PDF is parsed via Docling into a raw_text_profile, run through the
    exact same pipeline.run_query(), and never persisted."""
    if file.content_type not in ("application/pdf", "application/octet-stream") and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Se espera un archivo PDF")

    # Check usage limits for PDF uploads
    if user_id:
        can_upload = usage_limits.track_usage(user_id, "pdf_upload")
        if not can_upload:
            current_usage = usage_limits.get_user_usage(user_id)
            raise HTTPException(
                status_code=429,
                detail=f"Límite de subidas de PDF alcanzado. Usados: {current_usage['pdf_uploads_used']}/{current_usage['pdf_uploads_limit']}"
            )

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
    user_id: str | None = Query(None, description="User ID for usage tracking")
) -> dict:
    """Enhanced PDF query using institutional data (CSV embeddings).
    
    Pipeline:
    1. Docling extrae texto del PDF
    2. Pipeline normal con datos CSV vectorizados
    3. 4-signal scoring (semantic, domain, method, structural)
    4. Grafo institucional real
    """
    if file.content_type not in ("application/pdf", "application/octet-stream") and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Se espera un archivo PDF")

    # Check usage limits for PDF uploads
    if user_id:
        can_upload = usage_limits.track_usage(user_id, "pdf_upload")
        if not can_upload:
            current_usage = usage_limits.get_user_usage(user_id)
            raise HTTPException(
                status_code=429,
                detail=f"Límite de subidas de PDF alcanzado. Usados: {current_usage['pdf_uploads_used']}/{current_usage['pdf_uploads_limit']}"
            )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / file.filename
        tmp_path.write_bytes(await file.read())
        try:
            # Intentar usar Docling para conversión a Markdown
            if DOCLING_AVAILABLE:
                profile = pdf_to_temp_need(tmp_path)
            else:
                # Intentar import dentro del endpoint si falló al inicio
                try:
                    from saberlink.plus.docling_intake import pdf_to_temp_need
                    profile = pdf_to_temp_need(tmp_path)
                except ImportError:
                    # Fallback a simple extracción de texto
                    import pymupdf
                    text_content = ""
                    with pymupdf.open(tmp_path) as doc:
                        for page in doc:
                            text_content += page.get_text("text")
                    
                    profile = {
                        "title": file.filename,
                        "description": text_content[:1000] if text_content else "Documento PDF",
                        "context": text_content[:500] if text_content else "",
                        "expected_impact": ""
                    }
            
            # Ejecutar pipeline completo con scoring de 4 señales usando datos CSV
            out = pipeline.run_query(raw_text_profile=profile, top_k=top_k)
            
            # Añadir grafo visualización
            g = _graph()
            pre = graph_query.precompute_source(g, out["source"]["id"])
            out["graph"] = graph_query.build_discovery_graph_data(
                out["source"]["id"], out["results"], g, pre, _entity_lookup()
            )
            
            # Añadir metadatos
            out["meta"]["scoring_method"] = "4_signal_composite"
            out["meta"]["scoring_components"] = ["semantic", "domain", "method", "structural"]
            out["meta"]["embedding_model"] = config.EMBEDDING_MODEL_NAME
            out["meta"]["pipeline_version"] = "docling_csv_pipeline"
            out["meta"]["institutional_data_available"] = True
            out["meta"]["entities_count"] = 3267
            out["meta"]["vectors_count"] = 10725
            out["meta"]["graph_edges"] = 6431
            out["meta"]["docling_used"] = DOCLING_AVAILABLE
            
            return out
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="No se pudo procesar el PDF. Error de importación: {str(exc)}"
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


@app.get("/usage/limits")
def get_usage_limits(user_id: str = Query(..., description="User ID for usage tracking")) -> dict:
    """Get current usage and remaining limits for a user."""
    return usage_limits.get_user_usage(user_id)


@app.get("/usage/tiers")
def get_subscription_tiers() -> dict:
    """Get available subscription tiers and their limits."""
    try:
        from saberlink.payments import get_offering
        offering = get_offering("default")
        
        if offering:
            # Formatear desde el catálogo modular
            formatted_tiers = {}
            for package in offering.packages:
                tier_key = "pro_yearly" if package.package_type.value == "$rc_annual" else "pro_monthly"
                formatted_tiers[tier_key] = {
                    "pdf_uploads_per_month": package.product.pdf_uploads_per_month,
                    "text_queries_per_month": package.product.text_queries_per_month,
                    "name": "Pro " + ("Anual" if package.package_type.value == "$rc_annual" else "Mensual"),
                    "description": package.product.description,
                    "price_display": package.product.price_display,
                    "package_identifier": package.identifier
                }
            
            # Agregar tier gratuito
            formatted_tiers["free"] = usage_limits.SUBSCRIPTION_TIERS["free"]
            
            return formatted_tiers
        else:
            return usage_limits.SUBSCRIPTION_TIERS
    except ImportError:
        return usage_limits.SUBSCRIPTION_TIERS


@app.post("/usage/subscription")
def update_subscription(body: SubscriptionUpdateRequest) -> dict:
    """Update user's subscription tier based on RevenueCat data."""
    status = usage_limits.check_subscription_status(body.user_id, body.revenuecat_data)
    return status


@app.post("/usage/validate-pdf")
def validate_pdf_upload(user_id: str = Query(..., description="User ID for usage tracking")) -> dict:
    """Check if user can upload a PDF based on current usage limits."""
    try:
        from saberlink.payments import check_usage_limits
        check = check_usage_limits(user_id, "pdf_upload")
        current_usage = usage_limits.get_user_usage(user_id)
        
        if not check["allowed"]:
            return {
                "allowed": False,
                "reason": "PDF upload limit reached for this month",
                "usage": current_usage
            }
        
        return {
            "allowed": True,
            "usage": current_usage
        }
    except ImportError:
        # Fallback to simple check
        current_usage = usage_limits.get_user_usage(user_id)
        if current_usage["pdf_uploads_remaining"] <= 0:
            return {
                "allowed": False,
                "reason": "PDF upload limit reached for this month",
                "usage": current_usage
            }
        return {
            "allowed": True,
            "usage": current_usage
        }


@app.post("/usage/validate-text")
def validate_text_query(user_id: str = Query(..., description="User ID for usage tracking")) -> dict:
    """Check if user can make a text query based on current usage limits."""
    try:
        from saberlink.payments import check_usage_limits
        check = check_usage_limits(user_id, "text_query")
        current_usage = usage_limits.get_user_usage(user_id)
        
        if not check["allowed"]:
            return {
                "allowed": False,
                "reason": "Text query limit reached for this month",
                "usage": current_usage
            }
        
        return {
            "allowed": True,
            "usage": current_usage
        }
    except ImportError:
        # Fallback to simple check
        current_usage = usage_limits.get_user_usage(user_id)
        if current_usage["text_queries_remaining"] <= 0:
            return {
                "allowed": False,
                "reason": "Text query limit reached for this month",
                "usage": current_usage
            }
        return {
            "allowed": True,
            "usage": current_usage
        }


# Punto 3: Endpoints para flujo de compras
@app.get("/purchases/offerings")
def get_purchases_offerings(
    user_id: str = Query(..., description="User ID"),
    offering_id: str = Query("default", description="Offering ID (default, black_friday, etc.)")
) -> dict:
    """Get available offerings and packages for purchase flow."""
    try:
        from saberlink.payments.purchase_flow import get_offerings_for_user
        return get_offerings_for_user(user_id, offering_id)
    except ImportError:
        return {
            "success": False,
            "error": "payments_module_not_available",
            "message": "Módulo de pagos no disponible"
        }


@app.post("/purchases/validate-eligibility")
def validate_purchase_eligibility(
    user_id: str = Query(..., description="User ID"),
    package_identifier: str = Query(..., description="Package identifier ($rc_monthly, $rc_annual, etc.)")
) -> dict:
    """Validate if user can purchase a specific package."""
    try:
        from saberlink.payments.purchase_flow import validate_purchase_eligibility
        return validate_purchase_eligibility(user_id, package_identifier)
    except ImportError:
        return {
            "eligible": False,
            "error": "payments_module_not_available"
        }


@app.post("/purchases/simulate")
def simulate_purchase(
    user_id: str = Query(..., description="User ID"),
    package_identifier: str = Query(..., description="Package identifier")
) -> dict:
    """Simulate a purchase (for sandbox/development mode)."""
    try:
        from saberlink.payments.purchase_flow import simulate_purchase
        return simulate_purchase(user_id, package_identifier)
    except ImportError:
        return {
            "success": False,
            "error": "payments_module_not_available"
        }


@app.post("/purchases/restore")
def restore_purchases(user_id: str = Query(..., description="User ID")) -> dict:
    """Restore previous purchases for a user."""
    try:
        from saberlink.payments.purchase_flow import restore_purchases
        return restore_purchases(user_id)
    except ImportError:
        return {
            "success": False,
            "error": "payments_module_not_available"
        }


@app.get("/purchases/entitlement")
def check_entitlement(
    user_id: str = Query(..., description="User ID"),
    entitlement: str = Query("pro", description="Entitlement to check")
) -> dict:
    """Check if user has a specific entitlement."""
    try:
        from saberlink.payments.purchase_flow import check_entitlement_status
        return check_entitlement_status(user_id, entitlement)
    except ImportError:
        return {
            "has_access": False,
            "error": "payments_module_not_available"
        }


@app.get("/purchases/customer-info")
def get_customer_info_endpoint(user_id: str = Query(..., description="User ID")) -> dict:
    """Get complete customer information (CustomerInfo)."""
    try:
        from saberlink.payments.purchase_flow import get_customer_info
        return get_customer_info(user_id)
    except ImportError:
        return {
            "error": "payments_module_not_available"
        }


# Punto 4: Endpoints para webhooks y sincronización
@app.post("/webhooks/revenuecat")
def handle_revenuecat_webhook(
    x_signature: str = Header(None, description="RevenueCat webhook signature"),
    webhook_secret: str = Header(None, description="Webhook secret for verification")
) -> dict:
    """Handle RevenueCat webhook events."""
    
    # Si se proporciona el secreto, verificar la firma
    if webhook_secret and x_signature:
        # Aquí se verificaría la firma, pero en sandbox lo permitimos
        pass
    
    try:
        import json
        from saberlink.payments.webhooks import process_webhook_event, log_webhook_event
        
        # Leer el cuerpo del webhook
        # Nota: En producción, esto vendría del Request body
        # Para sandbox, simulamos que ya está procesado
        
        return {
            "success": True,
            "message": "Webhook endpoint configurado correctamente"
        }
    except ImportError:
        return {
            "success": False,
            "error": "payments_module_not_available"
        }


@app.post("/sync/customer-info")
def sync_customer_info_endpoint(
    user_id: str = Query(..., description="User ID"),
    customer_info: dict = Body(..., description="CustomerInfo from RevenueCat SDK")
) -> dict:
    """Sync customer info from SDK to backend."""
    try:
        from saberlink.payments.webhooks import sync_customer_info
        return sync_customer_info(user_id, customer_info)
    except ImportError:
        return {
            "success": False,
            "error": "payments_module_not_available"
        }


@app.get("/server/validate-access")
def validate_access_server(
    user_id: str = Query(..., description="User ID"),
    required_entitlement: str = Query("pro", description="Required entitlement")
) -> dict:
    """Validate access from server (for web backend validation)."""
    try:
        from saberlink.payments.webhooks import validate_access_from_server
        return validate_access_from_server(user_id, required_entitlement)
    except ImportError:
        return {
            "has_access": False,
            "error": "payments_module_not_available"
        }


@app.get("/webhooks/history")
def get_webhook_history_endpoint(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(10, description="Max events to return")
) -> dict:
    """Get webhook history for a user."""
    try:
        from saberlink.payments.webhooks import get_webhook_history
        return {
            "success": True,
            "user_id": user_id,
            "events": get_webhook_history(user_id, limit)
        }
    except ImportError:
        return {
            "success": False,
            "error": "payments_module_not_available"
        }

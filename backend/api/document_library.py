"""Persistent, local PDF library for user projects.

PDF files and chunk metadata live under backend/processed/user_library.
Embeddings are generated locally with sentence-transformers and stored in a
project-scoped Chroma collection. Cohere is deliberately optional.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from pathlib import Path

from saberlink import config, embeddings

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 180


def _connect() -> sqlite3.Connection:
    config.USER_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(config.USER_LIBRARY_DB)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            path TEXT NOT NULL,
            pages INTEGER NOT NULL,
            chunks INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.commit()
    return connection


def _safe_project(project_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", project_id)[:60] or "default"


def _collection(project_id: str):
    import chromadb
    from chromadb.config import Settings

    path = config.USER_LIBRARY_CHROMA_DIR / _safe_project(project_id)
    path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(name="pdf_chunks", metadata={"hnsw:space": "cosine"})


def _chunks(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    output = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + CHUNK_SIZE)
        output.append(cleaned[start:end])
        if end == len(cleaned):
            break
        start = end - CHUNK_OVERLAP
    return output


def _extract_pages(path: Path) -> list[tuple[int, str]]:
    import fitz

    with fitz.open(path) as document:
        return [(index + 1, page.get_text("text")) for index, page in enumerate(document)]


def index_pdf(project_id: str, filename: str, content: bytes) -> dict:
    document_id = f"DOC-{uuid.uuid4().hex[:12]}"
    project_dir = config.USER_LIBRARY_DIR / _safe_project(project_id) / "documents"
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / f"{document_id}.pdf"
    path.write_bytes(content)

    pages = _extract_pages(path)
    rows = []
    for page_number, text in pages:
        for chunk_index, text_chunk in enumerate(_chunks(text)):
            rows.append((page_number, chunk_index, text_chunk))
    if not rows:
        path.unlink(missing_ok=True)
        raise ValueError("El PDF no contiene texto extraíble. Prueba con un PDF que tenga texto seleccionable.")

    collection = _collection(project_id)
    vectors = embeddings.embed_texts([row[2] for row in rows])
    collection.upsert(
        ids=[f"{document_id}:{page}:{chunk}" for page, chunk, _ in rows],
        embeddings=vectors.tolist(),
        documents=[text for _, _, text in rows],
        metadatas=[{"document_id": document_id, "filename": filename, "page": page, "chunk": chunk} for page, chunk, _ in rows],
    )
    connection = _connect()
    connection.execute("INSERT INTO documents (id, project_id, filename, path, pages, chunks) VALUES (?, ?, ?, ?, ?, ?)", (document_id, project_id, filename, str(path), len(pages), len(rows)))
    connection.commit()
    connection.close()
    return {"id": document_id, "project_id": project_id, "filename": filename, "pages": len(pages), "chunks": len(rows), "status": "indexed"}


def list_documents(project_id: str) -> list[dict]:
    connection = _connect()
    rows = connection.execute("SELECT id, project_id, filename, pages, chunks, created_at FROM documents WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def query_project(project_id: str, query: str, top_k: int = 5) -> dict:
    documents = list_documents(project_id)
    if not documents:
        raise ValueError("Este proyecto todavía no tiene PDFs indexados")
    collection = _collection(project_id)
    if collection.count() == 0:
        raise ValueError("Este proyecto todavía no tiene fragmentos vectorizados")
    query_vector = embeddings.embed_one(query)
    result = collection.query(query_embeddings=[query_vector.tolist()], n_results=min(max(top_k * 3, 5), collection.count()), include=["documents", "metadatas", "distances"])
    matches = []
    for text, metadata, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
        matches.append({"filename": metadata["filename"], "document_id": metadata["document_id"], "page": metadata["page"], "snippet": text, "score": round(max(0.0, 1.0 - distance), 4)})
    grouped: dict[str, dict] = {}
    for match in matches:
        current = grouped.get(match["document_id"])
        if current is None:
            grouped[match["document_id"]] = {"document_id": match["document_id"], "filename": match["filename"], "score": match["score"], "evidence": [match]}
        elif len(current["evidence"]) < 3:
            current["evidence"].append(match)
            current["score"] = max(current["score"], match["score"])
    ranked = sorted(grouped.values(), key=lambda item: item["score"], reverse=True)[:top_k]
    nodes = [{"id": "QUERY", "label": query[:60], "type": "QUERY", "type_label": "Consulta", "color": "#d5a94d", "role": "source"}]
    edges = []
    for item in ranked:
        nodes.append({"id": item["document_id"], "label": item["filename"][:45], "type": "PDF", "type_label": "Documento PDF", "color": "#8fbe9d", "role": "result"})
        edges.append({"source": "QUERY", "target": item["document_id"], "kind": "semantic", "score": item["score"], "label": f"{item['score']:.2f}", "band": "alta" if item["score"] >= 0.7 else "media", "color": "#d5a94d", "tooltip": "Coincidencia semántica por fragmentos"})
    return {"source": {"id": "QUERY", "type": "QUERY", "official": False}, "meta": {"mode": "pdf_library", "project_id": project_id, "documents_searched": len(documents), "chunks_searched": collection.count(), "elapsed_seconds": 0, "demo_mode": False}, "results": [{"target": {"id": item["document_id"], "type": "PDF", "filename": item["filename"]}, "relevance": {"score": item["score"], "label": "alta" if item["score"] >= 0.7 else "media", "breakdown_status": "semantic_embedding"}, "explanation": f"Coincide semánticamente con fragmentos de {item['filename']}.", "evidence": [{"file": item["filename"], "id": item["document_id"], "field": f"page_{evidence['page']}", "snippet": evidence["snippet"]} for evidence in item["evidence"]]} for item in ranked], "opportunities": [], "graph": {"source_id": "QUERY", "nodes": nodes, "edges": edges}}

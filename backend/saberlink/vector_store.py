"""Stage A3: a single persistent ChromaDB collection over every embeddable
field across all entity types.

Design (see plan §2/§8 for rationale): one collection
(`saberlink_fields`), not one per entity-type/field — at this corpus size
(~10k field rows) a single collection with metadata filtering on
`entity_type`/`field_name` is simpler to keep in sync and just as fast.
Vector id = f"{entity_id}::{field_name}" (unique, human-readable, reversible
for debugging). Metadata carries entity_id/entity_type/field_name/
source_file/source_kind — **never the raw field text**, so evidence.py
always re-reads the current field value from entities.parquet instead of a
second, potentially stale copy.
"""

from __future__ import annotations

import pandas as pd

from saberlink import config, embeddings


_client = None
_collection = None


def get_client():
    # anonymized_telemetry=False avoids a one-time outbound telemetry call on
    # first client creation, which added tens of seconds to the very first
    # query of a process when the network call was slow/unreachable —
    # unacceptable for a live demo's first query.
    global _client
    if _client is None:
        import chromadb
        from chromadb.config import Settings

        config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(config.CHROMA_DIR), settings=Settings(anonymized_telemetry=False)
        )
    return _client


def get_collection(client=None):
    # Module-level cache: opening a PersistentClient/collection touches disk
    # (sqlite + HNSW index load) and dominates latency if repeated per
    # field-pair query — a live run_query() call does many of these, so this
    # cache is what keeps a full query in the sub-2s budget.
    global _collection
    if client is not None:
        return client.get_or_create_collection(
            name=config.CHROMA_COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
    if _collection is None:
        _collection = get_client().get_or_create_collection(
            name=config.CHROMA_COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
    return _collection


def build_index(fields_index: pd.DataFrame, batch_size: int = 128, client=None) -> int:
    collection = get_collection(client)
    available = fields_index[fields_index.field_status == "available"].reset_index(drop=True)

    total = 0
    for start in range(0, len(available), batch_size):
        batch = available.iloc[start : start + batch_size]
        vectors = embeddings.embed_texts(batch["field_text"].tolist())
        collection.upsert(
            ids=[f"{r.entity_id}::{r.field_name}" for r in batch.itertuples()],
            embeddings=vectors.tolist(),
            metadatas=[
                {
                    "entity_id": r.entity_id,
                    "entity_type": r.entity_type,
                    "field_name": r.field_name,
                    "source_file": r.source_file,
                    "source_kind": r.source_kind,
                }
                for r in batch.itertuples()
            ],
        )
        total += len(batch)
    return total


def query_field(query_embedding, entity_type: str, field_name: str, n_results: int, client=None):
    """Nearest neighbors, among vectors of one (entity_type, field_name),
    to `query_embedding`. Returns a list of {entity_id, similarity} sorted
    by descending similarity."""
    collection = get_collection(client)
    count = collection.count()
    if count == 0:
        return []
    result = collection.query(
        query_embeddings=[query_embedding.tolist() if hasattr(query_embedding, "tolist") else list(query_embedding)],
        n_results=min(n_results, count),
        where={"$and": [{"entity_type": entity_type}, {"field_name": field_name}]},
    )
    ids = result["ids"][0] if result["ids"] else []
    metadatas = result["metadatas"][0] if result["metadatas"] else []
    distances = result["distances"][0] if result["distances"] else []
    out = []
    for meta, dist in zip(metadatas, distances):
        out.append({"entity_id": meta["entity_id"], "similarity": max(0.0, 1.0 - dist)})
    return out


def run() -> int:
    fields_index = pd.read_parquet(config.FIELDS_INDEX_PARQUET)
    return build_index(fields_index)


if __name__ == "__main__":
    n = run()
    print(f"vector_store: indexed {n} field vectors into '{config.CHROMA_COLLECTION_NAME}' at {config.CHROMA_DIR}")

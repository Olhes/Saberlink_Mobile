"""Stage A4: build the explicit-relations graph.

Only relations that are explicit in the data become edges (direct FK
columns + the 6 junction tables), plus one deliberately weak/inferred edge:
NEED -> FAC via the regex-extracted `originating_faculty_id` from ingest.py
(tagged edge_kind="inferred" so graph_query.py can, and does, treat it as
lower-confidence than a real FK).

Every edge carries `relation_type` so evidence.py can cite *why* two nodes
are structurally close instead of a bare hop count.
"""

from __future__ import annotations

import pickle

import networkx as nx
import pandas as pd

from saberlink import config, schema


def _add_fk_edges(G: nx.Graph, entities: pd.DataFrame) -> None:
    for spec in schema.ENTITY_SPECS.values():
        sub = entities[entities.entity_type == spec.entity_type]
        for column, target_type in spec.fk_fields:
            if column not in sub.columns:
                continue
            for entity_id, target_id in zip(sub["entity_id"], sub[column]):
                if target_id is None or (isinstance(target_id, float)):
                    continue
                target_id = str(target_id).strip()
                if not target_id:
                    continue
                G.add_edge(
                    entity_id,
                    target_id,
                    relation_type=f"{spec.entity_type}.{column}",
                    edge_kind="explicit",
                )


def _add_inferred_need_faculty_edges(G: nx.Graph, entities: pd.DataFrame) -> None:
    needs = entities[entities.entity_type == "NEED"]
    if "originating_faculty_id" not in needs.columns:
        return
    for entity_id, fac_id in zip(needs["entity_id"], needs["originating_faculty_id"]):
        if fac_id is None or (isinstance(fac_id, float)):
            continue
        G.add_edge(
            entity_id,
            str(fac_id).strip(),
            relation_type="NEED.originating_unit(regex)",
            edge_kind="inferred",
        )


def _add_junction_edges(G: nx.Graph) -> None:
    for relative_path, from_col, from_type, to_col, to_type, relation_col in schema.JUNCTION_TABLES:
        df = pd.read_csv(config.DATA_ROOT / relative_path, encoding="utf-8-sig", dtype=str)
        for _, row in df.iterrows():
            G.add_edge(
                row[from_col],
                row[to_col],
                relation_type=str(row.get(relation_col, "")),
                edge_kind="explicit",
            )


def build_graph(entities: pd.DataFrame) -> nx.Graph:
    G = nx.Graph()
    G.add_nodes_from(entities["entity_id"])
    _add_fk_edges(G, entities)
    _add_inferred_need_faculty_edges(G, entities)
    _add_junction_edges(G)
    return G


def save_graph(G: nx.Graph, path=None) -> None:
    path = path or config.GRAPH_PICKLE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(G, f)


def load_graph(path=None) -> nx.Graph:
    path = path or config.GRAPH_PICKLE
    with open(path, "rb") as f:
        return pickle.load(f)


def run() -> nx.Graph:
    entities = pd.read_parquet(config.ENTITIES_PARQUET)
    G = build_graph(entities)
    save_graph(G)
    return G


if __name__ == "__main__":
    G = run()
    print(f"graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges -> {config.GRAPH_PICKLE}")

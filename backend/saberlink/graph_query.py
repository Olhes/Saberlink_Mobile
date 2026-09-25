"""Structural-proximity helpers over graph.gpickle.

Deliberately capped/low-weighted downstream (see scoring.py, config.py
DEFAULT_WEIGHTS["structural"]): a NEED's only edge is the weak, inferred
NEED->FAC link (originating_unit regex). Left unchecked, that would make
"same faculty" dominate the ranking — exactly what the official rules warn
against ("misma facultad no significa mayor pertinencia"). Capping the
weight and requiring >=2 hops to reach anything beyond the faculty node
itself keeps this signal a tie-breaker, not a driver.

Performance note: a query scores hundreds-to-thousands of candidates across
several candidate types. Running a fresh BFS (shortest_path_length AND
shortest_path) per candidate was the dominant cost of a live query (~2000
candidates x 2 BFS passes over a ~3200-node graph). `precompute_source` runs
ONE single-source BFS per query and every candidate then does an O(1) dict
lookup — call it once in pipeline.py and reuse it across every candidate
type.
"""

from __future__ import annotations

import networkx as nx

from saberlink import schema, viz

MAX_PATH_HOPS = 5


class PrecomputedSource:
    __slots__ = ("source", "paths", "neighbors")

    def __init__(self, source: str, paths: dict[str, list[str]], neighbors: set[str]):
        self.source = source
        self.paths = paths  # target_id -> shortest path (list of node ids), within MAX_PATH_HOPS
        self.neighbors = neighbors  # 1-hop neighbors of source


def precompute_source(G: nx.Graph, source: str) -> PrecomputedSource:
    if source not in G:
        return PrecomputedSource(source, {}, set())
    paths = nx.single_source_shortest_path(G, source, cutoff=MAX_PATH_HOPS)
    neighbors = set(G.neighbors(source))
    return PrecomputedSource(source, paths, neighbors)


def path_component(pre: PrecomputedSource, target: str) -> float:
    path = pre.paths.get(target)
    if path is None:
        return 0.0
    d = len(path) - 1
    return 1.0 / (1.0 + d)


def neighbor_overlap_component(pre: PrecomputedSource, G: nx.Graph, target: str) -> float:
    if target not in G:
        return 0.0
    n_target = set(G.neighbors(target))
    union = pre.neighbors | n_target
    if not union:
        return 0.0
    return len(pre.neighbors & n_target) / len(union)


def structural_score(pre: PrecomputedSource, G: nx.Graph, target: str) -> float:
    score = 0.5 * path_component(pre, target) + 0.5 * neighbor_overlap_component(pre, G, target)
    return max(0.0, min(1.0, score))


def describe_path(pre: PrecomputedSource, G: nx.Graph, target: str) -> str | None:
    """Human-readable trace of the shortest path, for evidence/explanation
    text — e.g. 'INV-014 pertenece a GRP-009, que ejecuta PRJ-081'."""
    path = pre.paths.get(target)
    if path is None or len(path) < 2:
        return None
    hops = []
    for a, b in zip(path[:-1], path[1:]):
        relation = G[a][b].get("relation_type", "relacionado con")
        hops.append(f"{a} -[{relation}]-> {b}")
    return " ; ".join(hops)


def _display_name(entity_id: str, entity_type: str, row: dict | None) -> str:
    if row is None:
        return entity_id
    spec = schema.ENTITY_SPECS.get(entity_type)
    name_field = spec.name_field if spec else None
    if name_field and row.get(name_field):
        return str(row[name_field])[:60]
    return entity_id


def build_discovery_graph_data(
    source_id: str,
    results: list[dict],
    G: nx.Graph,
    pre: PrecomputedSource,
    entity_lookup: dict[str, dict],
    source_label: str | None = None,
) -> dict:
    """Pure-data version of "the subgraph OF THE QUERY": the source node, the
    top-K connections run_query() actually ranked (each edge tagged by score
    band), plus only the graph hub nodes that explain each connection's
    structural proximity. No rendering concerns (no pyvis, no HTML) — this is
    consumed both by the API's /graph endpoint (returned as-is, JSON) and by
    saberlink.plus.pyvis_export (translated into a pyvis Network), so the two
    never compute "which nodes/edges belong in this view" twice.

    `results` is `run_query()["results"]`: each item has `target.id`,
    `relevance.score`, `relevance.label`, `explanation`.
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(node_id: str, *, role: str) -> None:
        if node_id in nodes:
            return
        row = entity_lookup.get(node_id)
        entity_type = (row or {}).get("entity_type") or ("NEED" if node_id.startswith("TEMP-") else "?")
        if role == "source" and node_id.startswith("TEMP-") and source_label:
            label = source_label[:60]
        else:
            label = _display_name(node_id, entity_type, row)
        nodes[node_id] = {
            "id": node_id,
            "label": label,
            "type": entity_type,
            "type_label": viz.ENTITY_TYPE_LABELS.get(entity_type, entity_type),
            "color": viz.ENTITY_TYPE_COLORS.get(entity_type, viz.DEFAULT_COLOR),
            "role": role,  # "source" | "result" | "hub"
        }

    add_node(source_id, role="source")

    for r in results:
        target_id = r["target"]["id"]
        score = r["relevance"]["score"]
        band = r["relevance"]["label"]
        add_node(target_id, role="result")
        edges.append(
            {
                "source": source_id,
                "target": target_id,
                "kind": "discovery",
                "score": score,
                "band": band,
                "color": viz.SCORE_BAND_COLORS.get(band, viz.DEFAULT_COLOR),
                "label": f"{score:.2f}",
                "tooltip": r["explanation"],
            }
        )

        path = pre.paths.get(target_id)
        if path and len(path) > 2:
            for hub in path[1:-1]:
                add_node(hub, role="hub")
            for a, b in zip(path[:-1], path[1:]):
                edge_data = G.get_edge_data(a, b) or {}
                edges.append(
                    {
                        "source": a,
                        "target": b,
                        "kind": "structural",
                        "relation": edge_data.get("relation_type", ""),
                        "inferred": edge_data.get("edge_kind") == "inferred",
                    }
                )

    return {"source_id": source_id, "nodes": list(nodes.values()), "edges": edges}

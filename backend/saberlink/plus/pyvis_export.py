"""[PLUS] Interactive HTML visualization of a query, via pyvis.

Strictly additive: reads processed/graph.gpickle and entities.parquet
(already built by the núcleo) and calls pipeline.run_query — deleting this
file breaks nothing else in saberlink/.

Two views:
- export_discovery_graph (default, what the CLI/Streamlit use): the query
  node + the top-K connections run_query() actually returned, each edge
  colored/labeled by its score, plus the graph hub node(s) that explain WHY
  each connection is structurally close. Small and legible (source + top_k
  + a handful of hubs) — this is "the subgraph OF THE QUERY" the original
  architecture note asked for, not a dump of the raw institutional graph.
  The actual node/edge selection is computed once, in
  saberlink.graph_query.build_discovery_graph_data — shared with the API's
  /graph endpoint (backend/api/main.py) so the two never compute it twice;
  this module only translates that data into a pyvis Network.
- export_ego_graph: the unfiltered radius-N neighborhood in graph.gpickle.
  Useful to audit the graph itself, but easily 100+ nodes and hard to read —
  kept as a secondary, explicitly-requested view, not the default.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pandas as pd

from saberlink import config, entity_lookup as entity_lookup_mod, graph_build, graph_query, pipeline, viz

ENTITY_TYPE_COLORS = viz.ENTITY_TYPE_COLORS
ENTITY_TYPE_LABELS = viz.ENTITY_TYPE_LABELS
DEFAULT_COLOR = viz.DEFAULT_COLOR
SCORE_BAND_COLORS = viz.SCORE_BAND_COLORS

# Pyvis-specific rendering knobs per node role — not a graph_query concern.
ROLE_SIZE = {"source": 42, "hub": 12, "result": 26}
ROLE_FONT_SIZE = {"source": 16, "hub": 10, "result": 13}


def _node_label(entity_id: str, entities: pd.DataFrame) -> str:
    row = entities.loc[entities.entity_id == entity_id]
    if row.empty:
        return entity_id
    row = row.iloc[0]
    for name_col in ("title", "full_name", "group_name", "program_name", "faculty_name", "capability_name", "line_name", "subject_name"):
        if name_col in row and pd.notna(row[name_col]):
            return f"{entity_id}\n{str(row[name_col])[:40]}"
    return entity_id


def _entity_type(entity_id: str, entities: pd.DataFrame) -> str:
    row = entities.loc[entities.entity_id == entity_id, "entity_type"]
    return row.iloc[0] if not row.empty else "?"


def _legend_html(used_types: set[str]) -> str:
    swatches = "".join(
        f'<div style="display:flex;align-items:center;margin:2px 0;">'
        f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;'
        f'background:{ENTITY_TYPE_COLORS.get(t, DEFAULT_COLOR)};margin-right:6px;"></span>'
        f'<span>{ENTITY_TYPE_LABELS.get(t, t)}</span></div>'
        for t in sorted(used_types)
    )
    score_rows = "".join(
        f'<div style="display:flex;align-items:center;margin:2px 0;">'
        f'<span style="display:inline-block;width:20px;height:3px;background:{color};margin-right:6px;"></span>'
        f'<span>conexión descubierta — relevancia {band}</span></div>'
        for band, color in SCORE_BAND_COLORS.items()
    )
    return f"""
<div style="position:fixed;top:12px;right:12px;background:white;border:1px solid #d1d5db;
            border-radius:8px;padding:10px 14px;font-family:sans-serif;font-size:12px;
            box-shadow:0 2px 8px rgba(0,0,0,0.15);z-index:1000;max-width:260px;">
  <div style="font-weight:600;margin-bottom:6px;">Tipos de entidad</div>
  {swatches}
  <div style="font-weight:600;margin:8px 0 4px;">Aristas</div>
  {score_rows}
  <div style="display:flex;align-items:center;margin:2px 0;">
    <span style="display:inline-block;width:20px;height:1px;background:#94a3b8;margin-right:6px;"></span>
    <span>relación estructural explícita</span></div>
  <div style="display:flex;align-items:center;margin:2px 0;">
    <span style="display:inline-block;width:20px;border-top:1px dashed #94a3b8;margin-right:6px;"></span>
    <span>relación estructural inferida</span></div>
</div>
"""


def _write_html(net, out_path: Path, extra_html: str = "") -> Path:
    html = net.generate_html(notebook=False)
    if extra_html:
        html = html.replace("</body>", extra_html + "</body>")
    # pyvis's own write_html() opens the file with the platform default
    # encoding (cp1252 on Windows), which crashes on accented Spanish text
    # in node labels — write it ourselves as UTF-8.
    out_path.write_text(html, encoding="utf-8")
    return out_path


def export_discovery_graph(
    entity_id: str | None = None,
    raw_text_profile: dict | None = None,
    top_k: int = 8,
    out_dir: Path | None = None,
) -> Path:
    """The legible default: query node + the connections run_query() actually
    ranked, each edge colored/labeled by score, plus only the graph hub
    node(s) that explain each connection's structural proximity.

    Accepts the same two query modes as pipeline.run_query — an existing
    entity_id, or a raw_text_profile (PDF-via-Docling / free text) for an
    ephemeral, non-persisted NEED. This has to call run_query itself (not
    reuse a previous call's result) because each raw_text_profile call mints
    a fresh TEMP-xxxxxxxx id — a previous call's id can't be looked up again."""
    from pyvis.network import Network

    out = pipeline.run_query(entity_id=entity_id, raw_text_profile=raw_text_profile, top_k=top_k)
    source_id = out["source"]["id"]
    entities = pd.read_parquet(config.ENTITIES_PARQUET)
    lookup = entity_lookup_mod.build(entities)
    graph = graph_build.load_graph()
    pre = graph_query.precompute_source(graph, source_id)
    source_label = (raw_text_profile or {}).get("title")

    graph_data = graph_query.build_discovery_graph_data(
        source_id, out["results"], graph, pre, lookup, source_label=source_label
    )

    net = Network(height="800px", width="100%", directed=True, notebook=False, cdn_resources="in_line")
    net.barnes_hut(spring_length=220, spring_strength=0.015, damping=0.2)

    used_types: set[str] = set()
    for node in graph_data["nodes"]:
        used_types.add(node["type"])
        is_source = node["role"] == "source"
        label = f"{node['id']}\n{node['label']}" if node["label"] != node["id"] else node["id"]
        net.add_node(
            node["id"], label=label, title=f"{node['id']} ({node['type_label']})",
            color=node["color"], size=ROLE_SIZE[node["role"]], borderWidth=3 if is_source else 1,
            font={"size": ROLE_FONT_SIZE[node["role"]]},
        )

    for edge in graph_data["edges"]:
        if edge["kind"] == "discovery":
            tooltip = edge["tooltip"].replace("\n", "<br>")
            net.add_edge(
                edge["source"], edge["target"],
                value=1 + edge["score"] * 5, color=edge["color"],
                title=f"score={edge['score']:.2f} ({edge['band']})<br>{tooltip}",
                label=edge["label"], font={"size": 11, "align": "top"},
            )
        else:
            net.add_edge(
                edge["source"], edge["target"], color="#94a3b8", width=1,
                dashes=edge["inferred"], title=edge["relation"], arrows="",
            )

    out_dir = out_dir or (config.PROCESSED_DIR / "subgraphs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{source_id}_discovery.html"
    return _write_html(net, out_path, extra_html=_legend_html(used_types))


def build_ego_graph(G: nx.Graph, entity_id: str, radius: int = 2) -> nx.Graph:
    if entity_id not in G:
        raise ValueError(f"Unknown entity_id in graph: {entity_id}")
    return nx.ego_graph(G, entity_id, radius=radius)


def export_ego_graph(entity_id: str, radius: int = 2, out_dir: Path | None = None) -> Path:
    """Secondary view: the raw, unfiltered radius-N graph neighborhood —
    useful to audit the explicit-relations graph itself, but dense (100+
    nodes at radius=2) and not meant as the primary demo visualization."""
    from pyvis.network import Network

    G = graph_build.load_graph()
    ego = build_ego_graph(G, entity_id, radius=radius)
    entities = pd.read_parquet(config.ENTITIES_PARQUET)

    net = Network(height="750px", width="100%", directed=False, notebook=False, cdn_resources="in_line")
    net.barnes_hut()

    used_types: set[str] = set()
    for node in ego.nodes:
        etype = _entity_type(node, entities)
        used_types.add(etype)
        color = ENTITY_TYPE_COLORS.get(etype, DEFAULT_COLOR)
        size = 30 if node == entity_id else 15
        net.add_node(node, label=_node_label(node, entities), title=f"{node} ({etype})", color=color, size=size)

    for a, b, data in ego.edges(data=True):
        relation = data.get("relation_type", "")
        is_inferred = data.get("edge_kind") == "inferred"
        net.add_edge(a, b, title=relation, dashes=is_inferred, color="#94a3b8")

    out_dir = out_dir or (config.PROCESSED_DIR / "subgraphs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{entity_id}_ego.html"
    return _write_html(net, out_path, extra_html=_legend_html(used_types))


# Backwards-compatible alias (previous name).
export_subgraph_html = export_ego_graph


if __name__ == "__main__":
    import sys

    query_id = sys.argv[1] if len(sys.argv) > 1 else "NEED-001"
    mode = sys.argv[2] if len(sys.argv) > 2 else "discovery"
    if mode == "ego":
        path = export_ego_graph(query_id)
    else:
        path = export_discovery_graph(query_id)
    print(f"escrito en {path}")

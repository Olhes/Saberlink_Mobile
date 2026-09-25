import pandas as pd

from saberlink import graph_build, ingest


def _build():
    entities, _ = ingest.run()
    return entities, graph_build.build_graph(entities)


def test_node_count_matches_entity_count():
    entities, G = _build()
    assert G.number_of_nodes() == len(entities)


def test_known_explicit_fk_edge_present():
    _, G = _build()
    assert G.has_edge("PRG-001", "FAC-001")
    assert G["PRG-001"]["FAC-001"]["edge_kind"] == "explicit"


def test_known_junction_edge_present():
    _, G = _build()
    assert G.has_edge("INV-001", "GRP-004")
    assert G["INV-001"]["GRP-004"]["edge_kind"] == "explicit"


def test_inferred_need_faculty_edge_is_tagged_inferred():
    _, G = _build()
    assert G.has_edge("NEED-021", "FAC-003")
    assert G["NEED-021"]["FAC-003"]["edge_kind"] == "inferred"


def test_every_edge_has_relation_type():
    _, G = _build()
    assert all("relation_type" in data for _, _, data in G.edges(data=True))


def test_edge_count_in_expected_ballpark():
    _, G = _build()
    # ~4,256 direct-FK rows + 42 inferred NEED->FAC + ~2,816 junction rows,
    # minus overlaps collapsed by the simple (non-multi) Graph (e.g.
    # PRJ.group_id vs project_group.csv both linking the same PRJ-GRP pair).
    assert 6000 <= G.number_of_edges() <= 7200

"""Proves run_query() has no 'cached answer' path: calling it twice with the
same id re-embeds and re-scores both times. This is the automated version of
the live-demo claim ("no resultados precargados") — see plan §4."""

from saberlink import embeddings, pipeline


def test_repeated_query_recomputes_embeddings(monkeypatch):
    calls = {"n": 0}
    original = embeddings.embed_texts

    def counting_embed_texts(texts):
        calls["n"] += 1
        return original(texts)

    monkeypatch.setattr(embeddings, "embed_texts", counting_embed_texts)

    pipeline.run_query(entity_id="NEED-001", top_k=3)
    first_call_count = calls["n"]
    assert first_call_count > 0

    pipeline.run_query(entity_id="NEED-001", top_k=3)
    second_call_count = calls["n"]
    assert second_call_count > first_call_count, "second call must re-embed, not reuse a stored result"


def test_repeated_query_produces_consistent_but_freshly_computed_scores():
    out1 = pipeline.run_query(entity_id="NEED-013", top_k=5)
    out2 = pipeline.run_query(entity_id="NEED-013", top_k=5)
    ids1 = [r["target"]["id"] for r in out1["results"]]
    ids2 = [r["target"]["id"] for r in out2["results"]]
    assert ids1 == ids2  # deterministic given fixed inputs, not "randomly cached"
    assert out1["meta"]["elapsed_seconds"] > 0
    assert out2["meta"]["elapsed_seconds"] > 0


def test_ephemeral_pdf_profile_is_not_persisted(tmp_path):
    before = pipeline.run_query(entity_id="NEED-001", top_k=1)
    raw_profile = {
        "title": "Riesgo de deserción en programas nocturnos",
        "description": "Se requiere anticipar abandono en estudiantes de horario nocturno.",
        "context": "Piloto interno, aún sin radicar como necesidad oficial.",
        "expected_impact": "Reducir la tasa de abandono nocturno.",
    }
    out = pipeline.run_query(raw_text_profile=raw_profile, top_k=3)
    assert out["source"]["official"] is False
    assert out["source"]["id"].startswith("TEMP-")
    # The ephemeral id must never leak into the persisted entities table.
    import pandas as pd

    from saberlink import config

    entities = pd.read_parquet(config.ENTITIES_PARQUET)
    assert out["source"]["id"] not in set(entities["entity_id"])

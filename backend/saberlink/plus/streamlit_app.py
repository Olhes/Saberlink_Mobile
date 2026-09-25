"""[PLUS] Thin Streamlit UI over pipeline.run_query.

Strictly additive: imports only from saberlink.pipeline (and, optionally,
saberlink.plus.pyvis_export for the subgraph view) — no núcleo module
imports from here, so deleting this file changes nothing else. If this
never gets built or breaks, notebooks/06_live_demo.ipynb is already a
complete substitute for the live demo.

Run with:
    streamlit run saberlink/plus/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from saberlink import pipeline  # noqa: E402

st.set_page_config(page_title="SaberLink", layout="wide")

if "warm" not in st.session_state:
    st.session_state["warm"] = False

st.title("SaberLink — Knowledge Nexus LATAM")
st.caption(
    "Dado un ID de necesidad institucional (o cualquier entidad), descubre conexiones, "
    "las prioriza con evidencia trazable y genera una oportunidad accionable."
)

with st.sidebar:
    st.header("Consulta")
    query_mode = st.radio("Modo de consulta", ["ID existente", "Texto libre (necesidad nueva)"])

    entity_id = None
    raw_text_profile = None
    if query_mode == "ID existente":
        entity_id = st.text_input("ID de entidad", value="NEED-001", help="Ej: NEED-001, PRJ-001, INV-001")
    else:
        st.caption(
            "Se trata como necesidad temporal — nunca se escribe en institutional_needs.csv "
            "(mismo mecanismo que el PDF vía Docling)."
        )
        title = st.text_input("Título", value="")
        description = st.text_area("Descripción", value="", height=120)
        context = st.text_area("Contexto (opcional)", value="", height=60)
        expected_impact = st.text_area("Impacto esperado (opcional)", value="", height=60)

    top_k = st.slider("Cuántos resultados mostrar", min_value=3, max_value=15, value=5)
    show_subgraph = st.checkbox("Mostrar subgrafo [PLUS]", value=False)
    run_clicked = st.button("Buscar conexiones", type="primary")
    if not st.session_state["warm"]:
        st.caption("La primera consulta del proceso tarda ~20s (carga el modelo). Las siguientes, 1-2s.")

if run_clicked:
    if query_mode == "Texto libre (necesidad nueva)":
        if not description.strip():
            st.error("Escribí al menos una descripción.")
            st.stop()
        raw_text_profile = {
            "title": title.strip() or description.strip()[:80],
            "description": description.strip(),
            "context": context.strip() or None,
            "expected_impact": expected_impact.strip() or None,
        }

    with st.spinner("Procesando en vivo — sin resultados precargados..."):
        try:
            out = pipeline.run_query(
                entity_id=entity_id.strip() if entity_id else None,
                raw_text_profile=raw_text_profile,
                top_k=top_k,
            )
        except ValueError as exc:
            st.error(str(exc))
            out = None
    st.session_state["warm"] = True

    if out:
        st.success(
            f"Consulta: {out['source']['id']} ({out['source']['type']}, "
            f"official={out['source']['official']}) — {out['meta']['elapsed_seconds']}s, "
            f"{out['meta']['total_candidates_scored']} candidatos evaluados"
        )

        col_results, col_detail = st.columns([1, 1.4])

        with col_results:
            st.subheader("Conexiones descubiertas")
            for i, r in enumerate(out["results"], 1):
                rel = r["relevance"]
                with st.container(border=True):
                    st.markdown(
                        f"**{i}. {r['target']['type']} {r['target']['id']}** "
                        f"— score {rel['score']:.2f} ({rel['label']})"
                    )
                    b = rel["breakdown"]
                    st.caption(
                        f"semántica={b['semantic']} · dominio={b['domain']} · "
                        f"método={b['method']} · estructural={b['structural']}"
                    )

        with col_detail:
            st.subheader("Explicación y evidencia (resultado #1)")
            if out["results"]:
                top = out["results"][0]
                st.write(top["explanation"])
                for ev in top["evidence"]:
                    st.code(f"{ev['file']} / {ev['id']} / {ev['field']}\n{ev['snippet']}", language=None)

            st.subheader("Oportunidades")
            if not out["opportunities"]:
                st.info("Ninguna regla disparó para esta consulta.")
            for o in out["opportunities"]:
                with st.container(border=True):
                    st.markdown(f"**[{o['type']}]** {o['opportunity']}")
                    st.caption(f"razón: {o['reason']} · prioridad: {o['priority']}")
                    st.caption(f"entidades relacionadas: {', '.join(o['related_entities'])}")

        if show_subgraph:
            st.subheader("Subgrafo de la consulta [PLUS]")
            st.caption(
                "Nodo consultado + las conexiones que el pipeline descubrió (coloreadas por score) "
                "+ los nodos puente que explican su cercanía estructural."
            )
            try:
                from saberlink.plus.pyvis_export import export_discovery_graph

                # Re-derive from the SAME inputs used for the query above —
                # a raw_text_profile query mints a fresh TEMP-xxxxxxxx id on
                # every run_query() call, so out["source"]["id"] from the
                # first call can't be looked up again here.
                html_path = export_discovery_graph(
                    entity_id=entity_id.strip() if entity_id else None,
                    raw_text_profile=raw_text_profile,
                    top_k=top_k,
                )
                st.components.v1.html(html_path.read_text(encoding="utf-8"), height=820, scrolling=True)
            except Exception as exc:  # pragma: no cover - PLUS convenience path
                st.warning(f"No se pudo generar el subgrafo: {exc}")

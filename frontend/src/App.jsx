import { useEffect, useState } from "react";
import { apiErrorMessage, fetchLegend, queryPdfEnhanced, runQuery } from "./api/client";
import CompactRail from "./components/CompactRail";
import NodeDetailDrawer from "./components/NodeDetailDrawer";
import SearchPanel from "./components/SearchPanel";
import DiscoveryGraph from "./graph/DiscoveryGraph";

function Mark() {
  return (
    <svg width="30" height="30" viewBox="0 0 30 30" fill="none" className="shrink-0">
      <line x1="6" y1="24" x2="15" y2="7" stroke="var(--color-gold-500)" strokeWidth="1" opacity="0.6" />
      <line x1="15" y1="7" x2="24" y2="20" stroke="var(--color-gold-500)" strokeWidth="1" opacity="0.6" />
      <line x1="6" y1="24" x2="24" y2="20" stroke="var(--color-verdigris-400)" strokeWidth="1" opacity="0.5" />
      <circle cx="15" cy="7" r="2.4" fill="var(--color-gold-400)" />
      <circle cx="6" cy="24" r="2" fill="var(--color-verdigris-400)" />
      <circle cx="24" cy="20" r="2" fill="var(--color-copper-400)" />
    </svg>
  );
}

export default function App() {
  const [legend, setLegend] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [queryResult, setQueryResult] = useState(null);
  const [graphData, setGraphData] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);

  useEffect(() => {
    fetchLegend().then(setLegend).catch(() => setLegend(null));
  }, []);

  async function handleSearch({ entityId, rawTextProfile, pdfFile, topK, useCohere }) {
    setLoading(true);
    setError(null);
    setGraphData(null);
    try {
      // The graph now comes back inline with the query result (backend
      // builds it from the very same run_query() call, so it works for an
      // ephemeral texto-libre/PDF source too — no second lookup by id).
      const result = pdfFile
        ? await queryPdfEnhanced({ file: pdfFile, topK, useCohere })
        : await runQuery({ entityId, rawTextProfile, topK });
      setQueryResult(result);
      setGraphData(result.graph || null);
      setSelectedNodeId(null);
    } catch (err) {
      setError(apiErrorMessage(err));
      setQueryResult(null);
    } finally {
      setLoading(false);
    }
  }

  const bandColors = Object.fromEntries(
    (legend?.score_bands || []).map((b) => [b.band, b.color])
  );

  return (
    <div className="min-h-screen">
      <div className="atlas-atmosphere" aria-hidden="true" />

      <header className="border-b border-gold-500/15 px-6 py-6">
        <div className="mx-auto flex max-w-[1600px] items-start gap-3">
          <Mark />
          <div>
            <h1 className="font-display text-2xl font-semibold tracking-tight text-parchment-200">
              SaberLink
              <span className="ml-2.5 font-body text-base font-normal italic text-ink-500">
                — un atlas del conocimiento institucional
              </span>
            </h1>
            <p className="mt-1.5 max-w-2xl font-body text-[15px] leading-relaxed text-parchment-200/60">
              Dado un ID, texto libre o un PDF, SaberLink traza la constelación de conexiones
              en vivo. Elige cualquier estrella del mapa para leer su relación.
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] px-6 py-7">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
          <aside className="flex flex-col gap-4 lg:sticky lg:top-6 lg:self-start">
            <SearchPanel onSubmit={handleSearch} loading={loading} />
            {queryResult && (
              <CompactRail
                results={queryResult.results}
                selectedNodeId={selectedNodeId}
                onSelect={setSelectedNodeId}
                bandColors={bandColors}
              />
            )}
          </aside>

          <section className="flex flex-col gap-4">
            {error && (
              <div className="rounded-xl border border-copper-500/30 bg-copper-500/10 px-4 py-3 font-body text-sm text-copper-400">
                {error}
              </div>
            )}

            {!queryResult && !error && !loading && (
              <div className="relative flex h-[70vh] min-h-[420px] items-center justify-center overflow-hidden rounded-2xl border border-gold-500/10 bg-ink-900/40">
                <div className="pointer-events-none absolute inset-0 opacity-40 [background-image:radial-gradient(var(--color-ink-500)_0.6px,transparent_0.6px)] [background-size:22px_22px]" />
                <p className="relative max-w-sm text-center font-body text-[15px] italic text-parchment-200/50">
                  Busca un ID, describe una necesidad o sube un PDF para trazar la red de
                  conexiones.
                </p>
              </div>
            )}

            {loading && (
              <div className="flex h-[70vh] min-h-[420px] items-center justify-center rounded-2xl border border-gold-500/10 bg-ink-900/40">
                <div className="flex flex-col items-center gap-3">
                  <div className="h-9 w-9 animate-spin rounded-full border-2 border-gold-500/25 border-t-gold-400" />
                  <p className="font-body text-sm italic text-parchment-200/50">
                    Procesando en vivo — sin resultados precargados…
                  </p>
                </div>
              </div>
            )}

            {queryResult && !loading && (
              <>
                <div className="rise-in flex flex-wrap items-center gap-3 rounded-xl border border-gold-500/15 bg-ink-900/50 px-4 py-2.5 font-mono text-xs text-parchment-200/70">
                  <span className="text-parchment-200">
                    {queryResult.source.id}{" "}
                    <span className="text-parchment-200/40">({queryResult.source.type})</span>
                  </span>
                  {!queryResult.source.official && (
                    <span className="rounded-full border border-copper-500/40 bg-copper-500/10 px-2 py-0.5 text-[10px] font-semibold text-copper-400">
                      necesidad temporal, no persistida
                    </span>
                  )}
                  <span>{queryResult.meta.elapsed_seconds}s</span>
                  <span>{queryResult.meta.total_candidates_scored} candidatos evaluados</span>
                  <span className="ml-auto italic text-gold-400/70">
                    Elige un nodo para ver su detalle →
                  </span>
                </div>

                {graphData ? (
                  <DiscoveryGraph
                    graphData={graphData}
                    legend={legend}
                    selectedNodeId={selectedNodeId}
                    onSelectNode={setSelectedNodeId}
                  />
                ) : (
                  <div className="flex h-[70vh] min-h-[420px] items-center justify-center rounded-2xl border border-gold-500/10 bg-ink-900/40 font-body text-sm italic text-parchment-200/40">
                    No se pudo construir el grafo para esta consulta.
                  </div>
                )}
              </>
            )}
          </section>
        </div>

        <footer className="mt-10 border-t border-gold-500/10 pt-4 font-body text-xs italic text-parchment-200/35">
          Sin LLM en el pipeline — embeddings (sentence-transformers), grafo (networkx) y
          scoring/oportunidades en Python propio. Sin cloud deploy, corre local.
        </footer>
      </main>

      <NodeDetailDrawer
        selectedNodeId={selectedNodeId}
        queryResult={queryResult}
        graphData={graphData}
        bandColors={bandColors}
        onClose={() => setSelectedNodeId(null)}
      />
    </div>
  );
}

import ScoreBreakdown from "./ScoreBreakdown";

const PRIORITY_COLORS = { alta: "#8fbf7a", media: "#cc9f45", baja: "#7d8798" };
const FALLBACK_BAND_COLORS = { alta: "#8fbf7a", media: "#cc9f45", baja: "#7d8798" };

function SectionLabel({ children, tag }) {
  return (
    <div className="mb-2 flex items-center gap-2">
      <span className="font-display text-[11px] font-medium tracking-[0.14em] text-gold-400/70">
        {children}
      </span>
      {tag && (
        <span className="rounded border border-ink-600 bg-ink-800 px-1.5 py-0.5 font-mono text-[10px] text-parchment-200/45">
          {tag}
        </span>
      )}
    </div>
  );
}

function OpportunityCard({ o }) {
  const color = PRIORITY_COLORS[o.priority] || "#7d8798";
  return (
    <div className="rounded-lg border border-ink-600 bg-ink-950/50 p-3">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="font-mono text-[10px] font-semibold uppercase tracking-wide text-verdigris-400">
          {o.type}
        </span>
        <span
          className="rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold"
          style={{ background: `${color}22`, color }}
        >
          prioridad {o.priority}
        </span>
      </div>
      <p className="font-body text-[15px] text-parchment-200/90">{o.opportunity}</p>
      <p className="mt-1 font-body text-xs italic text-parchment-200/40">razón: {o.reason}</p>
    </div>
  );
}

export default function NodeDetailDrawer({ selectedNodeId, queryResult, graphData, bandColors, onClose }) {
  const open = !!selectedNodeId;
  const colors = bandColors || FALLBACK_BAND_COLORS;

  const node = graphData?.nodes?.find((n) => n.id === selectedNodeId);
  const result = queryResult?.results?.find((r) => r.target.id === selectedNodeId);
  const isSource = selectedNodeId === queryResult?.source?.id;
  const relatedOpportunities =
    queryResult?.opportunities?.filter((o) => o.related_entities?.includes(selectedNodeId)) || [];

  // graphData (and so `node`) is only ever set for an official entity_id
  // query — a texto libre / PDF query has no persisted id to look up in
  // /graph, so its ranked results only exist in `result`. Falling back to
  // `result.target` keeps the drawer working in that case instead of
  // rendering nothing.
  const displayTypeLabel = node?.type_label || result?.target?.type || (isSource ? queryResult?.source?.type : "");
  const displayLabel = node?.label && node.label !== node.id ? node.label : null;

  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-ink-950/70 backdrop-blur-sm transition-opacity ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
      />
      <aside
        className={`fixed right-0 top-0 z-40 h-full w-full max-w-md transform overflow-y-auto border-l border-gold-500/15 bg-ink-900 p-6 shadow-[0_0_60px_rgba(0,0,0,0.5)] transition-transform duration-300 ease-out ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {selectedNodeId && (
          <div key={selectedNodeId} className="rise-in">
            <div className="mb-5 flex items-start justify-between gap-3 border-b border-gold-500/15 pb-4">
              <div>
                <div className="font-mono text-lg font-semibold text-parchment-200">
                  {selectedNodeId}
                </div>
                <div className="mt-0.5 font-display text-xs italic text-gold-400/70">
                  {displayTypeLabel}
                </div>
                {displayLabel && (
                  <p className="mt-1.5 font-body text-[15px] leading-snug text-parchment-200/80">
                    {displayLabel}
                  </p>
                )}
              </div>
              <button
                onClick={onClose}
                className="shrink-0 rounded-lg border border-ink-600 px-2 py-1 font-mono text-xs text-parchment-200/50 transition hover:border-gold-500/40 hover:text-parchment-200"
              >
                ✕
              </button>
            </div>

            {isSource && (
              <div className="rounded-lg border border-gold-500/20 bg-gold-500/[0.06] p-3.5 font-body text-[15px] text-parchment-200/80">
                Esta es la entidad consultada — el centro de la constelación. Elige cualquier
                otro nodo para leer por qué se conecta con ella.
                {queryResult?.meta && (
                  <p className="mt-2.5 font-mono text-xs text-parchment-200/40">
                    {queryResult.meta.elapsed_seconds}s · {queryResult.meta.total_candidates_scored}{" "}
                    candidatos evaluados
                  </p>
                )}
              </div>
            )}

            {!isSource && result && (
              <div className="flex flex-col gap-5">
                <span
                  className="w-fit rounded-full px-2.5 py-1 font-mono text-xs font-semibold"
                  style={{
                    background: `${colors[result.relevance.label] || "#7d8798"}22`,
                    color: colors[result.relevance.label] || "#7d8798",
                  }}
                >
                  {result.relevance.label} · {result.relevance.score.toFixed(2)}
                </span>

                <ScoreBreakdown
                  breakdown={result.relevance.breakdown}
                  status={result.relevance.breakdown_status}
                />

                <div>
                  <SectionLabel tag="texto generado">Explicación</SectionLabel>
                  <p className="font-body text-[15px] leading-relaxed text-parchment-200/85">
                    {result.explanation}
                  </p>
                </div>

                <div>
                  <SectionLabel>Evidencia — cadena de trazabilidad</SectionLabel>
                  {result.evidence.length === 0 ? (
                    <p className="font-body text-xs italic text-parchment-200/35">
                      Sin evidencia estructurada.
                    </p>
                  ) : (
                    <ol className="flex flex-col gap-2">
                      {result.evidence.map((ev, i) => (
                        <li
                          key={i}
                          className="rounded-lg border border-ink-600 bg-ink-950/50 p-3 text-xs"
                        >
                          <div className="mb-1.5 flex flex-wrap gap-x-1.5 gap-y-0.5 font-mono text-verdigris-400">
                            <span>{ev.file}</span>
                            <span className="text-parchment-200/25">/</span>
                            <span>{ev.id}</span>
                            <span className="text-parchment-200/25">/</span>
                            <span>{ev.field}</span>
                          </div>
                          <p className="font-body text-[13px] text-parchment-200/70">{ev.snippet}</p>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              </div>
            )}

            {!isSource && !result && (
              <div className="rounded-lg border border-ink-600 bg-ink-950/50 p-3.5 font-body text-[15px] text-parchment-200/70">
                Nodo puente estructural — no es una conexión rankeada directamente, aparece
                porque forma parte del camino en el grafo institucional que explica la
                cercanía de otra conexión.
              </div>
            )}

            {relatedOpportunities.length > 0 && (
              <div className="mt-6">
                <SectionLabel>Oportunidades relacionadas</SectionLabel>
                <div className="flex flex-col gap-3">
                  {relatedOpportunities.map((o, i) => (
                    <OpportunityCard key={i} o={o} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </aside>
    </>
  );
}

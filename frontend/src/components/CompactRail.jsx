const FALLBACK_BAND_COLORS = { alta: "#16a34a", media: "#cc9f45", baja: "#7d8798" };

export default function CompactRail({ results, selectedNodeId, onSelect, bandColors }) {
  const colors = bandColors || FALLBACK_BAND_COLORS;

  return (
    <div className="rounded-xl border border-gold-500/15 bg-ink-900/50 p-3">
      <div className="mb-1.5 flex items-baseline justify-between px-1.5">
        <span className="font-display text-[11px] font-medium tracking-[0.14em] text-gold-400/70">
          Ranking
        </span>
        <span className="font-mono text-[11px] text-parchment-200/35">{results.length}</span>
      </div>
      <ol className="flex flex-col divide-y divide-ink-700/60">
        {results.map((r, i) => {
          const color = colors[r.relevance.label] || "#7d8798";
          const selected = r.target.id === selectedNodeId;
          return (
            <li key={r.target.id}>
              <button
                type="button"
                onClick={() => onSelect(r.target.id)}
                className={`flex w-full items-center gap-2.5 px-1.5 py-2 text-left text-xs transition ${
                  selected ? "bg-gold-500/10" : "hover:bg-ink-800/50"
                }`}
              >
                <span
                  className={`w-4 shrink-0 text-right font-display italic ${selected ? "text-gold-400" : "text-parchment-200/30"}`}
                >
                  {i + 1}
                </span>
                <span
                  className="h-1.5 w-1.5 shrink-0 rounded-full"
                  style={{ background: color, boxShadow: `0 0 6px ${color}` }}
                  title={r.relevance.label}
                />
                <span className="flex-1 truncate font-mono text-parchment-200/85">
                  {r.target.id}
                </span>
                <span className="shrink-0 font-mono text-parchment-200/45">
                  {r.relevance.score.toFixed(2)}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

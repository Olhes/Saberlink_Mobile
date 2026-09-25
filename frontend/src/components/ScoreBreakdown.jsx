const SIGNAL_LABELS = {
  semantic: "Semántica",
  domain: "Dominio",
  method: "Método",
  structural: "Estructural",
};

const SIGNAL_COLORS = {
  semantic: "#e3bd6f",
  domain: "#7dbfae",
  method: "#d1897a",
  structural: "#7d8798",
};

export default function ScoreBreakdown({ breakdown, status }) {
  const keys = ["semantic", "domain", "method", "structural"];
  return (
    <div className="flex flex-col gap-1.5">
      {keys.map((key) => {
        const value = breakdown?.[key];
        const st = status?.[key];
        const na = st === "not_applicable" || st === "not_available" || value == null;
        return (
          <div key={key} className="flex items-center gap-2 text-xs">
            <span className="w-[70px] shrink-0 font-body italic text-parchment-200/45">
              {SIGNAL_LABELS[key]}
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-700/70">
              {!na && (
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.round(value * 100)}%`,
                    background: SIGNAL_COLORS[key],
                    boxShadow: `0 0 6px ${SIGNAL_COLORS[key]}55`,
                  }}
                />
              )}
            </div>
            <span className="w-9 shrink-0 text-right font-mono text-parchment-200/50">
              {na ? "n/d" : value.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

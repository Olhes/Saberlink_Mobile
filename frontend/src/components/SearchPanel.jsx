import { useEffect, useRef, useState } from "react";
import { searchEntities, queryPdfEnhanced } from "../api/client";

const ENTITY_TYPE_HINT = "Ej: NEED-001, PRJ-014, INV-032, GRP-009";

function FieldLabel({ children }) {
  return (
    <label className="mb-1.5 block font-display text-[11px] font-medium tracking-[0.14em] text-gold-400/70">
      {children}
    </label>
  );
}

const inputClass =
  "w-full rounded-lg border border-ink-600 bg-ink-950/70 px-3 py-2 font-body text-[15px] text-parchment-200 outline-none transition placeholder:text-parchment-200/25 focus:border-gold-500/60 focus:shadow-[0_0_0_3px_rgba(204,159,69,0.12)]";

export default function SearchPanel({ onSubmit, loading }) {
  const [mode, setMode] = useState("id"); // "id" | "text" | "pdf"
  const [entityId, setEntityId] = useState("NEED-001");
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [context, setContext] = useState("");
  const [expectedImpact, setExpectedImpact] = useState("");
  const [pdfFile, setPdfFile] = useState(null);
  const [topK, setTopK] = useState(8);
  const [useCohere, setUseCohere] = useState(true);
  const debounceRef = useRef(null);

  useEffect(() => {
    if (mode !== "id" || !entityId.trim()) {
      setSuggestions([]);
      return;
    }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const results = await searchEntities({ q: entityId.trim(), limit: 6 });
        setSuggestions(results);
      } catch {
        setSuggestions([]);
      }
    }, 250);
    return () => clearTimeout(debounceRef.current);
  }, [entityId, mode]);

  async function handleSubmit(e) {
    e.preventDefault();
    setShowSuggestions(false);
    if (mode === "id") {
      if (!entityId.trim()) return;
      onSubmit({ entityId: entityId.trim(), topK });
    } else if (mode === "text") {
      if (!description.trim()) return;
      onSubmit({
        rawTextProfile: {
          title: title.trim() || description.trim().slice(0, 80),
          description: description.trim(),
          context: context.trim() || null,
          expected_impact: expectedImpact.trim() || null,
        },
        topK,
      });
    } else {
      if (!pdfFile) return;
      onSubmit({ pdfFile, topK, useCohere });
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 rounded-xl border border-gold-500/15 bg-ink-900/50 p-5 shadow-[0_1px_0_rgba(240,217,163,0.05)_inset]"
    >
      <div className="flex gap-1 rounded-lg border border-ink-700 bg-ink-950/50 p-1 font-display text-[13px] font-medium">
        {[
          { key: "id", label: "ID existente" },
          { key: "text", label: "Texto libre" },
          { key: "pdf", label: "Subir PDF" },
        ].map((opt) => (
          <button
            key={opt.key}
            type="button"
            onClick={() => setMode(opt.key)}
            className={`flex-1 rounded-md px-2 py-1.5 transition ${
              mode === opt.key
                ? "bg-gold-500 text-ink-950 shadow-[0_0_12px_rgba(204,159,69,0.35)]"
                : "text-parchment-200/40 hover:text-parchment-200/80"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {mode === "id" && (
        <div className="relative">
          <FieldLabel>ID de entidad</FieldLabel>
          <input
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            placeholder={ENTITY_TYPE_HINT}
            className={`${inputClass} font-mono`}
          />
          {showSuggestions && suggestions.length > 0 && (
            <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-ink-600 bg-ink-900 shadow-2xl shadow-black/50">
              {suggestions.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onMouseDown={() => {
                      setEntityId(s.id);
                      setShowSuggestions(false);
                    }}
                    className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left hover:bg-ink-800"
                  >
                    <span className="font-mono text-sm text-gold-400">
                      {s.id} <span className="text-parchment-200/35">· {s.type_label}</span>
                    </span>
                    <span className="truncate font-body text-xs text-parchment-200/50">
                      {s.name}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {mode === "text" && (
        <div className="flex flex-col gap-3">
          <p className="font-body text-xs italic text-parchment-200/40">
            Se trata como necesidad temporal — nunca se escribe en institutional_needs.csv.
          </p>
          <div>
            <FieldLabel>Título</FieldLabel>
            <input value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} />
          </div>
          <div>
            <FieldLabel>Descripción</FieldLabel>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className={`${inputClass} resize-none`}
            />
          </div>
          <div>
            <FieldLabel>Contexto (opcional)</FieldLabel>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              rows={2}
              className={`${inputClass} resize-none`}
            />
          </div>
          <div>
            <FieldLabel>Impacto esperado (opcional)</FieldLabel>
            <textarea
              value={expectedImpact}
              onChange={(e) => setExpectedImpact(e.target.value)}
              rows={2}
              className={`${inputClass} resize-none`}
            />
          </div>
        </div>
      )}

      {mode === "pdf" && (
        <div className="flex flex-col gap-2">
          <p className="font-body text-xs italic text-parchment-200/40">
            Se extrae el texto vía Docling y se procesa con LightRAG + Cohere para análisis
            mejorado del grafo institucional.
          </p>
          <label className="flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-gold-500/25 bg-ink-950/50 px-3 py-7 text-center transition hover:border-gold-500/60 hover:bg-ink-950/70">
            <input
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
            />
            <span className="font-display text-sm font-medium text-parchment-200/80">
              {pdfFile ? pdfFile.name : "Click para elegir un PDF"}
            </span>
            <span className="font-mono text-[11px] text-parchment-200/35">
              {pdfFile ? `${(pdfFile.size / 1024).toFixed(0)} KB` : "Solo .pdf"}
            </span>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={useCohere}
              onChange={(e) => setUseCohere(e.target.checked)}
              className="accent-gold-500"
            />
            <span className="font-body text-xs text-parchment-200/70">
              Usar Cohere LLM para re-ranking y generación de oportunidades
            </span>
          </label>
        </div>
      )}

      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <span className="font-display text-[11px] font-medium tracking-[0.14em] text-gold-400/70">
            Resultados
          </span>
          <span className="font-mono text-xs text-parchment-200/60">{topK}</span>
        </div>
        <input
          type="range"
          min={3}
          max={15}
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
          className="w-full accent-gold-500"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="mt-1 rounded-lg bg-gold-500 px-4 py-2.5 font-display text-sm font-semibold text-ink-950 shadow-[0_0_18px_rgba(204,159,69,0.28)] transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {loading ? "Procesando en vivo…" : "Buscar conexiones"}
      </button>
    </form>
  );
}

import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";
import { useEffect, useMemo, useRef, useState } from "react";
import CytoscapeComponent from "react-cytoscapejs";

cytoscape.use(fcose);

const BANDS = ["alta", "media", "baja"];

// VOSviewer conventions this mirrors: uniform circles (color carries the
// category, not shape), node/label size driven by a weight — here the
// discovery score — light canvas, thin neutral edges, arrows dropped, and
// only the nodes that matter get a legible label.
const SOURCE_SIZE = 44;
const HUB_SIZE = 7;
const RESULT_MIN_SIZE = 15;
const RESULT_MAX_SIZE = 40;

function sizeForScore(score) {
  const s = Math.max(0, Math.min(1, score ?? 0));
  return RESULT_MIN_SIZE + s * (RESULT_MAX_SIZE - RESULT_MIN_SIZE);
}

function toElements(graphData) {
  if (!graphData) return [];

  const scoreByTarget = {};
  for (const e of graphData.edges) {
    if (e.kind === "discovery") scoreByTarget[e.target] = e.score;
  }

  const nodes = graphData.nodes.map((n) => {
    const score = scoreByTarget[n.id];
    const size = n.role === "source" ? SOURCE_SIZE : n.role === "hub" ? HUB_SIZE : sizeForScore(score);
    return {
      data: {
        id: n.id,
        label: n.role === "hub" ? "" : n.label,
        color: n.color,
        role: n.role,
        entityType: n.type,
        typeLabel: n.type_label,
        size,
        fontSize: n.role === "source" ? 15 : n.role === "hub" ? 0 : 8 + (size / RESULT_MAX_SIZE) * 8,
      },
    };
  });

  const edges = graphData.edges.map((e, i) => ({
    data: {
      id: `e${i}`,
      source: e.source,
      target: e.target,
      kind: e.kind,
      band: e.band || null,
      width: e.kind === "discovery" ? 0.6 + (e.score ?? 0) * 3.4 : 0.5,
      label: e.kind === "discovery" ? e.label : "",
      bandColor: e.kind === "discovery" ? e.color : null,
      inferred: !!e.inferred,
      tooltip: e.kind === "discovery" ? e.tooltip : e.relation,
    },
  }));
  return [...nodes, ...edges];
}

const STYLESHEET = [
  {
    selector: "node",
    style: {
      shape: "ellipse",
      "background-color": "data(color)",
      width: "data(size)",
      height: "data(size)",
      label: "data(label)",
      color: "#242017",
      "font-family": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
      "font-size": "data(fontSize)",
      "text-wrap": "wrap",
      "text-max-width": "90px",
      "text-valign": "bottom",
      "text-margin-y": 3,
      "border-width": 1,
      "border-color": "#ffffff",
      "border-opacity": 0.9,
      "transition-property": "opacity",
      "transition-duration": 150,
    },
  },
  {
    selector: 'node[role = "source"]',
    style: { "border-width": 2.5, "border-color": "#242017", "font-weight": 700 },
  },
  {
    selector: 'node[role = "result"]',
    style: { "font-weight": 500 },
  },
  {
    selector: 'node[role = "hub"]',
    style: { "background-opacity": 0.55, "border-opacity": 0.5 },
  },
  {
    selector: "node.selected",
    style: { "border-width": 3, "border-color": "#b8892f" },
  },
  {
    selector: "edge",
    style: {
      width: "data(width)",
      "line-color": "#b9b3a2",
      "curve-style": "bezier",
      "target-arrow-shape": "none",
      opacity: 0.85,
    },
  },
  {
    selector: 'edge[kind = "discovery"]',
    style: {
      "line-color": "#8f8878",
      label: "data(label)",
      "font-family": "IBM Plex Mono, monospace",
      "font-size": 8.5,
      color: "#5c5748",
      "text-background-color": "#f7f4ec",
      "text-background-opacity": 0.9,
      "text-background-padding": 1.5,
    },
  },
  {
    selector: 'edge[kind = "structural"]',
    style: { "line-color": "#d3cdbc", opacity: 0.6 },
  },
  {
    // Boolean data fields need the "?field" truthy-check form — "[inferred = \"true\"]"
    // compares against the *string* "true" and silently never matches a real boolean.
    selector: "edge[?inferred]",
    style: { "line-style": "dashed", "line-dash-pattern": [2, 3] },
  },
  {
    selector: ".faded",
    style: { opacity: 0.06 },
  },
  {
    selector: ".hidden-band",
    style: { display: "none" },
  },
];

// A fresh layout object (new reference) is what tells react-cytoscapejs's
// own diff (patch.js: shallowObjDiff on the `layout` prop) to call
// cy.layout(...).run() again — recomputed only when the actual graph data
// changes, via the [elements] dependency, never on unrelated re-renders
// (e.g. toggling a band filter chip or selecting a node).
function useDiscoveryLayout(elements) {
  return useMemo(() => {
    if (elements.length === 0) return { name: "preset" };
    return {
      name: "fcose",
      animate: true,
      animationDuration: 500,
      randomize: true,
      fit: true,
      padding: 56,
      nodeDimensionsIncludeLabels: true,
      nodeRepulsion: 8000,
      idealEdgeLength: 95,
      quality: "default",
    };
  }, [elements]);
}

/**
 * Controlled by `selectedNodeId`/`onSelectNode` so the same selection can be
 * driven either by clicking a node here or a row in the rail list (App.jsx
 * owns the single source of truth). Clicking a node (or a rail row) both
 * fades non-neighbors here AND surfaces that node's detail in App's drawer.
 */
export default function DiscoveryGraph({ graphData, legend, selectedNodeId, onSelectNode }) {
  const cyRef = useRef(null);
  const [activeBands, setActiveBands] = useState(new Set(BANDS));
  const elements = useMemo(() => toElements(graphData), [graphData]);
  const layout = useDiscoveryLayout(elements);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.edges('[kind = "discovery"]').forEach((edge) => {
      const band = edge.data("band");
      edge.toggleClass("hidden-band", band && !activeBands.has(band));
    });
  }, [activeBands, elements]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("selected");
    if (!selectedNodeId) {
      cy.elements().removeClass("faded");
      return;
    }
    const node = cy.getElementById(selectedNodeId);
    if (node.empty()) return;
    node.addClass("selected");
    const neighborhood = node.closedNeighborhood();
    cy.elements().addClass("faded");
    neighborhood.removeClass("faded");
  }, [selectedNodeId, elements]);

  function toggleBand(band) {
    setActiveBands((prev) => {
      const next = new Set(prev);
      if (next.has(band)) next.delete(band);
      else next.add(band);
      return next;
    });
  }

  function handleCyInit(cy) {
    cyRef.current = cy;
    // react-cytoscapejs calls this `cy` prop on every mount AND every
    // update (see its componentDidMount/componentDidUpdate) — and, under
    // React.StrictMode in dev, the whole component mounts, unmounts, and
    // remounts once on its first appearance. Without this guard, tap
    // handlers would stack up (once per update) on whichever cy instance
    // survives. The guard is per-instance (cy.scratch), so a genuinely new
    // cy instance (after a StrictMode remount) still gets wired up once.
    if (cy.scratch("_saberlinkBound")) return;
    cy.scratch("_saberlinkBound", true);
    cy.on("tap", "node", (evt) => onSelectNode?.(evt.target.id()));
    cy.on("tap", (evt) => {
      if (evt.target === cy) onSelectNode?.(null);
    });
  }

  if (!graphData) {
    return (
      <div className="relative flex h-[70vh] min-h-[420px] items-center justify-center overflow-hidden rounded-2xl border border-gold-500/10 bg-ink-900/40">
        <p className="font-body text-sm italic text-parchment-200/40">
          El grafo de descubrimiento aparece acá después de una búsqueda.
        </p>
      </div>
    );
  }

  const typeSwatches = legend?.entity_types || [];

  return (
    <div className="overflow-hidden rounded-2xl border border-gold-500/15 bg-ink-900/60 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <span className="font-display text-[11px] font-medium tracking-[0.14em] text-gold-400/70">
            Relevancia
          </span>
          <div className="flex gap-1.5">
            {BANDS.map((band) => (
              <button
                key={band}
                onClick={() => toggleBand(band)}
                className="rounded-full px-2.5 py-1 font-mono text-[11px] font-semibold transition"
                style={{
                  background: activeBands.has(band) ? "rgba(204,159,69,0.12)" : "transparent",
                  color: activeBands.has(band) ? "#e3bd6f" : "#4a5468",
                  border: `1px solid ${activeBands.has(band) ? "rgba(204,159,69,0.4)" : "#1a2136"}`,
                }}
              >
                {band}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={() => cyRef.current?.fit(undefined, 40)}
          className="rounded-lg border border-ink-600 px-2.5 py-1 font-display text-xs font-medium text-parchment-200/60 transition hover:border-gold-500/40 hover:text-gold-400"
        >
          Encuadrar todo
        </button>
      </div>

      {/* The diagram itself reads like a bibliometric map (VOSviewer-style):
          light canvas, uniform circles sized by score, thin neutral edges,
          no arrows — legibility over decoration. */}
      <div className="overflow-hidden rounded-xl border border-black/5 bg-[#f7f4ec] shadow-inner">
        <CytoscapeComponent
          elements={elements}
          stylesheet={STYLESHEET}
          layout={layout}
          style={{ width: "100%", height: "68vh", minHeight: "400px" }}
          cy={handleCyInit}
          wheelSensitivity={0.2}
        />

        {typeSwatches.length > 0 && (
          <div className="flex flex-wrap gap-x-4 gap-y-1.5 border-t border-black/5 bg-[#f7f4ec] px-4 py-2.5 text-[10.5px] text-[#5c5748]">
            {typeSwatches.map((t) => (
              <span key={t.type} className="flex items-center gap-1.5">
                <span
                  className="inline-block h-2 w-2 rounded-full border border-black/10"
                  style={{ background: t.color }}
                />
                {t.label}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

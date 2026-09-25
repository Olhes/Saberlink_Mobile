# SaberLink — Arquitectura técnica

**Objetivo:** dado un ID de necesidad institucional (o cualquier entidad),
descubrir conexiones relevantes en las 3 capas de Data V1.0, priorizarlas,
explicarlas con evidencia trazable, y generar una oportunidad accionable —
en vivo, sobre consultas nuevas, no precargadas.

---

## Pipeline — núcleo obligatorio + plus opcional

```
data/raw/ (3 capas, sin modificar originales)
  01_institution · 02_people_curriculum · 03_knowledge_needs
        ↓
Ingesta + normalización → backend/processed/
        ↓                          ↘ [PLUS] PDF subido por usuario → Docling → texto
Representación                              (se trata como "necesidad temporal",
  · embeddings por CAMPO → ChromaDB           no se persiste como entidad oficial)
  · grafo de relaciones explícitas
    (Programa→Facultad, Investigador→Grupo, etc.) → networkx
        ↓
Descubrimiento + scoring
  score = w1·similitud_semántica + w2·dominio_compartido + w3·método_compartido + w4·proximidad_estructural
        ↓
Evidencia + explicación
  cada resultado apunta a: archivo · registro (ID) · campo exacto
        ↓
Generador de oportunidades
  reglas sobre combinaciones (necesidad + antecedente + investigador + capacidad → tipo de oportunidad)
        ↓
Interfaz
  backend/api (FastAPI) → frontend/ (React + Cytoscape.js)
        ↘ [PLUS] backend/saberlink/plus/ — Streamlit + pyvis, notebook, PDF vía Docling
```

**Regla:** todo lo marcado `[PLUS]` se construye después de que el núcleo
(ingesta → scoring → evidencia → oportunidad → interfaz básica) funcione
end-to-end con datos reales. Si el tiempo aprieta, lo primero que se recorta
es el plus, nunca el núcleo.

**Por qué embeddings por campo y no por entidad completa:** el contrato de
salida exige decir de qué *campo* salió la evidencia (ej. `methodology`, no
todo el `abstract`). Si se embeben entidades completas, se pierde esa
granularidad.

**Por qué no basta con similitud coseno:** el documento oficial lo dice
explícito — "similarity no equivale a relevance". El score tiene que
combinar señales explícitas (dominio, método, estructura), no solo cercanía
de texto.

---

## Contrato de salida (desde el día 1)

```json
{
  "source": {"id": "NEED-XXX", "type": "NEED", "official": true},
  "results": [
    {
      "target": {"id": "PRJ-XXX", "type": "PRJ"},
      "relevance": {"score": 0.81, "label": "alta", "breakdown": {"semantic": 0.32, "domain": 0.74, "method": 0.81, "structural": 0.4}},
      "explanation": "texto en lenguaje natural, basado en el breakdown",
      "evidence": [{"file": "projects.csv", "id": "PRJ-081", "field": "methodology", "snippet": "..."}]
    }
  ],
  "opportunities": [
    {"type": "RESEARCH_CONTINUITY", "opportunity": "...", "reason": "...", "priority": "alta", "related_entities": ["PRJ-081"]}
  ],
  "meta": {"top_k": 8, "elapsed_seconds": 1.2, "total_candidates_scored": 340}
}
```

Este es el dict que devuelve `saberlink.pipeline.run_query()` — es el único
punto de entrada real del sistema; todo lo demás (notebooks, Streamlit,
la API HTTP) es una capa delgada sobre esta misma función.

---

## Repositorio — estructura

```
saberlink/                       (repo raíz)
├── docs/                        arquitectura, capturas
├── backend/
│   ├── saberlink/                núcleo: ingest, domain_vocab, embeddings,
│   │                              vector_store, graph_build, graph_query,
│   │                              scoring, evidence, opportunities, pipeline,
│   │                              schema, config — más plus/ (Streamlit, pyvis,
│   │                              Docling), estrictamente aditivo
│   ├── api/                      FastAPI delgada sobre saberlink.pipeline
│   ├── notebooks/                demo y validación técnica
│   ├── tests/
│   └── processed/                 (gitignored, regenerable)
├── frontend/                     React + Vite + Cytoscape.js
└── data/
    └── raw/                       dataset oficial (gitignored, ver data/README.md)
```

---

## Stack — herramienta exacta por etapa

| Etapa | Herramienta |
|---|---|
| Ingesta + normalización | pandas |
| PDF (plus) | Docling |
| Embeddings | sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`) |
| Guardado de vectores | ChromaDB |
| Grafo de relaciones explícitas | networkx |
| Descubrimiento + scoring | Python propio (fórmula compuesta, sin librería externa) |
| Generador de oportunidades | reglas en Python (if/else), sin IA generativa |
| API | FastAPI + uvicorn, capa delgada sobre `pipeline.run_query` |
| Frontend | React + Vite + Tailwind |
| Grafo visual | Cytoscape.js (frontend) — pyvis se mantiene en `[PLUS]` como respaldo offline |
| Interfaz alternativa [PLUS] | Streamlit, Jupyter Notebook |

Sin cloud deploy — corre local. No se usa ningún LLM en ningún punto del
pipeline; toda explicación es un template de string sobre un breakdown ya
calculado, nunca texto generado por un modelo.

**Por qué scoring y oportunidades son código propio y no una librería:**
necesitamos controlar exactamente qué señales entran al score y poder
mostrar el desglose. Una librería que infiere relaciones vía LLM puede
inventar entidades — el documento oficial marca eso como falla técnica
grave.

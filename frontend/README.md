# SaberLink — Frontend

Interfaz web (React + Vite + Tailwind + Cytoscape.js) sobre la API en
`backend/api/`. Ver el README del repo raíz para la visión general del
proyecto y `docs/architecture.md` para la arquitectura completa.

## Desarrollo

```powershell
npm install
cp .env.example .env   # ajustar VITE_API_BASE si la API no corre en :8000
npm run dev
```

Requiere que `backend/api/main.py` esté corriendo (`uvicorn api.main:app --reload --port 8000`
desde `backend/`) — ver el README raíz.

## Estructura

```
src/
├── api/client.js          cliente HTTP contra la API (axios)
├── components/            búsqueda, tarjetas de resultado, evidencia, oportunidades
├── graph/DiscoveryGraph.jsx   grafo de descubrimiento (Cytoscape.js + fcose)
└── App.jsx                 orquesta todo el flujo
```

Esta capa es estrictamente aditiva: consume solo la API HTTP, nunca importa
Python directamente. Si se elimina esta carpeta entera, `backend/` sigue
funcionando por su cuenta (CLI, notebooks, Streamlit).

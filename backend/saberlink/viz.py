"""Shared visual vocabulary for entity types and relevance bands.

Single source of truth for colors/labels used by both the [PLUS] pyvis
export (backend/saberlink/plus/pyvis_export.py) and the API's /graph and
/meta/legend endpoints (backend/api/main.py) — so the two never drift on
palette choices. No dependency on pyvis, networkx or FastAPI: safe for
either side to import.
"""

from __future__ import annotations

ENTITY_TYPE_COLORS: dict[str, str] = {
    "FAC": "#6b7280", "PRG": "#9ca3af", "GRP": "#2563eb", "LIN": "#60a5fa",
    "CAP": "#0891b2", "SRC": "#94a3b8", "INV": "#16a34a", "EXP": "#4ade80",
    "SUB": "#a855f7", "COM": "#c084fc", "LO": "#d8b4fe",
    "NEED": "#dc2626", "PRJ": "#ea580c", "THS": "#f59e0b", "PUB": "#eab308",
}
ENTITY_TYPE_LABELS: dict[str, str] = {
    "FAC": "Facultad", "PRG": "Programa", "GRP": "Grupo de investigación",
    "LIN": "Línea de investigación", "CAP": "Capacidad institucional",
    "SRC": "Fuente (metadata)", "INV": "Investigador", "EXP": "Expertise",
    "SUB": "Asignatura", "COM": "Competencia", "LO": "Resultado de aprendizaje",
    "NEED": "Necesidad", "PRJ": "Proyecto", "THS": "Tesis", "PUB": "Publicación",
}
DEFAULT_COLOR = "#d1d5db"
SCORE_BAND_COLORS = {"alta": "#16a34a", "media": "#f59e0b", "baja": "#9ca3af"}

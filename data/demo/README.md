# Datos demo de SaberLink

SaberLink puede ejecutarse sin descargar ni copiar datos de otro hackaton.

Cuando `backend/processed/` no existe, la API usa el conocimiento demo incluido en `backend/api/demo_data.py`. Ese modo permite probar:

- consulta por ID (`NEED-DEMO`);
- texto libre;
- carga de cualquier PDF valido;
- ranking, mapa, evidencia y oportunidades.

El PDF se acepta para demostrar el flujo de carga, pero en modo demo no se extrae su contenido. Para activar el procesamiento real de PDFs se necesita construir el indice institucional y tener Docling instalado.

## Datos reales opcionales

Si mas adelante quieres usar un dataset propio, colocalo en `data/raw/` con la estructura que documenta `data/README.md` y regenera `backend/processed/`. La API cambiara automaticamente de modo `demo` a modo `indexed`.

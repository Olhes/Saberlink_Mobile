# SaberLink — Knowledge Nexus LATAM

Dado el ID de una necesidad institucional (o cualquier entidad de Data V1.0),
SaberLink descubre conexiones relevantes entre las 3 capas del dataset, las
prioriza con un score explicado, las sustenta con evidencia trazable a
archivo/registro/campo, y genera una oportunidad accionable — en vivo, sobre
consultas nuevas, no precargadas.

Arquitectura completa y decisiones de diseño: [`docs/architecture.md`](docs/architecture.md).

## Estructura del repositorio

```
saberlink/
├── docs/            arquitectura, capturas
├── backend/         núcleo Python (saberlink/) + API FastAPI (api/) + notebooks + tests
├── frontend/        interfaz web (React + Vite + Cytoscape.js)
└── data/            dataset oficial (gitignorado — ver data/README.md)
```

### Biblioteca de PDFs del MVP

La app móvil incluye una pestaña `Biblioteca` para seleccionar varios PDFs.
Cada archivo se guarda en `backend/processed/user_library/`, se extrae por
páginas, se divide en fragmentos y se vectoriza localmente con
`sentence-transformers` en ChromaDB. La consulta de Biblioteca busca contra
todos los PDFs del proyecto y devuelve ranking con archivo, página y evidencia.

Endpoints:

```text
GET  /projects/mi-investigacion/documents
POST /projects/mi-investigacion/documents
POST /projects/mi-investigacion/query
```

Este flujo ya es independiente del dataset institucional y no requiere
Cohere. La clave de Cohere, si se usa, debe vivir únicamente en
`backend/.env` como `COHERE_API_KEY`.
## Stack

| Etapa | Herramienta |
|---|---|
| Ingesta + normalización | pandas |
| Embeddings | sentence-transformers (`all-mpnet-base-v2`, 768 dims) |
| Guardado de vectores | ChromaDB (persistente local, 1 colección) |
| Grafo de relaciones explícitas | networkx |
| Descubrimiento + scoring | Python propio, sin librería externa |
| Generador de oportunidades (núcleo) | reglas en Python (if/else), sin IA generativa |
| Generador de oportunidades [PLUS] | Cohere LLM (command-r-plus-08-2024) |
| API | FastAPI + uvicorn |
| Frontend | React + Vite + Tailwind + Cytoscape.js |
| Interfaz alternativa [PLUS] | Streamlit + pyvis, Jupyter Notebook |
| PDF de usuario [PLUS] | Docling |
| PDF mejorado [PLUS] | LightRAG + Cohere (búsqueda híbrida + re-ranking + oportunidades IA) |

El núcleo no usa LLMs — la explicación en texto es 100% generada por templates
de string sobre el breakdown ya calculado. Sin cloud deploy — corre local.

La integración con LightRAG + Cohere es opcional ([PLUS]) y solo se activa para
PDFs subidos por usuario, manteniendo el núcleo sin dependencias externas.

## Instalación

```powershell
cd backend
python -m venv .venv        # opcional, recomendado
pip install -r requirements.txt
```

Requiere Python 3.11+. La primera vez que se use el modelo de embeddings,
`sentence-transformers` lo descarga de Hugging Face (~420 MB) — no requiere
`HF_TOKEN` para uso anónimo (con límite de tasa más bajo).

Colocá el dataset oficial en `data/raw/` — ver [`data/README.md`](data/README.md).

Para usar las funciones avanzadas de PDF (LightRAG + Cohere), copia `backend/.env.example`
a `backend/.env` y configura tu API key de Cohere.

## Cómo reproducir la demo, de cero

```powershell
cd backend

# 1. Construir todo processed/ desde los datos crudos (o correr notebooks/02_ingest_and_graph.ipynb)
python -m saberlink.ingest
python -m saberlink.domain_vocab
python -m saberlink.vector_store   # tarda 1-2 min: descarga el modelo + embebe ~10.7k campos
python -m saberlink.graph_build

# 2. Probar una consulta por ID existente
python -m saberlink.demo NEED-001

# 2b. O sin ID: describir una necesidad en texto libre (se trata como
#     necesidad temporal, nunca se persiste — mismo mecanismo que el PDF
#     vía Docling, ver sección [PLUS])
python -m saberlink.demo --title "Detección temprana de plagio" --text "Necesitamos identificar similitud entre entregas de estudiantes..."
```

La primera consulta de un proceso tarda ~20s (carga el modelo de embeddings y
los índices en memoria). Las siguientes consultas del mismo proceso corren en
1-2s — para la demo en vivo, dejar el proceso corriendo desde antes de que el
evaluador dé el ID, no reiniciarlo por cada consulta.

## Interfaz web (backend + frontend)

### Arranque demo sin dataset externo

El backend incluye un conocimiento demo autonomo. Si no existe
`backend/processed/`, puedes iniciar la API despues de instalar sus
dependencias y probar ID, texto libre y PDF sin copiar datos de otro evento:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\run-demo.ps1
```

La API indicara `"mode": "demo"` en `/health`. Cuando exista un indice real,
usara automaticamente `"mode": "indexed"`.

```powershell
# Terminal 1 — API
cd backend
uvicorn api.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Abre `http://localhost:5173`. Permite buscar por ID o texto libre, ver el
ranking, la explicación/evidencia, las oportunidades generadas y el grafo de
descubrimiento interactivo (Cytoscape.js).

## MVP móvil Android (Expo + React Native)

La migración móvil vive en [`mobile/`](mobile/).

```powershell
cd mobile
npm install
Copy-Item .env.example .env
npx expo start
```

Con Expo Go se puede probar el flujo completo contra el modo demo autonomo de
la API, sin descargar datasets de otro hackaton. Para consultar el backend
desde un teléfono, configura `EXPO_PUBLIC_API_BASE` con
la IP local de tu PC.

## Sistema de Monetización y Límites de Uso

SaberLink incluye un sistema completo de monetización con RevenueCat SDK y límites de uso por suscripción.

### Planes de Suscripción

- **Gratis**: 5 PDFs/mes, 20 consultas de texto/mes
- **Pro Mensual**: 50 PDFs/mes, 500 consultas de texto/mes  
- **Pro Anual**: 100 PDFs/mes, 1000 consultas de texto/mes

### Backend - Sistema de Límites

El backend incluye un módulo de tracking de uso (`backend/api/usage_limits.py`) que:

- Rastrea uploads de PDFs y consultas de texto por usuario
- Valida límites según el plan de suscripción
- Reinicia contadores mensualmente
- Proporciona endpoints para gestión de suscripciones

**Endpoints nuevos:**
- `GET /usage/limits` - Obtener uso actual de un usuario
- `GET /usage/tiers` - Obtener planes disponibles
- `POST /usage/subscription` - Actualizar suscripción via RevenueCat
- `POST /usage/validate-pdf` - Validar si usuario puede subir PDF
- `POST /usage/validate-text` - Validar si usuario puede hacer consulta

### Frontend - Integración RevenueCat

El frontend web incluye:

- Página de planes/pricing con visualización de uso actual
- Integración con RevenueCat SDK (`@revenuecat/purchases-js`)
- Indicadores de uso en tiempo real en el header
- Sistema de user ID persistente en localStorage

**Configuración:**
```bash
cd frontend
# En .env.local
VITE_REVENUECAT_PUBLIC_KEY=tu_clave_publica_revenuecat
```

### App Móvil - RevenueCat Integration

La app móvil ya incluye RevenueCat SDK (`react-native-purchases`) con:

- Configuración automática via `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY`
- Sistema de paywall/upgrade con flujo de compra
- Tracking de uso con user ID persistente (AsyncStorage)
- Indicadores de uso en el header de la app

**Configuración:**
```bash
cd mobile
# En .env
EXPO_PUBLIC_REVENUECAT_ANDROID_KEY=tu_clave_android_revenuecat
```

### Flujo de Compra

1. Usuario hace clic en "PRO" o accede a página de planes
2. Sistema muestra planes disponibles con límites actuales
3. Usuario selecciona plan y completa compra via RevenueCat
4. Backend actualiza tier del usuario según datos de RevenueCat
5. Límites de uso se actualizan inmediatamente
6. Contadores se reinician mensualmente automáticamente

### Notas Importantes

- Para compras reales en móvil, necesitas crear un development build con EAS
- En web, RevenueCat funciona directamente en el navegador
- Los límites se aplican tanto para PDFs como consultas de texto
- El sistema funciona en modo demo sin configurar RevenueCat
- IDs de usuario se generan automáticamente y persisten localmente

## Mecanismo de descubrimiento y priorización

Cuatro señales, combinadas en una fórmula compuesta transparente
(`backend/saberlink/scoring.py`):

- **Semántica** (`w1=0.35`): similitud coseno máxima sobre una tabla explícita
  de pares de campos por tipo de entidad (ej. NEED.description ↔
  PRJ.problem_statement). Usa la similitud cruda, no reescalada, para que sea
  comparable entre distintos tipos de candidato en un mismo ranking.
- **Dominio** (`w2=0.30`): coeficiente de solape entre los términos de dominio
  de la fuente y del candidato, ponderado por frecuencia inversa de documento
  (un término genérico compartido por decenas de registros pesa poco; uno
  específico compartido por pocos, pesa mucho). Necesario porque
  `institutional_needs.csv` no tiene columna de dominio propia — los términos
  se extraen léxicamente contra un vocabulario controlado construido desde
  las columnas estructuradas del resto del dataset.
- **Método** (`w3=0.20`): similitud coseno entre campos de metodología
  (`PRJ.methodology`, `THS.methodology`, `INV.methodological_expertise`). No
  aplica cuando la fuente es NEED (sin campo de metodología, por diseño) — en
  ese caso el peso se redistribuye entre las demás señales, nunca se pone en 0.
- **Estructural** (`w4=0.15`, deliberadamente bajo): distancia de camino +
  solape de vecinos en el grafo de relaciones explícitas. Peso bajo a
  propósito para no premiar "misma facultad" por sí solo.

Un campo vacío en una entidad puntual se marca `not_available` y se excluye
(con renormalización de pesos) — nunca se trata como 0, porque vacío no
significa "el atributo no existe".

## Evidencia y explicabilidad

Cada resultado expone `evidence: [...]` con `{file, id, field, snippet}`,
releído de `entities.parquet` en el momento de la consulta (nunca de una
copia guardada, para que la evidencia no pueda desactualizarse). La
`explanation` es un template de string que solo inserta valores ya presentes
en el breakdown — no puede introducir una afirmación no sustentada, y se
marca `generated_text: true` para distinguirla visualmente de la evidencia.

## Validación técnica

`backend/notebooks/05_validation.ipynb` construye un set de 3 casos etiquetados
a mano, de dominios distintos (educación, salud, finanzas), con relevancia
determinada por **keyword matching independiente del ranking del pipeline**
(no circular). Reporta Precision@5, Recall@5, cobertura de evidencia
(verificación de que cada snippet citado existe verbatim en el dato crudo) y
latencia por consulta. `backend/tests/test_pipeline_live.py` prueba de forma
automatizada que no existe una respuesta cacheada: dos llamadas con el mismo
ID re-embeben y re-computan ambas veces.

## Features [PLUS]

Estrictamente aditivas — nada en `backend/saberlink/` (fuera de
`backend/saberlink/plus/`) importa de `saberlink/plus/`, y nada del núcleo
importa de `backend/api/` tampoco (verificado por
`backend/tests/test_plus_isolation.py`). Si el tiempo aprieta, tanto
`saberlink/plus/` como `frontend/` se pueden borrar enteros sin romper el
núcleo — el flujo por notebook/CLI sigue funcionando.

**PDF subido → necesidad temporal (Docling)**

```python
from saberlink.plus.docling_intake import pdf_to_temp_need
from saberlink import pipeline

profile = pdf_to_temp_need("ruta/al/documento.pdf")
out = pipeline.run_query(raw_text_profile=profile, top_k=5)
print(out["source"])  # {"id": "TEMP-xxxxxxxx", "type": "NEED", "official": False}
```

El perfil extraído nunca se escribe en `institutional_needs.csv` ni en
`entities.parquet` — vive solo en memoria durante esa llamada.

**PDF mejorado con LightRAG + Cohere (búsqueda híbrida)**

```python
from saberlink import pipeline

# Requiere COHERE_API_KEY environment variable
out = pipeline.run_hybrid_query("ruta/al/documento.pdf", use_cohere=True, top_k=5)
print(out["meta"])  # {"cohere_used": true, "institutional_results": X, "pdf_results": Y}
```

Este modo combina:
- Búsqueda en conocimiento institucional (sentence-transformers + ChromaDB)
- Búsqueda en grafo del PDF (LightRAG)
- Re-ranking con Cohere API (modelo `rerank-english-v3.0`)
- Generación de oportunidades mejoradas con LLM (modelo `command-r-plus-08-2024`, en español)

Para usar esta funcionalidad, instala las dependencias adicionales:
```powershell
pip install lightrag cohere pymupdf4llm
```

Configura tu API key en `backend/.env`:
```bash
COHERE_API_KEY=tu-api-key-aqui
```

**Uso via API:**

```powershell
# PDF estándar (Docling)
POST /query/pdf
Content-Type: multipart/form-data
file: <archivo.pdf>

# PDF mejorado (LightRAG + Cohere)
POST /query/pdf/enhanced
Content-Type: multipart/form-data
file: <archivo.pdf>
use_cohere: true
```

**Subgrafo interactivo (pyvis, respaldo offline)**

```powershell
cd backend
python -m saberlink.plus.pyvis_export NEED-001
# escribe processed/subgraphs/NEED-001_discovery.html — abrir en el navegador

python -m saberlink.plus.pyvis_export NEED-001 ego
# vista alterna: vecindario crudo del grafo institucional (radio 2, sin filtrar)
```

**Interfaz Streamlit (respaldo si el frontend React no está disponible)**

```powershell
cd backend
streamlit run saberlink/plus/streamlit_app.py
```

Permite escribir cualquier ID, ver el ranking, la explicación/evidencia del
resultado #1, las oportunidades generadas, y opcionalmente el subgrafo
(pyvis) embebido. Si ni Streamlit ni el frontend React están disponibles,
`backend/notebooks/06_live_demo.ipynb` cubre exactamente el mismo flujo.

## Ejecutar los tests

```powershell
cd backend
python -m pytest -q
```

## Limitaciones conocidas

- Las 7 reglas del generador de oportunidades están redactadas pensando en el
  flujo principal (consulta por `NEED-*`); funcionan también con otros tipos
  de fuente (`INV-*`, `PRJ-*`, `GRP-*`) pero el texto generado puede sonar
  menos natural en esos casos.
- El vocabulario de dominio es puramente léxico (substring matching), no usa
  sinónimos ni stemming — un término con una variante morfológica distinta a
  las del vocabulario no se detecta.
- No se cubren a fondo las 42 necesidades; el pipeline procesa toda la data
  igual, pero la validación profunda se enfoca en 2-4 casos de dominios
  distintos (según la guía oficial de alcance).

## Declaración de tecnologías y componentes externos

- Modelo preentrenado (núcleo): `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
  (Hugging Face, descarga anónima, sin fine-tuning).
- Modelos preentrenados (PLUS, solo si se usa `docling_intake.py`): modelos de
  layout/OCR de Docling (`docling-project/docling-layout-heron`, RapidOCR
  vía ONNX Runtime) — usados únicamente para extraer texto de un PDF subido
  por el usuario, nunca para inferir relaciones institucionales.
- Sin APIs externas, sin servicios cloud, sin LLM en ningún punto del pipeline.
- Sin datasets complementarios — todo el conocimiento viene de Data V1.0.

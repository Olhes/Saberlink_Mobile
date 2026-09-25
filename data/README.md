# Datos de SaberLink

La aplicacion no depende de los datos de otro hackaton para mostrar su MVP.
Si no existe `data/raw/` ni `backend/processed/`, la API inicia en modo demo
con datos propios incluidos en `backend/api/demo_data.py`. Ver
[`data/demo/README.md`](demo/README.md).

Los datos institucionales reales son opcionales y solo deben usarse si tienes
permiso para redistribuirlos.

## Datos institucionales opcionales

Copiá las tres carpetas oficiales dentro de `data/raw/`, de forma que quede:

```
data/raw/
├── 01_institution/
├── 02_people_curriculum/
└── 03_knowledge_needs/
```

`backend/saberlink/config.py::DATA_ROOT` apunta exactamente a `data/raw/`. Una
vez colocado, regenerá `backend/processed/` (también gitignorado, 100%
derivable) desde `backend/`:

```powershell
python -m saberlink.ingest
python -m saberlink.domain_vocab
python -m saberlink.vector_store   # descarga el modelo de embeddings, 1-2 min
python -m saberlink.graph_build
```

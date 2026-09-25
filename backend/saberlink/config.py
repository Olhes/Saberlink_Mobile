"""Central paths, model name, scoring weights and thresholds. No secrets here."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent

# Original Data V1.0 — read-only, never written to. Lives at <repo_root>/data/raw
# (gitignored by default — see data/README.md for how to place it there).
DATA_ROOT = PROJECT_ROOT.parent / "data" / "raw"
INSTITUTION_DIR = DATA_ROOT / "01_institution"
PEOPLE_DIR = DATA_ROOT / "02_people_curriculum"
NEEDS_DIR = DATA_ROOT / "03_knowledge_needs"
DOCUMENTS_DIR = NEEDS_DIR / "documents"

# Derived artifacts — 100% regenerable from DATA_ROOT.
PROCESSED_DIR = PROJECT_ROOT / "processed"
USER_LIBRARY_DIR = PROCESSED_DIR / "user_library"
USER_LIBRARY_DB = USER_LIBRARY_DIR / "library.sqlite3"
USER_LIBRARY_CHROMA_DIR = USER_LIBRARY_DIR / "chroma"
ENTITIES_PARQUET = PROCESSED_DIR / "entities.parquet"
FIELDS_INDEX_PARQUET = PROCESSED_DIR / "fields_index.parquet"
DOMAIN_VOCAB_JSON = PROCESSED_DIR / "domain_vocab.json"
GRAPH_PICKLE = PROCESSED_DIR / "graph.gpickle"
CHROMA_DIR = PROCESSED_DIR / "chroma"
VALIDATION_LABELS_JSON = PROCESSED_DIR / "validation_labels.json"

# Embedding model.
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
CHROMA_COLLECTION_NAME = "saberlink_fields"

# Scoring weights (semantic, domain, method, structural). Renormalized at
# query time over whichever components are schema-applicable for the given
# source/candidate entity-type pair — see saberlink/scoring.py.
DEFAULT_WEIGHTS = {
    "semantic": 0.35,
    "domain": 0.30,
    "method": 0.20,
    "structural": 0.15,
}

# Opportunity-rule thresholds.
DOMAIN_T = 0.5
METHOD_T = 0.5
SIG_T = 0.4

# Relevance label bands (absolute scale).
LABEL_BANDS = [
    (0.70, "alta"),
    (0.45, "media"),
    (0.0, "baja"),
]

DEFAULT_TOP_K = 8

# LightRAG integration [PLUS]
LIGHTRAG_DIR = PROJECT_ROOT / "knowledge_graph" / "lightrag_storage"
LIGHTRAG_GRAPH_FILE = LIGHTRAG_DIR / "graph.ml"
LIGHTRAG_EMBEDDINGS_FILE = LIGHTRAG_DIR / "embeddings.kv"

# Cohere API [PLUS] - set via environment variable COHERE_API_KEY
# Note: Cohere API key should start with "cohere_" prefix
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
COHERE_MODEL = "command-r-plus-08-2024"  # Updated model name
COHERE_EMBEDDING_MODEL = "embed-multilingual-v3.0"

"""Runtime configuration. Every value can be overridden with an environment variable."""
from __future__ import annotations

import os
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "y", "on"}


BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BACKEND_DIR / "data"))
SEED_DIR = DATA_DIR / "seed"
KB_DIR = DATA_DIR / "kb"
RUNTIME_DIR = Path(os.getenv("RUNTIME_DIR", DATA_DIR / "runtime"))
DB_PATH = Path(os.getenv("DB_PATH", RUNTIME_DIR / "schemesathi.db"))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", RUNTIME_DIR / "chroma"))
INGEST_DIR = Path(os.getenv("INGEST_DIR", RUNTIME_DIR / "ingested"))

# Embeddings. "sentence-transformers" is the real multilingual model; "hash" is a tiny
# offline fallback used only by unit tests (it is NOT cross-lingual).
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "sentence-transformers")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "kb_docs")

# LLM. MOCK_LLM=true runs the whole pipeline with deterministic heuristics instead of a model.
MOCK_LLM = _bool("MOCK_LLM", False)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "60"))
# Use the LLM to write free-text answers from retrieved passages (structured answers are
# always composed from tool output by code, so numbers cannot drift between languages).
LLM_COMPOSE = _bool("LLM_COMPOSE", True)

DEFAULT_TIMEZONE = "+05:30"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
AUTH_COOKIE_SECURE = _bool("AUTH_COOKIE_SECURE", False)

for _d in (RUNTIME_DIR, CHROMA_DIR, INGEST_DIR):
    _d.mkdir(parents=True, exist_ok=True)

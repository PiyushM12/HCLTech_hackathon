"""ChromaDB (persisted to disk) + multilingual sentence-transformers embeddings (R2).

We embed ourselves instead of using Chroma's default function so the model, the e5
"query:"/"passage:" prefixes and the comparison configurations are explicit."""
from __future__ import annotations

import hashlib
import math
import threading
from typing import Any

from .. import config

_lock = threading.Lock()
_embedder = None
_client = None


class Embedder:
    def __init__(self, backend: str, model_name: str):
        self.backend = backend
        self.model_name = model_name
        self.model = None
        if backend == "sentence-transformers":
            from sentence_transformers import SentenceTransformer
            try:  # cached model first: start-up must not depend on huggingface.co being reachable
                self.model = SentenceTransformer(model_name, device="cpu", local_files_only=True)
            except Exception:
                self.model = SentenceTransformer(model_name, device="cpu")
            # long-context models (bge-m3: 8192) need far more RAM; our chunks are one section each
            if (self.model.max_seq_length or 0) > 512:
                self.model.max_seq_length = 512
        self.e5 = "e5" in model_name.lower()
        self.batch_size = 8 if "bge-m3" in model_name.lower() else 32

    def _prefix(self, texts: list[str], kind: str) -> list[str]:
        if self.e5:
            return [f"{kind}: {t}" for t in texts]
        return texts

    def embed(self, texts: list[str], kind: str = "passage") -> list[list[float]]:
        if self.model is None:
            return [_hash_embed(t) for t in texts]
        vecs = self.model.encode(self._prefix(texts, kind), normalize_embeddings=True,
                                 batch_size=self.batch_size, show_progress_bar=False)
        return [v.tolist() for v in vecs]


def _hash_embed(text: str, dim: int = 384) -> list[float]:
    """Character 3-gram hashing. Test-only fallback; NOT cross-lingual."""
    v = [0.0] * dim
    t = f"  {text.lower()}  "
    for i in range(len(t) - 2):
        h = int(hashlib.md5(t[i:i + 3].encode()).hexdigest()[:8], 16)
        v[h % dim] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def get_embedder(model_name: str | None = None) -> Embedder:
    global _embedder
    name = model_name or config.EMBEDDING_MODEL
    with _lock:
        if _embedder is None or _embedder.model_name != name:
            _embedder = Embedder(config.EMBEDDING_BACKEND, name)
        return _embedder


def get_client():
    global _client
    with _lock:
        if _client is None:
            import chromadb
            from chromadb.config import Settings
            _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR),
                                                settings=Settings(anonymized_telemetry=False))
        return _client


def get_collection(name: str | None = None):
    return get_client().get_or_create_collection(name or config.CHROMA_COLLECTION,
                                                 metadata={"hnsw:space": "cosine"})


def _clean_meta(meta: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in meta.items():
        if v is None:
            v = ""
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        else:
            out[k] = str(v)
    return out


def upsert_chunks(source_id: str, chunks: list[dict[str, Any]], collection=None,
                  embedder: Embedder | None = None) -> int:
    col = collection or get_collection()
    emb = embedder or get_embedder()
    try:
        col.delete(where={"source_id": source_id})
    except Exception:
        pass
    if not chunks:
        return 0
    texts = [c["text"] for c in chunks]
    vectors = emb.embed(texts, "passage")
    col.upsert(ids=[f"{source_id}::{i}" for i in range(len(chunks))], embeddings=vectors,
               documents=texts, metadatas=[_clean_meta(c["meta"]) for c in chunks])
    return len(chunks)


def search(query: str, k: int = 6, scheme_ids: list[str] | None = None, as_of: str | None = None,
           max_authority: int = 5, collection=None, embedder: Embedder | None = None) -> list[dict[str, Any]]:
    col = collection or get_collection()
    total = col.count()
    if total == 0:
        return []
    emb = embedder or get_embedder()
    qv = emb.embed([query], "query")[0]
    fetch = min(total, max(k * 5, 20))
    res = col.query(query_embeddings=[qv], n_results=fetch, include=["documents", "metadatas", "distances"])
    hits: list[dict[str, Any]] = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        score = 1.0 - float(dist)
        if int(meta.get("authority_level") or 5) > max_authority:
            continue
        if as_of and meta.get("valid_until") and meta["valid_until"] < as_of:
            continue
        hit = {"source_id": meta.get("source_id"), "section": meta.get("section", ""), "text": doc,
               "score": round(score, 4), "meta": meta,
               "future": bool(as_of and meta.get("effective_from") and meta["effective_from"] > as_of)}
        if scheme_ids and meta.get("scheme_id") in scheme_ids:
            hit["score"] = round(hit["score"] + 0.03, 4)  # light boost for the scheme in play
        hits.append(hit)
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:k]


def get_section(source_id: str, section_prefix: str, collection=None) -> dict[str, Any] | None:
    """Fetch one specific chunk (used to pin the exact guideline section a rule cites)."""
    col = collection or get_collection()
    res = col.get(where={"source_id": source_id}, include=["documents", "metadatas"])
    num = (section_prefix or "").split(" ")[0]
    best = None
    for doc, meta in zip(res["documents"], res["metadatas"]):
        sec = meta.get("section", "")
        if sec.split(" ")[0] == num:
            return {"source_id": source_id, "section": sec, "text": doc, "score": 1.0, "meta": meta, "pinned": True}
        if best is None:
            best = {"source_id": source_id, "section": sec, "text": doc, "score": 1.0, "meta": meta, "pinned": True}
    return best if not num else None


def count() -> int:
    try:
        return get_collection().count()
    except Exception:
        return -1

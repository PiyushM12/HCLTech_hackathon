"""Ingestion of documents and grievances: seed build at start-up and live POST /ingest (R14).
 ingesting the decoment """
from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .. import config, db, loader
from . import effects as fx
from . import vectorstore as vs

DOC_TYPES = {"guideline", "policy", "circular", "amendment", "faq", "grievance", "community"}


class SourceMeta(BaseModel):
    """Source Register fields (Annex B); also the metadata JSON of POST /ingest."""
    source_id: str = Field(min_length=2, max_length=64)
    doc_type: str
    title: str = ""
    language: Literal["hi", "en", "kn", "ta", "mixed"] = "en"
    authority_level: int = Field(ge=1, le=5, default=2)
    scheme_id: Optional[str] = ""
    last_updated: Optional[str] = ""
    effective_from: Optional[str] = ""
    valid_until: Optional[str] = ""
    supersedes: Optional[str] = ""
    provenance: Optional[str] = ""
    synthetic: Optional[str] = "Y"
    file: Optional[str] = ""

    @field_validator("doc_type")
    @classmethod
    def _doc_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in DOC_TYPES:
            raise ValueError(f"doc_type must be one of {sorted(DOC_TYPES)}")
        return v

    @field_validator("last_updated", "effective_from", "valid_until")
    @classmethod
    def _date(cls, v: Optional[str]) -> str:
        v = (v or "").strip()
        if v:
            datetime.strptime(v, "%Y-%m-%d")
        return v

    @field_validator("authority_level", mode="before")
    @classmethod
    def _auth(cls, v: Any) -> int:
        return int(v) if v not in (None, "") else 2


def chunk_markdown(meta: SourceMeta, text: str) -> list[dict[str, Any]]:
    title_m = re.search(r"^#\s+(.+)$", text, re.M)
    title = meta.title or (title_m.group(1).strip() if title_m else meta.source_id)
    parts = re.split(r"^##\s+", text, flags=re.M)
    chunks = []
    base = meta.model_dump(exclude={"file"})
    base["title"] = title
    preamble = parts[0].strip()
    if preamble:
        chunks.append({"text": preamble, "meta": {**base, "section": "0 Header"}})
    for p in parts[1:]:
        heading, _, body = p.partition("\n")
        heading = heading.strip()
        body = body.strip()
        chunks.append({"text": f"{title}\n{heading}\n{body}", "meta": {**base, "section": heading}})
    return chunks


def chunk_grievance(meta: SourceMeta, g: dict[str, Any]) -> list[dict[str, Any]]:
    base = meta.model_dump(exclude={"file"})
    base["title"] = meta.title or g.get("citizen_question", "")[:80]
    text = f"Question: {g.get('citizen_question', '')}\nResolution: {g.get('resolution', '')}"
    return [{"text": text, "meta": {**base, "section": "grievance"}}]


def ingest(meta: SourceMeta, content: str, kind: Literal["md", "json"]) -> dict[str, Any]:
    if kind == "json":
        g = json.loads(content)
        if not isinstance(g, dict):
            raise ValueError("grievance JSON must be an object")
        chunks = chunk_grievance(meta, g)
        scan_text = f"{g.get('citizen_question', '')}\n{g.get('resolution', '')}"
        if not meta.scheme_id and g.get("scheme_id"):
            meta.scheme_id = g["scheme_id"]
    else:
        chunks = chunk_markdown(meta, content)
        scan_text = content
    flagged = fx.contains_instructions(scan_text)
    for c in chunks:
        c["meta"]["contains_instructions"] = "Y" if flagged else "N"
    n = vs.upsert_chunks(meta.source_id, chunks)
    found = fx.extract_effects(meta.model_dump(), content if kind == "md" else scan_text)
    now = datetime.now().isoformat(timespec="seconds")
    title = chunks[0]["meta"]["title"] if chunks else meta.title
    with db.get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO sources (source_id, doc_type, title, language, authority_level, scheme_id,
               last_updated, effective_from, valid_until, supersedes, provenance, synthetic, file, content,
               contains_instructions, ingested_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (meta.source_id, meta.doc_type, title, meta.language, meta.authority_level, meta.scheme_id or "",
             meta.last_updated, meta.effective_from, meta.valid_until, meta.supersedes, meta.provenance,
             meta.synthetic, meta.file, content, "Y" if flagged else "N", now))
        conn.execute("DELETE FROM doc_effects WHERE source_id=?", (meta.source_id,))
        for e in found:
            conn.execute(
                """INSERT INTO doc_effects (source_id, scheme_id, effect_type, field, new_value, values_json,
                   effective_from, last_updated, authority_level) VALUES (?,?,?,?,?,?,?,?,?)""",
                (e["source_id"], e["scheme_id"], e["effect_type"], e["field"], e.get("new_value", ""),
                 json.dumps(e.get("values", [])), e["effective_from"], e["last_updated"], e["authority_level"]))
    return {"source_id": meta.source_id, "chunks": n, "effects": found, "contains_instructions": flagged}


def build_kb(force: bool = False) -> dict[str, Any]:
    """Load seed CSVs and ingest every document in the Source Register."""
    db.init_db()
    report: dict[str, Any] = {"seed": loader.load_dir(config.SEED_DIR), "documents": 0, "chunks": 0, "errors": []}
    citizens_dir = config.DATA_DIR / "synthetic"
    if citizens_dir.exists():
        report["synthetic"] = loader.load_dir(citizens_dir)
    register = config.DATA_DIR / "source_register.csv"
    with register.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not force:
        with db.get_conn() as conn:
            have = {r["source_id"] for r in db.rows(conn, "SELECT source_id FROM sources")}
        if have >= {r["source_id"] for r in rows} and vs.count() > 0:
            report["skipped"] = "already built"
            return report
    for r in rows:
        try:
            meta = SourceMeta(**r)
            path = config.DATA_DIR / r["file"]
            content = path.read_text(encoding="utf-8")
            res = ingest(meta, content, "json" if path.suffix == ".json" else "md")
            report["documents"] += 1
            report["chunks"] += res["chunks"]
        except Exception as e:  # report and continue: one bad row must not stop the build
            report["errors"].append(f"{r.get('source_id')}: {e}")
    return report


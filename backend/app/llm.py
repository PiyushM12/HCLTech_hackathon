"""Local LLM access through Ollama (R1, 5.2 tips).

Small local models are unreliable at JSON, so every structured call is validated with
Pydantic, retried once with the validation error fed back, and the caller falls back to
deterministic code if it still fails. MOCK_LLM=true skips the model entirely."""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from . import config

M = TypeVar("M", bound=BaseModel)


@dataclass
class LLMStats:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"calls": self.calls, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens, "latency_ms": round(self.latency_ms, 1),
                "errors": self.errors[-5:]}


class LLM:
    def __init__(self) -> None:
        self.mock = config.MOCK_LLM
        self.model = config.OLLAMA_MODEL
        self.url = config.OLLAMA_URL.rstrip("/")
        self._available: bool | None = None
        self._checked_at = 0.0
        self._lock = threading.Lock()

    @property
    def mode(self) -> str:
        return "mock" if self.mock else "ollama"

    def available(self) -> bool:
        if self.mock:
            return False
        with self._lock:
            if self._available is not None and time.time() - self._checked_at < 30:
                return self._available
            try:
                r = httpx.get(f"{self.url}/api/tags", timeout=2.0)
                names = [m.get("name", "") for m in r.json().get("models", [])]
                self._available = r.status_code == 200 and any(n.startswith(self.model.split(":")[0]) for n in names)
            except Exception:
                self._available = False
            self._checked_at = time.time()
            return self._available

    def health(self) -> dict[str, Any]:
        if self.mock:
            return {"ok": True, "mode": "mock", "model": None, "note": "MOCK_LLM=true: deterministic heuristics"}
        ok = self.available()
        return {"ok": ok, "mode": "ollama", "model": self.model, "url": self.url,
                "note": None if ok else "Ollama not reachable or model not pulled; falling back to heuristics"}

    def _chat(self, messages: list[dict[str, str]], stats: LLMStats, json_mode: bool, temperature: float) -> str:
        t0 = time.perf_counter()
        body: dict[str, Any] = {"model": self.model, "messages": messages, "stream": False,
                                "options": {"temperature": temperature, "num_ctx": 4096}}
        if json_mode:
            body["format"] = "json"
        r = httpx.post(f"{self.url}/api/chat", json=body, timeout=config.LLM_TIMEOUT_S)
        r.raise_for_status()
        data = r.json()
        stats.calls += 1
        stats.prompt_tokens += int(data.get("prompt_eval_count") or 0)
        stats.completion_tokens += int(data.get("eval_count") or 0)
        stats.latency_ms += (time.perf_counter() - t0) * 1000
        return data.get("message", {}).get("content", "")

    def structured(self, system: str, user: str, schema: type[M], stats: LLMStats, retries: int = 1) -> M | None:
        if not self.available():
            return None
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for attempt in range(retries + 1):
            try:
                raw = self._chat(messages, stats, json_mode=True, temperature=0.0)
                obj = json.loads(_first_json(raw))
                return schema.model_validate(obj)
            except (ValidationError, json.JSONDecodeError, ValueError) as e:
                stats.errors.append(f"invalid output (attempt {attempt + 1}): {str(e)[:160]}")
                messages += [{"role": "assistant", "content": raw if 'raw' in locals() else ""},
                             {"role": "user", "content": f"That was not valid. Error: {str(e)[:300]}. "
                                                         f"Return only a JSON object matching the schema."}]
            except Exception as e:  # network / timeout
                stats.errors.append(f"llm call failed: {str(e)[:160]}")
                self._available = False
                return None
        return None

    def text(self, system: str, user: str, stats: LLMStats, temperature: float = 0.2) -> str | None:
        if not self.available():
            return None
        try:
            return self._chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                              stats, json_mode=False, temperature=temperature).strip()
        except Exception as e:
            stats.errors.append(f"llm call failed: {str(e)[:160]}")
            self._available = False
            return None


def _first_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("{"):
        return raw
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("no JSON object in output")
    return m.group(0)


llm = LLM()

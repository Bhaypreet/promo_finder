"""LLM layer on LangChain. Swap the model with one string, e.g.

    --picker groq:openai/gpt-oss-120b        (default, Groq free tier)
    --picker groq:qwen/qwen3.8-27b
    --picker openai:gpt-4.1-mini             (any provider LangChain's init_chat_model supports,
    --picker huggingface:<model-id>          once its integration package and API key are installed)
    --picker openai:<model> --base-url https://<gateway>/v1 --api-key-env KUKU_API_KEY
                                             (any OpenAI-compatible gateway, e.g. a company's own API)

What this module adds on top of `init_chat_model`:
  * Pydantic structured output (`with_structured_output(Schema, method="json_schema")`)
  * a persistent SQLite LLM cache: same prompt + model => no tokens spent, identical result
  * a token-per-minute budget per model, because Groq's free tier allows ~8K tokens/min/model
  * retries with back-off on rate limits, plus a fallback model when the primary is exhausted
  * token usage accounting per model (for the cost table)
"""
from __future__ import annotations

import hashlib
import os
import re
import threading
import time
import warnings
from collections import deque
from pathlib import Path

from langchain.chat_models import init_chat_model
from langchain_core.globals import set_llm_cache
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(os.environ.get("PROMO_CACHE_DIR") or ROOT / ".cache")   # point at /tmp on read-only hosts
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*allowed_objects.*")


def load_env(path: Path = ROOT / ".env") -> None:
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def enable_cache(path: Path | None = None) -> None:
    from langchain_community.cache import SQLiteCache
    path = path or CACHE / "llm_cache.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    set_llm_cache(SQLiteCache(database_path=str(path)))


class TokenBudget:
    """Sliding 60-second window so parallel calls stay under a provider's tokens-per-minute cap."""

    def __init__(self, tpm: int):
        self.tpm, self.events, self.lock = tpm, deque(), threading.Lock()

    def acquire(self, tokens: int) -> list:
        tokens = min(tokens, self.tpm)
        while True:
            with self.lock:
                now = time.time()
                while self.events and now - self.events[0][0] > 60:
                    self.events.popleft()
                used = sum(t for _, t in self.events)
                if used + tokens <= self.tpm:
                    ev = [now, tokens]
                    self.events.append(ev)
                    return ev
                wait = 60 - (now - self.events[0][0]) + 0.2
            time.sleep(max(0.5, wait))

    def refund(self, ev: list) -> None:
        """A cache hit spent no tokens: give the reservation back."""
        with self.lock:
            try:
                self.events.remove(ev)
            except ValueError:
                pass


USAGE: dict[str, dict] = {}
_usage_lock = threading.Lock()
_budgets: dict[str, TokenBudget] = {}


class LLM:
    """One role (picker / viewer) = one model string, its own token budget and an optional fallback."""

    def __init__(self, spec: str, tpm: int = 7800, max_tokens: int = 3000, fallback: str | None = None,
                 temperature: float = 0.2, otpm: int | None = None, expected_out: int = 400,
                 api_key: str | None = None, base_url: str | None = None):
        """otpm: some Groq models also cap OUTPUT tokens per minute (qwen3.8-27b: 1,000).
        api_key / base_url: use someone else's key or an OpenAI-compatible gateway instead of the env key.
        The key is passed straight to the client; it is never logged, cached or written to disk."""
        self.spec, self.max_tokens, self.fallback_spec = spec, max_tokens, fallback
        self.expected_out, self.api_key, self.base_url = expected_out, api_key, base_url
        # a different key has its own rate limit, so it gets its own token budget
        self.tag = "" if not (api_key or base_url) else "@" + hashlib.sha256(
            f"{api_key}|{base_url}".encode()).hexdigest()[:8]
        self.model = self._make(spec, temperature)
        self.fallback = self._make(fallback, temperature) if fallback else None
        for s in filter(None, (spec, fallback)):
            _budgets.setdefault(s + self.tag, TokenBudget(tpm))
            if otpm:
                _budgets.setdefault(s + self.tag + "#out", TokenBudget(otpm))

    def _make(self, spec: str, temperature: float):
        provider, _, name = spec.partition(":")
        # timeout: a stalled HTTP call used to hang the whole run (and the web demo with it).
        # max_retries stays low because structured() below already retries with Groq's suggested wait.
        kwargs = {"temperature": temperature, "max_retries": 2, "timeout": 90, "max_tokens": self.max_tokens}
        if provider == "groq" and "gpt-oss" in name:
            kwargs["reasoning_effort"] = "low"      # reasoning tokens count against the free-tier budget
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return init_chat_model(name, model_provider=provider, **kwargs)

    def structured(self, schema: type[BaseModel], system: str, user: str) -> tuple[BaseModel, str]:
        """Returns (parsed Pydantic object, model spec that produced it)."""
        msgs = [SystemMessage(system), HumanMessage(user)]
        est = (len(system) + len(user)) // 4 + self.max_tokens     # Groq counts max_tokens against TPM up front
        last = None
        for spec, model in ((self.spec, self.model), (self.fallback_spec, self.fallback)):
            if model is None:
                continue
            method = "json_schema"
            runnable = model.with_structured_output(schema, method=method, include_raw=True)
            b = spec + self.tag
            for attempt in range(4):
                ev = _budgets[b].acquire(est)
                ev_out = _budgets[b + "#out"].acquire(self.expected_out) if b + "#out" in _budgets else None
                t0 = time.time()
                try:
                    out = runnable.invoke(msgs)
                except Exception as e:
                    last = e
                    msg = str(e)
                    if "rate_limit" in msg.lower() and "per day" in msg.lower():
                        break                           # daily quota gone: go to the fallback model
                    low = msg.lower()
                    if any(k in low for k in ("401", "403", "invalid api key", "invalid_api_key", "authentication",
                                              "unauthorized", "permission")):
                        raise RuntimeError(f"{spec}: the API key was rejected ({msg[:200]})") from e
                    if "404" in low or "model_not_found" in low or "does not exist" in low:
                        raise RuntimeError(f"{spec}: model not found at this endpoint ({msg[:200]})") from e
                    if method == "json_schema" and ("json_schema" in low or "response_format" in low):
                        # some gateways don't support strict JSON-schema output: fall back to tool calling
                        method = "function_calling"
                        runnable = model.with_structured_output(schema, method=method, include_raw=True)
                        continue
                    if "parse" in msg.lower() or "validation" in msg.lower():
                        # the bad reply is now in the LLM cache; change the prompt so the retry is a fresh call
                        msgs = msgs[:2] + [HumanMessage(f"Your last answer failed validation: {msg[:300]}. "
                                                        "Answer again with every field of the schema.")]
                        continue
                    wait = re.search(r"try again in ([\d.]+)s", msg)          # Groq tells us how long to wait
                    time.sleep(float(wait.group(1)) + 1 if wait else 5 * (attempt + 1))
                    continue
                cache_hit = time.time() - t0 < 0.3
                if cache_hit:
                    _budgets[b].refund(ev)
                    if ev_out:
                        _budgets[b + "#out"].refund(ev_out)
                self._count(spec, out["raw"], cache_hit)
                if out.get("parsed") is not None:
                    return out["parsed"], spec
                last = out.get("parsing_error")         # Pydantic rejected it: ask again
                msgs = msgs[:2] + [HumanMessage(f"Your last answer failed validation: {str(last)[:400]}. "
                                                "Answer again, following the schema exactly.")]
        raise RuntimeError(f"{self.spec} failed: {last}")

    @staticmethod
    def _count(spec: str, raw, cache_hit: bool) -> None:
        u = getattr(raw, "usage_metadata", None) or {}
        with _usage_lock:
            d = USAGE.setdefault(spec, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cache_hits": 0})
            if cache_hit:
                d["cache_hits"] += 1
                return
            d["calls"] += 1
            d["input_tokens"] += u.get("input_tokens", 0)
            d["output_tokens"] += u.get("output_tokens", 0)


def check_key(spec: str, api_key: str | None = None, base_url: str | None = None) -> str:
    """One tiny call to confirm a key + model + endpoint work. Returns the model's reply."""
    llm = LLM(spec, max_tokens=20, api_key=api_key, base_url=base_url)
    reply = llm.model.invoke([HumanMessage("Reply with the single word OK.")])
    return str(reply.content).strip()[:50]

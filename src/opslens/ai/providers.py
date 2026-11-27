"""LLM providers behind one tiny interface: `complete(system, messages) -> Reply`.

  anthropic            Anthropic SDK (pip install 'opslens[ai]')
  openai               OpenAI Chat Completions
  openai_compatible    any OpenAI-style endpoint: set llm.base_url (vLLM, LM Studio, Together, Groq, Mistral, ...)
  glm                  Z.ai / Zhipu GLM (OpenAI-compatible endpoint)
  openrouter           OpenRouter (hundreds of models behind one key)
  ollama               a local Ollama server, no key
  litellm              anything LiteLLM supports (also azure, bedrock, gemini...): model "azure/<deployment>", "bedrock/<id>"

The OpenAI-style providers use plain HTTP (httpx), so they need no extra dependency. API keys are read from an
environment variable (llm.api_key_env, or the provider's usual one), never from the config file.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from ..config import LLMConfig

#: provider -> (base_url, usual key env var, default model or None = the user must choose one)
PRESETS: dict[str, tuple[str | None, str | None, str | None]] = {
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY", None),
    "openai_compatible": (None, "OPENAI_API_KEY", None),
    "glm": ("https://open.bigmodel.cn/api/paas/v4", "ZAI_API_KEY", None),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", None),
    "ollama": ("http://localhost:11434/v1", None, None),
}
ANTHROPIC_DEFAULT = "claude-opus-5-5"
#: models the server-side refusal fallback and adaptive thinking are used with
ANTHROPIC_CURRENT = {"claude-fable-5-2", "claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


class LLMError(RuntimeError):
    pass


@dataclass
class Reply:
    text: str
    refused: bool = False
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""


class Provider(Protocol):
    name: str
    model: str

    def complete(self, system: str, messages: list[dict[str, str]]) -> Reply: ...


class OpenAIStyle:
    def __init__(self, name: str, base_url: str, model: str, api_key: str | None, timeout: float = 180,
                 transport: httpx.BaseTransport | None = None, sleep: Any = time.sleep):
        self.name, self.model, self.base, self.key, self.sleep = name, model, base_url.rstrip("/"), api_key, sleep
        self.http = httpx.Client(timeout=timeout, transport=transport)

    def complete(self, system: str, messages: list[dict[str, str]]) -> Reply:
        body = {"model": self.model, "messages": [{"role": "system", "content": system}, *messages]}
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        last = ""
        for attempt in range(3):
            try:
                r = self.http.post(f"{self.base}/chat/completions", json=body, headers=headers)
            except httpx.HTTPError as e:
                raise LLMError(f"cannot reach {self.name} at {self.base}: {e}") from e
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                last = f"{r.status_code}"
                self.sleep(2 ** attempt)
                continue
            if r.status_code >= 400:
                raise LLMError(f"{self.name}: {r.status_code} {r.text[:300]}")
            d = r.json()
            try:
                choice = d["choices"][0]
                text = choice["message"].get("content") or ""
            except (KeyError, IndexError, TypeError) as e:
                raise LLMError(f"{self.name}: unexpected response shape") from e
            u = d.get("usage") or {}
            return Reply(text, choice.get("finish_reason") == "content_filter",
                         {"input": u.get("prompt_tokens", 0), "output": u.get("completion_tokens", 0)}, d.get("model", self.model))
        raise LLMError(f"{self.name}: still failing after retries ({last})")


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, effort: str, fallback: bool, client: Any = None):
        self.model, self.effort, self.fallback = model, effort, fallback
        if client is None:
            try:
                import anthropic
            except ImportError as e:
                raise LLMError("the anthropic provider needs the SDK: pip install 'opslens[ai]'") from e
            client = anthropic.Anthropic()  # ANTHROPIC_API_KEY, or an `ant auth login` profile
        self.client = client

    def complete(self, system: str, messages: list[dict[str, str]]) -> Reply:
        kw: dict[str, Any] = {"model": self.model, "max_tokens": 16000, "messages": messages,
                              "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]}
        current = self.model in ANTHROPIC_CURRENT
        if current:
            kw["thinking"] = {"type": "adaptive"}
            kw["output_config"] = {"effort": self.effort}
        try:
            if current and self.fallback:  # safety classifiers may decline: let the API retry on a fallback model
                r = self.client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
            else:
                r = self.client.messages.create(**kw)
        except Exception as e:  # the SDK's typed errors all derive from Exception; surface them without a traceback
            raise LLMError(f"anthropic: {getattr(e, 'message', None) or e}") from e
        text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        u = getattr(r, "usage", None)
        return Reply(text, r.stop_reason == "refusal",
                     {"input": getattr(u, "input_tokens", 0), "output": getattr(u, "output_tokens", 0),
                      "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0}, getattr(r, "model", self.model))


class LiteLLMProvider:
    def __init__(self, name: str, model: str, base_url: str | None, api_key: str | None):
        self.name, self.model, self.base_url, self.key = name, model, base_url, api_key
        try:
            import litellm
        except ImportError as e:
            raise LLMError("this provider needs LiteLLM: pip install litellm") from e
        self.litellm = litellm

    def complete(self, system: str, messages: list[dict[str, str]]) -> Reply:
        try:
            r = self.litellm.completion(model=self.model, api_base=self.base_url, api_key=self.key,
                                        messages=[{"role": "system", "content": system}, *messages])
        except Exception as e:
            raise LLMError(f"litellm: {e}") from e
        c = r.choices[0]
        u = getattr(r, "usage", None)
        return Reply(c.message.content or "", getattr(c, "finish_reason", "") == "content_filter",
                     {"input": getattr(u, "prompt_tokens", 0), "output": getattr(u, "completion_tokens", 0)}, self.model)


def make_provider(cfg: LLMConfig, env: dict[str, str] | None = None) -> Provider:
    env = os.environ if env is None else env
    p = cfg.provider
    if p == "none":
        raise LLMError("no AI provider is configured. Set one, e.g. `--set llm.provider=anthropic` "
                       "(or openai, openai_compatible, glm, openrouter, ollama, litellm). Everything else works without AI.")
    key = env.get(cfg.api_key_env) if cfg.api_key_env else None
    if p == "anthropic":
        return AnthropicProvider(cfg.model or ANTHROPIC_DEFAULT, cfg.effort, cfg.fallback)
    if p in ("litellm", "azure", "bedrock"):
        if not cfg.model:
            raise LLMError(f"llm.model is required for {p} (LiteLLM names, e.g. azure/<deployment> or bedrock/<model id>)")
        return LiteLLMProvider(p, cfg.model, cfg.base_url, key)
    base, key_env, _ = PRESETS[p]
    base = cfg.base_url or base
    if not base:
        raise LLMError("llm.base_url is required for openai_compatible (e.g. http://localhost:8000/v1)")
    if not cfg.model:
        raise LLMError(f"llm.model is required for {p}: name the model you want to use")
    key = key or (env.get(key_env) if key_env else None)
    if key_env and not key and p != "openai_compatible":
        raise LLMError(f"{p} needs an API key in ${cfg.api_key_env or key_env}")
    return OpenAIStyle(p, base, cfg.model, key)

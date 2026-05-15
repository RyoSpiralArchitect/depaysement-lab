from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from .proto_v2 import (
    BaseGenerator,
    cleanup_continuation,
)
from .mlx_intervention import MLXLayerPatch, MLXSteeringRuntimeConfig, load_mlx_steering_vectors


DEFAULT_STOP_SEQUENCES = [
    "\nNote:", "\n(Note:", " (Note:", "Note:",
    "\nAuthor's note:", "\nEditor's note:",
    "\nAs requested", "\nHere is", "\nHere's",
]


@dataclass
class HTTPRetryConfig:
    retries: int = 2
    timeout: float = 120.0
    backoff: float = 0.75


class JSONHTTPClient:
    """Tiny dependency-free JSON client for local inference servers."""

    def __init__(self, headers: Optional[Mapping[str, str]] = None, retry: Optional[HTTPRetryConfig] = None):
        self.headers = dict(headers or {})
        self.retry = retry or HTTPRetryConfig()

    def post(self, url: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json", **self.headers}
        last_error: Optional[BaseException] = None
        for attempt in range(self.retry.retries + 1):
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.retry.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                return json.loads(raw)
            except urllib.error.HTTPError as e:
                # Preserve server error bodies; they are usually the only useful clue.
                err_body = e.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"HTTP {e.code} from {url}: {err_body}")
            except Exception as e:  # pragma: no cover - network-specific
                last_error = e
            if attempt < self.retry.retries:
                time.sleep(self.retry.backoff * (2 ** attempt))
        raise RuntimeError(f"JSON POST failed after retries: {url}: {last_error}")


@dataclass
class OpenAICompatGenerator(BaseGenerator):
    """Generator for vLLM or any OpenAI-compatible /v1/chat/completions server.

    This intentionally uses raw HTTP instead of the OpenAI Python client so the repo
    can run with no cloud SDK dependency. It is primarily meant for local vLLM.
    """

    model: str
    base_url: str = "http://localhost:8000/v1"
    api_key: str = "EMPTY"
    system_prompt: Optional[str] = None
    extra_body: Dict[str, Any] = field(default_factory=dict)
    retry: HTTPRetryConfig = field(default_factory=HTTPRetryConfig)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self.client = JSONHTTPClient(headers=headers, retry=self.retry)

    def generate(self, prompt: str, n: int, temperature: float, top_p: float, max_new_tokens: int) -> List[str]:
        # Loop instead of relying on `n`, because compatibility varies across servers.
        out: List[str] = []
        for _ in range(max(1, n)):
            messages = []
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})
            messages.append({"role": "user", "content": prompt})
            payload: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": max(0.0, float(temperature)),
                "top_p": float(top_p),
                "max_tokens": int(max_new_tokens),
                "stop": DEFAULT_STOP_SEQUENCES,
            }
            payload.update(self.extra_body)
            data = self.client.post(f"{self.base_url}/chat/completions", payload)
            choices = data.get("choices") or []
            if not choices:
                out.append("")
                continue
            msg = choices[0].get("message") or {}
            text = msg.get("content") or choices[0].get("text") or ""
            out.append(cleanup_continuation(str(text)))
        return out


@dataclass
class OllamaGenerator(BaseGenerator):
    """Generator for a local Ollama /api/chat endpoint."""

    model: str
    base_url: str = "http://localhost:11434"
    system_prompt: Optional[str] = None
    keep_alive: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)
    retry: HTTPRetryConfig = field(default_factory=HTTPRetryConfig)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.client = JSONHTTPClient(retry=self.retry)

    def generate(self, prompt: str, n: int, temperature: float, top_p: float, max_new_tokens: int) -> List[str]:
        out: List[str] = []
        for _ in range(max(1, n)):
            messages = []
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})
            messages.append({"role": "user", "content": prompt})
            opts = {
                "temperature": max(0.0, float(temperature)),
                "top_p": float(top_p),
                "num_predict": int(max_new_tokens),
                "stop": DEFAULT_STOP_SEQUENCES,
                **self.options,
            }
            payload: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": opts,
            }
            if self.keep_alive is not None:
                payload["keep_alive"] = self.keep_alive
            data = self.client.post(f"{self.base_url}/api/chat", payload)
            msg = data.get("message") or {}
            out.append(cleanup_continuation(str(msg.get("content", ""))))
        return out


@dataclass
class MLXLMGenerator(BaseGenerator):
    """Generator for mlx-lm on Apple silicon.

    Activation steering is intentionally not implemented here yet. MLX generation
    is supported; internal layer intervention should be a separate model-specific
    module because MLX does not mirror PyTorch forward hooks exactly.
    """

    model_name: str
    chat_template: bool = False
    system_prompt: Optional[str] = None
    tokenizer_config: Optional[Dict[str, Any]] = None
    trust_remote_code: bool = False
    seed: Optional[int] = None
    steering: Optional[MLXSteeringRuntimeConfig] = None

    def __post_init__(self) -> None:
        try:
            from mlx_lm import generate, load  # type: ignore
            from mlx_lm.sample_utils import make_sampler  # type: ignore
            import mlx.core as mx  # type: ignore
        except Exception as e:  # pragma: no cover - platform/dependency-specific
            raise RuntimeError("MLX backend requires Apple MLX packages: pip install mlx-lm") from e
        self._generate = generate
        self._make_sampler = make_sampler
        self._mx = mx
        if self.seed is not None:
            mx.random.seed(int(self.seed))
        kwargs: Dict[str, Any] = {}
        if self.tokenizer_config:
            kwargs["tokenizer_config"] = self.tokenizer_config
        if self.trust_remote_code:
            kwargs.setdefault("tokenizer_config", {})["trust_remote_code"] = True
        self.model, self.tokenizer = load(self.model_name, **kwargs)
        self._steering_vectors = None
        if self.steering is not None and self.steering.enabled():
            self._steering_vectors = load_mlx_steering_vectors(self.steering.vectors_path)

    def _format_prompt(self, prompt: str) -> str:
        if not self.chat_template:
            if self.system_prompt:
                return self.system_prompt.rstrip() + "\n\n" + prompt
            return prompt
        tmpl = getattr(self.tokenizer, "apply_chat_template", None)
        if tmpl is None:
            return prompt
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})
        try:
            return tmpl(messages, tokenize=False, add_generation_prompt=True)
        except Exception:
            # Some tokenizer templates reject system messages. Fall back to user-only
            # rather than failing the whole experiment.
            return tmpl([{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True)

    def generate(self, prompt: str, n: int, temperature: float, top_p: float, max_new_tokens: int) -> List[str]:
        out: List[str] = []
        sampler = self._make_sampler(temp=max(0.0, float(temperature)), top_p=float(top_p))
        formatted = self._format_prompt(prompt)
        for _ in range(max(1, n)):
            if self._steering_vectors is not None and self.steering is not None:
                with MLXLayerPatch(
                    self.model,
                    layers=self.steering.layers,
                    vectors=self._steering_vectors,
                    alpha=self.steering.alpha,
                    position=self.steering.position,
                    apply_on=self.steering.apply_on,
                ):
                    text = self._generate(
                        self.model,
                        self.tokenizer,
                        prompt=formatted,
                        max_tokens=int(max_new_tokens),
                        sampler=sampler,
                        verbose=False,
                    )
            else:
                text = self._generate(
                    self.model,
                    self.tokenizer,
                    prompt=formatted,
                    max_tokens=int(max_new_tokens),
                    sampler=sampler,
                    verbose=False,
                )
            if not isinstance(text, str) and hasattr(text, "text"):
                text = text.text
            text = str(text)
            # mlx-lm usually returns only the continuation, but this guard is harmless.
            if text.startswith(formatted):
                text = text[len(formatted) :]
            out.append(cleanup_continuation(text))
        return out


def parse_jsonish(s: Optional[str]) -> Dict[str, Any]:
    if not s:
        return {}
    return json.loads(s)

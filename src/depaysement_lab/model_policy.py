from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


INSTRUCT_HINTS = (
    "instruct",
    "-it",
    "_it",
    ":instruct",
    "chat",
    "assistant",
    "hermes",
    "dolphin",
    "openchat",
    "zephyr",
    "qwen3",
    "qwen2.5",
    "llama3.2",
    "llama-3.2",
    "llama-3.1",
    "mistral-small",
)

BASE_HINTS = (
    "gpt2",
    "gpt-2",
    "distilgpt2",
    "pythia",
    "openelm",
    "base",
    "pretrain",
    "pretrained",
)


@dataclass(frozen=True)
class ModelPolicy:
    model: str
    kind: str  # instruct, base, unknown
    confidence: float
    reasons: List[str]
    recommendation: str

    def as_dict(self) -> Dict[str, object]:
        return {
            "model": self.model,
            "kind": self.kind,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "recommendation": self.recommendation,
        }


def infer_model_policy(model: str) -> ModelPolicy:
    name = (model or "").lower()
    reasons: List[str] = []

    instruct_hits = [h for h in INSTRUCT_HINTS if h in name]
    base_hits = [h for h in BASE_HINTS if h in name]

    # Explicit instruct/chat markers win over generic base markers, because model IDs
    # like Llama-3.2-3B-Instruct can include family words that are also used for base checkpoints.
    if instruct_hits:
        reasons.append("instruction/chat marker: " + ", ".join(instruct_hits[:4]))
        return ModelPolicy(
            model=model,
            kind="instruct",
            confidence=0.88,
            reasons=reasons,
            recommendation=(
                "Recommended for the main depaysement experiment: the model has a realist/assistant "
                "repair attractor that steering can bend against."
            ),
        )

    if base_hits:
        reasons.append("base/pre-RLHF marker: " + ", ".join(base_hits[:4]))
        return ModelPolicy(
            model=model,
            kind="base",
            confidence=0.80,
            reasons=reasons,
            recommendation=(
                "Use as a control condition, not the main condition. Base LMs are often already strange, "
                "so depaysement steering has less ordered language to rebel against."
            ),
        )

    return ModelPolicy(
        model=model,
        kind="unknown",
        confidence=0.35,
        reasons=["no obvious instruct/chat or base marker in the model name"],
        recommendation=(
            "Prefer an instruction-tuned/chat model for the main experiment; treat this model as unknown until "
            "a model-card or output sanity check confirms its tuning style."
        ),
    )


def default_english_system_prompt() -> str:
    return (
        "You are a careful literary generator. Write in English. Output only the requested literary continuation. "
        "Never include Note:, commentary, analysis, apologies, labels, or references to the prompt/instructions. "
        "Do not explain the image, do not summarize it, and do not add analysis."
    )

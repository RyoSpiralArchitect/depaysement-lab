import json
from types import SimpleNamespace

import numpy as np

from depaysement_lab.backends import _extract_logits_tensor
from depaysement_lab.prefix_probe import (
    jensen_shannon_divergence,
    load_prefix_pairs,
    run_prefix_counter_probe,
    softmax_probabilities,
)
from depaysement_lab.proto_v2 import DepaysementScorer, SelectorConfig


class TinyTokenizer:
    def decode(self, value):
        token_id = value[0] if isinstance(value, list) else value
        return f"token-{token_id}"


class FixedPrefixGenerator:
    def __init__(self):
        self.steering = SimpleNamespace(alpha=0.0, vectors_path="vectors.npz", apply_on="decode_only")
        self.tokenizer = TinyTokenizer()
        self.seed = 0

    def reset_seed(self, seed):
        self.seed = int(seed)
        return True

    def next_token_logits(self, prompt):
        if "induced glass garden" in prompt:
            return np.array([0.0, 2.0, 0.5])
        return np.array([2.0, 0.0, 0.5])

    def generate(self, prompt, n, temperature, top_p, max_new_tokens):
        alpha = float(self.steering.alpha)
        if alpha < 0:
            text = "The mug settles beside the sink while its handle keeps the shape of a small doorway."
        elif alpha > 0:
            text = "The mug becomes a window whose glass pours a narrow garden across the sink."
        else:
            text = "The mug waits beside the sink and reflects the kitchen light."
        return [text for _ in range(n)]


def _write_run(path, seed, condition, picks):
    path.write_text(
        json.dumps(
            {
                "seed": seed,
                "config": {"condition": condition},
                "steps": [
                    {"step": index, "picked": {"text": text}} for index, text in enumerate(picks, start=1)
                ],
            }
        ),
        encoding="utf-8",
    )


def test_extract_logits_tensor_supports_common_outputs():
    logits = np.array([[1.0, 2.0]])
    assert _extract_logits_tensor(SimpleNamespace(logits=logits)) is logits
    assert _extract_logits_tensor({"logits": logits}) is logits
    assert _extract_logits_tensor((logits, "cache")) is logits
    assert _extract_logits_tensor(logits) is logits


def test_jensen_shannon_divergence_is_symmetric_and_zero_on_identity():
    p = softmax_probabilities([2.0, 0.0, 0.5])
    q = softmax_probabilities([0.0, 2.0, 0.5])
    assert jensen_shannon_divergence(p, p) == 0.0
    assert jensen_shannon_divergence(p, q) > 0.2
    assert jensen_shannon_divergence(p, q) == jensen_shannon_divergence(q, p)


def test_load_prefix_pairs_keeps_reference_and_induced_history(tmp_path):
    reference = tmp_path / "reference.json"
    induced = tmp_path / "induced.json"
    seed = "A blue mug beside the sink"
    _write_run(reference, seed, "baseline", ["Plain step one.", "Plain step two.", "Unused."])
    _write_run(induced, seed, "persistent", ["An induced glass garden.", "It opens.", "Unused."])

    pair = load_prefix_pairs([str(reference)], [str(induced)], prefix_steps=2)[0]

    assert pair["reference_prefix"].endswith("Plain step two.")
    assert pair["induced_prefix"].endswith("It opens.")
    assert pair["reference_condition"] == "baseline"
    assert pair["induced_condition"] == "persistent"


def test_prefix_probe_separates_prefix_and_alpha_effects(tmp_path):
    reference = tmp_path / "reference.json"
    induced = tmp_path / "induced.json"
    seed = "A blue mug beside the sink"
    _write_run(reference, seed, "baseline", ["Plain counter.", "The mug waits.", "The tap drips."])
    _write_run(
        induced,
        seed,
        "persistent",
        ["An induced glass garden opens.", "The mug becomes a window.", "The tap grows leaves."],
    )

    report = run_prefix_counter_probe(
        FixedPrefixGenerator(),
        DepaysementScorer(),
        SelectorConfig(
            objective="banded-frontier",
            readability_min=0.0,
            frontier_quality_min=0.0,
        ),
        reference_paths=[str(reference)],
        induced_paths=[str(induced)],
        prefix_steps=3,
        alphas=(-0.6, 0.0, 0.6),
        candidates=2,
        max_new_tokens=32,
    )

    assert len(report["cells"]) == 6
    assert report["diagnostics"]["first_token_invariant_across_alpha"] is True
    assert report["diagnostics"]["mean_cross_prefix_jsd"] > 0.2
    assert all(cell["candidates"] for cell in report["cells"])

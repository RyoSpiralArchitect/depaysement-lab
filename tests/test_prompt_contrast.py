import json
from argparse import Namespace
from types import SimpleNamespace

from depaysement_lab import cli
from depaysement_lab.prompt_contrast import (
    HUMAN_FIELDS,
    anchor_phrase_metrics,
    build_blind_rating_sheet,
    build_prompt_contrast_prompt,
    classify_prompt_candidate,
    load_anchor_bank,
    run_prompt_steering_contrast,
)
from depaysement_lab.proto_v2 import DepaysementScorer, SelectorConfig


class PromptContrastGenerator:
    def __init__(self):
        self.steering = SimpleNamespace(alpha=0.0, vectors_path="vectors.npz")
        self.seed = 0

    def reset_seed(self, seed):
        self.seed = int(seed)
        return True

    def generate(self, prompt, n, temperature, top_p, max_new_tokens):
        alpha = float(self.steering.alpha)
        operational = "Create controlled semantic displacement" in prompt
        if alpha >= 1.0:
            text = (
                "The blue mug becomes a music box beside the sink, while the comb and morning light "
                "open into another music box"
            )
        elif alpha > 0.0:
            text = (
                "The blue mug becomes a doorway that lets the sink enter the comb, while morning light "
                "waits on its threshold."
            )
        elif operational:
            text = (
                "The blue mug glows beside the sink as if the comb were dreaming in the morning light."
            )
        else:
            text = "The blue mug shimmers beside the sink; the comb whispers to the morning light."
        return [text for _ in range(n)]


def _item():
    return {
        "id": "anchor01",
        "seed": "A blue mug rests beside the sink; a comb catches the morning light.",
        "anchors": ["blue mug", "sink", "comb", "morning light"],
    }


def test_anchor_bank_requires_anchors_to_appear_in_seed(tmp_path):
    path = tmp_path / "anchors.json"
    path.write_text(json.dumps({"items": [_item()]}), encoding="utf-8")

    loaded = load_anchor_bank(str(path))

    assert loaded[0]["id"] == "anchor01"
    assert loaded[0]["anchors"][-1] == "morning light"


def test_naive_and_operational_prompts_share_anchor_contract():
    naive = build_prompt_contrast_prompt(_item(), "naive")
    operational = build_prompt_contrast_prompt(_item(), "operational")

    for anchor in _item()["anchors"]:
        assert f'"{anchor}"' in naive
        assert f'"{anchor}"' in operational
    assert "surreal through depaysement" in naive
    assert "identity, role, affordance" in operational
    assert "Do not merely decorate" in operational


def test_anchor_phrase_metrics_use_phrase_level_coverage():
    metrics = anchor_phrase_metrics(
        "The blue mug touches the sink while morning light fades.",
        ["blue mug", "sink", "comb", "morning light"],
    )

    assert metrics["anchor_phrase_coverage"] == 0.75
    assert metrics["anchor_phrase_misses"] == ["comb"]


def test_candidate_classification_separates_near_miss_transport_and_failure():
    common = {
        "syntax_readability_proxy": 0.8,
        "unfinished": 0.0,
        "anchor_phrase_coverage": 1.0,
        "cliche_attractor_score": 0.0,
        "fantasy_prop_score": 0.0,
        "semantic_loop_pressure": 0.0,
        "object_budget_pressure": 0.0,
    }
    near = {**common, "ontology_collapse_density": 0.05, "surface_style_pressure": 0.6}
    transport = {**common, "ontology_collapse_density": 0.35, "surface_style_pressure": 0.0}
    failed = {**common, "ontology_collapse_density": 0.35, "surface_style_pressure": 0.0, "unfinished": 0.4}

    assert classify_prompt_candidate(near) == "decorative_near_miss"
    assert classify_prompt_candidate(transport) == "readable_transport"
    assert classify_prompt_candidate(failed) == "unfinished_or_unreadable_failure"


def test_prompt_contrast_retains_all_raw_cells_and_builds_blind_sheet():
    report = run_prompt_steering_contrast(
        PromptContrastGenerator(),
        DepaysementScorer(),
        SelectorConfig(objective="banded-frontier"),
        items=[_item()],
        alphas=(0.0, 0.6, 1.2),
        candidates=2,
        max_new_tokens=48,
    )

    assert len(report["cells"]) == 6
    assert all(len(cell["candidates"]) == 2 for cell in report["cells"])
    assert report["design"]["selector_used_for_generation"] is False
    assert report["triptych"]["available"] is True
    assert len(report["summary_rows"]) == 6

    public, key = build_blind_rating_sheet(report, seed_limit=1, random_seed=11)
    assert len(public) == 6
    assert tuple(public[0]) == HUMAN_FIELDS
    assert "prompt_mode" not in public[0]
    assert {item["prompt_mode"] for item in key["items"]} == {"naive", "operational"}


def test_prompt_contrast_accepts_dense_alpha_grid():
    report = run_prompt_steering_contrast(
        PromptContrastGenerator(),
        DepaysementScorer(),
        SelectorConfig(objective="banded-frontier"),
        items=[_item()],
        prompt_modes=("operational",),
        alphas=(0.0, 0.3, 0.6, 0.9, 1.2),
        candidates=1,
        max_new_tokens=48,
    )

    assert len(report["cells"]) == 5
    assert [row["alpha"] for row in report["summary_rows"]] == [0.0, 0.3, 0.6, 0.9, 1.2]


def test_prompt_contrast_strips_trailing_space_inside_multiline_candidates():
    generator = PromptContrastGenerator()
    original_generate = generator.generate

    def generate_with_trailing_space(*args, **kwargs):
        return [f"{text} \nSecond line. " for text in original_generate(*args, **kwargs)]

    generator.generate = generate_with_trailing_space
    report = run_prompt_steering_contrast(
        generator,
        DepaysementScorer(),
        SelectorConfig(objective="banded-frontier"),
        items=[_item()],
        alphas=(0.0, 0.6, 1.2),
        candidates=1,
        max_new_tokens=48,
    )

    texts = [candidate["text"] for cell in report["cells"] for candidate in cell["candidates"]]
    assert all(" \n" not in text and not text.endswith(" ") for text in texts)


def test_prompt_contrast_cli_does_not_require_selector_arguments(monkeypatch, tmp_path):
    generator = SimpleNamespace(system_prompt=None)
    captured = {}
    report = {
        "design": {"selector_used_for_generation": False},
        "summary_rows": [],
        "matched_summary_rows": [],
        "paired_contrasts": {},
        "matched_paired_contrasts": {},
        "triptych": {"available": False},
        "cells": [],
    }
    monkeypatch.setattr(cli, "emit_model_policy", lambda args: None)
    monkeypatch.setattr(cli, "load_anchor_bank", lambda path, limit=0: [_item()])
    monkeypatch.setattr(cli, "make_generator", lambda args, rng: generator)
    monkeypatch.setattr(cli, "steering_alpha_supported", lambda value: True)
    monkeypatch.setattr(cli, "make_scorer", lambda args: object())
    monkeypatch.setattr(
        cli,
        "make_selector_config",
        lambda args: (_ for _ in ()).throw(AssertionError("selector CLI arguments must not be read")),
    )

    def fake_run(generator_arg, scorer_arg, selector, **kwargs):
        captured["objective"] = selector.objective
        return report

    monkeypatch.setattr(cli, "run_prompt_steering_contrast", fake_run)
    monkeypatch.setattr(cli, "write_prompt_contrast_artifacts", lambda *args, **kwargs: {})
    monkeypatch.setattr(cli, "format_prompt_contrast_report", lambda value: "report")
    monkeypatch.setattr(cli, "resolve_model", lambda args: "test-model")
    args = Namespace(
        prompt_modes="naive,operational",
        alphas="0,0.6,1.2",
        anchor_bank="anchors.json",
        seed_limit=0,
        random_seed=7,
        candidates=2,
        temperature=1.0,
        top_p=0.9,
        max_new_tokens=32,
        resume=False,
        run_limit=0,
        rating_seed_limit=1,
        rating_random_seed=11,
        out_dir=str(tmp_path),
        backend="mlx",
        model="test-model",
        vectors="vectors.npz",
        steer_layers="6-16",
        mlx_steer_apply_on="decode_only",
    )

    cli.cmd_prompt_steering_contrast(args)

    assert captured["objective"] == "banded-frontier"

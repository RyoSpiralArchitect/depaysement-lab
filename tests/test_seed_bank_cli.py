import argparse
import json
import subprocess
import sys

from depaysement_lab.cli import load_seed_bank, make_selector_config, safe_seed_label
from depaysement_lab.proto_v2 import PromptBank


def test_load_seed_bank_reads_json_object_and_limits(tmp_path):
    path = tmp_path / "seeds.json"
    path.write_text(json.dumps({"seeds": ["The receipt on the counter", "The bus was late"]}), encoding="utf-8")

    assert load_seed_bank(str(path), "fallback", limit=1) == ["The receipt on the counter"]


def test_load_seed_bank_reads_text_and_deduplicates(tmp_path):
    path = tmp_path / "seeds.txt"
    path.write_text("# comment\nA blue mug\nA blue mug\nThe printer tray\n", encoding="utf-8")

    assert load_seed_bank(str(path), "fallback") == ["A blue mug", "The printer tray"]


def test_safe_seed_label_is_filename_friendly():
    assert safe_seed_label("The receipt on the counter!", 3).startswith("seed03_the_receipt")


def test_hard_ban_affordance_classes_expand_selector_terms():
    cfg = make_selector_config(
        argparse.Namespace(
            select_objective="banded-frontier",
            hard_ban_terms="custom hinge",
            hard_ban_affordance_classes="acoustic_mechanism,time_mechanism",
        )
    )

    assert "custom hinge" in cfg.hard_ban_terms
    assert "music box" in cfg.hard_ban_terms
    assert "harmonica" in cfg.hard_ban_terms
    assert "clock" in cfg.hard_ban_terms
    assert "metronome" in cfg.hard_ban_terms


def test_traceable_transport_selector_args_are_preserved():
    cfg = make_selector_config(
        argparse.Namespace(
            select_objective="banded-frontier",
            lineage_bridge_weight=1.1,
            lineage_bridge_min=0.35,
            traceable_transport_weight=1.4,
            trajectory_revisit_weight=0.8,
            unbridged_novelty_weight=1.2,
            object_budget_weight=0.9,
            hard_lineage_bridge_min=0.2,
        )
    )

    assert cfg.lineage_bridge_weight == 1.1
    assert cfg.lineage_bridge_min == 0.35
    assert cfg.traceable_transport_weight == 1.4
    assert cfg.trajectory_revisit_weight == 0.8
    assert cfg.unbridged_novelty_weight == 1.2
    assert cfg.object_budget_weight == 0.9
    assert cfg.hard_lineage_bridge_min == 0.2


def test_transition_prompt_bank_is_balanced_and_noise_free():
    bank = PromptBank.from_file("data/depaysement_transition_bank_en_v1.json")

    assert len(bank.positive_depaysement) == 24
    assert len(bank.negative_realist_repair) == 24
    assert bank.negative_weird_noise == []


def test_frontier_sweep_resume_skips_existing_runs(tmp_path):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("The receipt on the counter\nThe bus was late\n", encoding="utf-8")
    out_dir = tmp_path / "sweep"
    base_cmd = [
        sys.executable,
        "-m",
        "depaysement_lab.cli",
        "frontier-sweep",
        "--backend",
        "dummy",
        "--seed-bank",
        str(seeds),
        "--steps",
        "1",
        "--alphas",
        "0,0.5",
        "--candidate-grid",
        "1",
        "--max-token-grid",
        "16",
        "--select-objective",
        "banded-frontier",
        "--choose",
        "best",
        "--run-limit",
        "1",
        "--out-dir",
        str(out_dir),
    ]

    first = subprocess.run(base_cmd, check=True, capture_output=True, text=True)
    first_runs = sorted(out_dir.glob("selector_alpha_*.json"))
    assert len(first_runs) == 1
    assert "run limit reached after 1 new run" in first.stderr

    second = subprocess.run(base_cmd + ["--resume"], check=True, capture_output=True, text=True)
    second_runs = sorted(out_dir.glob("selector_alpha_*.json"))
    assert len(second_runs) == 2
    assert "resume skip existing" in second.stderr
    assert "run limit reached after 1 new run" in second.stderr

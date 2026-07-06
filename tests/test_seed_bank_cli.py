import argparse
import json
import subprocess
import sys

from depaysement_lab.cli import load_seed_bank, make_selector_config, safe_seed_label


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

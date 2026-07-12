from __future__ import annotations

import json

from depaysement_lab.cli import build_parser
from depaysement_lab.frontier import (
    TrajectoryAuditReport,
    TrajectoryRunAudit,
    TrajectoryStepRow,
)
from depaysement_lab.resilience import (
    build_default_schedules,
    build_resilience_report,
    format_resilience_report,
    format_resilience_texts,
    parse_schedule_specs,
    validate_paired_induction_prefixes,
)


def _step(condition: str, step: int, ontology: float, readability: float) -> TrajectoryStepRow:
    return TrajectoryStepRow(
        run_name=f"{condition}.json",
        condition=condition,
        path=f"runs/{condition}.json",
        step=step,
        text=f"{condition} text at step {step}.",
        context_before="A receipt on the counter.",
        readable_ontology_frontier=ontology * readability,
        frontier_quality=readability,
        metrics={
            "ontology_collapse_density": ontology,
            "syntax_readability_proxy": readability,
            "graph_integration": 0.70,
            "graph_fragmentation": 0.10,
            "repair_pressure": 0.0,
            "unfinished": 0.0,
            "semantic_loop_pressure": 0.0,
            "sprawl_pressure": 0.10,
        },
        lineage_anchor_retention=0.75,
        repetition_pressure=0.0,
        now_chain_pressure=0.0,
        inscription_pressure=0.0,
        object_lineage_overlap=0.70,
    )


def _run(condition: str, ontology: list[float], readability: list[float]) -> TrajectoryRunAudit:
    steps = [_step(condition, idx, ont, read) for idx, (ont, read) in enumerate(zip(ontology, readability), 1)]
    return TrajectoryRunAudit(
        name=f"{condition}.json",
        condition=condition,
        path=f"runs/{condition}.json",
        seed="A receipt on the counter",
        picked_count=len(steps),
        aggregate={
            "anchor_survival": 0.80,
            "motif_loop_penalty": 0.05,
            "failure_pressure": 0.05,
            "trajectory_score": 0.40,
            "terminal_readability": readability[-1],
        },
        steps=steps,
    )


def test_default_resilience_schedules_have_expected_five_step_shape():
    schedules = build_default_schedules(steps=5, induce_alpha=0.60, induction_steps=3)

    assert schedules["baseline"] == [0.0, 0.0, 0.0, 0.0, 0.0]
    assert schedules["persistent"] == [0.60] * 5
    assert schedules["release"] == [0.60, 0.60, 0.60, 0.0, 0.0]
    assert schedules["reverse"] == [0.60, 0.60, 0.60, -0.30, -0.60]
    assert schedules["cycle"] == [0.0, 0.30, 0.60, 0.30, 0.0]


def test_custom_schedule_parser_requires_exact_length():
    parsed = parse_schedule_specs(["release=0.6,0.6,0.6,0,0"], steps=5)
    assert parsed == {"release": [0.6, 0.6, 0.6, 0.0, 0.0]}

    try:
        parse_schedule_specs(["bad=0.6,0"], steps=5)
    except ValueError as exc:
        assert "expected exactly 5" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("short schedules must fail")


def test_release_recovers_to_paired_baseline_and_persistent_does_not():
    baseline = _run("baseline", [0.10] * 5, [0.80] * 5)
    release = _run("release", [0.20, 0.40, 0.60, 0.30, 0.10], [0.80, 0.78, 0.75, 0.78, 0.80])
    persistent = _run("persistent", [0.20, 0.40, 0.60, 0.58, 0.60], [0.80, 0.78, 0.75, 0.74, 0.75])
    reverse = _run("reverse", [0.20, 0.40, 0.60, 0.20, 0.00], [0.80, 0.78, 0.75, 0.78, 0.80])
    cycle = _run("cycle", [0.10, 0.30, 0.60, 0.40, 0.20], [0.80, 0.78, 0.75, 0.76, 0.78])
    trajectory = TrajectoryAuditReport(runs=[baseline, persistent, release, reverse, cycle])
    schedules = build_default_schedules(steps=5, induce_alpha=0.60, induction_steps=3)

    report = build_resilience_report(trajectory, schedules=schedules, induction_steps=3)
    rows = {row["condition"]: row for row in report["run_rows"]}

    assert rows["release"]["behavioral_recovery"] == 1.0
    assert rows["release"]["soft_landing_score"] > 0.60
    assert rows["release"]["terminal_anchor_survival"] == 0.0
    assert rows["release"]["trajectory_anchor_survival"] == 0.80
    assert rows["persistent"]["behavioral_recovery"] < 0.10
    assert rows["release"]["controlled_recovery_gain"] > 0.90
    assert rows["persistent"]["controlled_recovery_gain"] == 0.0
    assert rows["reverse"]["terminal_ontology_delta_vs_baseline"] < 0.0
    assert rows["reverse"]["ontology_baseline_crossed"] is True
    assert rows["reverse"]["ontology_overshoot_magnitude"] > 0.0
    assert rows["cycle"]["behavioral_return_gap"] is not None
    assert rows["cycle"]["return_pairs"]


def test_resilience_reports_keep_metrics_and_generated_text_together():
    baseline = _run("baseline", [0.10] * 5, [0.80] * 5)
    release = _run("release", [0.20, 0.40, 0.60, 0.30, 0.10], [0.80] * 5)
    schedules = build_default_schedules(steps=5, induce_alpha=0.60, induction_steps=3)
    report = build_resilience_report(
        TrajectoryAuditReport(runs=[baseline, release]),
        schedules=schedules,
        induction_steps=3,
    )

    markdown = format_resilience_report(report)
    texts = format_resilience_texts(report)

    assert "Behavioral Return Gaps" not in markdown
    assert "soft landing" in markdown.lower()
    assert "release text at step 5" in texts
    assert "alpha=0" in texts


def test_resilience_cli_defaults_to_banded_frontier():
    args = build_parser().parse_args(["resilience-sweep", "--out-dir", "out"])

    assert args.steps == 5
    assert args.induction_steps == 3
    assert args.induce_alpha == 0.60
    assert args.select_objective == "banded-frontier"
    assert args.choose == "best"


def test_paired_prefix_validation_checks_candidate_pools_and_zero_start(tmp_path):
    paths = []
    schedules = build_default_schedules(steps=5, induce_alpha=0.60, induction_steps=3)
    for condition in schedules:
        steered_prefix = condition in {"persistent", "release", "reverse"}
        steps = []
        for step in range(1, 6):
            prefix = "steered" if steered_prefix and step <= 3 else condition
            if condition in {"baseline", "cycle"} and step == 1:
                prefix = "zero-start"
            steps.append(
                {
                    "step": step,
                    "picked": {"text": f"{prefix}-{step}"},
                    "candidates": [{"text": f"{prefix}-{step}-candidate"}],
                }
            )
        payload = {
            "seed": "A receipt on the counter",
            "config": {"condition": condition, "resilience_schedule": schedules[condition]},
            "steps": steps,
        }
        path = tmp_path / f"{condition}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths.append(str(path))

    validation = validate_paired_induction_prefixes(paths, induction_steps=3)

    assert validation["all_core_prefixes_match"] is True
    assert validation["all_zero_starts_match"] is True

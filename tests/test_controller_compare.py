import json

from depaysement_lab.controller_compare import compare_adaptive_controllers


def _candidate(text, ontology, readability, stock=0.0):
    return {
        "text": text,
        "selector_metrics": {
            "readable_ontology_frontier": ontology * readability,
            "ontology_collapse_density": ontology,
            "syntax_readability_proxy": readability,
            "ordinary_anchor_retention": 1.0,
            "traceable_transport_score": ontology,
            "unfinished": 0.0,
            "repetition_pressure": 0.0,
            "sprawl_pressure": 0.0,
            "cliche_attractor_score": stock,
            "soft_style_cliche_score": 0.0,
            "fantasy_prop_score": 0.0,
        },
    }


def _run(mode, second_text):
    adaptive = mode != "fixed"
    trace = []
    if adaptive:
        trace = [
            {
                "step": 1,
                "alpha": 0.6,
                "next_alpha": 0.48,
                "action": "dampen" if mode == "hysteresis" else "legacy",
                "reason": "guard",
            },
            {
                "step": 2,
                "alpha": 0.48,
                "next_alpha": 0.48,
                "action": "hold" if mode == "hysteresis" else "legacy",
                "reason": "hold",
            },
        ]
    return {
        "seed": "A mug",
        "final_text": second_text,
        "config": {
            "seed_label": "seed01_a_mug",
            "trajectory_steering": {
                "base_alpha": 0.6,
                "adaptive": adaptive,
                "adaptive_mode": mode,
                "trace": trace,
            },
        },
        "steps": [
            {"step": 1, "picked": _candidate("same first step", 0.4, 0.7, stock=1.0)},
            {"step": 2, "picked": _candidate(second_text, 0.3, 0.8)},
        ],
    }


def test_controller_comparison_uses_seed_units_and_step_one_identity(tmp_path):
    paths = {}
    for condition in ("fixed", "hysteresis"):
        root = tmp_path / condition
        root.mkdir()
        (root / "steer_alpha_0p6_seed01.json").write_text(
            json.dumps(_run(condition, f"{condition} second step")),
            encoding="utf-8",
        )
        paths[condition] = root

    report = compare_adaptive_controllers(paths)

    assert report["seed_count"] == 1
    assert report["step_one_identity"]["all_identical"] is True
    hysteresis = next(row for row in report["condition_rows"] if row["condition"] == "hysteresis")
    assert hysteresis["dampen_count"] == 1
    assert hysteresis["hold_count"] == 1
    assert report["paired_deltas_vs_fixed"]["hysteresis"]["mean_alpha"]["seed_pairs"] == 1

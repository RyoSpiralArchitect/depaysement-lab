import json

from depaysement_lab.corridor_compare import compare_corridor_reports


def _report(scale):
    rows = []
    cells = []
    for alpha in (0.0, 0.6, 1.2):
        ontology = alpha * scale
        row = {
            "prompt_mode": "operational",
            "alpha": alpha,
            "seed_count": 1,
            "candidate_count": 1,
            "candidate_fraction": 1.0,
            "anchor_phrase_coverage": 1.0,
            "anchor_full_rate": 1.0,
            "ontology_collapse_density": ontology,
            "syntax_readability_proxy": 0.8,
            "traceable_transport_score": ontology,
            "failure_rate": 0.0,
        }
        rows.append(row)
        text = "same baseline" if alpha == 0.0 else f"condition text {scale} {alpha}"
        cells.append(
            {
                "item_id": "seed1",
                "prompt_mode": "operational",
                "alpha": alpha,
                "candidates": [
                    {
                        "candidate_index": 1,
                        "text": text,
                        "observer_label": "readable_transport",
                        "metrics": {
                            "anchor_phrase_coverage": 1.0,
                            "ontology_collapse_density": ontology,
                            "syntax_readability_proxy": 0.8,
                            "unfinished": 0.0,
                            "semantic_loop_pressure": 0.0,
                            "sprawl_pressure": 0.0,
                        },
                    }
                ],
            }
        )
    return {
        "design": {
            "alphas": [0.0, 0.6, 1.2],
            "prompt_modes": ["operational"],
            "candidates_per_cell": 1,
            "max_new_tokens": 32,
            "random_seed": 7,
        },
        "summary_rows": rows,
        "matched_summary_rows": rows,
        "cells": cells,
    }


def test_corridor_comparison_checks_zero_identity_and_preserves_text(tmp_path):
    paths = {}
    for name, scale in (("target", 0.3), ("random", 0.05)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(_report(scale)), encoding="utf-8")
        paths[name] = path

    report = compare_corridor_reports(paths)

    assert report["alpha_zero_candidate_texts_identical"] is True
    assert len(report["summary_rows"]) == 6
    target = next(row for row in report["diagnostic_high_ontology_exemplars"] if row["condition"] == "target")
    assert target["alpha"] == 1.2
    assert "condition text" in target["text"]

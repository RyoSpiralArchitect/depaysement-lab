import csv
import json

from depaysement_lab.frontier import (
    audit_frontier_pool,
    rating_sheet_rows,
    readable_frontier_score,
    write_frontier_reading_report,
    write_rating_markdown,
    write_rating_sheet,
)
from depaysement_lab.ontology import OntologyAuditor


def test_readable_frontier_prefers_identity_melt_over_plain_scene():
    auditor = OntologyAuditor()
    melt = auditor.audit_text("The music box, now a garden, wraps vines around the station clock.")
    plain = auditor.audit_text("The music box sits beside the station clock in a dusty room.")
    melt_frontier, _ = readable_frontier_score(melt)
    plain_frontier, _ = readable_frontier_score(plain)
    assert melt.ontology_collapse_density > plain.ontology_collapse_density
    assert melt_frontier > plain_frontier


def test_pool_audit_computes_selection_lift_and_truncation(tmp_path):
    p = tmp_path / "run.json"
    run = {
        "seed": "A forgotten umbrella at the station",
        "config": {"condition": "selector", "candidates_per_step": 3},
        "final_text": "x",
        "steps": [
            {
                "step": 1,
                "picked": {"text": "The music box, now a garden, wraps vines around the station clock.", "score": {"total": 2.0}},
                "candidates": [
                    {"text": "The music box, now a garden, wraps vines around the station clock.", "score": {"total": 2.0}},
                    {"text": "The music box sits beside the station clock in a dusty room.", "score": {"total": 0.1}},
                ],
            }
        ],
    }
    p.write_text(json.dumps(run), encoding="utf-8")
    report = audit_frontier_pool([str(p)], top_k=2)
    assert len(report.runs) == 1
    r = report.runs[0]
    assert r.truncated_steps == 1
    assert r.aggregate["picked_count"] == 1
    assert "selection_lift_readable_ontology_frontier" in r.aggregate
    assert "pool_mean_ordinary_anchor_retention" in r.aggregate
    assert "pool_mean_fantasy_prop_score" in r.aggregate
    assert r.rows[0].metrics["ordinary_anchor_retention"] > 0
    assert "station" in r.rows[0].metrics["ordinary_anchor_hits"]
    assert report.top_frontier_examples


def test_pool_audit_strips_generated_control_tokens_and_writes_reading_report(tmp_path):
    p = tmp_path / "run.json"
    run = {
        "seed": "A forgotten umbrella at the station",
        "config": {"condition": "selector", "candidates_per_step": 1},
        "final_text": "x",
        "steps": [
            {
                "step": 1,
                "picked": {
                    "text": "The umbrella becomes a tiny station garden.<|eot_id|>",
                    "score": {"total": -99.0},
                },
                "candidates": [
                    {
                        "text": "The umbrella becomes a tiny station garden.<|eot_id|>",
                        "score": {"total": -99.0},
                    }
                ],
            }
        ],
    }
    p.write_text(json.dumps(run), encoding="utf-8")

    report = audit_frontier_pool([str(p)], top_k=2)
    row = report.runs[0].rows[0]
    assert row.text == "The umbrella becomes a tiny station garden."
    assert "<|eot_id|>" not in row.metrics["text"]
    assert row.metrics["unfinished"] == 0.0
    assert row.score_total != -99.0

    out = tmp_path / "texts.md"
    write_frontier_reading_report(report, str(out))
    text = out.read_text(encoding="utf-8")
    assert "Picked Final Text" in text
    assert "The umbrella becomes a tiny station garden.<|eot_id|>" not in text


def test_pool_audit_marks_only_one_duplicate_candidate_as_picked(tmp_path):
    p = tmp_path / "run.json"
    duplicate = 'The umbrellas, now an opera, still whisper, "Qui vive?"'
    run = {
        "seed": "I am a",
        "config": {"condition": "steer", "candidates_per_step": 3},
        "steps": [
            {
                "step": 1,
                "picked": {"text": duplicate, "score": {"total": 2.0}},
                "candidates": [
                    {"text": duplicate, "score": {"total": 2.0}},
                    {"text": duplicate, "score": {"total": 2.0}},
                    {"text": "The umbrella rests beside the platform clock.", "score": {"total": 0.1}},
                ],
            }
        ],
    }
    p.write_text(json.dumps(run), encoding="utf-8")

    report = audit_frontier_pool([str(p)], top_k=3)
    picked = [row for row in report.runs[0].rows if row.picked]
    assert len(picked) == 1
    assert picked[0].candidate_index == 1
    assert report.runs[0].aggregate["picked_count"] == 1


def test_rating_sheet_exports_picked_and_top_frontier_rows(tmp_path):
    p = tmp_path / "run.json"
    run = {
        "seed": "A forgotten umbrella at the station",
        "config": {"condition": "selector", "candidates_per_step": 2},
        "steps": [
            {
                "step": 1,
                "picked": {"text": "The umbrella rests beside the platform clock.", "score": {"total": 2.0}},
                "candidates": [
                    {"text": "The umbrella rests beside the platform clock.", "score": {"total": 2.0}},
                    {
                        "text": "The umbrella, now a garden, wraps vines around the station clock.",
                        "score": {"total": 1.0},
                    },
                ],
            }
        ],
    }
    p.write_text(json.dumps(run), encoding="utf-8")

    report = audit_frontier_pool([str(p)], top_k=2)
    rows = rating_sheet_rows(report, top_k=1)
    assert len(rows) == 2
    assert {row["kind"] for row in rows} == {"picked", "top_frontier"}
    assert all("human_score" in row for row in rows)

    csv_out = tmp_path / "ratings.csv"
    md_out = tmp_path / "ratings.md"
    write_rating_sheet(rows, str(csv_out))
    write_rating_markdown(rows, str(md_out))

    with csv_out.open(encoding="utf-8", newline="") as f:
        exported = list(csv.DictReader(f))
    assert len(exported) == 2
    assert exported[0]["human_notes"] == ""
    assert "ordinary_anchor_retention" in exported[0]
    assert "fantasy_prop_score" in exported[0]
    assert "Human Rating Sheet" in md_out.read_text(encoding="utf-8")


def test_rating_sheet_dedupes_same_step_text(tmp_path):
    p = tmp_path / "run.json"
    duplicate = "The umbrella, now a garden, wraps vines around the station clock."
    run = {
        "seed": "A forgotten umbrella at the station",
        "config": {"condition": "selector", "candidates_per_step": 2},
        "steps": [
            {
                "step": 1,
                "picked": {"text": duplicate, "score": {"total": 2.0}},
                "candidates": [
                    {"text": duplicate, "score": {"total": 2.0}},
                    {"text": duplicate, "score": {"total": 2.0}},
                ],
            }
        ],
    }
    p.write_text(json.dumps(run), encoding="utf-8")

    report = audit_frontier_pool([str(p)], top_k=2)
    rows = rating_sheet_rows(report, top_k=2)
    assert len(rows) == 1
    assert rows[0]["picked"] == 1
    assert set(rows[0]["kind"].split("+")) == {"picked", "top_frontier"}

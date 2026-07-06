import csv
import json

from depaysement_lab.frontier import (
    FrontierAuditReport,
    FrontierCandidateRow,
    FrontierRunAudit,
    audit_frontier_pool,
    audit_trajectory_runs,
    format_trajectory_report,
    frontier_exemplar_store,
    rating_sheet_rows,
    readable_frontier_score,
    write_frontier_exemplar_store,
    write_frontier_reading_report,
    write_rating_markdown,
    write_rating_sheet,
)
from depaysement_lab.noun_graph import (
    build_affordance_reroute_report,
    build_noun_graph_report,
    frontier_band_documents,
    format_affordance_reroute_report,
    format_noun_graph_report,
    write_affordance_reroute_csv,
    write_affordance_reroute_json,
    write_noun_graph_json,
    write_noun_graph_nodes_csv,
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
    assert "pool_mean_stock_prop_attractor_score" in r.aggregate
    assert "pool_mean_soft_style_cliche_score" in r.aggregate
    assert r.rows[0].metrics["ordinary_anchor_retention"] > 0
    assert "station" in r.rows[0].metrics["ordinary_anchor_hits"]
    assert report.top_frontier_examples


def test_compliant_only_band_threshold_ignores_hard_banned_rows():
    banned = FrontierCandidateRow(
        run_name="run",
        condition="steer_alpha_0p77__reselect_banded-frontier_best",
        path="run.json",
        step=1,
        candidate_index=1,
        picked=False,
        text="The receipt, now a music box, opens with a porcelain doll and a key.",
        context_before="receipt",
        score_total=1.0,
        readable_ontology_frontier=1.0,
        frontier_quality=1.0,
        metrics={
            "hard_ban_failed": True,
            "hard_ban_hits": ["music box", "porcelain", "key"],
            "syntax_readability_proxy": 0.9,
            "ontology_collapse_density": 0.9,
            "unfinished": 0.0,
            "stock_prop_attractor_score": 1.0,
            "ordinary_anchor_retention": 0.5,
        },
    )
    compliant = FrontierCandidateRow(
        run_name="run",
        condition="steer_alpha_0p77__reselect_banded-frontier_best",
        path="run.json",
        step=1,
        candidate_index=2,
        picked=True,
        text="The receipt, now a mirror garden, leans toward a window of folded paper.",
        context_before="receipt",
        score_total=1.0,
        readable_ontology_frontier=0.6,
        frontier_quality=0.6,
        metrics={
            "hard_ban_failed": False,
            "hard_ban_hits": [],
            "syntax_readability_proxy": 0.8,
            "ontology_collapse_density": 0.6,
            "unfinished": 0.0,
            "stock_prop_attractor_score": 0.0,
            "ordinary_anchor_retention": 0.5,
        },
    )
    report = FrontierAuditReport(
        runs=[
            FrontierRunAudit(
                name="run",
                condition="steer_alpha_0p77__reselect_banded-frontier_best",
                path="run.json",
                seed="receipt",
                candidate_count=2,
                picked_count=1,
                steps=1,
                truncated_steps=0,
                aggregate={},
                rows=[banned, compliant],
            )
        ]
    )

    docs = frontier_band_documents(
        report,
        frontier_band_ratio=0.8,
        frontier_band_width=0.1,
        compliant_only=True,
    )

    assert [doc.text for doc in docs] == [compliant.text]
    assert docs[0].hard_ban_failed is False
    assert "optical_memory" in docs[0].affordance_classes


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
                    "text": "The umbrella becomes a tiny station garden.<|eot_id|><end_of_turn><eos>",
                    "score": {"total": -99.0},
                },
                "candidates": [
                    {
                        "text": "The umbrella becomes a tiny station garden.<|eot_id|><end_of_turn><eos>",
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
    assert "<end_of_turn>" not in row.metrics["text"]
    assert "<eos>" not in row.metrics["text"]
    assert row.metrics["unfinished"] == 0.0
    assert row.score_total != -99.0

    out = tmp_path / "texts.md"
    write_frontier_reading_report(report, str(out))
    text = out.read_text(encoding="utf-8")
    assert "Picked Final Text" in text
    assert "The umbrella becomes a tiny station garden.<|eot_id|>" not in text
    assert "<end_of_turn>" not in text
    assert "<eos>" not in text


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


def test_frontier_exemplar_store_exports_max_band_examples(tmp_path):
    p = tmp_path / "run.json"
    run = {
        "seed": "A receipt on the counter",
        "config": {"condition": "steer_alpha_0p66", "candidates_per_step": 3},
        "steps": [
            {
                "step": 1,
                "picked": {
                    "text": "The receipt, now a garden, wraps vines around the counter drawer.",
                    "score": {"total": 2.0},
                },
                "candidates": [
                    {
                        "text": "The receipt, now a garden, wraps vines around the counter drawer.",
                        "score": {"total": 2.0},
                    },
                    {
                        "text": "The receipt rests on the counter.",
                        "score": {"total": 1.0},
                    },
                    {
                        "text": "A tiny antique porcelain music box glows beside the receipt.",
                        "score": {"total": 0.5},
                    },
                ],
            }
        ],
    }
    p.write_text(json.dumps(run), encoding="utf-8")

    report = audit_frontier_pool([str(p)], top_k=3)
    store = frontier_exemplar_store(report, top_k=3)
    assert store["frontier_max"] > 0
    assert store["examples"]
    assert "legend_label" in store["examples"][0]
    assert "text" in store["examples"][0]

    md_out = tmp_path / "frontier_exemplars.md"
    json_out = tmp_path / "frontier_exemplars.json"
    write_frontier_exemplar_store(report, str(md_out), json_path=str(json_out), top_k=3)
    assert "Frontier Exemplar Store" in md_out.read_text(encoding="utf-8")
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["examples"][0]["text"]


def test_noun_graph_finds_frontier_hub_terms(tmp_path):
    p = tmp_path / "run.json"
    run = {
        "seed": "A receipt on the counter",
        "config": {"condition": "steer_alpha_0p66", "candidates_per_step": 2},
        "steps": [
            {
                "step": 1,
                "picked": {
                    "text": "The receipt, now a music box, opens with a brass key beside a station clock.",
                    "score": {"total": 2.0},
                },
                "candidates": [
                    {
                        "text": "The receipt, now a music box, opens with a brass key beside a station clock.",
                        "score": {"total": 2.0},
                    },
                    {
                        "text": "The receipt rests on the counter.",
                        "score": {"total": 1.0},
                    },
                ],
            },
            {
                "step": 2,
                "picked": {
                    "text": "The music box becomes a leather-bound book whose key ticks like a clock.",
                    "score": {"total": 2.0},
                },
                "candidates": [
                    {
                        "text": "The music box becomes a leather-bound book whose key ticks like a clock.",
                        "score": {"total": 2.0},
                    }
                ],
            },
        ],
    }
    p.write_text(json.dumps(run), encoding="utf-8")

    frontier_report = audit_frontier_pool([str(p)], top_k=3)
    graph = build_noun_graph_report(frontier_report, top_k=5, max_nodes=20)
    terms = {node["term"] for node in graph.nodes}
    assert {"music box", "key", "clock"} & terms
    assert any("canonical_stock_hub" in node["affordance_classes"] for node in graph.nodes)
    assert graph.edges
    rendered = format_noun_graph_report(graph)
    assert "Frontier Noun Graph" in rendered
    assert "Affordance Classes" in rendered

    json_out = tmp_path / "noun_graph.json"
    csv_out = tmp_path / "noun_graph_nodes.csv"
    write_noun_graph_json(graph, str(json_out))
    write_noun_graph_nodes_csv(graph, str(csv_out))
    assert json.loads(json_out.read_text(encoding="utf-8"))["nodes"]
    with csv_out.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert "affordance_classes" in rows[0]


def test_affordance_reroute_matrix_compares_class_shifts(tmp_path):
    base = tmp_path / "base.json"
    ablation = tmp_path / "ablation.json"
    base.write_text(
        json.dumps(
            {
                "seed": "A receipt on the counter",
                "config": {
                    "condition": "steer_alpha_0p66__reselect_banded-frontier_best",
                    "candidates_per_step": 1,
                },
                "steps": [
                    {
                        "step": 1,
                        "picked": {
                            "text": "The receipt, now a music box, opens with a brass key beside a station clock.",
                            "score": {"total": 2.0},
                        },
                        "candidates": [
                            {
                                "text": "The receipt, now a music box, opens with a brass key beside a station clock.",
                                "score": {"total": 2.0},
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ablation.write_text(
        json.dumps(
            {
                "seed": "A receipt on the counter",
                "config": {"condition": "steer_alpha_0p66", "candidates_per_step": 1},
                "steps": [
                    {
                        "step": 1,
                        "picked": {
                            "text": "The receipt, now a typewriter, opens a paper garden beside a harmonica.",
                            "score": {"total": 2.0},
                        },
                        "candidates": [
                            {
                                "text": "The receipt, now a typewriter, opens a paper garden beside a harmonica.",
                                "score": {"total": 2.0},
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    base_frontier = audit_frontier_pool([str(base)], top_k=2)
    ablation_frontier = audit_frontier_pool([str(ablation)], top_k=2)
    reroute = build_affordance_reroute_report(
        base_frontier,
        ablation_frontier,
        frontier_band_ratio=0.0,
        frontier_band_width=1.0,
    )
    by_class = {
        row["affordance_class"]: row
        for row in reroute.matrix
        if row["condition"] == "steer_alpha_0p66"
    }
    diagnostic = next(row for row in reroute.diagnostics if row["condition"] == "steer_alpha_0p66")
    assert by_class["canonical_stock_hub"]["delta"] < 0
    assert by_class["organic_expansion"]["delta"] > 0
    assert by_class["acoustic_mechanism"]["delta"] == 0
    assert diagnostic["frontier_survival_rate"] == 1.0
    assert diagnostic["canonical_drop"] > 0
    assert "affordance_load_delta" in diagnostic
    rendered = format_affordance_reroute_report(reroute)
    assert "Affordance Reroute Matrix" in rendered
    assert "Reroute Diagnostics" in rendered

    json_out = tmp_path / "reroute.json"
    csv_out = tmp_path / "reroute.csv"
    write_affordance_reroute_json(reroute, str(json_out))
    write_affordance_reroute_csv(reroute, str(csv_out))
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["matrix"]
    assert payload["diagnostics"]
    with csv_out.open(encoding="utf-8", newline="") as f:
        assert list(csv.DictReader(f))


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
    assert "stock_prop_attractor_score" in exported[0]
    assert "soft_style_cliche_score" in exported[0]
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


def test_trajectory_audit_scores_picked_sequence(tmp_path):
    p = tmp_path / "run.json"
    run = {
        "seed": "A forgotten umbrella at the station",
        "config": {"condition": "steer_alpha_0p66"},
        "steps": [
            {
                "step": 1,
                "picked": {
                    "text": "The umbrella, now a garden, wraps vines around the station clock.",
                    "score": {"total": 2.0, "anti_repetition": 0.0},
                },
            },
            {
                "step": 2,
                "picked": {
                    "text": 'The garden, now a clock, reads: "For the rain that kept waiting."',
                    "score": {"total": 1.0, "anti_repetition": -0.2},
                },
            },
        ],
    }
    p.write_text(json.dumps(run), encoding="utf-8")

    report = audit_trajectory_runs([str(p)], top_k=1)
    assert len(report.runs) == 1
    aggregate = report.runs[0].aggregate
    assert aggregate["trajectory_frontier_auc"] > 0
    assert aggregate["readable_transition_auc"] > 0
    assert aggregate["anchor_survival"] > 0
    assert aggregate["lineage_continuity"] > 0
    assert aggregate["object_lineage_continuity"] > 0
    assert aggregate["hub_revisit_rate"] > 0
    assert aggregate["motif_loop_penalty"] > 0
    assert aggregate["now_chain_pressure"] > 0
    assert aggregate["inscription_pressure"] > 0
    assert "Readable Ontology Collapse Trajectory" in format_trajectory_report(report)

import json

from depaysement_lab.proto_v2 import SelectorConfig
from depaysement_lab.reselect import posthoc_reselect_files, write_posthoc_reselect_batch


def test_posthoc_reselect_picks_frontier_candidate_without_generation(tmp_path):
    source = tmp_path / "run.json"
    seed = "A forgotten umbrella at the station"
    plain = "The umbrella rests beside the platform clock."
    frontier = "The umbrella, now a garden, wraps vines around the station clock."
    run = {
        "seed": seed,
        "config": {"condition": "source", "candidates_per_step": 2},
        "final_text": f"{seed}\n\n{plain}",
        "steps": [
            {
                "step": 1,
                "mode": "depaysement",
                "context_before": seed,
                "picked": {"text": plain, "score": {"total": 2.0}},
                "candidates": [
                    {"text": plain, "score": {"total": 2.0}},
                    {"text": frontier, "score": {"total": 1.0}},
                ],
            }
        ],
    }
    source.write_text(json.dumps(run), encoding="utf-8")

    results = posthoc_reselect_files(
        [str(source)],
        selector=SelectorConfig(objective="frontier"),
        choose="best",
    )

    assert len(results) == 1
    result = results[0]
    assert result.changed_steps == 1
    step = result.run["steps"][0]
    assert step["picked"]["text"] == frontier
    assert step["context_before"] == seed
    assert step["posthoc_context_policy"] == "recorded"
    assert step["posthoc_source_picked"]["text"] == plain
    assert step["candidates"][0]["selector_metrics"]["posthoc_rank"] == 1
    assert step["candidates"][0]["selector_metrics"]["posthoc_original_picked"] is False
    assert result.run["config"]["posthoc_reselect"] is True
    assert result.run["config"]["select_objective"] == "frontier"
    assert result.run["final_text"].endswith(frontier)


def test_write_posthoc_reselect_batch(tmp_path):
    source = tmp_path / "run.json"
    source.write_text(
        json.dumps(
            {
                "seed": "A forgotten umbrella at the station",
                "config": {"condition": "source", "candidates_per_step": 1},
                "steps": [
                    {
                        "step": 1,
                        "picked": {"text": "The umbrella, now a garden, wraps vines around the station clock."},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    results = posthoc_reselect_files([str(source)], selector=SelectorConfig(objective="frontier"))
    batch = write_posthoc_reselect_batch(results, str(tmp_path / "out"))

    assert len(batch.paths) == 1
    payload = json.loads((tmp_path / "out" / "run__frontier_best.json").read_text(encoding="utf-8"))
    assert payload["posthoc"]["artifact_name"] == "run__frontier_best"
    assert payload["config"]["posthoc_reselect"] is True

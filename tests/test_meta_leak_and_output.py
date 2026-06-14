from depaysement_lab.proto_v2 import (
    DepaysementScorer,
    DepaysementEngine,
    DummyGenerator,
    SelectorConfig,
    build_depaysement_prompt,
    cleanup_continuation,
)
import random


class FixedGenerator:
    def __init__(self, candidates):
        self.candidates = list(candidates)

    def generate(self, prompt, n, temperature, top_p, max_new_tokens):
        return self.candidates[:n]


class SequentialGenerator:
    def __init__(self, batches):
        self.batches = [list(batch) for batch in batches]
        self.calls = 0

    def generate(self, prompt, n, temperature, top_p, max_new_tokens):
        batch = self.batches[min(self.calls, len(self.batches) - 1)]
        self.calls += 1
        return batch[:n]


def test_meta_leak_is_cut_from_cleanup():
    text = "A plastic bag flaps beside the nest. (Note: I've tried to continue the fragment as per the instructions.)"
    assert cleanup_continuation(text) == "A plastic bag flaps beside the nest."


def test_meta_leak_is_heavily_penalized():
    scorer = DepaysementScorer()
    clean = scorer.score("A plastic bag flaps beside the nest.")
    leaky = scorer.score("A plastic bag flaps beside the nest. (Note: I've tried to continue the fragment as per the instructions.)")
    assert leaky.anti_meta_leak < -0.8
    assert clean.total > leaky.total


def test_write_run_serializes():
    rng = random.Random(0)
    engine = DepaysementEngine(DummyGenerator(rng), rng=rng)
    run = engine.write_run("A forgotten umbrella at the station", steps=1, candidates_per_step=3, keep_candidates=2)
    payload = run.to_dict()
    assert payload["final_text"].startswith("A forgotten umbrella")
    assert payload["steps"][0]["picked"]["score_compact"]
    assert len(payload["steps"][0]["candidates"]) <= 2


def test_cleanup_removes_generated_control_tokens():
    assert cleanup_continuation("A tiny station garden.<|eot_id|>") == "A tiny station garden."


def test_ban_terms_are_added_to_prompt_and_run_config():
    prompt = build_depaysement_prompt(
        "The receipt on the counter",
        motifs=["receipt"],
        ban_terms=["music box", "leather-bound book"],
    )
    assert "Do not use these words or phrases: music box; leather-bound book." in prompt
    assert "reroute it through ordinary objects" in prompt

    rng = random.Random(0)
    engine = DepaysementEngine(
        FixedGenerator(["The receipt folds itself into a small paper hinge."]),
        rng=rng,
    )
    run = engine.write_run(
        "The receipt on the counter",
        steps=1,
        candidates_per_step=1,
        choose="best",
        ban_terms=["music box", "leather-bound book"],
        include_prompt=True,
    )
    assert run.config["ban_terms"] == ["music box", "leather-bound book"]
    assert "leather-bound book" in run.steps[0].prompt


def test_frontier_selector_picks_readable_ontology_collapse():
    rng = random.Random(0)
    generator = FixedGenerator(
        [
            "The umbrella rests beside the platform clock.",
            "The umbrella, now a garden, wraps vines around the station clock.",
            "The platform clock is old and dusty.",
        ]
    )
    engine = DepaysementEngine(generator, rng=rng, selector=SelectorConfig(objective="frontier"))
    run = engine.write_run(
        "A forgotten umbrella at the station",
        steps=1,
        candidates_per_step=3,
        choose="best",
        keep_candidates=3,
    )
    picked = run.steps[0].picked
    assert "now a garden" in picked.text
    assert picked.selector_score is not None
    payload = run.to_dict()
    assert payload["config"]["select_objective"] == "frontier"
    assert payload["steps"][0]["picked"]["selector_metrics"]["readable_ontology_frontier"] > 0
    assert "cliche_attractor_score" in payload["steps"][0]["picked"]["selector_metrics"]


def test_banded_frontier_penalizes_out_of_band_collapse():
    rng = random.Random(0)
    generator = FixedGenerator(
        [
            "The umbrella becomes a tiny station garden beside the platform clock.",
            "The umbrella, now a garden, wraps vines around the station clock.",
            "The umbrella rests beside the platform clock.",
        ]
    )
    engine = DepaysementEngine(
        generator,
        rng=rng,
        selector=SelectorConfig(objective="banded-frontier"),
    )
    run = engine.write_run(
        "A forgotten umbrella at the station",
        steps=1,
        candidates_per_step=3,
        choose="best",
        keep_candidates=3,
    )

    picked = run.steps[0].picked
    assert "wraps vines" in picked.text
    assert picked.selector_metrics["objective"] == "banded-frontier"
    assert picked.selector_metrics["band_violation"] < run.steps[0].candidates[1].selector_metrics["band_violation"]


def test_anchor_guard_steers_selector_away_from_stock_fantasy_props():
    rng = random.Random(0)
    generator = FixedGenerator(
        [
            "An antique music box opens inside a porcelain miniature clock.",
            "The umbrella becomes a garden that grips the station sign with wet vines.",
            "The umbrella rests beside the station wall.",
        ]
    )
    engine = DepaysementEngine(
        generator,
        rng=rng,
        selector=SelectorConfig(
            objective="hybrid",
            fantasy_prop_weight=2.0,
            ordinary_anchor_weight=1.0,
            ordinary_anchor_min=0.5,
        ),
    )
    run = engine.write_run(
        "A forgotten umbrella at the station",
        steps=1,
        candidates_per_step=3,
        choose="best",
        keep_candidates=3,
    )

    picked = run.steps[0].picked
    fantasy = next(c for c in run.steps[0].candidates if "music box" in c.text)
    assert "station sign" in picked.text
    assert fantasy.selector_metrics["fantasy_prop_score"] > picked.selector_metrics["fantasy_prop_score"]
    assert picked.selector_metrics["ordinary_anchor_retention"] >= 0.5
    assert "umbrella" in picked.selector_metrics["ordinary_anchor_hits"]


def test_hard_unfinished_gate_rejects_truncated_frontier_candidate():
    rng = random.Random(0)
    truncated = (
        "The umbrella, now a garden, wraps vines around the station clock, "
        "as the platform, the sign, the ticket, the old rain, the"
    )
    complete = "The umbrella becomes a garden that grips the station sign."
    generator = FixedGenerator([truncated, complete])
    engine = DepaysementEngine(
        generator,
        rng=rng,
        selector=SelectorConfig(
            objective="banded-frontier",
            hard_unfinished_max=0.0,
            unfinished_weight=1.4,
        ),
    )
    run = engine.write_run(
        "A forgotten umbrella at the station",
        steps=1,
        candidates_per_step=2,
        choose="best",
        keep_candidates=2,
    )

    picked = run.steps[0].picked
    rejected = next(c for c in run.steps[0].candidates if c.text == truncated)
    assert picked.text == complete
    assert picked.selector_metrics["hard_gate_failed"] is False
    assert rejected.selector_metrics["hard_gate_failed"] is True
    assert rejected.selector_metrics["hard_gate_penalty"] > 0


def test_trajectory_stop_halts_after_unfinished_pick():
    rng = random.Random(0)
    generator = SequentialGenerator(
        [
            ["The umbrella, now a garden, wraps vines around the station clock."],
            ["The garden becomes a clock that listens to the platform rain."],
            ["The clock, now a ticket booth, as the platform, the sign, the old rain, the"],
            ["This step should not be generated."],
        ]
    )
    engine = DepaysementEngine(
        generator,
        rng=rng,
        selector=SelectorConfig(objective="frontier"),
    )
    run = engine.write_run(
        "A forgotten umbrella at the station",
        steps=5,
        candidates_per_step=1,
        choose="best",
        keep_candidates=1,
        trajectory_stop=True,
        trajectory_min_steps=3,
        trajectory_unfinished_max=0.0,
    )

    assert len(run.steps) == 3
    assert run.config["trajectory_stop"]["triggered"] is True
    assert run.config["trajectory_stop"]["step"] == 3
    assert "unfinished" in run.config["trajectory_stop"]["reason"]

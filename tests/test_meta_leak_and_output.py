from depaysement_lab.proto_v2 import DepaysementScorer, DepaysementEngine, DummyGenerator, SelectorConfig, cleanup_continuation
import random


class FixedGenerator:
    def __init__(self, candidates):
        self.candidates = list(candidates)

    def generate(self, prompt, n, temperature, top_p, max_new_tokens):
        return self.candidates[:n]


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

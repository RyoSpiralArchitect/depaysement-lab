from depaysement_lab.model_policy import infer_model_policy
from depaysement_lab.proto_v2 import DepaysementScorer


def test_base_model_is_control_condition():
    p = infer_model_policy("gpt2")
    assert p.kind == "base"
    assert "control" in p.recommendation.lower()


def test_instruct_model_is_main_condition():
    p = infer_model_policy("mlx-community/Llama-3.2-3B-Instruct-4bit")
    assert p.kind == "instruct"


def test_semantic_collage_scores_below_staged_image():
    scorer = DepaysementScorer()
    good = scorer.score("In the hospital corridor, the sea sleeps under a white sheet.")
    collage = scorer.score("Umbrella, moon, bone, ticket, fish, window, stamp, tongue, sea, sea, sea.")
    assert good.total > collage.total
    assert collage.anti_semantic_collage < -0.3

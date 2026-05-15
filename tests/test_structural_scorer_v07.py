from types import SimpleNamespace

from depaysement_lab.scorer_v07 import image_relation_graph, make_scorer_v07


def _args(**overrides):
    base = dict(
        bank=None,
        lexicon=None,
        disable_lexicon=False,
        enable_lexicon=False,
        lexicon_prior_scale=None,
        scorer_profile="structural",
        no_bank_score=False,
        bank_score_mode="auto",
        bank_weight=None,
        embed_model=None,
        device=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_structural_default_does_not_reward_surreal_vocabulary():
    scorer = make_scorer_v07(_args())
    score = scorer.score("The umbrella, the moon, the sea, and the refrigerator wait at the station.")
    assert score.concept_dispersion == 0.0
    assert score.pair_distance == 0.0
    assert score.agency_inversion == 0.0
    assert score.aesthetic_prior == 0.0
    assert score.bank_mode == "off"


def test_lexical_hash_bank_is_explicit_opt_in():
    default = make_scorer_v07(_args())
    hashed = make_scorer_v07(_args(bank_score_mode="hash"))
    assert default.score("A mirror sleeps inside the station.").bank_mode == "off"
    assert hashed.score("A mirror sleeps inside the station.").bank_mode == "lex"


def test_relation_graph_penalizes_parallel_cluster_sprawl():
    good = image_relation_graph("A faded photograph of a mountain range melts into the surrounding machinery.")
    weak = image_relation_graph(
        "The umbrella's handle is wrapped around a miniature skyscraper constructed from discarded keys, "
        "tangled in sparklers, next to a dog's kennel made of rusted train car wheels, "
        "inside which a deceased pigeon lies with its eyes glued shut with faint blue paint."
    )
    assert good.cluster_sprawl_penalty() == 0.0
    assert weak.cluster_sprawl_penalty() > 0.4

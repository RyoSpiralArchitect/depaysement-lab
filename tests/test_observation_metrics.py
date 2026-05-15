from depaysement_lab.observation import (
    HashNgramVectorizer,
    concept_field_distribution,
    graph_fragmentation,
    js_divergence,
)
from depaysement_lab.scorer_v07 import image_relation_graph


def test_js_divergence_for_distinct_field_distributions():
    a = concept_field_distribution("The office stamp waits beside a document.")
    b = concept_field_distribution("The sea carries a bird under the moon.")
    assert js_divergence(a, b) > 0.0


def test_graph_fragmentation_penalizes_sprawling_of_chain():
    integrated = image_relation_graph("The sea sleeps under a white sheet in the hospital corridor.")
    sprawling = image_relation_graph(
        "A cloud of document of rib of moon of shoe of silence of bird lies beside a chair, a key, a ticket, and a fish."
    )
    assert graph_fragmentation(sprawling) >= graph_fragmentation(integrated)


def test_hash_vectorizer_is_dependency_free_and_bounded():
    v = HashNgramVectorizer(dim=64)
    sim = v.similarity("A forgotten umbrella at the station", "The umbrella rests at the station wall")
    assert -1.0 <= sim <= 1.0

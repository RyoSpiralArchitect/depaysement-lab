from pathlib import Path

from depaysement_lab.proto_v2 import PromptBank


def test_prompt_bank_provenance_preserves_collection_inputs():
    bank = PromptBank(
        positive_depaysement=["positive", "positive"],
        negative_realist_repair=["realist"],
        negative_weird_noise=["noise"],
    )

    first = bank.provenance()
    second = bank.provenance()

    assert first == second
    assert first["format"] == "depaysement_lab.prompt_bank.v1"
    assert first["counts"] == {
        "positive_depaysement": 2,
        "negative_realist_repair": 1,
        "negative_weird_noise": 1,
    }
    assert first["prompts"]["positive_depaysement"] == ["positive", "positive"]
    assert len(first["canonical_sha256"]) == 64


def test_primary_prompt_bank_matches_documented_hash():
    root = Path(__file__).resolve().parents[1]
    bank = PromptBank.from_file(str(root / "data" / "depaysement_bank_en_v3.json"))

    assert bank.provenance()["canonical_sha256"] == (
        "b8428f00361bac7a59c6b7a777e42a3b6cbde6d1feb257639dc0cd784fe692f4"
    )

import json

from depaysement_lab.bank_audit import audit_bank_lexical_overlap


def test_bank_audit_separates_positive_and_negative_literal_hits(tmp_path):
    path = tmp_path / "bank.json"
    path.write_text(
        json.dumps(
            {
                "positive_depaysement": ["The receipt opens a hallway."],
                "negative_realist_repair": [],
                "negative_weird_noise": ["An antique music box waits in silver mist."],
            }
        ),
        encoding="utf-8",
    )

    report = audit_bank_lexical_overlap(path)

    assert report["positive_direct_overlap"] == {
        "stock_prop_attractor": 0,
        "soft_style_cliche": 0,
    }
    negative = report["partitions"]["negative_weird_noise"]["groups"]
    assert negative["stock_prop_attractor"]["unique_terms"] == ["antique", "music box"]
    assert negative["soft_style_cliche"]["unique_terms"] == ["mist", "silver mist"]

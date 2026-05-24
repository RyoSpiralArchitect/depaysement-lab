import json

from depaysement_lab.cli import load_seed_bank, safe_seed_label


def test_load_seed_bank_reads_json_object_and_limits(tmp_path):
    path = tmp_path / "seeds.json"
    path.write_text(json.dumps({"seeds": ["The receipt on the counter", "The bus was late"]}), encoding="utf-8")

    assert load_seed_bank(str(path), "fallback", limit=1) == ["The receipt on the counter"]


def test_load_seed_bank_reads_text_and_deduplicates(tmp_path):
    path = tmp_path / "seeds.txt"
    path.write_text("# comment\nA blue mug\nA blue mug\nThe printer tray\n", encoding="utf-8")

    assert load_seed_bank(str(path), "fallback") == ["A blue mug", "The printer tray"]


def test_safe_seed_label_is_filename_friendly():
    assert safe_seed_label("The receipt on the counter!", 3).startswith("seed03_the_receipt")

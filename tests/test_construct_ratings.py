import csv
import json

from depaysement_lab.construct_ratings import (
    analyze_construct_rows,
    merge_construct_ratings,
    parse_construct_value,
    read_construct_markdown,
)


def _write_fixture(tmp_path):
    markdown = tmp_path / "ratings.md"
    markdown.write_text(
        """# Blind Human Construct Rating

## R001

```text
The mug becomes a doorway.
```

human_anchor_traceable: 1
human_role_or_affordance_change: 1
human_merely_decorative: 0
human_readable: 1
human_stock_loop_or_sprawl_failure: 0
human_notes: Clean transport.

## R002

```text
The mug glows dreamily.
```

human_anchor_traceable: 1
human_role_or_affordance_change: 0
human_merely_decorative: 1
human_readable: 1
human_stock_loop_or_sprawl_failure:
human_notes: Missing one field.
""",
        encoding="utf-8",
    )
    public = tmp_path / "ratings.csv"
    with public.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "item_id",
                "text",
                "human_anchor_traceable",
                "human_role_or_affordance_change",
                "human_merely_decorative",
                "human_readable",
                "human_stock_loop_or_sprawl_failure",
                "human_notes",
            ],
        )
        writer.writeheader()
        writer.writerow({"item_id": "R001", "text": "The mug becomes a doorway."})
        writer.writerow({"item_id": "R002", "text": "The mug glows dreamily."})
    key = tmp_path / "key.json"
    key.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "item_id": "R001",
                        "source_item_id": "seed1",
                        "prompt_mode": "operational",
                        "alpha": 0.6,
                        "candidate_index": 1,
                        "observer_label": "readable_transport",
                        "metrics": {
                            "anchor_phrase_coverage": 1.0,
                            "ontology_collapse_density": 0.4,
                            "syntax_readability_proxy": 0.8,
                        },
                    },
                    {
                        "item_id": "R002",
                        "source_item_id": "seed1",
                        "prompt_mode": "operational",
                        "alpha": 0.0,
                        "candidate_index": 1,
                        "observer_label": "decorative_near_miss",
                        "metrics": {
                            "anchor_phrase_coverage": 1.0,
                            "ontology_collapse_density": 0.1,
                            "syntax_readability_proxy": 0.8,
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return markdown, public, key


def test_construct_markdown_parser_and_value_validation(tmp_path):
    markdown, _, _ = _write_fixture(tmp_path)
    parsed = read_construct_markdown(str(markdown))

    assert parsed["R001"]["human_notes"] == "Clean transport."
    assert parsed["R001"]["text"] == "The mug becomes a doorway."
    assert parse_construct_value("0.5") == 0.5
    assert parse_construct_value("0/5") is None


def test_construct_analysis_preserves_missing_values(tmp_path):
    markdown, public, key = _write_fixture(tmp_path)
    merged, rows, warnings = merge_construct_ratings(
        markdown_path=str(markdown),
        rating_csv_path=str(public),
        key_path=str(key),
    )
    analysis = analyze_construct_rows(rows, source=str(markdown), bootstrap_samples=20)

    assert merged[0]["human_role_or_affordance_change"] == "1"
    assert rows[0]["human_construct_score"] == 1.0
    assert rows[0]["human_construct_floor_score"] == 1.0
    assert rows[0]["human_construct_permissive"] == 1
    assert rows[0]["human_construct_strict"] == 1
    assert rows[1]["human_construct_complete"] == 0
    assert analysis["complete_construct_rows"] == 1
    assert analysis["observer_confusion"]["permissive"]["tp"] == 1
    assert analysis["observer_confusion"]["strict"]["tp"] == 1
    assert warnings == []

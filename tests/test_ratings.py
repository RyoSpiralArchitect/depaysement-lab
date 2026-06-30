import csv
import math

from depaysement_lab.ratings import (
    analyze_rating_rows,
    format_rating_analysis,
    load_rating_rows,
    merge_markdown_ratings,
    read_markdown_ratings,
    write_rating_rows,
)


def test_merge_markdown_ratings_and_analyze(tmp_path):
    sheet = tmp_path / "ratings.csv"
    rows = [
        {
            "id": "a",
            "picked": "1",
            "condition": "alpha_0p6",
            "kind": "picked",
            "readable_ontology_frontier": "0.1",
            "ontology_collapse_density": "0.5",
            "syntax_readability_proxy": "0.7",
            "unfinished": "0",
            "human_score": "",
            "human_notes": "",
        },
        {
            "id": "b",
            "picked": "0",
            "condition": "alpha_0p6",
            "kind": "top_frontier",
            "readable_ontology_frontier": "0.3",
            "ontology_collapse_density": "0.7",
            "syntax_readability_proxy": "0.6",
            "unfinished": "0",
            "human_score": "",
            "human_notes": "",
        },
    ]
    write_rating_rows(str(sheet), rows, list(rows[0]))
    markdown = tmp_path / "ratings.md"
    markdown.write_text(
        "\n".join(
            [
                "# Human Rating Sheet",
                "",
                "## 1. a",
                "",
                "human_score: 6.5",
                "",
                "human_notes: too clear",
                "",
                "## 2. b",
                "",
                "human_score:",
                "8.5",
                "",
                "human_notes:",
                "nicely odd",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    loaded, fieldnames = load_rating_rows(str(sheet))
    assert read_markdown_ratings(str(markdown))["b"]["human_score"] == "8.5"
    assert merge_markdown_ratings(loaded, str(markdown)) == 4
    assert loaded[0]["human_score"] == "6.5"
    assert loaded[1]["human_notes"] == "nicely odd"

    analysis = analyze_rating_rows(
        loaded,
        metrics=["readable_ontology_frontier", "syntax_readability_proxy"],
        source=str(sheet),
    )
    assert analysis["n"] == 2
    assert math.isclose(analysis["correlations"][0]["spearman"], 1.0)
    assert analysis["top_rows"][0]["id"] == "b"
    assert "Human Taste Rating Analysis" in format_rating_analysis(analysis)

    write_rating_rows(str(sheet), loaded, fieldnames)
    with sheet.open("r", encoding="utf-8", newline="") as f:
        saved = list(csv.DictReader(f))
    assert saved[1]["human_score"] == "8.5"

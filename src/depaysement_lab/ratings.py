"""Human rating sheet analysis utilities."""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


DEFAULT_RATING_METRICS: Tuple[str, ...] = (
    "readable_ontology_frontier",
    "frontier_quality",
    "ontology_collapse_density",
    "identity_melt_score",
    "affordance_corruption_score",
    "category_bleeding_score",
    "syntax_readability_proxy",
    "graph_integration",
    "repair_pressure",
    "cliche_attractor_score",
    "fantasy_prop_score",
    "ordinary_anchor_retention",
    "unfinished",
    "meta_leak",
    "score_total",
)


def load_rating_rows(path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    p = Path(path)
    if p.suffix.lower() == ".jsonl":
        rows = [
            json.loads(line)
            for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        fieldnames: List[str] = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        return rows, fieldnames
    with p.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def write_rating_rows(path: str, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() == ".jsonl":
        with p.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
        return
    fields = list(fieldnames)
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with p.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def read_markdown_ratings(path: str) -> Dict[str, Dict[str, str]]:
    """Read inline or next-line human_score/human_notes from a rating Markdown view."""

    heading_re = re.compile(r"^##\s+\d+\.\s+(.+?)\s*$")
    ratings: Dict[str, Dict[str, str]] = {}
    current_id: Optional[str] = None
    pending_field: Optional[str] = None

    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        heading = heading_re.match(line)
        if heading:
            current_id = heading.group(1).strip()
            ratings.setdefault(current_id, {})
            pending_field = None
            continue
        if current_id is None:
            continue
        stripped = line.strip()
        if stripped.startswith("human_score:"):
            value = stripped.split(":", 1)[1].strip()
            if value:
                ratings[current_id]["human_score"] = value
                pending_field = None
            else:
                pending_field = "human_score"
            continue
        if stripped.startswith("human_notes:"):
            value = stripped.split(":", 1)[1].strip()
            if value:
                ratings[current_id]["human_notes"] = value
                pending_field = None
            else:
                pending_field = "human_notes"
            continue
        if pending_field and stripped and not stripped.startswith("human_"):
            ratings[current_id][pending_field] = stripped
            pending_field = None

    return ratings


def merge_markdown_ratings(rows: Sequence[Dict[str, Any]], markdown_path: str) -> int:
    ratings = read_markdown_ratings(markdown_path)
    changed = 0
    for row in rows:
        row_id = str(row.get("id") or "")
        patch = ratings.get(row_id)
        if not patch:
            continue
        for field in ("human_score", "human_notes"):
            if field in patch and row.get(field) != patch[field]:
                row[field] = patch[field]
                changed += 1
    return changed


def analyze_rating_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    metrics: Sequence[str] = DEFAULT_RATING_METRICS,
    source: str = "",
) -> Dict[str, Any]:
    scored = [dict(row) for row in rows if parse_float(row.get("human_score")) is not None]
    correlations = []
    for metric in metrics:
        pairs = [
            (parse_float(row.get(metric)), parse_float(row.get("human_score")))
            for row in scored
        ]
        pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
        xs = [float(x) for x, _ in pairs]
        ys = [float(y) for _, y in pairs]
        correlations.append(
            {
                "metric": metric,
                "n": len(pairs),
                "pearson": pearson(xs, ys),
                "spearman": pearson(rankdata(xs), rankdata(ys)) if len(pairs) >= 2 else None,
            }
        )

    top_rows = sorted(scored, key=lambda r: parse_float(r.get("human_score")) or 0.0, reverse=True)
    bottom_rows = sorted(scored, key=lambda r: parse_float(r.get("human_score")) or 0.0)
    analysis = {
        "source": source,
        "n": len(scored),
        "correlations": correlations,
        "group_means": {
            "condition": group_means(scored, lambda r: str(r.get("condition") or "unknown")),
            "picked": group_means(scored, lambda r: "picked" if truthy(r.get("picked")) else "not_picked"),
            "kind": group_means(scored, lambda r: str(r.get("kind") or "unknown")),
            "unfinished": group_means(
                scored,
                lambda r: "unfinished_gt_0" if (parse_float(r.get("unfinished")) or 0.0) > 0 else "clean_tail",
            ),
            "readability_band": group_means(scored, readability_band),
            "ontology_band": group_means(scored, ontology_band),
        },
        "top_rows": [compact_rating_row(row) for row in top_rows[:5]],
        "bottom_rows": [compact_rating_row(row) for row in bottom_rows[:5]],
        "notes": [
            "Small-n analysis: use directionally, not as a final calibration.",
            "Human notes are treated as taste signals, not labels to optimize blindly.",
        ],
    }
    return analysis


def format_rating_analysis(analysis: Mapping[str, Any]) -> str:
    lines = [
        "# Human Taste Rating Analysis",
        "",
        f"Source: `{analysis.get('source', '')}`",
        f"Rated rows: {analysis.get('n', 0)}",
        "",
        "This is a small-n calibration pass. Read correlations as directional hints, then check the text.",
        "",
        "## Correlations",
        "",
        "| metric | n | pearson | spearman |",
        "|---|---:|---:|---:|",
    ]
    for row in analysis.get("correlations", []):
        lines.append(
            "| {metric} | {n} | {pearson} | {spearman} |".format(
                metric=row.get("metric", ""),
                n=row.get("n", 0),
                pearson=format_number(row.get("pearson")),
                spearman=format_number(row.get("spearman")),
            )
        )

    group_means = analysis.get("group_means", {})
    for title, rows in group_means.items():
        lines.extend(
            [
                "",
                f"## Group Means: {title}",
                "",
                "| group | n | human | frontier | ont | read | unfinished |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in rows:
            lines.append(
                "| {group} | {n} | {human} | {frontier} | {ont} | {read} | {unfinished} |".format(
                    group=row.get("group", ""),
                    n=row.get("n", 0),
                    human=format_number(row.get("mean_human_score")),
                    frontier=format_number(row.get("mean_readable_ontology_frontier")),
                    ont=format_number(row.get("mean_ontology_collapse_density")),
                    read=format_number(row.get("mean_syntax_readability_proxy")),
                    unfinished=format_number(row.get("mean_unfinished")),
                )
            )

    lines.extend(["", "## Top Human-Rated Rows", ""])
    lines.extend(format_row_table(analysis.get("top_rows", [])))
    lines.extend(["", "## Lowest Human-Rated Rows", ""])
    lines.extend(format_row_table(analysis.get("bottom_rows", [])))
    lines.extend(
        [
            "",
            "## Working Read",
            "",
            "- The human scores are not simply tracking `readable_ontology_frontier`.",
            "- Very high readability can become too predictable or too polished.",
            "- The stronger taste signals in this pass are oddness, daydream drift, and distorted but still legible image motion.",
            "- `unfinished` needs a finer split: hard cutoff hurts, but quote-tail or fragmentary closure can still work.",
            "- A next selector should use human score as a calibration target, with a band-pass around readability rather than a monotonic readability bonus.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def format_row_table(rows: Iterable[Mapping[str, Any]]) -> List[str]:
    lines = [
        "| id | score | picked | frontier | ont | read | unfinished | note |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {id} | {score} | {picked} | {frontier} | {ont} | {read} | {unfinished} | {note} |".format(
                id=row.get("id", ""),
                score=format_number(row.get("human_score")),
                picked=row.get("picked", ""),
                frontier=format_number(row.get("readable_ontology_frontier")),
                ont=format_number(row.get("ontology_collapse_density")),
                read=format_number(row.get("syntax_readability_proxy")),
                unfinished=format_number(row.get("unfinished")),
                note=escape_table(str(row.get("human_notes") or "")),
            )
        )
    return lines


def compact_rating_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    fields = (
        "id",
        "kind",
        "condition",
        "step",
        "candidate_index",
        "picked",
        "readable_ontology_frontier",
        "frontier_quality",
        "ontology_collapse_density",
        "syntax_readability_proxy",
        "unfinished",
        "score_total",
        "human_score",
        "human_notes",
    )
    return {field: row.get(field, "") for field in fields}


def group_means(
    rows: Sequence[Mapping[str, Any]],
    key_fn: Callable[[Mapping[str, Any]], str],
) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault(key_fn(row), []).append(row)
    out = []
    for group, group_rows in sorted(groups.items(), key=lambda item: item[0]):
        out.append(
            {
                "group": group,
                "n": len(group_rows),
                "mean_human_score": mean_values(group_rows, "human_score"),
                "mean_readable_ontology_frontier": mean_values(group_rows, "readable_ontology_frontier"),
                "mean_ontology_collapse_density": mean_values(group_rows, "ontology_collapse_density"),
                "mean_syntax_readability_proxy": mean_values(group_rows, "syntax_readability_proxy"),
                "mean_unfinished": mean_values(group_rows, "unfinished"),
            }
        )
    return out


def readability_band(row: Mapping[str, Any]) -> str:
    value = parse_float(row.get("syntax_readability_proxy"))
    if value is None:
        return "unknown"
    if value < 0.58:
        return "low_readability"
    if value < 0.80:
        return "mid_readability"
    return "high_readability"


def ontology_band(row: Mapping[str, Any]) -> str:
    value = parse_float(row.get("ontology_collapse_density"))
    if value is None:
        return "unknown"
    if value < 0.40:
        return "low_ontology"
    if value <= 0.65:
        return "target_ontology"
    return "high_ontology"


def parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).replace("\u3000", " ").strip()
    if not text:
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "picked"}


def mean_values(rows: Sequence[Mapping[str, Any]], field: str) -> Optional[float]:
    values = [parse_float(row.get(field)) for row in rows]
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx < 1e-12 or deny < 1e-12:
        return None
    return num / (denx * deny)


def rankdata(xs: Sequence[float]) -> List[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def format_number(value: Any) -> str:
    parsed = parse_float(value)
    if parsed is None:
        return "n/a"
    return f"{parsed:.3f}"


def escape_table(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()

"""Analysis for blinded prompt x steering construct ratings."""

from __future__ import annotations

import csv
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .ratings import format_number, pearson, rankdata


CONSTRUCT_FIELDS: Tuple[str, ...] = (
    "human_anchor_traceable",
    "human_role_or_affordance_change",
    "human_merely_decorative",
    "human_readable",
    "human_stock_loop_or_sprawl_failure",
)

MACHINE_METRICS: Tuple[str, ...] = (
    "anchor_phrase_coverage",
    "ontology_collapse_density",
    "syntax_readability_proxy",
    "surface_style_pressure",
    "decoration_without_transport",
    "cliche_attractor_score",
    "soft_style_cliche_score",
    "semantic_loop_pressure",
    "sprawl_pressure",
    "unfinished",
    "traceable_transport_score",
    "readable_ontology_frontier",
)


def read_construct_markdown(path: str) -> Dict[str, Dict[str, str]]:
    heading_re = re.compile(r"^##\s+(R\d+)\s*$")
    entries: Dict[str, Dict[str, str]] = {}
    current_id: Optional[str] = None
    in_code = False
    text_lines: List[str] = []
    pending_field: Optional[str] = None

    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        heading = heading_re.match(line)
        if heading:
            current_id = heading.group(1)
            entries.setdefault(current_id, {})
            in_code = False
            text_lines = []
            pending_field = None
            continue
        if current_id is None:
            continue
        if line.strip().startswith("```"):
            if in_code:
                entries[current_id]["text"] = "\n".join(text_lines).strip()
                text_lines = []
            in_code = not in_code
            continue
        if in_code:
            text_lines.append(line)
            continue
        stripped = line.strip()
        matched_field = next(
            (field for field in (*CONSTRUCT_FIELDS, "human_notes") if stripped.startswith(f"{field}:")),
            None,
        )
        if matched_field:
            value = stripped.split(":", 1)[1].strip()
            if value:
                entries[current_id][matched_field] = value
                pending_field = None
            else:
                pending_field = matched_field
            continue
        if pending_field and stripped and not stripped.startswith("human_"):
            entries[current_id][pending_field] = stripped
            pending_field = None
    return entries


def parse_construct_value(value: Any) -> Optional[float]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if parsed not in (0.0, 0.5, 1.0):
        return None
    return parsed


def merge_construct_ratings(
    *,
    markdown_path: str,
    rating_csv_path: str,
    key_path: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    markdown = read_construct_markdown(markdown_path)
    with Path(rating_csv_path).open("r", encoding="utf-8", newline="") as handle:
        public_rows = [dict(row) for row in csv.DictReader(handle)]
    key_payload = json.loads(Path(key_path).read_text(encoding="utf-8"))
    key_by_id = {str(item["item_id"]): item for item in key_payload.get("items", [])}
    warnings: List[str] = []
    merged_public: List[Dict[str, Any]] = []
    analysis_rows: List[Dict[str, Any]] = []

    for row in public_rows:
        item_id = str(row.get("item_id") or "")
        patch = markdown.get(item_id, {})
        merged = dict(row)
        if patch.get("text") and str(row.get("text") or "").strip() != patch["text"].strip():
            warnings.append(f"{item_id}: Markdown text differs from CSV text")
        for field in (*CONSTRUCT_FIELDS, "human_notes"):
            if field in patch:
                merged[field] = patch[field]
        merged_public.append(merged)

        key = key_by_id.get(item_id)
        if key is None:
            warnings.append(f"{item_id}: missing condition key")
            continue
        analysis = {
            **merged,
            "source_item_id": key.get("source_item_id", ""),
            "seed": key.get("seed", ""),
            "prompt_mode": key.get("prompt_mode", ""),
            "alpha": key.get("alpha", ""),
            "candidate_index": key.get("candidate_index", ""),
            "observer_label": key.get("observer_label", ""),
        }
        metrics = key.get("metrics", {})
        for metric in MACHINE_METRICS:
            analysis[metric] = metrics.get(metric, "")
        numeric: Dict[str, Optional[float]] = {}
        for field in CONSTRUCT_FIELDS:
            raw_value = analysis.get(field, "")
            numeric[field] = parse_construct_value(raw_value)
            if str(raw_value or "").strip() and numeric[field] is None:
                warnings.append(f"{item_id}: invalid {field}={raw_value!r}; expected 0, 0.5, or 1")
        if all(numeric[field] is not None for field in CONSTRUCT_FIELDS):
            aligned = _aligned_construct_values(numeric)
            analysis["human_construct_score"] = sum(aligned.values()) / len(aligned)
            analysis["human_construct_mean_score"] = analysis["human_construct_score"]
            analysis["human_construct_floor_score"] = min(aligned.values())
            analysis["human_construct_permissive"] = int(
                analysis["human_construct_floor_score"] >= 0.5
            )
            analysis["human_construct_strict"] = int(
                analysis["human_construct_floor_score"] == 1.0
            )
            analysis["human_construct_complete"] = 1
        else:
            analysis["human_construct_score"] = ""
            analysis["human_construct_mean_score"] = ""
            analysis["human_construct_floor_score"] = ""
            analysis["human_construct_permissive"] = ""
            analysis["human_construct_strict"] = ""
            analysis["human_construct_complete"] = 0
        analysis_rows.append(analysis)

    unknown_ids = sorted(set(markdown) - {str(row.get("item_id") or "") for row in public_rows})
    warnings.extend(f"{item_id}: Markdown item missing from CSV" for item_id in unknown_ids)
    return merged_public, analysis_rows, warnings


def analyze_construct_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    source: str,
    warnings: Sequence[str] = (),
    positive_threshold: float = 0.50,
    bootstrap_samples: int = 5000,
    random_seed: int = 20260713,
) -> Dict[str, Any]:
    complete = [dict(row) for row in rows if int(row.get("human_construct_complete", 0) or 0) == 1]
    correlations = []
    human_scores = [float(row["human_construct_score"]) for row in complete]
    for metric in MACHINE_METRICS:
        pairs = [
            (float(row[metric]), float(row["human_construct_score"]))
            for row in complete
            if row.get(metric, "") not in (None, "")
        ]
        xs = [x for x, _ in pairs]
        ys = [y for _, y in pairs]
        correlations.append(
            {
                "metric": metric,
                "n": len(pairs),
                "pearson": pearson(xs, ys),
                "spearman": pearson(rankdata(xs), rankdata(ys)) if len(pairs) >= 2 else None,
            }
        )

    for row in complete:
        row["human_construct_permissive"] = int(
            float(row["human_construct_floor_score"]) >= float(positive_threshold)
        )
    confusions = {
        "permissive": _confusion(complete, human_field="human_construct_permissive"),
        "strict": _confusion(complete, human_field="human_construct_strict"),
    }
    bootstraps = {
        tier: _bootstrap_confusion_by_seed(
            complete,
            human_field=f"human_construct_{tier}",
            samples=bootstrap_samples,
            random_seed=random_seed,
        )
        for tier in ("permissive", "strict")
    }
    groups = {
        "observer_label": _group_rows(complete, lambda row: str(row.get("observer_label") or "unknown")),
        "condition": _group_rows(
            complete,
            lambda row: f"{row.get('prompt_mode', 'unknown')} alpha={float(row.get('alpha', 0.0)):.1f}",
        ),
    }
    false_positives = [
        _compact_disagreement(row)
        for row in complete
        if _machine_positive(row) and not bool(row["human_construct_permissive"])
    ]
    false_negatives = [
        _compact_disagreement(row)
        for row in complete
        if not _machine_positive(row) and bool(row["human_construct_permissive"])
    ]
    field_completion = {
        field: sum(parse_construct_value(row.get(field)) is not None for row in rows)
        for field in CONSTRUCT_FIELDS
    }
    return {
        "source": source,
        "rated_rows": len(rows),
        "complete_construct_rows": len(complete),
        "source_seed_count": len({str(row.get("source_item_id") or "") for row in rows}),
        "field_completion": field_completion,
        "construct_definition": {
            "aligned_dimensions": [
                "anchor_traceable",
                "role_or_affordance_change",
                "readable",
                "not_merely_decorative",
                "not_stock_loop_or_sprawl_failure",
            ],
            "descriptive_score": "arithmetic mean of five aligned 0/0.5/1 dimensions",
            "classification": (
                "non-compensatory minimum across the five aligned dimensions; "
                "permissive requires every dimension >= threshold and strict requires every dimension = 1"
            ),
            "permissive_floor_threshold": float(positive_threshold),
            "strict_floor_threshold": 1.0,
        },
        "mean_human_construct_score": sum(human_scores) / len(human_scores) if human_scores else None,
        "observer_confusion": confusions,
        "observer_confusion_seed_bootstrap": bootstraps,
        "correlations": correlations,
        "groups": groups,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "warnings": list(warnings),
        "notes": [
            "The construct score is an exploratory operationalization, not population literary taste.",
            "Classification is conjunctive: strength on one dimension cannot compensate for absent transport or readability.",
            "Permissive and strict tiers bracket ambiguous 0.5 ratings instead of selecting a favorable cutoff post hoc.",
            "Bootstrap resamples source scenes; six source scenes remain a small effective sample.",
            "Half-ratings preserve uncertainty instead of forcing a binary decision.",
        ],
    }


def write_construct_analysis(
    analysis: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    merged_public: Sequence[Mapping[str, Any]],
    *,
    out_dir: str,
    public_csv_path: Optional[str] = None,
) -> Dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "human_construct_analysis.md"
    json_path = out / "human_construct_analysis.json"
    rows_path = out / "human_construct_unblinded.csv"
    report_path.write_text(format_construct_analysis(analysis), encoding="utf-8")
    json_path.write_text(json.dumps(dict(analysis), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(rows_path, rows)
    if public_csv_path:
        _write_csv(Path(public_csv_path), merged_public)
    return {
        "report": str(report_path),
        "json": str(json_path),
        "unblinded_csv": str(rows_path),
        "public_csv": str(public_csv_path or ""),
    }


def format_construct_analysis(analysis: Mapping[str, Any]) -> str:
    confusions = analysis.get("observer_confusion", {})
    bootstraps = analysis.get("observer_confusion_seed_bootstrap", {})
    lines = [
        "# Human Construct Validation",
        "",
        f"Source: `{analysis.get('source', '')}`",
        f"Rated rows: {analysis.get('rated_rows', 0)}",
        f"Complete five-field rows: {analysis.get('complete_construct_rows', 0)}",
        f"Source scenes: {analysis.get('source_seed_count', 0)}",
        "",
        "The descriptive mean averages anchor traceability, role/affordance change, readability,",
        "non-decorative displacement, and absence of stock/loop/sprawl failure. Classification is",
        "non-compensatory: every dimension must clear the tier threshold. This is a construct audit,",
        "not a population estimate of literary taste.",
        "",
        "## Field Completion",
        "",
        "| field | valid ratings |",
        "|---|---:|",
    ]
    for field, count in analysis.get("field_completion", {}).items():
        lines.append(f"| {field} | {count} |")
    lines.extend(
        [
            "",
            "## Observer Label Against Human Construct",
            "",
            "Permissive: every aligned dimension is at least "
            f"`{analysis.get('construct_definition', {}).get('permissive_floor_threshold', 0.50):.2f}`. "
            "Strict: every aligned dimension is `1.00`.",
            "",
            "| tier | positive N | TP | FP | TN | FN | precision | recall | specificity | F1 | accuracy |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for tier in ("permissive", "strict"):
        confusion = confusions.get(tier, {})
        lines.append(
            "| {tier} | {positive_n} | {tp} | {fp} | {tn} | {fn} | {precision} | {recall} | "
            "{specificity} | {f1} | {accuracy} |".format(
                tier=tier,
                positive_n=confusion.get("human_positive_n", 0),
                tp=confusion.get("tp", 0),
                fp=confusion.get("fp", 0),
                tn=confusion.get("tn", 0),
                fn=confusion.get("fn", 0),
                precision=format_number(confusion.get("precision")),
                recall=format_number(confusion.get("recall")),
                specificity=format_number(confusion.get("specificity")),
                f1=format_number(confusion.get("f1")),
                accuracy=format_number(confusion.get("accuracy")),
            )
        )
    lines.extend(
        [
            "",
            "Seed-bootstrap 95% intervals:",
            "",
            "| tier | metric | mean | 95% CI |",
            "|---|---|---:|---:|",
        ]
    )
    for tier in ("permissive", "strict"):
        for metric, result in bootstraps.get(tier, {}).items():
            lines.append(
                f"| {tier} | {metric} | {format_number(result.get('mean'))} | "
                f"[{format_number(result.get('ci95_low'))}, {format_number(result.get('ci95_high'))}] |"
            )
    lines.extend(["", "## Correlation With Human Construct", "", "| metric | n | Pearson | Spearman |", "|---|---:|---:|---:|"])
    for row in sorted(
        analysis.get("correlations", []),
        key=lambda value: abs(float(value.get("spearman") or 0.0)),
        reverse=True,
    ):
        lines.append(
            f"| {row.get('metric', '')} | {row.get('n', 0)} | "
            f"{format_number(row.get('pearson'))} | {format_number(row.get('spearman'))} |"
        )
    for group_name, group_rows in analysis.get("groups", {}).items():
        lines.extend(
            [
                "",
                f"## Group Means: {group_name}",
                "",
                "| group | n | descriptive mean | permissive rate | strict rate |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in group_rows:
            lines.append(
                f"| {row['group']} | {row['n']} | {row['mean_human_construct_score']:.3f} | "
                f"{row['permissive_rate']:.3f} | {row['strict_rate']:.3f} |"
            )
    lines.extend(_format_disagreements("Permissive False Positives", analysis.get("false_positives", [])))
    lines.extend(_format_disagreements("Permissive False Negatives", analysis.get("false_negatives", [])))
    if analysis.get("warnings"):
        lines.extend(["", "## Parse Warnings", ""])
        lines.extend(f"- {warning}" for warning in analysis["warnings"])
    lines.extend(["", "## Interpretation Boundary", ""])
    lines.extend(f"- {note}" for note in analysis.get("notes", []))
    return "\n".join(lines).rstrip() + "\n"


def _aligned_construct_values(values: Mapping[str, Optional[float]]) -> Dict[str, float]:
    return {
        "anchor_traceable": float(values["human_anchor_traceable"] or 0.0),
        "role_or_affordance_change": float(values["human_role_or_affordance_change"] or 0.0),
        "readable": float(values["human_readable"] or 0.0),
        "not_merely_decorative": 1.0 - float(values["human_merely_decorative"] or 0.0),
        "not_stock_loop_or_sprawl_failure": 1.0
        - float(values["human_stock_loop_or_sprawl_failure"] or 0.0),
    }


def _machine_positive(row: Mapping[str, Any]) -> bool:
    return str(row.get("observer_label") or "") == "readable_transport"


def _confusion(rows: Sequence[Mapping[str, Any]], *, human_field: str) -> Dict[str, Any]:
    tp = fp = tn = fn = 0
    for row in rows:
        machine = _machine_positive(row)
        human = bool(int(row.get(human_field, 0) or 0))
        if machine and human:
            tp += 1
        elif machine:
            fp += 1
        elif human:
            fn += 1
        else:
            tn += 1
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    return {
        "n": len(rows),
        "human_positive_n": tp + fn,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "specificity": _ratio(tn, tn + fp),
        "f1": _ratio(2.0 * precision * recall, precision + recall),
        "accuracy": _ratio(tp + tn, len(rows)),
    }


def _bootstrap_confusion_by_seed(
    rows: Sequence[Mapping[str, Any]],
    *,
    human_field: str,
    samples: int,
    random_seed: int,
) -> Dict[str, Dict[str, float]]:
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("source_item_id") or "")].append(row)
    seeds = sorted(grouped)
    if not seeds:
        return {}
    rng = random.Random(random_seed)
    draws: Dict[str, List[float]] = defaultdict(list)
    for _ in range(max(1, int(samples))):
        sampled: List[Mapping[str, Any]] = []
        for _ in seeds:
            sampled.extend(grouped[seeds[rng.randrange(len(seeds))]])
        result = _confusion(sampled, human_field=human_field)
        for metric in ("precision", "recall", "specificity", "f1", "accuracy"):
            draws[metric].append(float(result[metric]))
    return {
        metric: {
            "mean": sum(values) / len(values),
            "ci95_low": _percentile(values, 0.025),
            "ci95_high": _percentile(values, 0.975),
        }
        for metric, values in draws.items()
    }


def _group_rows(rows: Sequence[Mapping[str, Any]], key_fn) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[key_fn(row)].append(row)
    return [
        {
            "group": group,
            "n": len(group_rows),
            "mean_human_construct_score": sum(float(row["human_construct_score"]) for row in group_rows)
            / len(group_rows),
            "permissive_rate": sum(int(row.get("human_construct_permissive", 0) or 0) for row in group_rows)
            / len(group_rows),
            "strict_rate": sum(int(row.get("human_construct_strict", 0) or 0) for row in group_rows)
            / len(group_rows),
        }
        for group, group_rows in sorted(grouped.items())
    ]


def _compact_disagreement(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "item_id": row.get("item_id", ""),
        "source_item_id": row.get("source_item_id", ""),
        "condition": f"{row.get('prompt_mode', '')} alpha={float(row.get('alpha', 0.0)):.1f}",
        "observer_label": row.get("observer_label", ""),
        "human_construct_score": row.get("human_construct_score", ""),
        "text": row.get("text", ""),
        "human_notes": row.get("human_notes", ""),
    }


def _format_disagreements(title: str, rows: Sequence[Mapping[str, Any]]) -> List[str]:
    lines = ["", f"## {title}", ""]
    if not rows:
        return [*lines, "None."]
    for row in rows:
        lines.extend(
            [
                f"### {row.get('item_id', '')} | {row.get('condition', '')}",
                "",
                f"observer=`{row.get('observer_label', '')}` | human_construct={float(row.get('human_construct_score', 0.0)):.3f}",
                "",
                "```text",
                str(row.get("text") or ""),
                "```",
                "",
                f"Human note: {row.get('human_notes', '')}",
                "",
            ]
        )
    return lines


def _ratio(numerator: float, denominator: float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _percentile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    position = max(0.0, min(1.0, float(quantile))) * (len(ordered) - 1)
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: List[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        if fields:
            writer.writeheader()
            writer.writerows(rows)

"""Cross-controller comparison for selector-free prompt-steering sweeps."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


DISPLAY_METRICS = (
    "anchor_phrase_coverage",
    "anchor_full_rate",
    "ontology_collapse_density",
    "syntax_readability_proxy",
    "traceable_transport_score",
    "failure_rate",
)


def compare_corridor_reports(condition_paths: Mapping[str, str | Path]) -> Dict[str, Any]:
    if len(condition_paths) < 2:
        raise ValueError("At least two corridor conditions are required")
    reports = {name: _load_report(path) for name, path in condition_paths.items()}
    rows = []
    matched_rows = []
    for condition, report in reports.items():
        for row in report.get("summary_rows", []):
            rows.append({"condition": condition, **dict(row)})
        for row in report.get("matched_summary_rows", []):
            matched_rows.append({"condition": condition, **dict(row)})
    _validate_grids(rows, reports)
    zero_identity = _zero_candidate_signatures(reports)
    exemplars = [
        exemplar
        for condition, report in reports.items()
        if (exemplar := _diagnostic_high_ontology_exemplar(condition, report)) is not None
    ]
    return {
        "conditions": list(reports),
        "source_paths": {name: str(Path(path)) for name, path in condition_paths.items()},
        "summary_rows": rows,
        "matched_summary_rows": matched_rows,
        "alpha_zero_candidate_texts_identical": zero_identity,
        "diagnostic_high_ontology_exemplars": exemplars,
        "interpretation_boundary": [
            "No selector chose any reported candidate pool.",
            "The deterministic observer failed the accompanying human construct audit and is not a quality judge.",
            "Diagnostic exemplars maximize the observer's ontology metric under exact-anchor and completion gates; they are not best outputs.",
            "A factorized vector is an offline intervention on measured contrasts, not evidence of functionally independent latent axes.",
        ],
    }


def write_corridor_comparison(report: Mapping[str, Any], out_dir: str | Path) -> Dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "factorized_corridor_comparison.json"
    csv_path = out / "factorized_corridor_comparison.csv"
    markdown_path = out / "factorized_corridor_comparison.md"
    exemplar_path = out / "factorized_corridor_exemplars.md"
    plot_path = out / "factorized_corridor_comparison.png"
    json_path.write_text(json.dumps(dict(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(csv_path, report.get("summary_rows", []))
    markdown_path.write_text(format_corridor_comparison(report), encoding="utf-8")
    exemplar_path.write_text(format_corridor_exemplars(report), encoding="utf-8")
    _write_corridor_plot(report, plot_path)
    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(markdown_path),
        "exemplars": str(exemplar_path),
        "plot": str(plot_path),
    }


def format_corridor_comparison(report: Mapping[str, Any]) -> str:
    lines = [
        "# Selector-Free Factorized Corridor Pilot",
        "",
        f"Conditions: `{', '.join(report.get('conditions', []))}`",
        f"Alpha-zero candidate texts identical: `{str(report.get('alpha_zero_candidate_texts_identical', False)).lower()}`",
        "",
        "## Raw Pool Curves",
        "",
        "| condition | alpha | candidates | anchor | full anchor | ontology | readability | traceable | failure |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report.get("summary_rows", []):
        lines.append(
            f"| {row['condition']} | {float(row['alpha']):.2f} | {int(row['candidate_count'])} | "
            f"{float(row['anchor_phrase_coverage']):.3f} | {float(row['anchor_full_rate']):.3f} | "
            f"{float(row['ontology_collapse_density']):.3f} | "
            f"{float(row['syntax_readability_proxy']):.3f} | "
            f"{float(row['traceable_transport_score']):.3f} | {float(row['failure_rate']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Exact-Anchor Subset",
            "",
            "| condition | alpha | matched fraction | ontology | readability | failure |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report.get("matched_summary_rows", []):
        lines.append(
            f"| {row['condition']} | {float(row['alpha']):.2f} | {float(row['candidate_fraction']):.3f} | "
            f"{float(row['ontology_collapse_density']):.3f} | "
            f"{float(row['syntax_readability_proxy']):.3f} | {float(row['failure_rate']):.3f} |"
        )
    lines.extend(["", "## Interpretation Boundary", ""])
    lines.extend(f"- {note}" for note in report.get("interpretation_boundary", []))
    return "\n".join(lines).rstrip() + "\n"


def format_corridor_exemplars(report: Mapping[str, Any]) -> str:
    lines = [
        "# Diagnostic High-Ontology Exemplars",
        "",
        "Each text maximizes the deterministic ontology metric within one condition after requiring",
        "every anchor phrase, local completion, and readability >= 0.55. This exposes what the metric",
        "is rewarding; it is not a literary ranking.",
    ]
    for row in report.get("diagnostic_high_ontology_exemplars", []):
        metrics = row["metrics"]
        lines.extend(
            [
                "",
                f"## {row['condition']} | alpha={float(row['alpha']):.2f}",
                "",
                f"seed: `{row['item_id']}` | candidate: `{int(row['candidate_index'])}` | "
                f"observer: `{row['observer_label']}`",
                "",
                f"anchor={float(metrics['anchor_phrase_coverage']):.3f} | "
                f"ontology={float(metrics['ontology_collapse_density']):.3f} | "
                f"readability={float(metrics['syntax_readability_proxy']):.3f} | "
                f"failure={float(row['failure']):.3f}",
                "",
                "```text",
                str(row["text"]),
                "```",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _load_report(path: str | Path) -> Dict[str, Any]:
    candidate = Path(path)
    if candidate.is_dir():
        candidate = candidate / "prompt_steering_contrast.json"
    if not candidate.exists():
        raise FileNotFoundError(f"Prompt contrast report not found: {path}")
    return json.loads(candidate.read_text(encoding="utf-8"))


def _validate_grids(rows: Sequence[Mapping[str, Any]], reports: Mapping[str, Mapping[str, Any]]) -> None:
    expected = None
    for condition, report in reports.items():
        design = report.get("design", {})
        identity = (
            tuple(float(value) for value in design.get("alphas", [])),
            tuple(str(value) for value in design.get("prompt_modes", [])),
            int(design.get("candidates_per_cell", 0)),
            int(design.get("max_new_tokens", 0)),
            int(design.get("random_seed", 0)),
        )
        if expected is None:
            expected = identity
        elif identity != expected:
            raise ValueError(f"Corridor design mismatch for {condition}: {identity} != {expected}")
    if not rows:
        raise ValueError("Corridor reports contain no summary rows")


def _zero_candidate_signatures(reports: Mapping[str, Mapping[str, Any]]) -> bool:
    signatures = []
    for report in reports.values():
        cells = sorted(
            (cell for cell in report.get("cells", []) if abs(float(cell.get("alpha", 0.0))) <= 1e-12),
            key=lambda cell: (str(cell.get("item_id")), str(cell.get("prompt_mode"))),
        )
        signatures.append(
            [
                (
                    str(cell.get("item_id")),
                    str(cell.get("prompt_mode")),
                    tuple(str(candidate.get("text")) for candidate in cell.get("candidates", [])),
                )
                for cell in cells
            ]
        )
    return all(signature == signatures[0] for signature in signatures[1:])


def _diagnostic_high_ontology_exemplar(
    condition: str,
    report: Mapping[str, Any],
) -> Dict[str, Any] | None:
    eligible = []
    for cell in report.get("cells", []):
        if float(cell.get("alpha", 0.0)) <= 0.0:
            continue
        for candidate in cell.get("candidates", []):
            metrics = candidate.get("metrics", {})
            if float(metrics.get("anchor_phrase_coverage", 0.0)) < 1.0:
                continue
            if float(metrics.get("syntax_readability_proxy", 0.0)) < 0.55:
                continue
            if float(metrics.get("unfinished", 0.0)) > 0.05:
                continue
            eligible.append((cell, candidate))
    if not eligible:
        return None
    cell, candidate = max(
        eligible,
        key=lambda pair: (
            float(pair[1]["metrics"].get("ontology_collapse_density", 0.0)),
            -float(pair[0].get("alpha", 0.0)),
            -int(pair[1].get("candidate_index", 0)),
        ),
    )
    metrics = dict(candidate["metrics"])
    failure = max(
        float(metrics.get("semantic_loop_pressure", 0.0)),
        float(metrics.get("sprawl_pressure", 0.0)),
        float(metrics.get("unfinished", 0.0)),
    )
    return {
        "condition": condition,
        "item_id": cell.get("item_id", ""),
        "alpha": float(cell.get("alpha", 0.0)),
        "candidate_index": int(candidate.get("candidate_index", 0)),
        "observer_label": candidate.get("observer_label", ""),
        "metrics": metrics,
        "failure": failure,
        "text": candidate.get("text", ""),
    }


def _write_corridor_plot(report: Mapping[str, Any], path: Path) -> None:
    import matplotlib.pyplot as plt

    metrics = (
        ("ontology_collapse_density", "Ontology collapse density"),
        ("anchor_full_rate", "Exact-anchor candidate rate"),
        ("syntax_readability_proxy", "Readability proxy"),
        ("failure_rate", "Observer failure rate"),
    )
    rows = list(report.get("summary_rows", []))
    figure, axes = plt.subplots(2, 2, figsize=(11.5, 8.0), sharex=True, constrained_layout=True)
    metric_values: Dict[str, list[float]] = {
        metric: [float(row[metric]) for row in rows]
        for metric, _ in metrics
    }
    for axis, (metric, title) in zip(axes.flat, metrics):
        for condition in report.get("conditions", []):
            selected = sorted(
                (row for row in rows if row["condition"] == condition),
                key=lambda row: float(row["alpha"]),
            )
            axis.plot(
                [float(row["alpha"]) for row in selected],
                [float(row[metric]) for row in selected],
                marker="o",
                linewidth=1.8,
                label=condition,
            )
        axis.set_title(title)
        axis.set_xlabel("steering alpha")
        if metric == "ontology_collapse_density":
            axis.set_ylim(0.0, max(0.25, max(metric_values[metric]) * 1.15))
            axis.axhline(0.20, color="#666666", linewidth=0.8, linestyle="--")
        elif metric == "syntax_readability_proxy":
            low = max(0.0, min(metric_values[metric]) - 0.04)
            high = min(1.0, max(metric_values[metric]) + 0.04)
            axis.set_ylim(low, high)
            axis.axhline(0.55, color="#666666", linewidth=0.8, linestyle="--")
        else:
            axis.set_ylim(0.0, 1.0)
        axis.grid(alpha=0.2)
    axes[0, 0].legend(frameon=False, fontsize=8, ncol=2)
    figure.suptitle("Selector-free factorized steering pilot", fontsize=13)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=190, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        if fields:
            writer.writeheader()
            writer.writerows(rows)

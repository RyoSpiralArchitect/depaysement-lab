#!/usr/bin/env python3
"""Summarize a four-condition loop x bridge-budget controller experiment."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Mapping, Sequence


CONDITION_ORDER = ("baseline", "loop", "bridge", "combined")
CONDITION_LABELS = {
    "baseline": "Baseline",
    "loop": "Loop pressure",
    "bridge": "Bridge + budget",
    "combined": "Combined",
}
METRICS = (
    "readable_ontology_frontier",
    "ontology_collapse_density",
    "syntax_readability_proxy",
    "graph_fragmentation",
    "semantic_loop_pressure",
    "trajectory_revisit_pressure",
    "lineage_bridge",
    "unbridged_novelty",
    "object_budget_pressure",
    "traceable_transport_score",
    "ordinary_anchor_retention",
    "unfinished",
)
REPORT_NAMES = ("frontier_sweep_report.json", "posthoc_reselect_report.json")


def _load_report(path: Path) -> tuple[Path, Mapping[str, Any]]:
    if path.is_dir():
        report_path = next((path / name for name in REPORT_NAMES if (path / name).is_file()), None)
        if report_path is None:
            names = ", ".join(REPORT_NAMES)
            raise FileNotFoundError(f"No report found in {path}; expected one of: {names}")
    else:
        report_path = path
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(report, Mapping) or not isinstance(report.get("runs"), list):
        raise ValueError(f"Unsupported report shape: {report_path}")
    return report_path, report


def _flatten_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in report.get("runs", []):
        seed = str(run.get("seed", ""))
        run_name = str(run.get("name", ""))
        for raw_row in run.get("rows", []):
            row = dict(raw_row)
            row["seed"] = seed
            row["run_name"] = run_name
            rows.append(row)
    return rows


def _metric(row: Mapping[str, Any], name: str) -> float:
    if name in row:
        return float(row.get(name, 0.0) or 0.0)
    metrics = row.get("metrics", {})
    if isinstance(metrics, Mapping):
        return float(metrics.get(name, 0.0) or 0.0)
    return 0.0


def _mean(rows: Sequence[Mapping[str, Any]], name: str) -> float:
    return fmean(_metric(row, name) for row in rows) if rows else 0.0


def _summarize_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"count": len(rows)}
    summary.update({name: _mean(rows, name) for name in METRICS})
    return summary


def _selected(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if bool(row.get("picked", False))]


def _fmt(value: float) -> str:
    return f"{float(value):.3f}"


def _write_summary_csv(path: Path, summaries: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("condition", "scope", "count", *METRICS),
            lineterminator="\n",
        )
        writer.writeheader()
        for condition in CONDITION_ORDER:
            for scope in ("pool", "picked"):
                row = summaries[condition][scope]
                writer.writerow({"condition": condition, "scope": scope, **row})


def _interaction_rows(
    summaries: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scope in ("pool", "picked"):
        for metric in METRICS:
            baseline = float(summaries["baseline"][scope][metric])
            loop = float(summaries["loop"][scope][metric])
            bridge = float(summaries["bridge"][scope][metric])
            combined = float(summaries["combined"][scope][metric])
            rows.append(
                {
                    "scope": scope,
                    "metric": metric,
                    "baseline": baseline,
                    "loop": loop,
                    "bridge": bridge,
                    "combined": combined,
                    "loop_effect": loop - baseline,
                    "bridge_effect": bridge - baseline,
                    "combined_effect": combined - baseline,
                    "interaction": combined - loop - bridge + baseline,
                }
            )
    return rows


def _write_interactions_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = (
        "scope",
        "metric",
        "baseline",
        "loop",
        "bridge",
        "combined",
        "loop_effect",
        "bridge_effect",
        "combined_effect",
        "interaction",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_by_seed_csv(path: Path, condition_rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
    fieldnames = ("condition", "seed", "count", *METRICS)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for condition in CONDITION_ORDER:
            grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
            for row in _selected(condition_rows[condition]):
                grouped[str(row.get("seed", ""))].append(row)
            for seed in sorted(grouped):
                writer.writerow(
                    {
                        "condition": condition,
                        "seed": seed,
                        **_summarize_rows(grouped[seed]),
                    }
                )


def _write_text_store(path: Path, condition_rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
    lines = ["# Traceable Transport Factorial: Picked Text Store", ""]
    for condition in CONDITION_ORDER:
        lines.extend((f"## {CONDITION_LABELS[condition]}", ""))
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in _selected(condition_rows[condition]):
            grouped[str(row.get("seed", ""))].append(row)
        for seed in sorted(grouped):
            lines.extend((f"### {seed}", ""))
            for row in sorted(grouped[seed], key=lambda item: int(item.get("step", 0))):
                metrics = row.get("metrics", {})
                lines.append(
                    " | ".join(
                        (
                            f"step={int(row.get('step', 0))}",
                            f"frontier={_fmt(_metric(row, 'readable_ontology_frontier'))}",
                            f"loop={_fmt(_metric(row, 'semantic_loop_pressure'))}",
                            f"revisit={_fmt(_metric(row, 'trajectory_revisit_pressure'))}",
                            f"bridge={_fmt(_metric(row, 'lineage_bridge'))}",
                            f"unbridged={_fmt(_metric(row, 'unbridged_novelty'))}",
                            f"budget={_fmt(_metric(row, 'object_budget_pressure'))}",
                            f"traceable={_fmt(_metric(row, 'traceable_transport_score'))}",
                            f"eligible={bool(metrics.get('selector_eligible', False)) if isinstance(metrics, Mapping) else False}",
                        )
                    )
                )
                lines.extend(("", "```text", str(row.get("text", "")).strip(), "```", ""))
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_report(
    path: Path,
    summaries: Mapping[str, Mapping[str, Mapping[str, Any]]],
    interactions: Sequence[Mapping[str, Any]],
    source_paths: Mapping[str, Path],
) -> None:
    picked_interactions = {row["metric"]: row for row in interactions if row["scope"] == "picked"}
    display_metrics = (
        "readable_ontology_frontier",
        "syntax_readability_proxy",
        "semantic_loop_pressure",
        "trajectory_revisit_pressure",
        "lineage_bridge",
        "unbridged_novelty",
        "object_budget_pressure",
        "traceable_transport_score",
    )
    lines = [
        "# Traceable Transport Controller Factorial",
        "",
        "This report compares live selection pressure on two axes: semantic-loop/revisit pressure and lineage-bridge/object-budget pressure. Means pool all saved candidates or all picked steps. Because each live pick changes the next prompt context, downstream pools are controller-conditioned trajectories rather than a fixed paired candidate set.",
        "",
        "## Picked Means",
        "",
        "| condition | N | frontier | read | loop | revisit | bridge | unbridged | budget | traceable |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for condition in CONDITION_ORDER:
        row = summaries[condition]["picked"]
        lines.append(
            "| "
            + " | ".join(
                (
                    CONDITION_LABELS[condition],
                    str(row["count"]),
                    _fmt(row["readable_ontology_frontier"]),
                    _fmt(row["syntax_readability_proxy"]),
                    _fmt(row["semantic_loop_pressure"]),
                    _fmt(row["trajectory_revisit_pressure"]),
                    _fmt(row["lineage_bridge"]),
                    _fmt(row["unbridged_novelty"]),
                    _fmt(row["object_budget_pressure"]),
                    _fmt(row["traceable_transport_score"]),
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "## Picked 2x2 Contrasts",
            "",
            "`interaction = combined - loop - bridge + baseline` on pooled picked means.",
            "",
            "| metric | loop effect | bridge effect | combined effect | interaction |",
            "|---|---:|---:|---:|---:|",
        )
    )
    for metric in display_metrics:
        row = picked_interactions[metric]
        lines.append(
            f"| {metric} | {float(row['loop_effect']):+.3f} | {float(row['bridge_effect']):+.3f} | "
            f"{float(row['combined_effect']):+.3f} | {float(row['interaction']):+.3f} |"
        )
    lines.extend(("", "## Interpretation Boundary", ""))
    lines.extend(
        (
            "- The factorial isolates selector configuration at step 1, but later candidate pools diverge because selected text is appended to the next prompt.",
            "- A low loop score is not accepted as successful transport when unbridged novelty or object-budget pressure rises.",
            "- A low-budget closed semantic cycle is not accepted as successful transport when loop or trajectory-revisit pressure rises.",
            "- These deterministic lexical metrics are observer outputs, not human taste labels; the picked text store is part of the audit.",
            "",
            "## Sources",
            "",
        )
    )
    for condition in CONDITION_ORDER:
        lines.append(f"- {CONDITION_LABELS[condition]}: `{source_paths[condition]}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_plot(path: Path, condition_rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
    import matplotlib.pyplot as plt

    colors = {
        "baseline": "#4B5563",
        "loop": "#D1495B",
        "bridge": "#2F6B9A",
        "combined": "#2E7D5B",
    }
    markers = {"baseline": "o", "loop": "s", "bridge": "^", "combined": "D"}
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.8), constrained_layout=True)
    panels = (
        (
            "semantic_loop_pressure",
            "object_budget_pressure",
            "Failure exchange",
            "Semantic loop",
            "Object budget",
        ),
        (
            "lineage_bridge",
            "traceable_transport_score",
            "Traceable rerouting",
            "Lineage bridge",
            "Traceable transport",
        ),
    )
    for axis, (x_name, y_name, title, x_label, y_label) in zip(axes, panels):
        for condition in CONDITION_ORDER:
            rows = _selected(condition_rows[condition])
            axis.scatter(
                [_metric(row, x_name) for row in rows],
                [_metric(row, y_name) for row in rows],
                s=48,
                alpha=0.78,
                marker=markers[condition],
                color=colors[condition],
                edgecolor="white",
                linewidth=0.55,
                label=CONDITION_LABELS[condition],
            )
            axis.scatter(
                [_mean(rows, x_name)],
                [_mean(rows, y_name)],
                s=180,
                marker=markers[condition],
                facecolor=colors[condition],
                edgecolor="#111827",
                linewidth=1.1,
                zorder=5,
            )
        axis.set(xlim=(-0.025, 1.025), ylim=(-0.025, 1.025), xlabel=x_label, ylabel=y_label, title=title)
        axis.grid(color="#D1D5DB", linewidth=0.7, alpha=0.65)
        axis.set_axisbelow(True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        frameon=False,
        fontsize=9,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.035),
        ncol=4,
    )
    fig.suptitle("Mistral traceable-transport controller: picked steps", fontsize=14, y=1.035)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def summarize(inputs: Mapping[str, Path], out_dir: Path) -> dict[str, Any]:
    missing = [name for name in CONDITION_ORDER if name not in inputs]
    if missing:
        raise ValueError(f"Missing conditions: {', '.join(missing)}")
    out_dir.mkdir(parents=True, exist_ok=True)

    source_paths: dict[str, Path] = {}
    condition_rows: dict[str, list[dict[str, Any]]] = {}
    summaries: dict[str, dict[str, dict[str, Any]]] = {}
    for condition in CONDITION_ORDER:
        source_path, report = _load_report(inputs[condition])
        rows = _flatten_rows(report)
        source_paths[condition] = source_path
        condition_rows[condition] = rows
        summaries[condition] = {
            "pool": _summarize_rows(rows),
            "picked": _summarize_rows(_selected(rows)),
        }

    seed_sets = {
        condition: {str(row.get("seed", "")) for row in rows} for condition, rows in condition_rows.items()
    }
    if len({tuple(sorted(seeds)) for seeds in seed_sets.values()}) != 1:
        raise ValueError(f"Condition seed sets differ: {seed_sets}")

    interactions = _interaction_rows(summaries)
    payload = {
        "format": "traceable-transport-factorial-v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "conditions": {name: str(source_paths[name]) for name in CONDITION_ORDER},
        "summaries": summaries,
        "interactions": interactions,
        "notes": [
            "Live conditions share generation settings, but selected context changes downstream pools.",
            "Interaction values are descriptive contrasts of pooled means, not independent causal estimates.",
            "Generated text remains part of the audit because all metrics are transparent heuristics.",
        ],
    }
    (out_dir / "factorial_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_summary_csv(out_dir / "factorial_summary.csv", summaries)
    _write_interactions_csv(out_dir / "factorial_interactions.csv", interactions)
    _write_by_seed_csv(out_dir / "factorial_by_seed.csv", condition_rows)
    _write_text_store(out_dir / "factorial_picked_texts.md", condition_rows)
    _write_report(out_dir / "factorial_report.md", summaries, interactions, source_paths)
    _write_plot(out_dir / "factorial_plot.png", condition_rows)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for condition in CONDITION_ORDER:
        parser.add_argument(f"--{condition}", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs = {condition: getattr(args, condition) for condition in CONDITION_ORDER}
    payload = summarize(inputs, args.out_dir)
    print(json.dumps(payload["summaries"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

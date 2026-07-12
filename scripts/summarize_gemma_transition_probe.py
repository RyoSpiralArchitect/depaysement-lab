#!/usr/bin/env python3
"""Summarize Gemma endpoint-vs-transition steering across layer windows and doses."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Mapping, Sequence


PROBE_ORDER = ("endpoint_mid", "transition_early", "transition_mid", "transition_late")
PROBE_LABELS = {
    "endpoint_mid": "Endpoint, layers 9-15",
    "transition_early": "Transition, layers 2-8",
    "transition_mid": "Transition, layers 9-15",
    "transition_late": "Transition, layers 16-22",
}
PROBE_META = {
    "endpoint_mid": {"vector_family": "endpoint", "layers": "9-15"},
    "transition_early": {"vector_family": "transition", "layers": "2-8"},
    "transition_mid": {"vector_family": "transition", "layers": "9-15"},
    "transition_late": {"vector_family": "transition", "layers": "16-22"},
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
    "stock_prop_attractor_score",
    "fantasy_prop_score",
    "unfinished",
)
ALPHA_RE = re.compile(r"(?:selector|steer)_alpha_([^_]+)")


def _report_path(path: Path) -> Path:
    report = path / "frontier_sweep_report.json" if path.is_dir() else path
    if not report.is_file():
        raise FileNotFoundError(f"Frontier report not found: {report}")
    return report


def _load_rows(path: Path) -> tuple[Path, list[dict[str, Any]]]:
    report_path = _report_path(path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for run in report.get("runs", []):
        for raw_row in run.get("rows", []):
            row = dict(raw_row)
            row["seed"] = str(run.get("seed", ""))
            row["run_name"] = str(run.get("name", ""))
            rows.append(row)
    return report_path, rows


def _alpha(condition: str) -> float:
    match = ALPHA_RE.search(condition)
    if not match:
        raise ValueError(f"Could not parse alpha from condition: {condition}")
    return float(match.group(1).replace("m", "-").replace("p", "."))


def _metric(row: Mapping[str, Any], name: str) -> float:
    if name in row:
        return float(row.get(name, 0.0) or 0.0)
    metrics = row.get("metrics", {})
    return float(metrics.get(name, 0.0) or 0.0) if isinstance(metrics, Mapping) else 0.0


def _selected(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if bool(row.get("picked", False))]


def _summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"count": len(rows)}
    for metric in METRICS:
        summary[metric] = fmean(_metric(row, metric) for row in rows) if rows else 0.0
    return summary


def _group_by_alpha(rows: Sequence[Mapping[str, Any]]) -> dict[float, list[Mapping[str, Any]]]:
    grouped: dict[float, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_alpha(str(row.get("condition", "")))].append(row)
    return dict(grouped)


def _fmt(value: float) -> str:
    return f"{float(value):.3f}"


def _summary_rows(
    probe_rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for probe in PROBE_ORDER:
        grouped = _group_by_alpha(probe_rows[probe])
        for alpha in sorted(grouped):
            for scope, rows in (("pool", grouped[alpha]), ("picked", _selected(grouped[alpha]))):
                out.append(
                    {
                        "probe": probe,
                        "label": PROBE_LABELS[probe],
                        **PROBE_META[probe],
                        "alpha": alpha,
                        "scope": scope,
                        **_summarize(rows),
                    }
                )
    return out


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = ("probe", "label", "vector_family", "layers", "alpha", "scope", "count", *METRICS)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_by_seed(path: Path, probe_rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
    fieldnames = ("probe", "vector_family", "layers", "alpha", "seed", "count", *METRICS)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for probe in PROBE_ORDER:
            grouped: dict[tuple[float, str], list[Mapping[str, Any]]] = defaultdict(list)
            for row in _selected(probe_rows[probe]):
                grouped[(_alpha(str(row.get("condition", ""))), str(row.get("seed", "")))].append(row)
            for (alpha, seed), rows in sorted(grouped.items()):
                writer.writerow(
                    {
                        "probe": probe,
                        **PROBE_META[probe],
                        "alpha": alpha,
                        "seed": seed,
                        **_summarize(rows),
                    }
                )


def _vector_cosines(endpoint_path: Path, transition_path: Path) -> list[dict[str, float]]:
    import numpy as np

    endpoint = np.load(endpoint_path)
    transition = np.load(transition_path)
    common = sorted(
        set(endpoint.files) & set(transition.files),
        key=lambda key: int(key.split("_", 1)[1]),
    )
    rows: list[dict[str, float]] = []
    for key in common:
        left = np.asarray(endpoint[key], dtype=np.float64)
        right = np.asarray(transition[key], dtype=np.float64)
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        cosine = float(np.dot(left, right) / denominator) if denominator else 0.0
        rows.append({"layer": int(key.split("_", 1)[1]), "cosine": cosine})
    return rows


def _write_cosines(path: Path, rows: Sequence[Mapping[str, float]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("layer", "cosine"),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_text_store(path: Path, probe_rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
    lines = ["# Gemma Transition-Vector Layer Probe: Picked Text Store", ""]
    for probe in PROBE_ORDER:
        lines.extend((f"## {PROBE_LABELS[probe]}", ""))
        grouped: dict[tuple[float, str], list[Mapping[str, Any]]] = defaultdict(list)
        for row in _selected(probe_rows[probe]):
            grouped[(_alpha(str(row.get("condition", ""))), str(row.get("seed", "")))].append(row)
        for (alpha, seed), rows in sorted(grouped.items()):
            lines.extend((f"### alpha={alpha:g} | {seed}", ""))
            for row in sorted(rows, key=lambda item: int(item.get("step", 0))):
                lines.append(
                    " | ".join(
                        (
                            f"step={int(row.get('step', 0))}",
                            f"frontier={_fmt(_metric(row, 'readable_ontology_frontier'))}",
                            f"ont={_fmt(_metric(row, 'ontology_collapse_density'))}",
                            f"read={_fmt(_metric(row, 'syntax_readability_proxy'))}",
                            f"bridge={_fmt(_metric(row, 'lineage_bridge'))}",
                            f"traceable={_fmt(_metric(row, 'traceable_transport_score'))}",
                            f"stock={_fmt(_metric(row, 'stock_prop_attractor_score'))}",
                        )
                    )
                )
                lines.extend(("", "```text", str(row.get("text", "")).strip(), "```", ""))
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _summary_lookup(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, float, str], Mapping[str, Any]]:
    return {(str(row["probe"]), float(row["alpha"]), str(row["scope"])): row for row in rows}


def _write_report(
    path: Path,
    summary_rows: Sequence[Mapping[str, Any]],
    cosine_rows: Sequence[Mapping[str, float]],
    source_paths: Mapping[str, Path],
) -> None:
    lookup = _summary_lookup(summary_rows)
    lines = [
        "# Gemma Transition-Vector Layer-Window Probe",
        "",
        "This probe compares the original endpoint-surreal centroid direction with a lexically matched transition direction. Early, middle, and late windows contain seven layers each. Values below pool all picked steps across four mundane seeds.",
        "",
        "## Picked Dose Response",
        "",
        "| probe | alpha | N | frontier | ontology | read | bridge | unbridged | budget | traceable | stock |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for probe in PROBE_ORDER:
        for alpha in (0.0, 0.8, 1.1, 1.4):
            row = lookup[(probe, alpha, "picked")]
            lines.append(
                "| "
                + " | ".join(
                    (
                        PROBE_LABELS[probe],
                        f"{alpha:g}",
                        str(row["count"]),
                        _fmt(row["readable_ontology_frontier"]),
                        _fmt(row["ontology_collapse_density"]),
                        _fmt(row["syntax_readability_proxy"]),
                        _fmt(row["lineage_bridge"]),
                        _fmt(row["unbridged_novelty"]),
                        _fmt(row["object_budget_pressure"]),
                        _fmt(row["traceable_transport_score"]),
                        _fmt(row["stock_prop_attractor_score"]),
                    )
                )
                + " |"
            )

    cosine_values = [float(row["cosine"]) for row in cosine_rows]
    lines.extend(
        (
            "",
            "## Direction Geometry",
            "",
            f"Across shared layers, endpoint/transition cosine has mean `{fmean(cosine_values):.3f}`, minimum `{min(cosine_values):.3f}`, and maximum `{max(cosine_values):.3f}`.",
            "",
            "## Within-Probe Peak",
            "",
        )
    )
    late_zero = lookup[("transition_late", 0.0, "picked")]
    late_peak = lookup[("transition_late", 1.1, "picked")]
    endpoint_zero = lookup[("endpoint_mid", 0.0, "picked")]
    endpoint_same = lookup[("endpoint_mid", 1.1, "picked")]
    lines.extend(
        (
            "The late transition window has a narrow response peak at `alpha=1.1`:",
            "",
            f"- frontier: `{late_zero['readable_ontology_frontier']:.3f} -> {late_peak['readable_ontology_frontier']:.3f}`",
            f"- ontology: `{late_zero['ontology_collapse_density']:.3f} -> {late_peak['ontology_collapse_density']:.3f}`",
            f"- readability: `{late_zero['syntax_readability_proxy']:.3f} -> {late_peak['syntax_readability_proxy']:.3f}`",
            f"- traceable transport: `{late_zero['traceable_transport_score']:.3f} -> {late_peak['traceable_transport_score']:.3f}`",
            "",
            "At the same middle layers and dose, the endpoint direction does not show that response:",
            "",
            f"- endpoint frontier: `{endpoint_zero['readable_ontology_frontier']:.3f} -> {endpoint_same['readable_ontology_frontier']:.3f}`",
            f"- endpoint ontology: `{endpoint_zero['ontology_collapse_density']:.3f} -> {endpoint_same['ontology_collapse_density']:.3f}`",
            "",
            "## Late-Window Seed Decomposition",
            "",
            "| seed | frontier delta | ontology delta | readability delta |",
            "|---|---:|---:|---:|",
        )
    )
    by_seed: dict[str, dict[float, list[Mapping[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in _selected(_load_rows(source_paths["transition_late"])[1]):
        by_seed[str(row.get("seed", ""))][_alpha(str(row.get("condition", "")))].append(row)
    for seed in sorted(by_seed):
        zero = _summarize(by_seed[seed][0.0])
        peak = _summarize(by_seed[seed][1.1])
        lines.append(
            f"| {seed} | {peak['readable_ontology_frontier'] - zero['readable_ontology_frontier']:+.3f} | "
            f"{peak['ontology_collapse_density'] - zero['ontology_collapse_density']:+.3f} | "
            f"{peak['syntax_readability_proxy'] - zero['syntax_readability_proxy']:+.3f} |"
        )
    lines.extend(
        (
            "",
            "## Interpretation Boundary",
            "",
            "- Independent MLX runs are stochastic; their alpha-zero pools are not identical paired controls.",
            "- The late-window peak is dose-localized and direction-specific, but the highest-scoring texts include shallow color/state substitutions and stock-like cat/rose/notebook motifs.",
            "- The result supports a layer-local transition response, not a claim that Gemma's readable depaysement problem is solved.",
            "- The full picked-text store is part of the audit because observer maxima can overstate qualitative transformation.",
            "",
            "## Sources",
            "",
        )
    )
    for probe in PROBE_ORDER:
        lines.append(f"- {PROBE_LABELS[probe]}: `{source_paths[probe]}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_plot(path: Path, summary_rows: Sequence[Mapping[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    lookup = _summary_lookup(summary_rows)
    colors = {
        "endpoint_mid": "#4B5563",
        "transition_early": "#D08C32",
        "transition_mid": "#2F6B9A",
        "transition_late": "#2E7D5B",
    }
    markers = {"endpoint_mid": "o", "transition_early": "s", "transition_mid": "^", "transition_late": "D"}
    panels = (
        ("readable_ontology_frontier", "Readable-ontology frontier"),
        ("ontology_collapse_density", "Ontology collapse"),
        ("syntax_readability_proxy", "Readability"),
        ("traceable_transport_score", "Traceable transport"),
    )
    alphas = (0.0, 0.8, 1.1, 1.4)
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 8.0), constrained_layout=True)
    for axis, (metric, title) in zip(axes.flat, panels):
        for probe in PROBE_ORDER:
            values = [float(lookup[(probe, alpha, "picked")][metric]) for alpha in alphas]
            axis.plot(
                alphas,
                values,
                color=colors[probe],
                marker=markers[probe],
                linewidth=2.0,
                markersize=7,
                label=PROBE_LABELS[probe],
            )
        axis.set(title=title, xlabel="Steering alpha", ylabel="Pooled picked mean", xticks=alphas)
        axis.grid(color="#D1D5DB", linewidth=0.7, alpha=0.65)
        axis.set_axisbelow(True)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.025), ncol=4)
    fig.suptitle("Gemma 2: steering direction x layer window x dose", fontsize=14, y=1.02)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _write_delta_plot(path: Path, summary_rows: Sequence[Mapping[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    lookup = _summary_lookup(summary_rows)
    colors = {
        "endpoint_mid": "#4B5563",
        "transition_early": "#D08C32",
        "transition_mid": "#2F6B9A",
        "transition_late": "#2E7D5B",
    }
    markers = {"endpoint_mid": "o", "transition_early": "s", "transition_mid": "^", "transition_late": "D"}
    panels = (
        ("readable_ontology_frontier", "Delta frontier"),
        ("ontology_collapse_density", "Delta ontology collapse"),
        ("syntax_readability_proxy", "Delta readability"),
        ("traceable_transport_score", "Delta traceable transport"),
    )
    alphas = (0.0, 0.8, 1.1, 1.4)
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 8.0), constrained_layout=True)
    for axis, (metric, title) in zip(axes.flat, panels):
        axis.axhline(0.0, color="#6B7280", linewidth=0.9)
        for probe in PROBE_ORDER:
            baseline = float(lookup[(probe, 0.0, "picked")][metric])
            values = [float(lookup[(probe, alpha, "picked")][metric]) - baseline for alpha in alphas]
            axis.plot(
                alphas,
                values,
                color=colors[probe],
                marker=markers[probe],
                linewidth=2.0,
                markersize=7,
                label=PROBE_LABELS[probe],
            )
        axis.set(
            title=title, xlabel="Steering alpha", ylabel="Change from this probe's alpha=0", xticks=alphas
        )
        axis.grid(color="#D1D5DB", linewidth=0.7, alpha=0.65)
        axis.set_axisbelow(True)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.025), ncol=4)
    fig.suptitle("Gemma 2: within-probe steering response", fontsize=14, y=1.02)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _write_cosine_plot(path: Path, rows: Sequence[Mapping[str, float]]) -> None:
    import matplotlib.pyplot as plt

    fig, axis = plt.subplots(figsize=(8.2, 3.7), constrained_layout=True)
    layers = [int(row["layer"]) for row in rows]
    values = [float(row["cosine"]) for row in rows]
    axis.axhline(0.0, color="#6B7280", linewidth=0.9)
    axis.bar(layers, values, color="#2F6B9A", width=0.72)
    axis.set(
        title="Endpoint vs transition vector cosine",
        xlabel="Transformer layer",
        ylabel="Cosine similarity",
        xticks=layers,
    )
    axis.grid(axis="y", color="#D1D5DB", linewidth=0.7, alpha=0.65)
    axis.set_axisbelow(True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def summarize(
    inputs: Mapping[str, Path],
    endpoint_vectors: Path,
    transition_vectors: Path,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    source_paths: dict[str, Path] = {}
    probe_rows: dict[str, list[dict[str, Any]]] = {}
    for probe in PROBE_ORDER:
        source_paths[probe], probe_rows[probe] = _load_rows(inputs[probe])

    summary_rows = _summary_rows(probe_rows)
    cosine_rows = _vector_cosines(endpoint_vectors, transition_vectors)
    _write_csv(out_dir / "gemma_transition_summary.csv", summary_rows)
    _write_by_seed(out_dir / "gemma_transition_by_seed.csv", probe_rows)
    _write_cosines(out_dir / "gemma_transition_vector_cosine.csv", cosine_rows)
    _write_text_store(out_dir / "gemma_transition_picked_texts.md", probe_rows)
    _write_report(out_dir / "gemma_transition_report.md", summary_rows, cosine_rows, source_paths)
    _write_plot(out_dir / "gemma_transition_dose_response.png", summary_rows)
    _write_delta_plot(out_dir / "gemma_transition_delta_response.png", summary_rows)
    _write_cosine_plot(out_dir / "gemma_transition_vector_cosine.png", cosine_rows)

    payload = {
        "format": "gemma-transition-layer-probe-v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "sources": {probe: str(source_paths[probe]) for probe in PROBE_ORDER},
        "endpoint_vectors": str(endpoint_vectors),
        "transition_vectors": str(transition_vectors),
        "summary": summary_rows,
        "vector_cosine": cosine_rows,
        "notes": [
            "Alpha-zero runs are independent stochastic controls, not shared candidate pools.",
            "The observer is deterministic and lexical; picked texts remain part of the audit.",
        ],
    }
    (out_dir / "gemma_transition_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for probe in PROBE_ORDER:
        parser.add_argument(f"--{probe.replace('_', '-')}", dest=probe, type=Path, required=True)
    parser.add_argument("--endpoint-vectors", type=Path, required=True)
    parser.add_argument("--transition-vectors", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs = {probe: getattr(args, probe) for probe in PROBE_ORDER}
    payload = summarize(inputs, args.endpoint_vectors, args.transition_vectors, args.out_dir)
    print(
        json.dumps(
            {"rows": len(payload["summary"]), "cosine_layers": len(payload["vector_cosine"])}, indent=2
        )
    )


if __name__ == "__main__":
    main()

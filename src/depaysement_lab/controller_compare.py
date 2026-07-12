"""Compare fixed, legacy-adaptive, and hysteretic trajectory controllers."""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


STEP_METRICS = (
    "readable_ontology_frontier",
    "ontology_collapse_density",
    "syntax_readability_proxy",
    "ordinary_anchor_retention",
    "traceable_transport_score",
    "unfinished",
    "loop_pressure",
    "stock_pressure",
    "guard_pressure",
)


def compare_adaptive_controllers(condition_paths: Mapping[str, str | Path]) -> Dict[str, Any]:
    if len(condition_paths) < 2:
        raise ValueError("At least two controller conditions are required")
    runs = {
        condition: _load_run_directory(path)
        for condition, path in condition_paths.items()
    }
    seed_sets = {condition: set(condition_runs) for condition, condition_runs in runs.items()}
    expected_seeds = next(iter(seed_sets.values()))
    for condition, seeds in seed_sets.items():
        if seeds != expected_seeds:
            raise ValueError(f"Controller seed mismatch for {condition}: {seeds} != {expected_seeds}")
    step_rows = []
    run_rows = []
    for condition, condition_runs in runs.items():
        for seed_id, payload in sorted(condition_runs.items()):
            extracted = _extract_run(condition, seed_id, payload)
            step_rows.extend(extracted["steps"])
            run_rows.append(extracted["summary"])
    condition_rows = _condition_rows(run_rows)
    fixed_name = "fixed" if "fixed" in runs else next(iter(runs))
    paired_deltas = _paired_deltas(run_rows, fixed_name=fixed_name)
    step_one_identity = _step_one_identity(runs)
    return {
        "conditions": list(runs),
        "fixed_reference": fixed_name,
        "source_paths": {name: str(path) for name, path in condition_paths.items()},
        "seed_count": len(expected_seeds),
        "step_one_identity": step_one_identity,
        "condition_rows": condition_rows,
        "run_rows": run_rows,
        "step_rows": step_rows,
        "paired_deltas_vs_fixed": paired_deltas,
        "interpretation_boundary": [
            "The seed, not the trajectory step or candidate, is the comparison unit.",
            "This is a four-seed controller pilot and does not estimate population literary quality.",
            "Controller feedback uses a deterministic observer that failed the separate human construct audit.",
            "The controller acts between completed candidate-selection steps, not during token decoding.",
            "A controller can faithfully regulate a miscalibrated observer and still worsen the text.",
        ],
    }


def write_adaptive_controller_report(report: Mapping[str, Any], out_dir: str | Path) -> Dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "adaptive_controller_comparison.json"
    csv_path = out / "adaptive_controller_runs.csv"
    steps_path = out / "adaptive_controller_steps.csv"
    markdown_path = out / "adaptive_controller_comparison.md"
    texts_path = out / "adaptive_controller_trajectories.md"
    plot_path = out / "adaptive_controller_comparison.png"
    json_path.write_text(json.dumps(dict(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(csv_path, report.get("run_rows", []))
    _write_csv(steps_path, report.get("step_rows", []))
    markdown_path.write_text(format_adaptive_controller_report(report), encoding="utf-8")
    texts_path.write_text(format_adaptive_controller_trajectories(report), encoding="utf-8")
    _write_adaptive_controller_plot(report, plot_path)
    return {
        "json": str(json_path),
        "runs_csv": str(csv_path),
        "steps_csv": str(steps_path),
        "markdown": str(markdown_path),
        "trajectories": str(texts_path),
        "plot": str(plot_path),
    }


def format_adaptive_controller_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Candidate-Step Adaptive Steering Pilot",
        "",
        f"Conditions: `{', '.join(report.get('conditions', []))}`",
        f"Seeds: `{int(report.get('seed_count', 0))}`",
        "Step-one picked texts identical: "
        f"`{int(report.get('step_one_identity', {}).get('identical_seed_count', 0))}` / "
        f"`{int(report.get('step_one_identity', {}).get('seed_count', 0))}` seeds",
        "",
        "## Condition Means",
        "",
        "| condition | runs | alpha | ontology | readability | frontier | unfinished | loop | stock | guard | boost / dampen / hold / legacy / fixed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report.get("condition_rows", []):
        lines.append(
            f"| {row['condition']} | {int(row['runs'])} | {float(row['mean_alpha']):.3f} | "
            f"{float(row['mean_ontology_collapse_density']):.3f} | "
            f"{float(row['mean_syntax_readability_proxy']):.3f} | "
            f"{float(row['mean_readable_ontology_frontier']):.3f} | "
            f"{float(row['mean_unfinished']):.3f} | {float(row['mean_loop_pressure']):.3f} | "
            f"{float(row['mean_stock_pressure']):.3f} | {float(row['mean_guard_pressure']):.3f} | "
            f"{int(row['boost_count'])} / {int(row['dampen_count'])} / {int(row['hold_count'])} / "
            f"{int(row['legacy_count'])} / {int(row['fixed_count'])} |"
        )
    lines.extend(
        [
            "",
            f"## Seed-Paired Deltas vs {report.get('fixed_reference', 'fixed')}",
            "",
            "| condition | metric | seed pairs | mean delta | median delta |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for condition, metrics in report.get("paired_deltas_vs_fixed", {}).items():
        for metric, row in metrics.items():
            lines.append(
                f"| {condition} | {metric} | {int(row['seed_pairs'])} | "
                f"{float(row['mean_delta']):+.3f} | {float(row['median_delta']):+.3f} |"
            )
    lines.extend(["", "## Interpretation Boundary", ""])
    lines.extend(f"- {note}" for note in report.get("interpretation_boundary", []))
    return "\n".join(lines).rstrip() + "\n"


def format_adaptive_controller_trajectories(report: Mapping[str, Any]) -> str:
    lines = [
        "# Adaptive Controller Trajectories",
        "",
        "Raw picked texts are exposed because the feedback observer is not a literary judge.",
    ]
    grouped: Dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in report.get("step_rows", []):
        grouped[(str(row["condition"]), str(row["seed_id"]))].append(row)
    for (condition, seed_id), rows in sorted(grouped.items()):
        lines.extend(["", f"## {condition} | {seed_id}", ""])
        for row in sorted(rows, key=lambda value: int(value["step"])):
            lines.extend(
                [
                    f"### Step {int(row['step'])} | alpha={float(row['alpha']):.2f} | {row['action']}",
                    "",
                    f"ontology={float(row['ontology_collapse_density']):.3f} | "
                    f"read={float(row['syntax_readability_proxy']):.3f} | "
                    f"unfinished={float(row['unfinished']):.3f} | "
                    f"loop={float(row['loop_pressure']):.3f} | stock={float(row['stock_pressure']):.3f}",
                    "",
                    f"reason: {row['reason'] or 'fixed alpha'}",
                    "",
                    "```text",
                    str(row["text"]),
                    "```",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _load_run_directory(path: str | Path) -> Dict[str, Dict[str, Any]]:
    root = Path(path)
    paths = [root] if root.is_file() else sorted(root.glob("steer_*.json"))
    runs = {}
    for run_path in paths:
        payload = json.loads(run_path.read_text(encoding="utf-8"))
        if "steps" not in payload or "config" not in payload:
            continue
        seed_id = str(payload["config"].get("seed_label") or payload.get("seed") or run_path.stem)
        runs[seed_id] = payload
    if not runs:
        raise ValueError(f"No write-run artifacts found in {path}")
    return runs


def _extract_run(condition: str, seed_id: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    steering = payload.get("config", {}).get("trajectory_steering", {})
    trace_by_step = {int(row["step"]): row for row in steering.get("trace", [])}
    base_alpha = float(steering.get("base_alpha", payload.get("config", {}).get("sweep_alpha", 0.0)))
    step_rows = []
    for step in payload.get("steps", []):
        step_index = int(step["step"])
        trace = trace_by_step.get(step_index, {})
        picked = step.get("picked", {})
        metrics = picked.get("selector_metrics", {})
        repetition = float(metrics.get("repetition_pressure", 0.0) or 0.0)
        sprawl = float(metrics.get("sprawl_pressure", 0.0) or 0.0)
        loop = max(repetition, sprawl)
        stock = max(
            float(metrics.get("cliche_attractor_score", 0.0) or 0.0),
            float(metrics.get("soft_style_cliche_score", 0.0) or 0.0),
            float(metrics.get("fantasy_prop_score", 0.0) or 0.0),
        )
        unfinished = float(metrics.get("unfinished", 0.0) or 0.0)
        row = {
            "condition": condition,
            "seed_id": seed_id,
            "seed": payload.get("seed", ""),
            "step": step_index,
            "alpha": float(trace.get("alpha", base_alpha)),
            "next_alpha": float(trace.get("next_alpha", trace.get("alpha", base_alpha))),
            "action": str(trace.get("action") or ("fixed" if not trace else "legacy")),
            "reason": str(trace.get("reason") or ""),
            "readable_ontology_frontier": float(metrics.get("readable_ontology_frontier", 0.0) or 0.0),
            "ontology_collapse_density": float(metrics.get("ontology_collapse_density", 0.0) or 0.0),
            "syntax_readability_proxy": float(metrics.get("syntax_readability_proxy", 0.0) or 0.0),
            "ordinary_anchor_retention": float(metrics.get("ordinary_anchor_retention", 0.0) or 0.0),
            "traceable_transport_score": float(metrics.get("traceable_transport_score", 0.0) or 0.0),
            "unfinished": unfinished,
            "loop_pressure": loop,
            "stock_pressure": stock,
            "guard_pressure": max(unfinished, loop, stock),
            "text": picked.get("text", ""),
        }
        step_rows.append(row)
    actions = Counter(row["action"] for row in step_rows)
    summary = {
        "condition": condition,
        "seed_id": seed_id,
        "seed": payload.get("seed", ""),
        "steps": len(step_rows),
        "mean_alpha": _mean(row["alpha"] for row in step_rows),
        "final_alpha": float(step_rows[-1]["alpha"]) if step_rows else base_alpha,
        "boost_count": actions["boost"],
        "dampen_count": actions["dampen"],
        "hold_count": actions["hold"],
        "legacy_count": actions["legacy"],
        "fixed_count": actions["fixed"],
        "final_text": payload.get("final_text", ""),
    }
    for metric in STEP_METRICS:
        summary[f"mean_{metric}"] = _mean(row[metric] for row in step_rows)
    return {"steps": step_rows, "summary": summary}


def _condition_rows(run_rows: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    grouped: Dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in run_rows:
        grouped[str(row["condition"])].append(row)
    rows = []
    for condition, condition_runs in grouped.items():
        row = {
            "condition": condition,
            "runs": len(condition_runs),
            "mean_alpha": _mean(value["mean_alpha"] for value in condition_runs),
            "boost_count": sum(int(value["boost_count"]) for value in condition_runs),
            "dampen_count": sum(int(value["dampen_count"]) for value in condition_runs),
            "hold_count": sum(int(value["hold_count"]) for value in condition_runs),
            "legacy_count": sum(int(value["legacy_count"]) for value in condition_runs),
            "fixed_count": sum(int(value["fixed_count"]) for value in condition_runs),
        }
        for metric in STEP_METRICS:
            row[f"mean_{metric}"] = _mean(value[f"mean_{metric}"] for value in condition_runs)
        rows.append(row)
    order = {condition: index for index, condition in enumerate(grouped)}
    return sorted(rows, key=lambda row: order[row["condition"]])


def _paired_deltas(
    run_rows: Sequence[Mapping[str, Any]],
    *,
    fixed_name: str,
) -> Dict[str, Dict[str, Any]]:
    lookup = {(str(row["condition"]), str(row["seed_id"])): row for row in run_rows}
    conditions = list(dict.fromkeys(str(row["condition"]) for row in run_rows))
    seeds = sorted(str(row["seed_id"]) for row in run_rows if row["condition"] == fixed_name)
    metrics = (
        "mean_alpha",
        "mean_ontology_collapse_density",
        "mean_syntax_readability_proxy",
        "mean_readable_ontology_frontier",
        "mean_unfinished",
        "mean_loop_pressure",
        "mean_stock_pressure",
        "mean_guard_pressure",
    )
    out = {}
    for condition in conditions:
        if condition == fixed_name:
            continue
        condition_metrics = {}
        for metric in metrics:
            deltas = [
                float(lookup[(condition, seed)][metric]) - float(lookup[(fixed_name, seed)][metric])
                for seed in seeds
            ]
            condition_metrics[metric] = {
                "seed_pairs": len(deltas),
                "mean_delta": _mean(deltas),
                "median_delta": statistics.median(deltas) if deltas else 0.0,
                "seed_deltas": deltas,
            }
        out[condition] = condition_metrics
    return out


def _step_one_identity(runs: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> Dict[str, Any]:
    conditions = list(runs)
    seeds = sorted(next(iter(runs.values())))
    by_seed = {}
    for seed_id in seeds:
        texts = {
            condition: str(runs[condition][seed_id].get("steps", [{}])[0].get("picked", {}).get("text", ""))
            for condition in conditions
        }
        by_seed[seed_id] = {
            "identical": len(set(texts.values())) == 1,
            "texts": texts,
        }
    identical_count = sum(bool(row["identical"]) for row in by_seed.values())
    return {
        "seed_count": len(seeds),
        "identical_seed_count": identical_count,
        "identical_seed_fraction": identical_count / len(seeds) if seeds else 0.0,
        "all_identical": identical_count == len(seeds),
        "by_seed": by_seed,
    }


def _write_adaptive_controller_plot(report: Mapping[str, Any], path: Path) -> None:
    import matplotlib.pyplot as plt

    panels = (
        ("alpha", "Applied steering alpha", (0.0, 1.0)),
        ("ontology_collapse_density", "Picked ontology density", (0.0, 1.0)),
        ("syntax_readability_proxy", "Picked readability proxy", (0.0, 1.0)),
        ("guard_pressure", "Max observer guard pressure", (0.0, 1.0)),
    )
    rows = list(report.get("step_rows", []))
    figure, axes = plt.subplots(2, 2, figsize=(11.5, 8.0), sharex=True, constrained_layout=True)
    for axis, (metric, title, limits) in zip(axes.flat, panels):
        for condition in report.get("conditions", []):
            by_step: Dict[int, list[float]] = defaultdict(list)
            for row in rows:
                if row["condition"] == condition:
                    by_step[int(row["step"])].append(float(row[metric]))
            steps = sorted(by_step)
            means = [_mean(by_step[step]) for step in steps]
            axis.plot(steps, means, marker="o", linewidth=2.0, label=condition)
        axis.set_title(title)
        axis.set_xlabel("trajectory step")
        axis.set_xticks(sorted({int(row["step"]) for row in rows}))
        axis.set_ylim(*limits)
        axis.grid(alpha=0.2)
    axes[0, 0].legend(frameon=False, fontsize=8)
    figure.suptitle("Candidate-step adaptive steering: four-seed pilot", fontsize=13)
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


def _mean(values) -> float:
    collected = [float(value) for value in values]
    return sum(collected) / len(collected) if collected else 0.0

"""Behavioral resilience reports for scheduled activation steering.

The resilience sweep asks whether a readable semantic displacement can be
induced, released, or reversed while preserving the lineage of the original
scene.  All measurements here are output-side heuristics.  They do not claim
to measure hidden-state geometry or safety alignment.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .frontier import TrajectoryAuditReport, TrajectoryRunAudit, anchor_guard_metrics, clamp01


STANDARD_CONDITION_ORDER: Tuple[str, ...] = (
    "baseline",
    "persistent",
    "release",
    "reverse",
    "cycle",
)

STATE_METRICS: Tuple[str, ...] = (
    "ontology_collapse_density",
    "syntax_readability_proxy",
    "graph_integration",
    "repair_pressure",
    "unfinished",
)

STEP_CSV_FIELDS: Tuple[str, ...] = (
    "condition",
    "seed",
    "run_name",
    "path",
    "step",
    "alpha",
    "readable_ontology_frontier",
    "frontier_quality",
    "ontology_collapse_density",
    "syntax_readability_proxy",
    "graph_integration",
    "graph_fragmentation",
    "repair_pressure",
    "unfinished",
    "lineage_anchor_retention",
    "object_lineage_overlap",
    "repetition_pressure",
    "semantic_loop_pressure",
    "sprawl_pressure",
    "paired_baseline_distance",
    "text",
)


def build_default_schedules(
    *,
    steps: int = 5,
    induce_alpha: float = 0.60,
    induction_steps: int = 3,
) -> Dict[str, List[float]]:
    """Return the canonical induce/release/reverse/cycle intervention set."""

    steps = int(steps)
    induction_steps = int(induction_steps)
    if steps < 2:
        raise ValueError("resilience schedules require at least two steps")
    if not 1 <= induction_steps < steps:
        raise ValueError("induction_steps must be between 1 and steps - 1")
    alpha = float(induce_alpha)
    remaining = steps - induction_steps
    reverse_tail = [-(alpha * (idx + 1) / remaining) for idx in range(remaining)]
    if steps == 1:
        cycle = [0.0]
    else:
        cycle = [
            alpha * (1.0 - abs((2.0 * idx / (steps - 1)) - 1.0))
            for idx in range(steps)
        ]
    return {
        "baseline": [0.0] * steps,
        "persistent": [alpha] * steps,
        "release": [alpha] * induction_steps + [0.0] * remaining,
        "reverse": [alpha] * induction_steps + reverse_tail,
        "cycle": cycle,
    }


def parse_schedule_specs(specs: Sequence[str], *, steps: int) -> Dict[str, List[float]]:
    """Parse repeatable ``NAME=A,B,C`` schedule specifications."""

    schedules: Dict[str, List[float]] = {}
    for raw in specs:
        name, sep, values = str(raw).partition("=")
        name = name.strip()
        if not sep or not name:
            raise ValueError(f"schedule must use NAME=A,B,... syntax: {raw!r}")
        schedule = [float(part.strip()) for part in values.split(",") if part.strip()]
        if len(schedule) != int(steps):
            raise ValueError(
                f"schedule {name!r} has {len(schedule)} values; expected exactly {steps}"
            )
        if name in schedules:
            raise ValueError(f"duplicate resilience schedule name: {name!r}")
        schedules[name] = schedule
    if not schedules:
        raise ValueError("at least one named schedule is required")
    return schedules


def build_resilience_report(
    trajectory_report: TrajectoryAuditReport,
    *,
    schedules: Mapping[str, Sequence[float]],
    induction_steps: int = 3,
    minimum_induction_gap: float = 0.02,
) -> Dict[str, Any]:
    """Pair trajectory audits by seed and compute behavioral recovery metrics."""

    induction_steps = int(induction_steps)
    schedule_map = {str(k): [float(v) for v in values] for k, values in schedules.items()}
    runs = list(trajectory_report.runs)
    baseline_by_seed = {
        run.seed: run
        for run in runs
        if run.condition == "baseline"
    }
    step_rows: List[Dict[str, Any]] = []
    run_rows: List[Dict[str, Any]] = []

    for run in runs:
        schedule = schedule_map.get(run.condition, [])
        baseline = baseline_by_seed.get(run.seed)
        baseline_steps = {row.step: row for row in baseline.steps} if baseline else {}
        rows_for_run: List[Dict[str, Any]] = []
        for idx, row in enumerate(run.steps):
            baseline_step = baseline_steps.get(row.step)
            out = _step_row(run, row, schedule[idx] if idx < len(schedule) else 0.0)
            out["paired_baseline_distance"] = (
                _state_distance(row.metrics, baseline_step.metrics)
                if baseline_step is not None
                else None
            )
            rows_for_run.append(out)
            step_rows.append(out)
        run_rows.append(
            _run_resilience_row(
                run,
                rows_for_run,
                baseline,
                induction_steps=induction_steps,
                minimum_induction_gap=float(minimum_induction_gap),
            )
        )

    _attach_persistent_contrasts(run_rows)

    condition_order = _ordered_conditions(schedule_map)
    condition_summaries = [
        _condition_summary(condition, [row for row in run_rows if row["condition"] == condition])
        for condition in condition_order
    ]
    step_summaries = _step_summaries(step_rows, condition_order)
    return {
        "design": {
            "schedules": schedule_map,
            "induction_steps": induction_steps,
            "minimum_induction_gap": float(minimum_induction_gap),
            "state_metrics": list(STATE_METRICS),
            "baseline_definition": "alpha=0 with the same depaysement prompt, selector, and generation budget",
        },
        "condition_order": condition_order,
        "condition_summaries": condition_summaries,
        "run_rows": run_rows,
        "step_summaries": step_summaries,
        "step_rows": step_rows,
        "trajectory_audit": trajectory_report.to_dict(include_steps=True),
        "notes": [
            "Recovery is paired by seed against the alpha=0 baseline condition.",
            "Behavioral state distance is the mean absolute difference across output-side heuristic metrics; it is not a hidden-state distance.",
            "Recovery is undefined when the induction gap is below the configured minimum, because there is no detectable displacement to recover from.",
            "Soft landing multiplies clipped behavioral recovery by terminal readability, anchor, lineage, completion, and graph quality.",
            "Controlled recovery gain is the bounded recovery difference from the paired persistent condition; the unbounded normalized and absolute gap reductions remain in JSON.",
            "Signed terminal ontology delta and baseline-cross rate expose counter-steering overshoot that an absolute recovery distance would hide.",
            "Cycle return gaps are behavioral path-dependence diagnostics and remain confounded by autoregressive context history.",
            "Generated prose in the reading store remains necessary for human judgment.",
        ],
    }


def validate_paired_induction_prefixes(
    paths: Sequence[str],
    *,
    induction_steps: int,
) -> Dict[str, Any]:
    """Verify that matched schedules share exact picked and candidate prefixes."""

    records: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for raw_path in paths:
        path = Path(raw_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            continue
        config = payload.get("config") if isinstance(payload.get("config"), Mapping) else {}
        condition = str(config.get("condition") or "")
        seed = str(payload.get("seed") or "")
        steps = list(payload.get("steps") or [])[: int(induction_steps)]
        picked = [
            str(step.get("picked", {}).get("text", ""))
            for step in steps
            if isinstance(step, Mapping)
        ]
        pools = [
            [str(candidate.get("text", "")) for candidate in step.get("candidates", []) if isinstance(candidate, Mapping)]
            for step in steps
            if isinstance(step, Mapping)
        ]
        schedule = list(config.get("resilience_schedule") or [])[: int(induction_steps)]
        records[seed][condition] = {
            "picked_hash": _stable_hash(picked),
            "candidate_pool_hash": _stable_hash(pools),
            "first_step_hash": _stable_hash({"picked": picked[:1], "pool": pools[:1]}),
            "schedule": [float(value) for value in schedule],
            "step_count": len(steps),
        }

    rows: List[Dict[str, Any]] = []
    core = ("persistent", "release", "reverse")
    for seed, conditions in records.items():
        available = [name for name in core if name in conditions]
        complete = len(available) == len(core)
        picked_hashes = {conditions[name]["picked_hash"] for name in available}
        pool_hashes = {conditions[name]["candidate_pool_hash"] for name in available}
        schedule_prefixes = {tuple(conditions[name]["schedule"]) for name in available}
        baseline = conditions.get("baseline")
        cycle = conditions.get("cycle")
        zero_start_match = None
        if baseline is not None and cycle is not None:
            zero_start_match = baseline["first_step_hash"] == cycle["first_step_hash"]
        rows.append(
            {
                "seed": seed,
                "complete": complete,
                "conditions": available,
                "schedule_prefix_match": complete and len(schedule_prefixes) == 1,
                "picked_prefix_match": complete and len(picked_hashes) == 1,
                "candidate_pool_prefix_match": complete and len(pool_hashes) == 1,
                "baseline_cycle_step1_match": zero_start_match,
            }
        )
    return {
        "rows": rows,
        "seed_count": len(rows),
        "complete_seed_count": sum(bool(row["complete"]) for row in rows),
        "all_core_prefixes_match": bool(rows)
        and all(
            row["complete"]
            and row["schedule_prefix_match"]
            and row["picked_prefix_match"]
            and row["candidate_pool_prefix_match"]
            for row in rows
        ),
        "all_zero_starts_match": bool(rows)
        and all(row["baseline_cycle_step1_match"] is True for row in rows),
    }


def _step_row(run: TrajectoryRunAudit, row: Any, alpha: float) -> Dict[str, Any]:
    metrics = row.metrics
    return {
        "condition": run.condition,
        "seed": run.seed,
        "run_name": run.name,
        "path": run.path,
        "step": int(row.step),
        "alpha": float(alpha),
        "readable_ontology_frontier": float(row.readable_ontology_frontier),
        "frontier_quality": float(row.frontier_quality),
        "ontology_collapse_density": _metric(metrics, "ontology_collapse_density"),
        "syntax_readability_proxy": _metric(metrics, "syntax_readability_proxy"),
        "graph_integration": _metric(metrics, "graph_integration"),
        "graph_fragmentation": _metric(metrics, "graph_fragmentation"),
        "repair_pressure": _metric(metrics, "repair_pressure"),
        "unfinished": _metric(metrics, "unfinished"),
        "lineage_anchor_retention": float(row.lineage_anchor_retention),
        "object_lineage_overlap": float(row.object_lineage_overlap),
        "repetition_pressure": float(row.repetition_pressure),
        "semantic_loop_pressure": _metric(metrics, "semantic_loop_pressure"),
        "sprawl_pressure": max(
            _metric(metrics, "sprawl_pressure"),
            _metric(metrics, "graph_fragmentation"),
        ),
        "paired_baseline_distance": None,
        "text": row.text,
    }


def _run_resilience_row(
    run: TrajectoryRunAudit,
    rows: Sequence[Mapping[str, Any]],
    baseline: Optional[TrajectoryRunAudit],
    *,
    induction_steps: int,
    minimum_induction_gap: float,
) -> Dict[str, Any]:
    aggregate = run.aggregate
    terminal = rows[-1] if rows else {}
    induced = _row_for_step(rows, induction_steps)
    baseline_induced = _audit_step_for_step(baseline, induction_steps)
    baseline_terminal = baseline.steps[-1] if baseline and baseline.steps else None
    induction_gap: Optional[float] = None
    terminal_gap: Optional[float] = None
    recovery_raw: Optional[float] = None
    recovery: Optional[float] = None
    ontology_recovery_raw: Optional[float] = None
    ontology_recovery: Optional[float] = None
    induced_ontology_delta: Optional[float] = None
    terminal_ontology_delta: Optional[float] = None
    ontology_baseline_crossed: Optional[bool] = None
    ontology_overshoot_magnitude: Optional[float] = None
    if induced and baseline_induced and baseline_terminal:
        induction_gap = _state_distance(induced, baseline_induced.metrics)
        terminal_gap = _state_distance(terminal, baseline_terminal.metrics)
        if induction_gap >= minimum_induction_gap:
            recovery_raw = 1.0 - (terminal_gap / induction_gap)
            recovery = clamp01(recovery_raw)
        induced_ontology_delta = (
            float(induced.get("ontology_collapse_density", 0.0))
            - _metric(baseline_induced.metrics, "ontology_collapse_density")
        )
        terminal_ontology_delta = (
            float(terminal.get("ontology_collapse_density", 0.0))
            - _metric(baseline_terminal.metrics, "ontology_collapse_density")
        )
        induced_ont_gap = abs(induced_ontology_delta)
        terminal_ont_gap = abs(terminal_ontology_delta)
        if induced_ont_gap >= minimum_induction_gap:
            ontology_recovery_raw = 1.0 - (terminal_ont_gap / induced_ont_gap)
            ontology_recovery = clamp01(ontology_recovery_raw)
            ontology_baseline_crossed = induced_ontology_delta * terminal_ontology_delta < 0.0
            ontology_overshoot_magnitude = terminal_ont_gap if ontology_baseline_crossed else 0.0

    terminal_read = float(terminal.get("syntax_readability_proxy", 0.0) or 0.0)
    terminal_lineage = float(terminal.get("object_lineage_overlap", 0.0) or 0.0)
    terminal_unfinished = float(terminal.get("unfinished", 0.0) or 0.0)
    terminal_sprawl = float(terminal.get("sprawl_pressure", 0.0) or 0.0)
    trajectory_anchor = float(aggregate.get("anchor_survival", 0.0) or 0.0)
    terminal_anchor = float(
        anchor_guard_metrics(run.seed, str(terminal.get("text", ""))).get("ordinary_anchor_retention", 0.0)
    )
    landing_quality = (
        0.30 * terminal_read
        + 0.25 * terminal_anchor
        + 0.20 * terminal_lineage
        + 0.15 * (1.0 - terminal_unfinished)
        + 0.10 * (1.0 - terminal_sprawl)
    )
    soft_landing = float(recovery * landing_quality) if recovery is not None else None
    return_gap, return_pairs = _behavioral_return_gap(rows)
    return {
        "condition": run.condition,
        "seed": run.seed,
        "run_name": run.name,
        "path": run.path,
        "picked_count": int(run.picked_count),
        "induction_gap": induction_gap,
        "terminal_gap": terminal_gap,
        "behavioral_recovery_raw": recovery_raw,
        "behavioral_recovery": recovery,
        "ontology_recovery_raw": ontology_recovery_raw,
        "ontology_recovery": ontology_recovery,
        "induced_ontology_delta_vs_baseline": induced_ontology_delta,
        "terminal_ontology_delta_vs_baseline": terminal_ontology_delta,
        "ontology_baseline_crossed": ontology_baseline_crossed,
        "ontology_overshoot_magnitude": ontology_overshoot_magnitude,
        "landing_quality": float(landing_quality),
        "soft_landing_score": soft_landing,
        "behavioral_return_gap": return_gap,
        "return_pairs": return_pairs,
        "terminal_ontology": float(terminal.get("ontology_collapse_density", 0.0) or 0.0),
        "terminal_readability": terminal_read,
        "terminal_frontier": float(terminal.get("readable_ontology_frontier", 0.0) or 0.0),
        "terminal_anchor_survival": terminal_anchor,
        "trajectory_anchor_survival": trajectory_anchor,
        "terminal_object_lineage": terminal_lineage,
        "terminal_unfinished": terminal_unfinished,
        "terminal_sprawl": terminal_sprawl,
        "motif_loop_penalty": float(aggregate.get("motif_loop_penalty", 0.0) or 0.0),
        "failure_pressure": float(aggregate.get("failure_pressure", 0.0) or 0.0),
        "trajectory_score": float(aggregate.get("trajectory_score", 0.0) or 0.0),
    }


def _state_distance(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    return sum(abs(_metric(a, key) - _metric(b, key)) for key in STATE_METRICS) / len(STATE_METRICS)


def _behavioral_return_gap(rows: Sequence[Mapping[str, Any]]) -> Tuple[Optional[float], List[Dict[str, Any]]]:
    if len({round(float(row.get("alpha", 0.0)), 9) for row in rows}) <= 1:
        return None, []
    groups: Dict[float, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[round(float(row.get("alpha", 0.0)), 9)].append(row)
    pairs: List[Dict[str, Any]] = []
    for alpha, group in sorted(groups.items()):
        if len(group) < 2:
            continue
        first, last = group[0], group[-1]
        first_idx = rows.index(first)
        last_idx = rows.index(last)
        if not any(
            round(float(row.get("alpha", 0.0)), 9) != alpha
            for row in rows[first_idx + 1 : last_idx]
        ):
            continue
        gap = _state_distance(first, last)
        pairs.append(
            {
                "alpha": float(alpha),
                "first_step": int(first.get("step", 0)),
                "last_step": int(last.get("step", 0)),
                "state_gap": float(gap),
            }
        )
    return (_mean([row["state_gap"] for row in pairs]) if pairs else None), pairs


def _condition_summary(condition: str, rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    fields = (
        "induction_gap",
        "terminal_gap",
        "behavioral_recovery",
        "ontology_recovery",
        "induced_ontology_delta_vs_baseline",
        "terminal_ontology_delta_vs_baseline",
        "ontology_baseline_crossed",
        "ontology_overshoot_magnitude",
        "landing_quality",
        "soft_landing_score",
        "terminal_gap_reduction_vs_persistent",
        "controlled_recovery_gain",
        "controlled_recovery_gain_raw",
        "soft_landing_delta_vs_persistent",
        "behavioral_return_gap",
        "terminal_ontology",
        "terminal_readability",
        "terminal_frontier",
        "terminal_anchor_survival",
        "trajectory_anchor_survival",
        "terminal_object_lineage",
        "terminal_unfinished",
        "terminal_sprawl",
        "motif_loop_penalty",
        "failure_pressure",
        "trajectory_score",
    )
    out: Dict[str, Any] = {"condition": condition, "n": len(rows)}
    for field in fields:
        out[field] = _summary_stats([row.get(field) for row in rows])
    out["recoverable_n"] = sum(row.get("behavioral_recovery") is not None for row in rows)
    return out


def _attach_persistent_contrasts(rows: Sequence[Dict[str, Any]]) -> None:
    persistent_by_seed = {
        str(row.get("seed", "")): row
        for row in rows
        if row.get("condition") == "persistent"
    }
    for row in rows:
        row["terminal_gap_reduction_vs_persistent"] = None
        row["controlled_recovery_gain"] = None
        row["controlled_recovery_gain_raw"] = None
        row["soft_landing_delta_vs_persistent"] = None
        persistent = persistent_by_seed.get(str(row.get("seed", "")))
        if persistent is None or row.get("condition") == "baseline":
            continue
        terminal_gap = row.get("terminal_gap")
        persistent_gap = persistent.get("terminal_gap")
        induction_gap = row.get("induction_gap")
        if terminal_gap is not None and persistent_gap is not None:
            reduction = float(persistent_gap) - float(terminal_gap)
            row["terminal_gap_reduction_vs_persistent"] = reduction
            if induction_gap is not None and float(induction_gap) > 1e-12:
                row["controlled_recovery_gain_raw"] = reduction / float(induction_gap)
        recovery = row.get("behavioral_recovery")
        persistent_recovery = persistent.get("behavioral_recovery")
        if recovery is not None and persistent_recovery is not None:
            row["controlled_recovery_gain"] = float(recovery) - float(persistent_recovery)
        landing = row.get("soft_landing_score")
        persistent_landing = persistent.get("soft_landing_score")
        if landing is not None and persistent_landing is not None:
            row["soft_landing_delta_vs_persistent"] = float(landing) - float(persistent_landing)


def _step_summaries(rows: Sequence[Mapping[str, Any]], condition_order: Sequence[str]) -> List[Dict[str, Any]]:
    fields = (
        "alpha",
        "readable_ontology_frontier",
        "frontier_quality",
        "ontology_collapse_density",
        "syntax_readability_proxy",
        "graph_integration",
        "graph_fragmentation",
        "repair_pressure",
        "unfinished",
        "lineage_anchor_retention",
        "object_lineage_overlap",
        "repetition_pressure",
        "semantic_loop_pressure",
        "sprawl_pressure",
        "paired_baseline_distance",
    )
    out: List[Dict[str, Any]] = []
    for condition in condition_order:
        steps = sorted({int(row["step"]) for row in rows if row["condition"] == condition})
        for step in steps:
            group = [row for row in rows if row["condition"] == condition and int(row["step"]) == step]
            item: Dict[str, Any] = {"condition": condition, "step": step, "n": len(group)}
            for field in fields:
                item[field] = _summary_stats([row.get(field) for row in group])
            out.append(item)
    return out


def _summary_stats(values: Sequence[Any]) -> Dict[str, Any]:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not clean:
        return {"n": 0, "mean": None, "std": None, "sem": None, "min": None, "max": None}
    avg = _mean(clean)
    std = math.sqrt(sum((value - avg) ** 2 for value in clean) / (len(clean) - 1)) if len(clean) > 1 else 0.0
    return {
        "n": len(clean),
        "mean": float(avg),
        "std": float(std),
        "sem": float(std / math.sqrt(len(clean))) if clean else None,
        "min": float(min(clean)),
        "max": float(max(clean)),
    }


def format_resilience_report(report: Mapping[str, Any]) -> str:
    design = report.get("design", {})
    lines: List[str] = [
        "# Semantic Resilience Sweep",
        "",
        "## Design",
        "",
        "| condition | per-step alpha schedule |",
        "|---|---|",
    ]
    schedules = design.get("schedules", {})
    for condition in report.get("condition_order", []):
        schedule = schedules.get(condition, [])
        lines.append(f"| {condition} | {', '.join(f'{float(value):g}' for value in schedule)} |")
    validation = report.get("paired_design_validation")
    if isinstance(validation, Mapping):
        lines.extend(
            [
                "",
                "Paired-prefix validation: "
                f"core={_yes_no(validation.get('all_core_prefixes_match'))}, "
                f"zero-start={_yes_no(validation.get('all_zero_starts_match'))}, "
                f"complete seeds={int(validation.get('complete_seed_count', 0))}/"
                f"{int(validation.get('seed_count', 0))}.",
            ]
        )
    lines.extend(
        [
            "",
            f"Induction ends after step {int(design.get('induction_steps', 0))}. "
            f"Minimum detectable induction gap: {float(design.get('minimum_induction_gap', 0.0)):.3f}.",
            "",
            "## Condition Summary",
            "",
            "| condition | n | induced | recovery | gain vs persist | soft landing | ont delta | cross rate | terminal ont | terminal read | anchor | lineage | unfinished | loop |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report.get("condition_summaries", []):
        lines.append(
            "| {condition} | {n} | {induced} | {recovery} | {gain} | {landing} | {ont_delta} | {cross} | {ont} | {read} | {anchor} | {lineage} | {unfinished} | {loop} |".format(
                condition=row.get("condition", ""),
                n=row.get("n", 0),
                induced=_fmt_stat(row.get("induction_gap")),
                recovery=_fmt_stat(row.get("behavioral_recovery")),
                gain=_fmt_stat(row.get("controlled_recovery_gain")),
                landing=_fmt_stat(row.get("soft_landing_score")),
                ont_delta=_fmt_stat(row.get("terminal_ontology_delta_vs_baseline")),
                cross=_fmt_stat(row.get("ontology_baseline_crossed")),
                ont=_fmt_stat(row.get("terminal_ontology")),
                read=_fmt_stat(row.get("terminal_readability")),
                anchor=_fmt_stat(row.get("terminal_anchor_survival")),
                lineage=_fmt_stat(row.get("terminal_object_lineage")),
                unfinished=_fmt_stat(row.get("terminal_unfinished")),
                loop=_fmt_stat(row.get("motif_loop_penalty")),
            )
        )
    lines.extend(
        [
            "",
            "## Step Trajectories",
            "",
            "| condition | step | alpha | ont | read | frontier | baseline distance | unfinished |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report.get("step_summaries", []):
        lines.append(
            "| {condition} | {step} | {alpha} | {ont} | {read} | {frontier} | {distance} | {unfinished} |".format(
                condition=row.get("condition", ""),
                step=row.get("step", ""),
                alpha=_fmt_stat(row.get("alpha")),
                ont=_fmt_stat(row.get("ontology_collapse_density")),
                read=_fmt_stat(row.get("syntax_readability_proxy")),
                frontier=_fmt_stat(row.get("readable_ontology_frontier")),
                distance=_fmt_stat(row.get("paired_baseline_distance")),
                unfinished=_fmt_stat(row.get("unfinished")),
            )
        )
    return_pairs = [row for row in report.get("run_rows", []) if row.get("behavioral_return_gap") is not None]
    if return_pairs:
        lines.extend(
            [
                "",
                "## Behavioral Return Gaps",
                "",
                "| condition | seed | mean repeated-alpha gap | pairs |",
                "|---|---|---:|---|",
            ]
        )
        for row in return_pairs:
            pairs = "; ".join(
                f"a={pair['alpha']:g}:s{pair['first_step']}->s{pair['last_step']}={pair['state_gap']:.3f}"
                for pair in row.get("return_pairs", [])
            )
            lines.append(
                f"| {row['condition']} | {_single_line(row['seed'])} | "
                f"{float(row['behavioral_return_gap']):.3f} | {pairs} |"
            )
    lines.extend(["", "## Notes"])
    lines.extend(f"- {note}" for note in report.get("notes", []))
    return "\n".join(lines).rstrip() + "\n"


def format_resilience_texts(report: Mapping[str, Any]) -> str:
    audit = report.get("trajectory_audit", {})
    schedules = report.get("design", {}).get("schedules", {})
    lines: List[str] = [
        "# Semantic Resilience Reading Store",
        "",
        "Read the trajectories alongside the metrics; numerical recovery is not a substitute for taste.",
        "",
    ]
    runs = audit.get("runs", []) if isinstance(audit, Mapping) else []
    by_seed: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for run in runs:
        by_seed[str(run.get("seed", ""))].append(run)
    condition_order = list(report.get("condition_order", []))
    order_index = {name: idx for idx, name in enumerate(condition_order)}
    for seed_idx, (seed, seed_runs) in enumerate(by_seed.items(), 1):
        lines.extend([f"## {seed_idx}. {seed}", ""])
        seed_runs = sorted(seed_runs, key=lambda run: order_index.get(str(run.get("condition", "")), 999))
        for run in seed_runs:
            condition = str(run.get("condition", ""))
            aggregate = run.get("aggregate", {})
            schedule = schedules.get(condition, [])
            lines.extend(
                [
                    f"### {condition}",
                    "",
                    f"schedule={','.join(f'{float(value):g}' for value in schedule)} | "
                    f"trajectory={float(aggregate.get('trajectory_score', 0.0)):.3f} | "
                    f"terminal_read={float(aggregate.get('terminal_readability', 0.0)):.3f} | "
                    f"anchor={float(aggregate.get('anchor_survival', 0.0)):.3f} | "
                    f"loop={float(aggregate.get('motif_loop_penalty', 0.0)):.3f}",
                    "",
                ]
            )
            for idx, step in enumerate(run.get("steps", [])):
                alpha = float(schedule[idx]) if idx < len(schedule) else 0.0
                metrics = step.get("metrics", {})
                lines.extend(
                    [
                        f"**step {step.get('step', idx + 1)} / alpha={alpha:g}** "
                        f"ont={float(metrics.get('ontology_collapse_density', 0.0)):.3f} "
                        f"read={float(metrics.get('syntax_readability_proxy', 0.0)):.3f} "
                        f"frontier={float(step.get('readable_ontology_frontier', 0.0)):.3f}",
                        "",
                        "```text",
                        str(step.get("text", "")),
                        "```",
                        "",
                    ]
                )
    return "\n".join(lines).rstrip() + "\n"


def write_resilience_artifacts(report: Mapping[str, Any], out_dir: str) -> Dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "report_md": str(out / "resilience_report.md"),
        "report_json": str(out / "resilience_report.json"),
        "steps_csv": str(out / "resilience_steps.csv"),
        "texts_md": str(out / "resilience_texts.md"),
        "plot": str(out / "resilience_plot.png"),
    }
    Path(paths["report_md"]).write_text(format_resilience_report(report), encoding="utf-8")
    Path(paths["report_json"]).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    Path(paths["texts_md"]).write_text(format_resilience_texts(report), encoding="utf-8")
    with Path(paths["steps_csv"]).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(STEP_CSV_FIELDS), lineterminator="\n")
        writer.writeheader()
        for row in report.get("step_rows", []):
            writer.writerow({field: row.get(field, "") for field in STEP_CSV_FIELDS})
    try:
        write_resilience_plot(report, paths["plot"])
    except RuntimeError:
        paths["plot"] = ""
    return paths


def write_resilience_plot(report: Mapping[str, Any], path: str) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("resilience plotting requires matplotlib") from exc

    colors = {
        "baseline": "#4b5563",
        "persistent": "#c44536",
        "release": "#2374ab",
        "reverse": "#2f855a",
        "cycle": "#805ad5",
    }
    fallback = ["#4b5563", "#c44536", "#2374ab", "#2f855a", "#805ad5", "#b7791f"]
    order = list(report.get("condition_order", []))
    summaries = list(report.get("step_summaries", []))
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 7.6))
    fig.subplots_adjust(top=0.82, bottom=0.10, left=0.08, right=0.98, hspace=0.36, wspace=0.23)
    panels = (
        (axes[0][0], "ontology_collapse_density", "Ontology collapse density"),
        (axes[0][1], "syntax_readability_proxy", "Readability"),
        (axes[1][0], "paired_baseline_distance", "Distance from paired baseline"),
    )
    for condition_idx, condition in enumerate(order):
        color = colors.get(condition, fallback[condition_idx % len(fallback)])
        rows = sorted(
            [row for row in summaries if row.get("condition") == condition],
            key=lambda row: int(row.get("step", 0)),
        )
        xs = [int(row["step"]) for row in rows]
        for ax, metric, _ in panels:
            ys = [_stat_mean(row.get(metric)) for row in rows]
            sems = [_stat_sem(row.get(metric)) for row in rows]
            valid = [(x, y, sem) for x, y, sem in zip(xs, ys, sems) if y is not None]
            if not valid:
                continue
            vx, vy, ve = zip(*valid)
            ax.plot(vx, vy, marker="o", linewidth=2.0, markersize=4.5, color=color, label=condition)
            ax.fill_between(
                vx,
                [max(0.0, y - sem) for y, sem in zip(vy, ve)],
                [min(1.0, y + sem) for y, sem in zip(vy, ve)],
                color=color,
                alpha=0.12,
                linewidth=0,
            )
    for ax, _, title in panels:
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Generation step")
        ax.set_xticks(sorted({int(row.get("step", 0)) for row in summaries}))
        ax.set_ylim(-0.02, 1.02)
        ax.grid(True, color="#d7dce2", linewidth=0.7, alpha=0.7)
    axes[0][0].set_ylabel("Mean score")
    axes[1][0].set_ylabel("Mean absolute metric gap")

    condition_summaries = {
        row.get("condition"): row for row in report.get("condition_summaries", [])
    }
    bar_conditions = [name for name in order if name != "baseline"]
    values = [_stat_mean(condition_summaries.get(name, {}).get("soft_landing_score")) or 0.0 for name in bar_conditions]
    errors = [_stat_sem(condition_summaries.get(name, {}).get("soft_landing_score")) for name in bar_conditions]
    axes[1][1].bar(
        range(len(bar_conditions)),
        values,
        yerr=errors,
        capsize=3,
        color=[colors.get(name, fallback[idx % len(fallback)]) for idx, name in enumerate(bar_conditions)],
        alpha=0.88,
    )
    axes[1][1].set_title("Terminal soft landing", fontsize=11)
    axes[1][1].set_ylabel("Mean score")
    axes[1][1].set_xticks(range(len(bar_conditions)), bar_conditions, rotation=20, ha="right")
    axes[1][1].set_ylim(0.0, 1.0)
    axes[1][1].grid(True, axis="y", color="#d7dce2", linewidth=0.7, alpha=0.7)
    if not any(
        _stat_mean(condition_summaries.get(name, {}).get("soft_landing_score")) is not None
        for name in bar_conditions
    ):
        axes[1][1].text(
            0.5,
            0.5,
            "No detectable induction",
            transform=axes[1][1].transAxes,
            ha="center",
            va="center",
            color="#4b5563",
        )
    handles, labels = axes[0][0].get_legend_handles_labels()
    if handles:
        fig.legend(
            handles,
            labels,
            loc="upper center",
            bbox_to_anchor=(0.5, 0.915),
            ncol=min(len(labels), 5),
            frameon=False,
        )
    fig.suptitle("Semantic Resilience Under Scheduled Steering", fontsize=14, y=0.985)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _row_for_step(rows: Sequence[Mapping[str, Any]], step: int) -> Optional[Mapping[str, Any]]:
    for row in rows:
        if int(row.get("step", 0)) == int(step):
            return row
    return None


def _audit_step_for_step(run: Optional[TrajectoryRunAudit], step: int) -> Optional[Any]:
    if run is None:
        return None
    for row in run.steps:
        if int(row.step) == int(step):
            return row
    return None


def _metric(values: Mapping[str, Any], key: str) -> float:
    value = values.get(key, 0.0)
    if value is None:
        return 0.0
    return float(value)


def _ordered_conditions(schedules: Mapping[str, Sequence[float]]) -> List[str]:
    known = [name for name in STANDARD_CONDITION_ORDER if name in schedules]
    return known + sorted(name for name in schedules if name not in known)


def _mean(values: Sequence[float]) -> float:
    return sum(float(value) for value in values) / len(values) if values else 0.0


def _fmt_stat(stat: Any) -> str:
    if not isinstance(stat, Mapping) or stat.get("mean") is None:
        return "-"
    mean = float(stat["mean"])
    sem = stat.get("sem")
    if stat.get("n", 0) > 1 and sem is not None:
        return f"{mean:.3f} +/- {float(sem):.3f}"
    return f"{mean:.3f}"


def _stat_mean(stat: Any) -> Optional[float]:
    if not isinstance(stat, Mapping) or stat.get("mean") is None:
        return None
    return float(stat["mean"])


def _stat_sem(stat: Any) -> float:
    if not isinstance(stat, Mapping) or stat.get("sem") is None:
        return 0.0
    return float(stat["sem"])


def _single_line(text: Any) -> str:
    return " ".join(str(text or "").split())


def _yes_no(value: Any) -> str:
    return "pass" if value is True else "fail"


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

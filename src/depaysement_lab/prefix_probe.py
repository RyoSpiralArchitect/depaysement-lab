"""Fixed-prefix counter-steering diagnostics.

The probe separates two effects that are conflated in an autoregressive
resilience trajectory:

1. the text prefix already emitted under steering; and
2. the activation intervention applied to future decode states.

For each matched mundane and induced prefix, the same next-step prompt is run
under negative, zero, and positive steering.  The first-token prefill
distribution and the generated candidate pools are both retained.  Under MLX
``decode_only`` steering, first-token logits must be invariant across alpha for
a fixed prefix, while the baseline and induced prefixes may differ.
"""

from __future__ import annotations

import csv
import glob
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

import numpy as np

from .proto_v2 import (
    Candidate,
    DepaysementEngine,
    SelectorConfig,
    build_depaysement_prompt,
    join_text,
    ordinary_anchor_retention,
    set_generator_steer_alpha,
)


PREFIX_ORDER: Tuple[str, ...] = ("reference", "induced")
SELECTOR_METRICS: Tuple[str, ...] = (
    "readable_ontology_frontier",
    "frontier_quality",
    "ontology_collapse_density",
    "syntax_readability_proxy",
    "graph_integration",
    "repair_pressure",
    "unfinished",
    "ordinary_anchor_retention",
    "semantic_loop_pressure",
    "lineage_bridge",
    "trajectory_revisit_pressure",
    "unbridged_novelty",
    "object_budget_pressure",
    "traceable_transport_score",
)


def softmax_probabilities(logits: Sequence[float]) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float64)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("logits must be a non-empty one-dimensional array")
    shifted = values - np.max(values)
    exp_values = np.exp(shifted)
    total = float(exp_values.sum())
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("logits produced an invalid softmax normalizer")
    return exp_values / total


def jensen_shannon_divergence(p: Sequence[float], q: Sequence[float]) -> float:
    """Return base-2 Jensen-Shannon divergence in the closed interval [0, 1]."""

    p_values = _normalized_probabilities(p)
    q_values = _normalized_probabilities(q)
    if p_values.shape != q_values.shape:
        raise ValueError("probability vectors must have the same shape")
    midpoint = 0.5 * (p_values + q_values)
    return 0.5 * _kl_divergence(p_values, midpoint) + 0.5 * _kl_divergence(q_values, midpoint)


def load_prefix_pairs(
    reference_paths: Sequence[str],
    induced_paths: Sequence[str],
    *,
    prefix_steps: int,
) -> List[Dict[str, Any]]:
    """Load and pair run artifacts by exact seed text."""

    reference = _load_run_map(reference_paths, label="reference")
    induced = _load_run_map(induced_paths, label="induced")
    shared = sorted(set(reference) & set(induced))
    if not shared:
        raise ValueError("reference and induced run sets share no seed texts")
    missing_reference = sorted(set(induced) - set(reference))
    missing_induced = sorted(set(reference) - set(induced))
    if missing_reference or missing_induced:
        raise ValueError(
            "run sets must contain the same seeds; "
            f"missing_reference={missing_reference}, missing_induced={missing_induced}"
        )

    pairs: List[Dict[str, Any]] = []
    for index, seed in enumerate(shared, start=1):
        reference_path, reference_run = reference[seed]
        induced_path, induced_run = induced[seed]
        pairs.append(
            {
                "seed_index": index,
                "seed": seed,
                "reference_path": reference_path,
                "induced_path": induced_path,
                "reference_condition": _condition(reference_run),
                "induced_condition": _condition(induced_run),
                "reference_prefix": _prefix_text(reference_run, prefix_steps),
                "induced_prefix": _prefix_text(induced_run, prefix_steps),
            }
        )
    return pairs


def run_prefix_counter_probe(
    generator: Any,
    scorer: Any,
    selector: SelectorConfig,
    *,
    reference_paths: Sequence[str],
    induced_paths: Sequence[str],
    prefix_steps: int = 3,
    alphas: Sequence[float] = (-0.6, 0.0, 0.6),
    candidates: int = 8,
    temperature: float = 1.05,
    top_p: float = 0.92,
    max_new_tokens: int = 120,
    choose: str = "best",
    prompt_style: str = "scene",
    ban_terms: Sequence[str] = (),
    random_seed: int = 7,
    top_k_logits: int = 12,
) -> Dict[str, Any]:
    """Run the fixed-prefix by alpha factorial and retain all continuations."""

    alpha_values = _validated_alphas(alphas)
    if not hasattr(generator, "next_token_logits"):
        raise TypeError("prefix probe requires a generator with next_token_logits(prompt)")
    if not hasattr(generator, "reset_seed"):
        raise TypeError("prefix probe requires a generator with reset_seed(seed)")
    pairs = load_prefix_pairs(reference_paths, induced_paths, prefix_steps=prefix_steps)
    engine = DepaysementEngine(
        generator,
        scorer=scorer,
        rng=random.Random(random_seed),
        motif_jitter=0.0,
        selector=selector,
    )
    probability_cache: Dict[Tuple[str, str, float], np.ndarray] = {}
    logit_cache: Dict[Tuple[str, str, float], np.ndarray] = {}
    cells: List[Dict[str, Any]] = []

    for pair in pairs:
        seed = str(pair["seed"])
        seed_index = int(pair["seed_index"])
        cell_seed = int(random_seed) + (seed_index * 1009)
        for prefix_kind in PREFIX_ORDER:
            prefix = str(pair[f"{prefix_kind}_prefix"])
            prompt = build_depaysement_prompt(
                prefix,
                motifs=(),
                style=prompt_style,
                ban_terms=ban_terms,
            )
            for alpha in alpha_values:
                if not set_generator_steer_alpha(generator, alpha):
                    raise RuntimeError("generator does not expose mutable steering alpha")
                generator.reset_seed(cell_seed)
                logits = np.asarray(generator.next_token_logits(prompt), dtype=np.float64)
                probabilities = softmax_probabilities(logits)
                key = (seed, prefix_kind, float(alpha))
                probability_cache[key] = probabilities
                logit_cache[key] = logits

                generator.reset_seed(cell_seed)
                raw = generator.generate(
                    prompt,
                    n=int(candidates),
                    temperature=float(temperature),
                    top_p=float(top_p),
                    max_new_tokens=int(max_new_tokens),
                )
                scored = [
                    Candidate(text, scorer.score(text, context=prefix)) for text in raw if str(text).strip()
                ]
                if not scored:
                    raise RuntimeError(
                        f"generator returned no usable candidates for seed={seed!r}, "
                        f"prefix={prefix_kind}, alpha={alpha}"
                    )
                ranked = engine._rank_candidates_for_selection(scored, context=prefix)
                engine.rng.seed(cell_seed)
                picked = engine._pick(ranked, choose=choose, score_fn=engine._pick_score)
                candidate_payloads = [
                    _candidate_payload(candidate, seed=seed, scorer=scorer) for candidate in ranked
                ]
                picked_index = next(index for index, candidate in enumerate(ranked) if candidate is picked)
                cells.append(
                    {
                        "seed_index": seed_index,
                        "seed": seed,
                        "prefix_kind": prefix_kind,
                        "prefix_condition": pair[f"{prefix_kind}_condition"],
                        "prefix": prefix,
                        "prefix_sha256": hashlib.sha256(prefix.encode("utf-8")).hexdigest(),
                        "alpha": float(alpha),
                        "generation_seed": cell_seed,
                        "prompt": prompt,
                        "logits_sha256": hashlib.sha256(
                            np.asarray(logits, dtype=np.float32).tobytes()
                        ).hexdigest(),
                        "logit_entropy_bits": _entropy_bits(probabilities),
                        "top_tokens": _top_tokens(
                            generator.tokenizer,
                            logits,
                            probabilities,
                            top_k=max(1, int(top_k_logits)),
                        ),
                        "candidate_count": len(candidate_payloads),
                        "pool_metrics": _mean_candidate_metrics(candidate_payloads),
                        "picked_index": picked_index,
                        "picked": candidate_payloads[picked_index],
                        "candidates": candidate_payloads,
                    }
                )

    zero_alpha = next(value for value in alpha_values if abs(value) <= 1e-12)
    for cell in cells:
        seed = str(cell["seed"])
        prefix_kind = str(cell["prefix_kind"])
        alpha = float(cell["alpha"])
        key = (seed, prefix_kind, alpha)
        zero_key = (seed, prefix_kind, zero_alpha)
        other_prefix = "induced" if prefix_kind == "reference" else "reference"
        other_key = (seed, other_prefix, alpha)
        current_prob = probability_cache[key]
        zero_prob = probability_cache[zero_key]
        current_logits = logit_cache[key]
        zero_logits = logit_cache[zero_key]
        cell["alpha_jsd_from_zero"] = jensen_shannon_divergence(current_prob, zero_prob)
        cell["alpha_logit_max_abs_delta_from_zero"] = float(np.max(np.abs(current_logits - zero_logits)))
        cell["alpha_top_token_matches_zero"] = bool(np.argmax(current_prob) == np.argmax(zero_prob))
        cell["prefix_jsd_at_alpha"] = jensen_shannon_divergence(current_prob, probability_cache[other_key])
        cell["prefix_top_token_matches"] = bool(
            np.argmax(current_prob) == np.argmax(probability_cache[other_key])
        )

    summary_rows = _summary_rows(cells, alpha_values)
    max_alpha_jsd = max(float(cell["alpha_jsd_from_zero"]) for cell in cells)
    mean_prefix_jsd = _mean(float(cell["prefix_jsd_at_alpha"]) for cell in cells)
    apply_on = str(getattr(getattr(generator, "steering", None), "apply_on", "unknown"))
    expected_prefill_invariance = apply_on == "decode_only"
    return {
        "schema_version": 1,
        "design": {
            "factorial": "2 prefixes x 3 steering directions",
            "prefixes": list(PREFIX_ORDER),
            "alphas": alpha_values,
            "zero_alpha": zero_alpha,
            "prefix_steps": int(prefix_steps),
            "candidates_per_cell": int(candidates),
            "temperature": float(temperature),
            "top_p": float(top_p),
            "max_new_tokens": int(max_new_tokens),
            "choose": choose,
            "prompt_style": prompt_style,
            "ban_terms": list(ban_terms),
            "random_seed": int(random_seed),
            "selector": selector.to_dict(),
            "steering_apply_on": apply_on,
            "expected_prefill_invariance": expected_prefill_invariance,
            "first_token_invariance_tolerance": 1e-10,
        },
        "diagnostics": {
            "max_within_prefix_alpha_jsd": max_alpha_jsd,
            "mean_cross_prefix_jsd": mean_prefix_jsd,
            "first_token_invariant_across_alpha": bool(max_alpha_jsd <= 1e-10),
            "decode_only_expectation_met": (
                bool(max_alpha_jsd <= 1e-10) if expected_prefill_invariance else None
            ),
        },
        "pairs": pairs,
        "summary_rows": summary_rows,
        "cells": cells,
        "notes": [
            "Each alpha cell resets the MLX RNG to the same seed before generation.",
            "Within-prefix first-token JSD isolates whether steering modifies prompt prefill.",
            "Cross-prefix first-token JSD isolates the effect of already-emitted autoregressive text.",
            "Candidate metrics are deterministic output-side heuristics, not hidden-state distances.",
            "Negative steering edits future decode states; it cannot erase an induced textual prefix.",
            "The full generated prose is retained for human interpretation.",
        ],
    }


def format_prefix_probe_report(report: Mapping[str, Any]) -> str:
    design = report["design"]
    diagnostics = report["diagnostics"]
    lines = [
        "# Fixed-Prefix Counter-Steering Probe",
        "",
        "## Design",
        "",
        (
            f"Paired prefixes: reference vs induced after {design['prefix_steps']} steps; "
            f"alpha={design['alphas']}; candidates={design['candidates_per_cell']}; "
            f"apply_on={design['steering_apply_on']}."
        ),
        "",
        (
            "The probe asks whether counter-steering changes the first continuation distribution, "
            "or only later decode states after an already-induced text prefix has entered context."
        ),
        "",
        "## First-Token Decomposition",
        "",
        "| diagnostic | value |",
        "|---|---:|",
        f"| max within-prefix alpha JSD | {float(diagnostics['max_within_prefix_alpha_jsd']):.12g} |",
        f"| mean cross-prefix JSD | {float(diagnostics['mean_cross_prefix_jsd']):.6f} |",
        (
            "| first token invariant across alpha | "
            f"{str(bool(diagnostics['first_token_invariant_across_alpha'])).lower()} |"
        ),
        "",
        "## Behavioral Summary",
        "",
        (
            "| prefix | alpha | n | pool frontier | picked frontier | picked ontology | "
            "picked read | picked seed anchor | picked traceable | picked loop |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["summary_rows"]:
        lines.append(
            "| {prefix_kind} | {alpha:.3f} | {n} | {pool_frontier:.3f} | "
            "{picked_frontier:.3f} | {picked_ontology:.3f} | {picked_read:.3f} | "
            "{picked_seed_anchor:.3f} | {picked_traceable:.3f} | {picked_loop:.3f} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            (
                "If decode-only first-token logits remain invariant across alpha while they differ across prefixes, "
                "the failed soft landing is localized to autoregressive path dependence plus future-state steering. "
                "It does not establish that the hidden-state trajectory is globally irreversible."
            ),
            "",
            "See `prefix_counter_probe_reading.md` for every selected continuation and its source prefix.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_prefix_probe_artifacts(report: Mapping[str, Any], out_dir: str) -> Dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out / "prefix_counter_probe.json",
        "csv": out / "prefix_counter_probe_summary.csv",
        "report": out / "prefix_counter_probe.md",
        "reading": out / "prefix_counter_probe_reading.md",
        "plot": out / "prefix_counter_probe.png",
    }
    paths["json"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    rows = list(report["summary_rows"])
    with paths["csv"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]) if rows else [],
            lineterminator="\n",
        )
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    paths["report"].write_text(format_prefix_probe_report(report), encoding="utf-8")
    paths["reading"].write_text(_format_reading_store(report), encoding="utf-8")
    _write_prefix_probe_plot(report, paths["plot"])
    return {name: str(path) for name, path in paths.items()}


def _load_run_map(paths: Sequence[str], *, label: str) -> Dict[str, Tuple[str, Mapping[str, Any]]]:
    expanded: List[str] = []
    for raw in paths:
        matches = sorted(glob.glob(str(raw)))
        expanded.extend(matches or [str(raw)])
    out: Dict[str, Tuple[str, Mapping[str, Any]]] = {}
    for raw in expanded:
        path = Path(raw)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError(f"{label} run must be a JSON object: {path}")
        seed = str(payload.get("seed") or "").strip()
        if not seed:
            raise ValueError(f"{label} run has no seed: {path}")
        if seed in out:
            raise ValueError(f"duplicate {label} seed {seed!r}: {out[seed][0]} and {path}")
        out[seed] = (str(path), payload)
    if not out:
        raise ValueError(f"no {label} run artifacts were loaded")
    return out


def _condition(run: Mapping[str, Any]) -> str:
    config = run.get("config") if isinstance(run.get("config"), Mapping) else {}
    return str(config.get("condition") or "unknown")


def _prefix_text(run: Mapping[str, Any], prefix_steps: int) -> str:
    seed = str(run.get("seed") or "").strip()
    text = seed
    steps = list(run.get("steps") or [])
    if len(steps) < int(prefix_steps):
        raise ValueError(f"run for seed {seed!r} has {len(steps)} steps; expected at least {prefix_steps}")
    for step in steps[: int(prefix_steps)]:
        if not isinstance(step, Mapping):
            continue
        picked = step.get("picked") if isinstance(step.get("picked"), Mapping) else {}
        text = join_text(text, str(picked.get("text") or ""))
    return text


def _validated_alphas(alphas: Sequence[float]) -> List[float]:
    values = [float(value) for value in alphas]
    if len(values) != 3:
        raise ValueError("prefix probe requires exactly three alpha values")
    if not any(abs(value) <= 1e-12 for value in values):
        raise ValueError("prefix probe alphas must include zero")
    if not any(value < 0.0 for value in values) or not any(value > 0.0 for value in values):
        raise ValueError("prefix probe alphas must include one negative and one positive value")
    if len(set(values)) != len(values):
        raise ValueError("prefix probe alphas must be unique")
    return values


def _candidate_payload(candidate: Candidate, *, seed: str, scorer: Any) -> Dict[str, Any]:
    payload = candidate.to_dict()
    anchor, hits, terms = ordinary_anchor_retention(
        seed,
        candidate.text,
        concept_fields=scorer.concept_fields if scorer.lexicon_enabled else None,
    )
    payload["seed_anchor_retention"] = float(anchor)
    payload["seed_anchor_hits"] = list(hits)
    payload["seed_anchor_terms"] = list(terms)
    return payload


def _mean_candidate_metrics(candidates: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key in SELECTOR_METRICS:
        values = [
            float(candidate.get("selector_metrics", {}).get(key, 0.0) or 0.0) for candidate in candidates
        ]
        out[key] = _mean(values)
    out["seed_anchor_retention"] = _mean(
        float(candidate.get("seed_anchor_retention", 0.0) or 0.0) for candidate in candidates
    )
    out["selector_eligible_rate"] = _mean(
        1.0 if candidate.get("selector_metrics", {}).get("selector_eligible") else 0.0
        for candidate in candidates
    )
    return out


def _summary_rows(cells: Sequence[Mapping[str, Any]], alphas: Sequence[float]) -> List[Dict[str, Any]]:
    grouped: MutableMapping[Tuple[str, float], List[Mapping[str, Any]]] = defaultdict(list)
    for cell in cells:
        grouped[(str(cell["prefix_kind"]), float(cell["alpha"]))].append(cell)
    rows: List[Dict[str, Any]] = []
    for prefix_kind in PREFIX_ORDER:
        for alpha in alphas:
            group = grouped[(prefix_kind, float(alpha))]
            rows.append(
                {
                    "prefix_kind": prefix_kind,
                    "alpha": float(alpha),
                    "n": len(group),
                    "pool_frontier": _cell_metric_mean(group, "pool_metrics", "readable_ontology_frontier"),
                    "pool_ontology": _cell_metric_mean(group, "pool_metrics", "ontology_collapse_density"),
                    "pool_read": _cell_metric_mean(group, "pool_metrics", "syntax_readability_proxy"),
                    "pool_seed_anchor": _cell_metric_mean(group, "pool_metrics", "seed_anchor_retention"),
                    "pool_traceable": _cell_metric_mean(group, "pool_metrics", "traceable_transport_score"),
                    "pool_loop": _cell_metric_mean(group, "pool_metrics", "semantic_loop_pressure"),
                    "pool_unbridged": _cell_metric_mean(group, "pool_metrics", "unbridged_novelty"),
                    "pool_object_budget": _cell_metric_mean(group, "pool_metrics", "object_budget_pressure"),
                    "picked_frontier": _picked_metric_mean(group, "readable_ontology_frontier"),
                    "picked_ontology": _picked_metric_mean(group, "ontology_collapse_density"),
                    "picked_read": _picked_metric_mean(group, "syntax_readability_proxy"),
                    "picked_seed_anchor": _mean(
                        float(cell["picked"].get("seed_anchor_retention", 0.0) or 0.0) for cell in group
                    ),
                    "picked_traceable": _picked_metric_mean(group, "traceable_transport_score"),
                    "picked_loop": _picked_metric_mean(group, "semantic_loop_pressure"),
                    "picked_unbridged": _picked_metric_mean(group, "unbridged_novelty"),
                    "picked_object_budget": _picked_metric_mean(group, "object_budget_pressure"),
                    "alpha_jsd_mean": _mean(float(cell["alpha_jsd_from_zero"]) for cell in group),
                    "alpha_jsd_max": max(float(cell["alpha_jsd_from_zero"]) for cell in group),
                    "prefix_jsd_mean": _mean(float(cell["prefix_jsd_at_alpha"]) for cell in group),
                }
            )
    return rows


def _cell_metric_mean(group: Sequence[Mapping[str, Any]], container: str, metric: str) -> float:
    return _mean(float(cell[container].get(metric, 0.0) or 0.0) for cell in group)


def _picked_metric_mean(group: Sequence[Mapping[str, Any]], metric: str) -> float:
    return _mean(float(cell["picked"].get("selector_metrics", {}).get(metric, 0.0) or 0.0) for cell in group)


def _top_tokens(
    tokenizer: Any,
    logits: np.ndarray,
    probabilities: np.ndarray,
    *,
    top_k: int,
) -> List[Dict[str, Any]]:
    count = min(int(top_k), int(logits.size))
    indices = np.argpartition(logits, -count)[-count:]
    indices = indices[np.argsort(logits[indices])[::-1]]
    return [
        {
            "token_id": int(index),
            "token": _decode_token(tokenizer, int(index)),
            "logit": float(logits[index]),
            "probability": float(probabilities[index]),
        }
        for index in indices
    ]


def _decode_token(tokenizer: Any, token_id: int) -> str:
    decode = getattr(tokenizer, "decode", None)
    if decode is None:
        return str(token_id)
    for value in ([token_id], token_id):
        try:
            return str(decode(value))
        except Exception:
            continue
    return str(token_id)


def _normalized_probabilities(values: Sequence[float]) -> np.ndarray:
    probabilities = np.asarray(values, dtype=np.float64)
    if probabilities.ndim != 1 or probabilities.size == 0:
        raise ValueError("probabilities must be a non-empty one-dimensional array")
    if np.any(probabilities < 0.0):
        raise ValueError("probabilities cannot be negative")
    total = float(probabilities.sum())
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("probabilities must have positive finite mass")
    return probabilities / total


def _kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
    mask = p > 0.0
    return float(np.sum(p[mask] * np.log2(p[mask] / q[mask])))


def _entropy_bits(probabilities: np.ndarray) -> float:
    mask = probabilities > 0.0
    return float(-np.sum(probabilities[mask] * np.log2(probabilities[mask])))


def _mean(values: Iterable[float]) -> float:
    collected = [float(value) for value in values]
    return sum(collected) / len(collected) if collected else 0.0


def _format_reading_store(report: Mapping[str, Any]) -> str:
    lines = [
        "# Fixed-Prefix Counter-Steering Reading Store",
        "",
        "Every selected continuation is shown in full. Metrics are navigation aids, not taste labels.",
    ]
    cells_by_seed: MutableMapping[str, List[Mapping[str, Any]]] = defaultdict(list)
    for cell in report["cells"]:
        cells_by_seed[str(cell["seed"])].append(cell)
    for seed, cells in cells_by_seed.items():
        lines.extend(["", f"## {seed}"])
        for prefix_kind in PREFIX_ORDER:
            prefix_cells = [cell for cell in cells if cell["prefix_kind"] == prefix_kind]
            prefix_cells.sort(key=lambda cell: float(cell["alpha"]))
            if not prefix_cells:
                continue
            lines.extend(
                [
                    "",
                    f"### {prefix_kind.title()} Prefix",
                    "",
                    "```text",
                    str(prefix_cells[0]["prefix"]),
                    "```",
                ]
            )
            for cell in prefix_cells:
                metrics = cell["picked"].get("selector_metrics", {})
                lines.extend(
                    [
                        "",
                        f"#### alpha={float(cell['alpha']):.3f}",
                        "",
                        (
                            f"frontier={float(metrics.get('readable_ontology_frontier', 0.0)):.3f} | "
                            f"ontology={float(metrics.get('ontology_collapse_density', 0.0)):.3f} | "
                            f"read={float(metrics.get('syntax_readability_proxy', 0.0)):.3f} | "
                            f"seed_anchor={float(cell['picked'].get('seed_anchor_retention', 0.0)):.3f} | "
                            f"traceable={float(metrics.get('traceable_transport_score', 0.0)):.3f}"
                        ),
                        "",
                        "```text",
                        str(cell["picked"].get("text", "")),
                        "```",
                    ]
                )
    return "\n".join(lines) + "\n"


def _write_prefix_probe_plot(report: Mapping[str, Any], path: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - optional plotting dependency
        raise RuntimeError("prefix probe plotting requires matplotlib") from exc

    rows = list(report["summary_rows"])
    colors = {"reference": "#236A8D", "induced": "#D1495B"}
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4), constrained_layout=True)

    ax = axes[0]
    for prefix_kind in PREFIX_ORDER:
        selected = [row for row in rows if row["prefix_kind"] == prefix_kind]
        ax.plot(
            [row["alpha"] for row in selected],
            [row["alpha_jsd_mean"] for row in selected],
            marker="o",
            color=colors[prefix_kind],
            label=f"within {prefix_kind}",
        )
    cross = [row for row in rows if row["prefix_kind"] == "reference"]
    ax.plot(
        [row["alpha"] for row in cross],
        [row["prefix_jsd_mean"] for row in cross],
        marker="s",
        linestyle="--",
        color="#3A7D44",
        label="reference vs induced",
    )
    ax.set_xlabel("steering alpha")
    ax.set_ylabel("first-token JSD (bits)")
    ax.set_title("Prefix effect vs steering effect")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1]
    for prefix_kind in PREFIX_ORDER:
        selected = [row for row in rows if row["prefix_kind"] == prefix_kind]
        ax.plot(
            [row["picked_seed_anchor"] for row in selected],
            [row["picked_ontology"] for row in selected],
            marker="o",
            color=colors[prefix_kind],
            label=prefix_kind,
        )
        for row in selected:
            ax.annotate(
                f"{float(row['alpha']):+.2f}",
                (float(row["picked_seed_anchor"]), float(row["picked_ontology"])),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=7,
            )
    ax.set_xlabel("picked original-seed anchor")
    ax.set_ylabel("picked ontology collapse")
    ax.set_title("Behavior after the fixed prefix")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)

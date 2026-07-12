"""Prompt x activation-steering contrast for controlled semantic displacement.

The experiment gives prompting a strong baseline rather than comparing steering
against an intentionally vague instruction. Two prompts share the same output
and anchor constraints:

``naive``
    asks for surreal writing and depaysement by name;
``operational``
    defines the target as a traceable change in identity, role, affordance, or
    relation and explicitly distinguishes it from decorative language.

Each prompt is crossed with zero and at least two positive steering values. The
one-step raw candidate pools are audited without selector intervention.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from .proto_v2 import (
    Candidate,
    DepaysementEngine,
    SelectorConfig,
    current_generator_steer_alpha,
    set_generator_steer_alpha,
)


PROMPT_MODES: Tuple[str, ...] = ("naive", "operational")
FAILURE_LABELS = {
    "anchor_loss_failure",
    "unfinished_or_unreadable_failure",
    "stock_loop_or_sprawl_failure",
    "overcollapse_failure",
}
SURFACE_STYLE_MARKERS: Tuple[str, ...] = (
    "as if",
    "dance",
    "danced",
    "dream",
    "dreamlike",
    "ethereal",
    "glow",
    "glowing",
    "iridescent",
    "kaleidoscope",
    "melancholy",
    "moon",
    "moonlit",
    "shimmer",
    "shimmering",
    "silver",
    "spectral",
    "whisper",
    "whispering",
)
SUMMARY_METRICS: Tuple[str, ...] = (
    "anchor_phrase_coverage",
    "ontology_collapse_density",
    "syntax_readability_proxy",
    "readable_ontology_frontier",
    "traceable_transport_score",
    "surface_style_pressure",
    "decoration_without_transport",
    "cliche_attractor_score",
    "fantasy_prop_score",
    "semantic_loop_pressure",
    "unbridged_novelty",
    "object_budget_pressure",
    "unfinished",
)
RATE_LABELS: Tuple[Tuple[str, str], ...] = (
    ("decorative_near_miss_rate", "decorative_near_miss"),
    ("stable_rate", "ontologically_stable"),
    ("readable_transport_rate", "readable_transport"),
)
HUMAN_FIELDS: Tuple[str, ...] = (
    "item_id",
    "text",
    "human_anchor_traceable",
    "human_role_or_affordance_change",
    "human_merely_decorative",
    "human_readable",
    "human_stock_loop_or_sprawl_failure",
    "human_notes",
)


def load_anchor_bank(path: str, *, limit: int = 0) -> List[Dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_items = payload.get("items") if isinstance(payload, Mapping) else payload
    if not isinstance(raw_items, list):
        raise ValueError("anchor bank must be a list or an object containing an 'items' list")
    items: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, Mapping):
            raise ValueError(f"anchor bank item {index} must be an object")
        item_id = str(raw.get("id") or f"anchor{index:02d}").strip()
        seed = str(raw.get("seed") or "").strip()
        anchors = [str(value).strip() for value in raw.get("anchors", []) if str(value).strip()]
        if not item_id or item_id in seen_ids:
            raise ValueError(f"anchor bank item id is empty or duplicated: {item_id!r}")
        if not seed or len(anchors) < 2:
            raise ValueError(f"anchor bank item {item_id!r} needs a seed and at least two anchors")
        missing = [anchor for anchor in anchors if not _phrase_present(seed, anchor)]
        if missing:
            raise ValueError(f"anchor bank item {item_id!r} seed is missing anchors: {missing}")
        seen_ids.add(item_id)
        items.append({"id": item_id, "seed": seed, "anchors": anchors})
        if limit and len(items) >= int(limit):
            break
    if not items:
        raise ValueError("anchor bank contained no usable items")
    return items


def build_prompt_contrast_prompt(item: Mapping[str, Any], mode: str) -> str:
    mode = str(mode).strip().lower()
    if mode not in PROMPT_MODES:
        raise ValueError(f"unknown prompt mode: {mode!r}")
    anchors = [str(anchor) for anchor in item["anchors"]]
    anchor_line = "; ".join(f'"{anchor}"' for anchor in anchors)
    if mode == "naive":
        instruction = (
            "Make the scene surreal through depaysement. Preserve the named things while making the "
            "image strange and evocative."
        )
    else:
        instruction = (
            "Create controlled semantic displacement. Change at least one named thing's identity, role, "
            "affordance, or concrete relation while every named thing remains traceable. Do not merely "
            "decorate the scene with dreamlike adjectives or explain the symbolism."
        )
    return (
        "Write one or two complete English sentences that continue the mundane scene below.\n"
        "Output only the continuation. No labels, commentary, analysis, or explanation.\n"
        f"Use every anchor phrase unchanged at least once: {anchor_line}.\n"
        "Do not replace the anchor set with unrelated objects, a different protagonist, or a new postcard.\n"
        f"Instruction: {instruction}\n"
        f"Mundane scene: {str(item['seed']).strip()}\n"
        f"Required anchor phrases before you finish: {anchor_line}. The continuation is invalid if any is missing.\n"
        "Continuation:\n"
    )


def anchor_phrase_metrics(text: str, anchors: Sequence[str]) -> Dict[str, Any]:
    hits = [str(anchor) for anchor in anchors if _phrase_present(text, str(anchor))]
    misses = [str(anchor) for anchor in anchors if str(anchor) not in hits]
    coverage = len(hits) / max(1, len(anchors))
    return {
        "anchor_phrase_coverage": float(coverage),
        "anchor_phrase_hits": hits,
        "anchor_phrase_misses": misses,
    }


def surface_style_metrics(text: str) -> Dict[str, Any]:
    hits = [marker for marker in SURFACE_STYLE_MARKERS if _phrase_present(text, marker)]
    pressure = min(1.0, len(hits) / 3.0)
    return {"surface_style_pressure": float(pressure), "surface_style_hits": hits}


def classify_prompt_candidate(metrics: Mapping[str, Any]) -> str:
    readability = float(metrics.get("syntax_readability_proxy", 0.0) or 0.0)
    unfinished = float(metrics.get("unfinished", 0.0) or 0.0)
    ontology = float(metrics.get("ontology_collapse_density", 0.0) or 0.0)
    anchor = float(metrics.get("anchor_phrase_coverage", 0.0) or 0.0)
    cliche = float(metrics.get("cliche_attractor_score", 0.0) or 0.0)
    fantasy = float(metrics.get("fantasy_prop_score", 0.0) or 0.0)
    loop = float(metrics.get("semantic_loop_pressure", 0.0) or 0.0)
    surface = float(metrics.get("surface_style_pressure", 0.0) or 0.0)
    if readability < 0.55 or unfinished > 0.05:
        return "unfinished_or_unreadable_failure"
    if anchor < 0.75:
        return "anchor_loss_failure"
    if cliche > 0.60 or fantasy > 0.80 or loop > 0.55:
        return "stock_loop_or_sprawl_failure"
    if ontology > 0.65:
        return "overcollapse_failure"
    if anchor >= 0.75 and 0.20 <= ontology <= 0.65:
        return "readable_transport"
    if anchor >= 0.75 and ontology < 0.20 and surface > 0.0:
        return "decorative_near_miss"
    if ontology < 0.20:
        return "ontologically_stable"
    return "mixed_or_untraceable"


def run_prompt_steering_contrast(
    generator: Any,
    scorer: Any,
    selector: SelectorConfig,
    *,
    items: Sequence[Mapping[str, Any]],
    prompt_modes: Sequence[str] = PROMPT_MODES,
    alphas: Sequence[float] = (0.0, 0.6, 1.2),
    candidates: int = 8,
    temperature: float = 1.05,
    top_p: float = 0.92,
    max_new_tokens: int = 120,
    random_seed: int = 7,
    cell_dir: Optional[str] = None,
    resume: bool = False,
    run_limit: int = 0,
    progress: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    modes = _validate_prompt_modes(prompt_modes)
    alpha_values = _validate_alphas(alphas)
    if not hasattr(generator, "reset_seed"):
        raise TypeError("prompt contrast requires a generator with reset_seed(seed)")
    original_alpha = current_generator_steer_alpha(generator)
    if not set_generator_steer_alpha(generator, original_alpha):
        raise TypeError("prompt contrast requires mutable activation steering")
    engine = DepaysementEngine(
        generator=generator,
        scorer=scorer,
        rng=random.Random(random_seed),
        motif_jitter=0.0,
        selector=selector,
    )
    cell_root = Path(cell_dir) if cell_dir else None
    if cell_root:
        cell_root.mkdir(parents=True, exist_ok=True)
    cells: List[Dict[str, Any]] = []
    new_runs = 0
    stopped_early = False
    total_cells = len(items) * len(modes) * len(alpha_values)
    try:
        for item_index, item in enumerate(items, start=1):
            cell_seed = int(random_seed) + item_index * 1009
            for mode in modes:
                prompt = build_prompt_contrast_prompt(item, mode)
                for alpha in alpha_values:
                    path = _cell_path(cell_root, str(item["id"]), mode, alpha) if cell_root else None
                    if resume and path and path.exists():
                        cell = json.loads(path.read_text(encoding="utf-8"))
                        _validate_resumed_cell(cell, item=item, mode=mode, alpha=alpha)
                        for candidate in cell["candidates"]:
                            candidate["text"] = _clean_candidate_text(candidate.get("text", ""))
                        cells.append(cell)
                        if progress:
                            progress(f"{len(cells)}/{total_cells} resume {path.name}")
                        continue
                    if run_limit and new_runs >= int(run_limit):
                        stopped_early = True
                        break
                    if not set_generator_steer_alpha(generator, float(alpha)):
                        raise RuntimeError("generator rejected steering alpha update")
                    if progress:
                        progress(
                            f"{len(cells) + 1}/{total_cells} run {item['id']} {mode} alpha={float(alpha):.2f}"
                        )
                    generator.reset_seed(cell_seed)
                    raw = generator.generate(
                        prompt,
                        n=int(candidates),
                        temperature=float(temperature),
                        top_p=float(top_p),
                        max_new_tokens=int(max_new_tokens),
                    )
                    payloads = _score_candidates(
                        raw,
                        item=item,
                        engine=engine,
                        scorer=scorer,
                    )
                    if not payloads:
                        raise RuntimeError(
                            f"generator returned no usable candidates for {item['id']}/{mode}/alpha={alpha}"
                        )
                    cell = {
                        "item_id": str(item["id"]),
                        "item_index": int(item_index),
                        "seed": str(item["seed"]),
                        "anchors": list(item["anchors"]),
                        "prompt_mode": mode,
                        "alpha": float(alpha),
                        "generation_seed": int(cell_seed),
                        "prompt": prompt,
                        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                        "requested_candidates": int(candidates),
                        "generated_candidates": len(payloads),
                        "candidates": payloads,
                    }
                    if path:
                        path.write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    cells.append(cell)
                    new_runs += 1
                if stopped_early:
                    break
            if stopped_early:
                break
    finally:
        set_generator_steer_alpha(generator, original_alpha)

    if not cells:
        raise RuntimeError("prompt contrast produced no cells")
    summary_rows = _summary_rows(cells, modes=modes, alphas=alpha_values)
    seed_rows = _seed_rows(cells, modes=modes, alphas=alpha_values)
    matched_summary_rows = _summary_rows(
        cells,
        modes=modes,
        alphas=alpha_values,
        minimum_anchor_coverage=1.0,
    )
    matched_seed_rows = _seed_rows(
        cells,
        modes=modes,
        alphas=alpha_values,
        minimum_anchor_coverage=1.0,
    )
    return {
        "design": {
            "prompt_modes": modes,
            "alphas": alpha_values,
            "candidates_per_cell": int(candidates),
            "temperature": float(temperature),
            "top_p": float(top_p),
            "max_new_tokens": int(max_new_tokens),
            "random_seed": int(random_seed),
            "selector_used_for_generation": False,
            "shared_rng_reset_across_conditions": True,
            "new_cells": int(new_runs),
            "stopped_early": bool(stopped_early),
        },
        "items": [dict(item) for item in items],
        "cells": cells,
        "summary_rows": summary_rows,
        "matched_summary_rows": matched_summary_rows,
        "seed_rows": seed_rows,
        "matched_seed_rows": matched_seed_rows,
        "contrasts": _condition_contrasts(summary_rows, alphas=alpha_values),
        "paired_contrasts": _paired_seed_contrasts(
            seed_rows,
            alphas=alpha_values,
            random_seed=random_seed + 701,
        ),
        "matched_paired_contrasts": _paired_seed_contrasts(
            matched_seed_rows,
            alphas=alpha_values,
            random_seed=random_seed + 1701,
        ),
        "triptych": build_representative_triptych(cells, alphas=alpha_values),
        "notes": [
            "All candidates are retained; no selector chooses the reported pool outcomes.",
            "Observer labels are deterministic navigation aids, not art-historical or human judgments.",
            "RNG resets remove one preventable source of sampling drift but do not pair divergent token paths.",
        ],
    }


def write_prompt_contrast_artifacts(
    report: Mapping[str, Any],
    out_dir: str,
    *,
    rating_seed_limit: int = 6,
    rating_random_seed: int = 20260712,
) -> Dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out / "prompt_steering_contrast.json",
        "summary_json": out / "prompt_steering_summary.json",
        "candidates_csv": out / "prompt_steering_candidates.csv",
        "summary_csv": out / "prompt_steering_summary.csv",
        "matched_summary_csv": out / "prompt_steering_matched_summary.csv",
        "by_seed_csv": out / "prompt_steering_by_seed.csv",
        "paired_csv": out / "prompt_steering_paired_contrasts.csv",
        "report": out / "prompt_steering_report.md",
        "texts": out / "prompt_steering_texts.md",
        "triptych": out / "prompt_steering_triptych.md",
        "rating_csv": out / "human_construct_rating.csv",
        "rating_markdown": out / "human_construct_rating.md",
        "rating_key": out / "human_construct_rating_key.json",
        "plot": out / "prompt_steering_contrast.png",
    }
    paths["json"].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compact_report = {key: value for key, value in report.items() if key != "cells"}
    paths["summary_json"].write_text(
        json.dumps(compact_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(paths["candidates_csv"], _candidate_rows(report["cells"]))
    _write_csv(paths["summary_csv"], list(report["summary_rows"]))
    _write_csv(paths["matched_summary_csv"], list(report["matched_summary_rows"]))
    _write_csv(paths["by_seed_csv"], list(report["seed_rows"]))
    _write_csv(paths["paired_csv"], _paired_contrast_rows(report))
    paths["report"].write_text(format_prompt_contrast_report(report), encoding="utf-8")
    paths["texts"].write_text(_format_full_text_store(report), encoding="utf-8")
    paths["triptych"].write_text(_format_triptych(report["triptych"]), encoding="utf-8")
    rating_rows, rating_key = build_blind_rating_sheet(
        report,
        seed_limit=rating_seed_limit,
        random_seed=rating_random_seed,
    )
    _write_csv(paths["rating_csv"], rating_rows, fieldnames=HUMAN_FIELDS)
    paths["rating_markdown"].write_text(_format_rating_markdown(rating_rows), encoding="utf-8")
    paths["rating_key"].write_text(
        json.dumps(rating_key, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_prompt_contrast_plot(report, paths["plot"])
    return {name: str(path) for name, path in paths.items()}


def build_blind_rating_sheet(
    report: Mapping[str, Any],
    *,
    seed_limit: int = 6,
    random_seed: int = 20260712,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    item_order = [str(item["id"]) for item in report["items"]]
    selected_ids = set(item_order[: max(1, int(seed_limit))])
    source_rows: List[Dict[str, Any]] = []
    for cell in report["cells"]:
        if str(cell["item_id"]) not in selected_ids:
            continue
        representative = select_representative_candidate(cell["candidates"])
        source_rows.append({"cell": cell, "candidate": representative})
    rng = random.Random(int(random_seed))
    rng.shuffle(source_rows)
    public_rows: List[Dict[str, Any]] = []
    key_rows: List[Dict[str, Any]] = []
    for index, source in enumerate(source_rows, start=1):
        item_id = f"R{index:03d}"
        candidate = source["candidate"]
        cell = source["cell"]
        public_rows.append(
            {
                "item_id": item_id,
                "text": candidate["text"],
                "human_anchor_traceable": "",
                "human_role_or_affordance_change": "",
                "human_merely_decorative": "",
                "human_readable": "",
                "human_stock_loop_or_sprawl_failure": "",
                "human_notes": "",
            }
        )
        key_rows.append(
            {
                "item_id": item_id,
                "source_item_id": cell["item_id"],
                "seed": cell["seed"],
                "anchors": cell["anchors"],
                "prompt_mode": cell["prompt_mode"],
                "alpha": cell["alpha"],
                "candidate_index": candidate["candidate_index"],
                "observer_label": candidate["observer_label"],
                "metrics": candidate["metrics"],
            }
        )
    return public_rows, {
        "blinded": True,
        "rating_random_seed": int(random_seed),
        "seed_limit": int(seed_limit),
        "items": key_rows,
    }


def build_representative_triptych(
    cells: Sequence[Mapping[str, Any]],
    *,
    alphas: Sequence[float],
) -> Dict[str, Any]:
    alpha_values = sorted(float(value) for value in alphas)
    zero = min(alpha_values, key=abs)
    positive = [value for value in alpha_values if value > zero + 1e-12]
    corridor = positive[0] if positive else zero
    high = positive[-1] if positive else zero
    grouped: MutableMapping[str, Dict[float, Mapping[str, Any]]] = defaultdict(dict)
    for cell in cells:
        if cell["prompt_mode"] == "operational":
            grouped[str(cell["item_id"])][float(cell["alpha"])] = cell
    ranked: List[Tuple[float, str]] = []
    for item_id, by_alpha in grouped.items():
        if not all(alpha in by_alpha for alpha in (zero, corridor, high)):
            continue
        full = {
            alpha: [
                candidate
                for candidate in by_alpha[alpha]["candidates"]
                if float(candidate["metrics"].get("anchor_phrase_coverage", 0.0)) >= 1.0
            ]
            for alpha in (zero, corridor, high)
        }
        zero_pool = full[zero] or by_alpha[zero]["candidates"]
        corridor_pool = full[corridor] or by_alpha[corridor]["candidates"]
        high_pool = full[high] or by_alpha[high]["candidates"]
        zero_labels = {candidate["observer_label"] for candidate in zero_pool}
        corridor_labels = {candidate["observer_label"] for candidate in corridor_pool}
        high_labels = {candidate["observer_label"] for candidate in high_pool}
        score = 0.0
        score += sum(1.0 for alpha in (zero, corridor, high) if full[alpha])
        score += 2.0 if zero_labels & {"decorative_near_miss", "ontologically_stable"} else 0.0
        score += 3.0 if "readable_transport" in corridor_labels else 0.0
        score += 2.0 if high_labels & FAILURE_LABELS else 0.0
        ranked.append((score, item_id))
    if not ranked:
        return {"available": False, "reason": "no complete operational alpha triplet"}
    _, item_id = max(ranked, key=lambda value: (value[0], value[1]))
    by_alpha = grouped[item_id]
    stages = []
    preferences = (
        (zero, "Prompt only", ("decorative_near_miss", "ontologically_stable")),
        (corridor, "Steered corridor", ("readable_transport",)),
        (high, "High alpha", tuple(FAILURE_LABELS)),
    )
    for alpha, stage, labels in preferences:
        candidate = select_representative_candidate(
            by_alpha[alpha]["candidates"],
            preferred_labels=labels,
            minimum_anchor_coverage=1.0,
        )
        stages.append(
            {
                "stage": stage,
                "alpha": float(alpha),
                "prompt_mode": "operational",
                "anchor_contract_met": float(candidate["metrics"]["anchor_phrase_coverage"]) >= 1.0,
                "candidate": candidate,
            }
        )
    cell = by_alpha[zero]
    return {
        "available": True,
        "item_id": item_id,
        "seed": cell["seed"],
        "anchors": cell["anchors"],
        "stages": stages,
        "selection": "same operational prompt and seed; preferred observer category, then cell-medoid distance",
    }


def select_representative_candidate(
    candidates: Sequence[Mapping[str, Any]],
    *,
    preferred_labels: Sequence[str] = (),
    minimum_anchor_coverage: float = 0.75,
) -> Dict[str, Any]:
    pool = [candidate for candidate in candidates if candidate.get("text")]
    if not pool:
        raise ValueError("cannot select a representative from an empty candidate pool")
    compliant = [
        candidate
        for candidate in pool
        if float(candidate["metrics"].get("anchor_phrase_coverage", 0.0)) >= minimum_anchor_coverage
        and float(candidate["metrics"].get("unfinished", 0.0)) <= 0.05
    ]
    preferred = [candidate for candidate in compliant if candidate.get("observer_label") in set(preferred_labels)]
    eligible = preferred or compliant
    eligible = eligible or pool
    keys = (
        "ontology_collapse_density",
        "syntax_readability_proxy",
        "surface_style_pressure",
        "traceable_transport_score",
    )
    medians = {
        key: statistics.median(float(candidate["metrics"].get(key, 0.0) or 0.0) for candidate in pool)
        for key in keys
    }

    def distance(candidate: Mapping[str, Any]) -> Tuple[float, int]:
        metrics = candidate["metrics"]
        value = sum(abs(float(metrics.get(key, 0.0) or 0.0) - medians[key]) for key in keys)
        return value, int(candidate.get("candidate_index", 0))

    return dict(min(eligible, key=distance))


def format_prompt_contrast_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Prompt x Steering Contrast",
        "",
        (
            "This one-step experiment compares raw candidate pools. The generator receives either a naive "
            "surreal/depaysement instruction or an operational definition of traceable role change. No selector "
            "chooses the reported outcomes."
        ),
        "",
        "## Pool Summary",
        "",
        "| prompt | alpha | seeds | candidates | anchor | full anchor | ontology | read | frontier | traceable | surface | decorative | near miss | transport | failure |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["summary_rows"]:
        lines.append(
            "| {prompt_mode} | {alpha:.2f} | {seed_count} | {candidate_count} | "
            "{anchor_phrase_coverage:.3f} | {anchor_full_rate:.3f} | {ontology_collapse_density:.3f} | "
            "{syntax_readability_proxy:.3f} | {readable_ontology_frontier:.3f} | "
            "{traceable_transport_score:.3f} | {surface_style_pressure:.3f} | "
            "{decoration_without_transport:.3f} | {decorative_near_miss_rate:.3f} | "
            "{readable_transport_rate:.3f} | {failure_rate:.3f} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Exact-Anchor Matched Subset",
            "",
            "Only candidates containing every required anchor phrase are retained below.",
            "",
            "| prompt | alpha | matched / all | ontology | read | frontier | near miss | transport | failure |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report["matched_summary_rows"]:
        lines.append(
            "| {prompt_mode} | {alpha:.2f} | {candidate_count} ({candidate_fraction:.3f}) | "
            "{ontology_collapse_density:.3f} | {syntax_readability_proxy:.3f} | "
            "{readable_ontology_frontier:.3f} | {decorative_near_miss_rate:.3f} | "
            "{readable_transport_rate:.3f} | {failure_rate:.3f} |".format(**row)
        )
    lines.extend(["", "## Pooled Descriptive Contrasts", ""])
    for name, contrast in report["contrasts"].items():
        lines.extend(
            [
                f"### {name.replace('_', ' ').title()}",
                "",
                f"`{contrast['left']}` minus `{contrast['right']}`",
                "",
                "| metric | delta |",
                "|---|---:|",
            ]
        )
        for metric, value in contrast["delta"].items():
            lines.append(f"| {metric} | {float(value):+.3f} |")
        lines.append("")
    _append_paired_contrast_section(
        lines,
        title="Seed-Paired Contrasts",
        contrasts=report["paired_contrasts"],
    )
    _append_paired_contrast_section(
        lines,
        title="Seed-Paired Exact-Anchor Contrasts",
        contrasts=report["matched_paired_contrasts"],
    )
    lines.extend(["## Representative Same-Prompt Triptych", "", _format_triptych(report["triptych"]).strip()])
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "- Prompt-only is treated as a strong competitor, not a deliberately weak straw baseline.",
            "- Seed-paired bootstrap intervals use the 12 mundane scenes as units; candidates are not treated as independent observations.",
            "- The triptych is deterministic but illustrative; condition-level claims must use the complete pools.",
            "- Observer labels are operational near-miss/transport/failure categories, not final literary judgments.",
            "- The blinded human sheet tests anchor traceability, role change, decoration, readability, and failure separately.",
        ]
    )
    return "\n".join(lines) + "\n"


def _append_paired_contrast_section(
    lines: List[str],
    *,
    title: str,
    contrasts: Mapping[str, Any],
) -> None:
    shown_metrics = (
        "anchor_phrase_coverage",
        "ontology_collapse_density",
        "readable_transport_rate",
        "failure_rate",
    )
    lines.extend([f"## {title}", ""])
    for name, contrast in contrasts.items():
        lines.extend(
            [
                f"### {name.replace('_', ' ').title()}",
                "",
                f"`{contrast['left']}` minus `{contrast['right']}`",
                "",
                "| metric | seed pairs | mean delta | bootstrap 95% CI | positive seeds |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for metric in shown_metrics:
            result = contrast["metrics"][metric]
            lines.append(
                f"| {metric} | {int(result['seed_pairs'])} | {float(result['mean_delta']):+.3f} | "
                f"[{float(result['ci95_low']):+.3f}, {float(result['ci95_high']):+.3f}] | "
                f"{float(result['positive_seed_fraction']):.3f} |"
            )
        lines.append("")


def _score_candidates(
    texts: Sequence[str],
    *,
    item: Mapping[str, Any],
    engine: DepaysementEngine,
    scorer: Any,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for index, raw in enumerate(texts, start=1):
        text = _clean_candidate_text(raw)
        if not text:
            continue
        candidate = Candidate(text=text, score=scorer.score(text, context=str(item["seed"])))
        engine._attach_selector_metrics(candidate, context=str(item["seed"]))
        metrics = dict(candidate.selector_metrics)
        metrics.update(anchor_phrase_metrics(text, item["anchors"]))
        metrics.update(surface_style_metrics(text))
        ontology = float(metrics.get("ontology_collapse_density", 0.0) or 0.0)
        metrics["decoration_without_transport"] = float(
            metrics["anchor_phrase_coverage"]
            * metrics["syntax_readability_proxy"]
            * metrics["surface_style_pressure"]
            * (1.0 - ontology)
        )
        out.append(
            {
                "candidate_index": int(index),
                "text": text,
                "score": candidate.to_dict()["score"],
                "metrics": metrics,
                "observer_label": classify_prompt_candidate(metrics),
            }
        )
    return out


def _summary_rows(
    cells: Sequence[Mapping[str, Any]],
    *,
    modes: Sequence[str],
    alphas: Sequence[float],
    minimum_anchor_coverage: float = 0.0,
) -> List[Dict[str, Any]]:
    grouped: MutableMapping[Tuple[str, float], List[Mapping[str, Any]]] = defaultdict(list)
    for cell in cells:
        grouped[(str(cell["prompt_mode"]), float(cell["alpha"]))].append(cell)
    rows: List[Dict[str, Any]] = []
    for mode in modes:
        for alpha in alphas:
            group = grouped.get((mode, float(alpha)), [])
            if group:
                rows.append(
                    _aggregate_cells(
                        group,
                        prompt_mode=mode,
                        alpha=float(alpha),
                        minimum_anchor_coverage=minimum_anchor_coverage,
                    )
                )
    return rows


def _seed_rows(
    cells: Sequence[Mapping[str, Any]],
    *,
    modes: Sequence[str],
    alphas: Sequence[float],
    minimum_anchor_coverage: float = 0.0,
) -> List[Dict[str, Any]]:
    lookup = {
        (str(cell["item_id"]), str(cell["prompt_mode"]), float(cell["alpha"])): cell for cell in cells
    }
    item_order = list(dict.fromkeys(str(cell["item_id"]) for cell in cells))
    rows: List[Dict[str, Any]] = []
    for item_id in item_order:
        for mode in modes:
            for alpha in alphas:
                cell = lookup.get((item_id, mode, float(alpha)))
                if not cell:
                    continue
                row = _aggregate_cells(
                    [cell],
                    prompt_mode=mode,
                    alpha=float(alpha),
                    minimum_anchor_coverage=minimum_anchor_coverage,
                )
                row["item_id"] = item_id
                row["seed"] = cell["seed"]
                rows.append(row)
    return rows


def _aggregate_cells(
    cells: Sequence[Mapping[str, Any]],
    *,
    prompt_mode: str,
    alpha: float,
    minimum_anchor_coverage: float = 0.0,
) -> Dict[str, Any]:
    all_candidates = [candidate for cell in cells for candidate in cell["candidates"]]
    candidates = [
        candidate
        for candidate in all_candidates
        if float(candidate["metrics"].get("anchor_phrase_coverage", 0.0) or 0.0)
        >= float(minimum_anchor_coverage)
    ]
    row: Dict[str, Any] = {
        "prompt_mode": prompt_mode,
        "alpha": float(alpha),
        "seed_count": len({str(cell["item_id"]) for cell in cells}),
        "candidate_count": len(candidates),
        "candidate_fraction": len(candidates) / max(1, len(all_candidates)),
        "minimum_anchor_coverage": float(minimum_anchor_coverage),
    }
    for metric in SUMMARY_METRICS:
        row[metric] = _mean(float(candidate["metrics"].get(metric, 0.0) or 0.0) for candidate in candidates)
    labels = [str(candidate["observer_label"]) for candidate in candidates]
    for rate_name, label in RATE_LABELS:
        row[rate_name] = _mean(1.0 if value == label else 0.0 for value in labels)
    row["failure_rate"] = _mean(1.0 if value in FAILURE_LABELS else 0.0 for value in labels)
    row["mixed_rate"] = _mean(1.0 if value == "mixed_or_untraceable" else 0.0 for value in labels)
    row["anchor_full_rate"] = _mean(
        1.0 if float(candidate["metrics"].get("anchor_phrase_coverage", 0.0)) >= 1.0 else 0.0
        for candidate in all_candidates
    )
    row["anchor_traceable_rate"] = _mean(
        1.0 if float(candidate["metrics"].get("anchor_phrase_coverage", 0.0)) >= 0.75 else 0.0
        for candidate in all_candidates
    )
    return row


def _condition_contrasts(
    rows: Sequence[Mapping[str, Any]],
    *,
    alphas: Sequence[float],
) -> Dict[str, Any]:
    lookup = {(str(row["prompt_mode"]), float(row["alpha"])): row for row in rows}
    values = sorted(float(value) for value in alphas)
    zero = min(values, key=abs)
    positive = [value for value in values if value > zero + 1e-12]
    corridor = positive[0] if positive else zero
    high = positive[-1] if positive else zero
    specs = {
        "operational_prompt_gain_at_zero": (("operational", zero), ("naive", zero)),
        "naive_corridor_steering_gain": (("naive", corridor), ("naive", zero)),
        "operational_corridor_steering_gain": (("operational", corridor), ("operational", zero)),
        "naive_high_alpha_change": (("naive", high), ("naive", corridor)),
        "operational_high_alpha_change": (("operational", high), ("operational", corridor)),
    }
    metrics = (
        "anchor_phrase_coverage",
        "ontology_collapse_density",
        "syntax_readability_proxy",
        "decoration_without_transport",
        "decorative_near_miss_rate",
        "readable_transport_rate",
        "failure_rate",
    )
    out: Dict[str, Any] = {}
    for name, (left_key, right_key) in specs.items():
        if left_key not in lookup or right_key not in lookup:
            continue
        left = lookup[left_key]
        right = lookup[right_key]
        out[name] = {
            "left": f"{left_key[0]} alpha={left_key[1]:.2f}",
            "right": f"{right_key[0]} alpha={right_key[1]:.2f}",
            "delta": {metric: float(left[metric]) - float(right[metric]) for metric in metrics},
        }
    required = {
        "op_corridor": ("operational", corridor),
        "op_zero": ("operational", zero),
        "naive_corridor": ("naive", corridor),
        "naive_zero": ("naive", zero),
    }
    if all(key in lookup for key in required.values()):
        out["prompt_x_corridor_interaction"] = {
            "left": "operational corridor gain",
            "right": "naive corridor gain",
            "delta": {
                metric: (
                    float(lookup[required["op_corridor"]][metric])
                    - float(lookup[required["op_zero"]][metric])
                    - float(lookup[required["naive_corridor"]][metric])
                    + float(lookup[required["naive_zero"]][metric])
                )
                for metric in metrics
            },
        }
    return out


def _paired_seed_contrasts(
    rows: Sequence[Mapping[str, Any]],
    *,
    alphas: Sequence[float],
    random_seed: int,
    bootstrap_samples: int = 5000,
) -> Dict[str, Any]:
    lookup = {
        (str(row["item_id"]), str(row["prompt_mode"]), float(row["alpha"])): row
        for row in rows
    }
    item_ids = sorted({str(row["item_id"]) for row in rows})
    values = sorted(float(value) for value in alphas)
    zero = min(values, key=abs)
    positive = [value for value in values if value > zero + 1e-12]
    corridor = positive[0] if positive else zero
    high = positive[-1] if positive else zero
    specs = {
        "operational_prompt_gain_at_zero": (("operational", zero), ("naive", zero)),
        "naive_corridor_steering_gain": (("naive", corridor), ("naive", zero)),
        "operational_corridor_steering_gain": (("operational", corridor), ("operational", zero)),
        "naive_high_alpha_change": (("naive", high), ("naive", corridor)),
        "operational_high_alpha_change": (("operational", high), ("operational", corridor)),
    }
    metrics = (
        "anchor_phrase_coverage",
        "ontology_collapse_density",
        "syntax_readability_proxy",
        "decoration_without_transport",
        "decorative_near_miss_rate",
        "readable_transport_rate",
        "failure_rate",
    )
    out: Dict[str, Any] = {}
    for spec_index, (name, (left_key, right_key)) in enumerate(specs.items()):
        metric_results: Dict[str, Any] = {}
        for metric_index, metric in enumerate(metrics):
            differences = []
            for item_id in item_ids:
                left = lookup.get((item_id, left_key[0], left_key[1]))
                right = lookup.get((item_id, right_key[0], right_key[1]))
                if not left or not right:
                    continue
                if int(left.get("candidate_count", 0)) <= 0 or int(right.get("candidate_count", 0)) <= 0:
                    continue
                differences.append(float(left[metric]) - float(right[metric]))
            rng = random.Random(int(random_seed) + spec_index * 101 + metric_index * 1009)
            low, high_ci = _bootstrap_mean_interval(
                differences,
                rng=rng,
                samples=bootstrap_samples,
            )
            metric_results[metric] = {
                "seed_pairs": len(differences),
                "mean_delta": _mean(differences),
                "median_delta": statistics.median(differences) if differences else 0.0,
                "ci95_low": low,
                "ci95_high": high_ci,
                "positive_seed_fraction": _mean(1.0 if value > 0.0 else 0.0 for value in differences),
                "seed_deltas": differences,
            }
        out[name] = {
            "left": f"{left_key[0]} alpha={left_key[1]:.2f}",
            "right": f"{right_key[0]} alpha={right_key[1]:.2f}",
            "bootstrap_unit": "seed",
            "bootstrap_samples": int(bootstrap_samples),
            "metrics": metric_results,
        }
    interaction_results: Dict[str, Any] = {}
    for metric_index, metric in enumerate(metrics):
        differences = []
        for item_id in item_ids:
            op_corridor = lookup.get((item_id, "operational", corridor))
            op_zero = lookup.get((item_id, "operational", zero))
            naive_corridor = lookup.get((item_id, "naive", corridor))
            naive_zero = lookup.get((item_id, "naive", zero))
            quartet = (op_corridor, op_zero, naive_corridor, naive_zero)
            if not all(quartet) or any(int(row.get("candidate_count", 0)) <= 0 for row in quartet if row):
                continue
            differences.append(
                float(op_corridor[metric])
                - float(op_zero[metric])
                - float(naive_corridor[metric])
                + float(naive_zero[metric])
            )
        rng = random.Random(int(random_seed) + 9001 + metric_index * 1009)
        low, high_ci = _bootstrap_mean_interval(differences, rng=rng, samples=bootstrap_samples)
        interaction_results[metric] = {
            "seed_pairs": len(differences),
            "mean_delta": _mean(differences),
            "median_delta": statistics.median(differences) if differences else 0.0,
            "ci95_low": low,
            "ci95_high": high_ci,
            "positive_seed_fraction": _mean(1.0 if value > 0.0 else 0.0 for value in differences),
            "seed_deltas": differences,
        }
    out["prompt_x_corridor_interaction"] = {
        "left": "operational corridor gain",
        "right": "naive corridor gain",
        "bootstrap_unit": "seed",
        "bootstrap_samples": int(bootstrap_samples),
        "metrics": interaction_results,
    }
    return out


def _bootstrap_mean_interval(
    values: Sequence[float],
    *,
    rng: random.Random,
    samples: int,
) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return float(values[0]), float(values[0])
    means = []
    for _ in range(max(1, int(samples))):
        means.append(_mean(values[rng.randrange(len(values))] for _ in values))
    means.sort()
    return _percentile(means, 0.025), _percentile(means, 0.975)


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    position = max(0.0, min(1.0, float(quantile))) * (len(values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(values[lower])
    fraction = position - lower
    return float(values[lower]) * (1.0 - fraction) + float(values[upper]) * fraction


def _paired_contrast_rows(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for scope, key in (("all", "paired_contrasts"), ("exact_anchor", "matched_paired_contrasts")):
        for contrast_name, contrast in report[key].items():
            for metric, result in contrast["metrics"].items():
                rows.append(
                    {
                        "scope": scope,
                        "contrast": contrast_name,
                        "left": contrast["left"],
                        "right": contrast["right"],
                        "metric": metric,
                        **{name: value for name, value in result.items() if name != "seed_deltas"},
                    }
                )
    return rows


def _candidate_rows(cells: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    extra_metrics = (
        "identity_melt_score",
        "affordance_corruption_score",
        "category_bleeding_score",
        "frontier_quality",
        "stock_prop_attractor_score",
        "lineage_bridge",
        "trajectory_revisit_pressure",
    )
    for cell in cells:
        for candidate in cell["candidates"]:
            metrics = candidate["metrics"]
            rows.append(
                {
                    "item_id": cell["item_id"],
                    "seed": cell["seed"],
                    "anchors": "; ".join(cell["anchors"]),
                    "prompt_mode": cell["prompt_mode"],
                    "alpha": cell["alpha"],
                    "generation_seed": cell["generation_seed"],
                    "candidate_index": candidate["candidate_index"],
                    "observer_label": candidate["observer_label"],
                    "text": candidate["text"],
                    "anchor_phrase_hits": "; ".join(metrics.get("anchor_phrase_hits", [])),
                    "anchor_phrase_misses": "; ".join(metrics.get("anchor_phrase_misses", [])),
                    "surface_style_hits": "; ".join(metrics.get("surface_style_hits", [])),
                    **{metric: metrics.get(metric, 0.0) for metric in SUMMARY_METRICS},
                    **{metric: metrics.get(metric, 0.0) for metric in extra_metrics},
                }
            )
    return rows


def _format_full_text_store(report: Mapping[str, Any]) -> str:
    lines = [
        "# Prompt x Steering Full Text Store",
        "",
        "Every generated candidate is retained. Observer labels are navigation aids, not taste labels.",
    ]
    for cell in report["cells"]:
        lines.extend(
            [
                "",
                f"## {cell['item_id']} | {cell['prompt_mode']} | alpha={float(cell['alpha']):.2f}",
                "",
                f"Seed: `{cell['seed']}`",
                "",
                f"Anchors: {', '.join(cell['anchors'])}",
            ]
        )
        for candidate in cell["candidates"]:
            metrics = candidate["metrics"]
            lines.extend(
                [
                    "",
                    f"### Candidate {candidate['candidate_index']} | {candidate['observer_label']}",
                    "",
                    (
                        f"anchor={float(metrics['anchor_phrase_coverage']):.3f} | "
                        f"ontology={float(metrics['ontology_collapse_density']):.3f} | "
                        f"read={float(metrics['syntax_readability_proxy']):.3f} | "
                        f"frontier={float(metrics['readable_ontology_frontier']):.3f} | "
                        f"surface={float(metrics['surface_style_pressure']):.3f}"
                    ),
                    "",
                    "```text",
                    str(candidate["text"]),
                    "```",
                ]
            )
    return "\n".join(lines) + "\n"


def _format_triptych(triptych: Mapping[str, Any]) -> str:
    if not triptych.get("available"):
        return f"Triptych unavailable: {triptych.get('reason', 'unknown reason')}\n"
    lines = [
        f"Seed: `{triptych['seed']}`",
        "",
        f"Anchors: {', '.join(triptych['anchors'])}",
    ]
    for stage in triptych["stages"]:
        candidate = stage["candidate"]
        metrics = candidate["metrics"]
        lines.extend(
            [
                "",
                f"### {stage['stage']} | alpha={float(stage['alpha']):.2f}",
                "",
                (
                    f"Observer label: `{candidate['observer_label']}` | "
                    f"all anchors matched: `{'yes' if stage['anchor_contract_met'] else 'no'}`"
                ),
                "",
                (
                    f"anchor={float(metrics['anchor_phrase_coverage']):.3f} | "
                    f"ontology={float(metrics['ontology_collapse_density']):.3f} | "
                    f"read={float(metrics['syntax_readability_proxy']):.3f} | "
                    f"frontier={float(metrics['readable_ontology_frontier']):.3f}"
                ),
                "",
                "```text",
                str(candidate["text"]),
                "```",
            ]
        )
    return "\n".join(lines) + "\n"


def _format_rating_markdown(rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# Blind Human Construct Rating",
        "",
        "Fill each binary field with 0 or 1. Conditions, alpha, seed identity, and machine metrics are hidden.",
        "",
        "- `human_anchor_traceable`: the named source objects remain identifiable.",
        "- `human_role_or_affordance_change`: at least one object changes what it is, does, or permits.",
        "- `human_merely_decorative`: oddness comes mainly from adjectives, atmosphere, or polished metaphor.",
        "- `human_readable`: the sentence remains locally readable and complete.",
        "- `human_stock_loop_or_sprawl_failure`: stock props, recurrence, or unrelated noun accumulation dominates.",
    ]
    for row in rows:
        lines.extend(
            [
                "",
                f"## {row['item_id']}",
                "",
                "```text",
                str(row["text"]),
                "```",
                "",
                "human_anchor_traceable:",
                "",
                "human_role_or_affordance_change:",
                "",
                "human_merely_decorative:",
                "",
                "human_readable:",
                "",
                "human_stock_loop_or_sprawl_failure:",
                "",
                "human_notes:",
            ]
        )
    return "\n".join(lines) + "\n"


def _write_prompt_contrast_plot(report: Mapping[str, Any], path: Path) -> None:
    try:
        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D
    except ImportError as exc:  # pragma: no cover - optional plotting dependency
        raise RuntimeError("prompt contrast plotting requires matplotlib") from exc

    rows = list(report["matched_summary_rows"])
    cells = list(report["cells"])
    alphas = sorted({float(row["alpha"]) for row in rows})
    color_map = plt.get_cmap("viridis")
    palette = {
        alpha: color_map(index / max(1, len(alphas) - 1))
        for index, alpha in enumerate(alphas)
    }
    markers = {"naive": "o", "operational": "^"}
    present_modes = [mode for mode in PROMPT_MODES if any(row["prompt_mode"] == mode for row in rows)]
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.5), constrained_layout=True)
    fig.patch.set_facecolor("white")

    ax = axes[0]
    for cell in cells:
        for candidate in cell["candidates"]:
            metrics = candidate["metrics"]
            if float(metrics["anchor_phrase_coverage"]) < 1.0:
                continue
            ax.scatter(
                float(metrics["ontology_collapse_density"]),
                float(metrics["syntax_readability_proxy"]),
                s=18,
                alpha=0.42,
                color=palette[float(cell["alpha"])],
                marker=markers[str(cell["prompt_mode"])],
                linewidths=0,
            )
    ax.axvspan(0.20, 0.60, color="#DCE8D5", alpha=0.35)
    ax.axhline(0.55, color="#555555", linewidth=0.8, linestyle="--")
    ax.set_xlabel("ontology collapse density")
    ax.set_ylabel("readability proxy")
    legend_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=palette[alpha], label=f"alpha={alpha:.1f}")
        for alpha in alphas
    ]
    legend_handles.extend(
        [
            Line2D([0], [0], marker=markers[mode], color="#555555", linestyle="none", label=mode)
            for mode in present_modes
        ]
    )
    ax.legend(handles=legend_handles, frameon=False, fontsize=7, loc="lower right")
    ax.set_title("Exact-anchor raw candidates")
    ax.grid(alpha=0.18)

    ax = axes[1]
    for mode in present_modes:
        selected = [row for row in rows if row["prompt_mode"] == mode]
        if not selected:
            continue
        ax.plot(
            [row["alpha"] for row in selected],
            [row["readable_transport_rate"] for row in selected],
            marker=markers[mode],
            linewidth=2,
            label=f"{mode}: transport",
        )
        ax.plot(
            [row["alpha"] for row in selected],
            [row["decorative_near_miss_rate"] for row in selected],
            marker=markers[mode],
            linestyle="--",
            linewidth=1.4,
            label=f"{mode}: near miss",
        )
    ax.set_xlabel("steering alpha")
    ax.set_ylabel("candidate rate")
    ax.set_ylim(0.0, 1.0)
    ax.set_title("Surface imitation vs role change")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False, fontsize=7, loc="upper right", ncol=2)

    ax = axes[2]
    labels = [f"{row['prompt_mode'].title()}\n{float(row['alpha']):.1f}" for row in rows]
    x = list(range(len(rows)))
    ax.bar(x, [row["failure_rate"] for row in rows], color="#C14953", label="failure")
    ax.bar(
        x,
        [row["readable_transport_rate"] for row in rows],
        bottom=[row["failure_rate"] for row in rows],
        color="#2F855A",
        label="readable transport",
    )
    ax.set_xticks(x, labels, rotation=45, ha="right")
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("candidate rate")
    ax.set_title("Transport and failure mass")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.grid(axis="y", alpha=0.2)

    fig.suptitle("Prompt x steering contrast: same anchors, no selector", fontsize=12)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=190, bbox_inches="tight", facecolor="white", transparent=False)
    plt.close(fig)


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    fieldnames: Optional[Sequence[str]] = None,
) -> None:
    names = list(fieldnames or (list(rows[0]) if rows else []))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n", extrasaction="ignore")
        if names:
            writer.writeheader()
            writer.writerows(rows)


def _cell_path(root: Path, item_id: str, mode: str, alpha: float) -> Path:
    return root / f"{item_id}__{mode}__alpha_{_float_label(alpha)}.json"


def _float_label(value: float) -> str:
    text = f"{float(value):.3f}".rstrip("0").rstrip(".")
    return text.replace("-", "neg").replace(".", "p") or "0"


def _validate_resumed_cell(
    cell: Mapping[str, Any],
    *,
    item: Mapping[str, Any],
    mode: str,
    alpha: float,
) -> None:
    identity = (str(cell.get("item_id")), str(cell.get("prompt_mode")), float(cell.get("alpha", math.nan)))
    expected = (str(item["id"]), str(mode), float(alpha))
    if identity != expected:
        raise ValueError(f"resume cell identity mismatch: found={identity}, expected={expected}")


def _validate_prompt_modes(modes: Sequence[str]) -> List[str]:
    values = [str(mode).strip().lower() for mode in modes if str(mode).strip()]
    if not values or any(value not in PROMPT_MODES for value in values):
        raise ValueError(f"prompt modes must be selected from {PROMPT_MODES}")
    return list(dict.fromkeys(values))


def _validate_alphas(alphas: Sequence[float]) -> List[float]:
    values = [float(value) for value in alphas]
    if len(values) < 3 or len(set(values)) != len(values):
        raise ValueError("prompt contrast requires at least three unique alpha values")
    if not any(abs(value) <= 1e-12 for value in values):
        raise ValueError("prompt contrast alphas must include zero")
    if sum(1 for value in values if value > 0.0) < 2:
        raise ValueError("prompt contrast alphas must contain at least two positive values")
    return sorted(values)


def _normalize_phrase(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text).lower()))


def _clean_candidate_text(text: Any) -> str:
    return "\n".join(line.rstrip() for line in str(text).strip().splitlines()).strip()


def _phrase_present(text: str, phrase: str) -> bool:
    haystack = f" {_normalize_phrase(text)} "
    needle = f" {_normalize_phrase(phrase)} "
    return bool(needle.strip()) and needle in haystack


def _mean(values: Iterable[float]) -> float:
    collected = [float(value) for value in values]
    return sum(collected) / len(collected) if collected else 0.0

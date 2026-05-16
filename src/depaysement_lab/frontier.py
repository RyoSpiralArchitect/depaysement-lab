"""Readable Ontology Collapse Frontier (v1.0).

This module audits *candidate pools* rather than only the picked continuation.
It is meant to answer a narrower question than the v0.9 ontology audit:

    Did activation steering move the generation distribution itself, or did the
    external selector merely cherry-pick a rare collapsed candidate?

The metrics are deliberately transparent heuristics.  They are not a theory of
surrealism.  Treat them as instruments for comparing conditions and for
selecting samples to send to human evaluation.
"""

from __future__ import annotations

import csv
import dataclasses
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .ontology import OntologyAuditor, OntologyMetrics, clamp01, join_like, load_run_records
from .scorer_v07 import V07DepaysementScorer


GENERATED_SPECIAL_TOKENS: Tuple[str, ...] = (
    "<|eot_id|>",
    "<|end_of_text|>",
    "<|begin_of_text|>",
    "<|im_end|>",
    "</s>",
    "<s>",
)

FRONTIER_METRICS: Tuple[str, ...] = (
    "readable_ontology_frontier",
    "ontology_collapse_density",
    "identity_melt_score",
    "affordance_corruption_score",
    "category_bleeding_score",
    "syntax_readability_proxy",
    "graph_integration",
    "graph_fragmentation",
    "repair_pressure",
    "atmospheric_conservation",
    "unfinished",
    "meta_leak",
    "score_total",
)


@dataclass
class FrontierCandidateRow:
    run_name: str
    condition: str
    path: str
    step: int
    candidate_index: int
    picked: bool
    text: str
    context_before: str
    score_total: float
    readable_ontology_frontier: float
    frontier_quality: float
    metrics: Dict[str, Any]
    source_score: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class FrontierRunAudit:
    name: str
    condition: str
    path: str
    seed: str
    candidate_count: int
    picked_count: int
    steps: int
    truncated_steps: int
    aggregate: Dict[str, Any]
    rows: List[FrontierCandidateRow] = field(default_factory=list)

    def to_dict(self, *, include_rows: bool = True) -> Dict[str, Any]:
        out = {
            "name": self.name,
            "condition": self.condition,
            "path": self.path,
            "seed": self.seed,
            "candidate_count": self.candidate_count,
            "picked_count": self.picked_count,
            "steps": self.steps,
            "truncated_steps": self.truncated_steps,
            "aggregate": self.aggregate,
        }
        if include_rows:
            out["rows"] = [r.to_dict() for r in self.rows]
        return out


@dataclass
class FrontierAuditReport:
    runs: List[FrontierRunAudit]
    comparisons: List[Dict[str, Any]] = field(default_factory=list)
    top_frontier_examples: List[Dict[str, Any]] = field(default_factory=list)
    failure_examples: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self, *, include_rows: bool = True) -> Dict[str, Any]:
        return {
            "runs": [r.to_dict(include_rows=include_rows) for r in self.runs],
            "comparisons": self.comparisons,
            "top_frontier_examples": list(self.top_frontier_examples),
            "failure_examples": list(self.failure_examples),
            "notes": list(self.notes),
        }


class FrontierAuditor:
    """Audit candidate-pool distributions for readable ontology collapse."""

    def __init__(
        self,
        scorer: Optional[V07DepaysementScorer] = None,
        *,
        ontology_threshold: float = 0.23,
        readability_threshold: float = 0.58,
        repair_threshold: float = 0.35,
    ):
        self.scorer = scorer or V07DepaysementScorer(lexicon_enabled=False, lexicon_prior_scale=0.0)
        self.ontology = OntologyAuditor(scorer=self.scorer)
        self.ontology_threshold = float(ontology_threshold)
        self.readability_threshold = float(readability_threshold)
        self.repair_threshold = float(repair_threshold)

    def audit_run(self, run: Mapping[str, Any], *, name: str, path: str = "") -> FrontierRunAudit:
        seed = str(run.get("seed") or "")
        config = run.get("config") if isinstance(run.get("config"), Mapping) else {}
        condition = str(config.get("condition") or _condition_from_name(name) or Path(path).stem or name)
        expected_candidates = int(config.get("candidates_per_step") or config.get("candidates") or 0)
        rows: List[FrontierCandidateRow] = []
        truncated_steps = 0
        running_context = clean_generated_text(seed)
        steps = list(run.get("steps", []) or [])
        for step_idx, step in enumerate(steps, 1):
            if not isinstance(step, Mapping):
                continue
            context = clean_generated_text(str(step.get("context_before") or running_context))
            picked = step.get("picked") if isinstance(step.get("picked"), Mapping) else {}
            picked_text = clean_generated_text(str(picked.get("text") or step.get("text") or ""))
            candidates = list(step.get("candidates", []) or [])
            if not candidates and picked_text:
                candidates = [picked]
            elif picked_text and not any(
                clean_generated_text(str(c.get("text") or "")) == picked_text
                for c in candidates
                if isinstance(c, Mapping)
            ):
                candidates.append(picked)
            if expected_candidates and 0 < len(candidates) < expected_candidates:
                truncated_steps += 1
            for cand_idx, cand in enumerate(candidates, 1):
                if not isinstance(cand, Mapping):
                    continue
                raw_text = str(cand.get("text") or "")
                text = clean_generated_text(raw_text)
                if not text.strip():
                    continue
                score_dict = cand.get("score") if isinstance(cand.get("score"), Mapping) else {}
                score_total = float(self.scorer.score(text, context=context).total)
                m = self.ontology.audit_text(text, context=context)
                frontier_score, frontier_quality = readable_frontier_score(m)
                rows.append(
                    FrontierCandidateRow(
                        run_name=name,
                        condition=condition,
                        path=path,
                        step=int(step.get("step") or step_idx),
                        candidate_index=cand_idx,
                        picked=(text == picked_text),
                        text=text,
                        context_before=context,
                        score_total=score_total,
                        readable_ontology_frontier=frontier_score,
                        frontier_quality=frontier_quality,
                        metrics=m.to_dict(),
                        source_score=dict(score_dict),
                        raw_text=raw_text,
                    )
                )
            if picked_text:
                running_context = join_like(running_context, picked_text)
        agg = aggregate_frontier_rows(
            rows,
            ontology_threshold=self.ontology_threshold,
            readability_threshold=self.readability_threshold,
            repair_threshold=self.repair_threshold,
        )
        return FrontierRunAudit(
            name=name,
            condition=condition,
            path=path,
            seed=seed,
            candidate_count=len(rows),
            picked_count=sum(1 for r in rows if r.picked),
            steps=len(steps),
            truncated_steps=truncated_steps,
            aggregate=agg,
            rows=rows,
        )


def audit_frontier_pool(
    paths: Sequence[str],
    *,
    scorer: Optional[V07DepaysementScorer] = None,
    top_k: int = 8,
    ontology_threshold: float = 0.23,
    readability_threshold: float = 0.58,
    repair_threshold: float = 0.35,
) -> FrontierAuditReport:
    auditor = FrontierAuditor(
        scorer=scorer,
        ontology_threshold=ontology_threshold,
        readability_threshold=readability_threshold,
        repair_threshold=repair_threshold,
    )
    runs: List[FrontierRunAudit] = []
    for path in paths:
        for name, run in load_run_records(path):
            runs.append(auditor.audit_run(run, name=name, path=path))
    comparisons = compare_frontier_runs(runs)
    all_rows = [r for run in runs for r in run.rows]
    top = sorted(all_rows, key=lambda r: r.readable_ontology_frontier, reverse=True)[: max(0, top_k)]
    failures = sorted(all_rows, key=failure_score, reverse=True)[: max(0, top_k)]
    notes = [
        "Readable Ontology Collapse Frontier audits candidate pools, not only picked outputs.",
        "pool_shift compares mean candidate-pool metrics; selection_lift compares picked candidates against their saved pool.",
        "If truncated_steps > 0, the artifact saved only a subset of the generated candidates; rerun with --save-candidates >= --candidates for full pool geometry.",
        "Metrics are heuristic instruments. Use human ratings before treating them as empirical claims.",
    ]
    return FrontierAuditReport(
        runs=runs,
        comparisons=comparisons,
        top_frontier_examples=[compact_row(r) for r in top],
        failure_examples=[compact_row(r) for r in failures],
        notes=notes,
    )


def clean_generated_text(text: str) -> str:
    """Remove model control tokens that should not participate in scoring."""

    clean = str(text or "")
    for token in GENERATED_SPECIAL_TOKENS:
        clean = clean.replace(token, " ")
    clean = re.sub(r"[ \t]+", " ", clean)
    clean = re.sub(r"\s+([,.;:!?])", r"\1", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


def readable_frontier_score(m: OntologyMetrics) -> Tuple[float, float]:
    """Return (frontier_score, frontier_quality).

    quality captures whether the candidate remains readable and scene-integrated.
    The frontier score multiplies quality by ontology collapse density.  Atmosphere
    is a weak stabilizer rather than a hard requirement, because some good samples
    are stark rather than damp/faded.
    """

    anti_repair = 1.0 - float(m.repair_pressure)
    anti_unfinished = 1.0 - float(m.unfinished)
    anti_meta = 1.0 - float(m.meta_leak)
    graph_factor = 0.50 + 0.50 * float(m.graph_integration)
    atmosphere_factor = 0.82 + 0.18 * float(m.atmospheric_conservation)
    quality = clamp01(
        float(m.syntax_readability_proxy)
        * graph_factor
        * anti_repair
        * anti_unfinished
        * anti_meta
    )
    frontier = clamp01(float(m.ontology_collapse_density) * quality * atmosphere_factor)
    return frontier, quality


def failure_score(row: FrontierCandidateRow) -> float:
    m = row.metrics
    # High ontology with low readability is interesting failure; repair pressure
    # and unfinished tails are also frontier breakers.
    ont = float(m.get("ontology_collapse_density", 0.0))
    read_fail = 1.0 - float(m.get("syntax_readability_proxy", 0.0))
    frag = float(m.get("graph_fragmentation", 0.0))
    repair = float(m.get("repair_pressure", 0.0))
    unfinished = float(m.get("unfinished", 0.0))
    meta = float(m.get("meta_leak", 0.0))
    return ont * (0.45 * read_fail + 0.25 * frag + 0.20 * repair + 0.25 * unfinished + 0.25 * meta)


def aggregate_frontier_rows(
    rows: Sequence[FrontierCandidateRow],
    *,
    ontology_threshold: float,
    readability_threshold: float,
    repair_threshold: float,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "candidate_count": len(rows),
        "picked_count": sum(1 for r in rows if r.picked),
    }
    if not rows:
        out["phenomenon_label"] = "empty_pool"
        return out
    picked = [r for r in rows if r.picked]
    pool_stats = summarize_rows(rows, prefix="pool")
    picked_stats = summarize_rows(picked, prefix="picked") if picked else {}
    out.update(pool_stats)
    out.update(picked_stats)
    for metric in FRONTIER_METRICS:
        pkey = f"picked_mean_{metric}"
        ckey = f"pool_mean_{metric}"
        if pkey in out and ckey in out:
            out[f"selection_lift_{metric}"] = float(out[pkey]) - float(out[ckey])
    out["pool_frontier_hit_rate"] = hit_rate(rows, ontology_threshold, readability_threshold, repair_threshold)
    out["picked_frontier_hit_rate"] = hit_rate(picked, ontology_threshold, readability_threshold, repair_threshold) if picked else 0.0
    out["pool_unfinished_rate"] = sum(1 for r in rows if float(r.metrics.get("unfinished", 0.0)) > 0.0) / len(rows)
    out["picked_unfinished_rate"] = (sum(1 for r in picked if float(r.metrics.get("unfinished", 0.0)) > 0.0) / len(picked)) if picked else 0.0
    out["phenomenon_label"] = frontier_label(out)
    return out


def summarize_rows(rows: Sequence[FrontierCandidateRow], *, prefix: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for metric in FRONTIER_METRICS:
        vals = [row_metric(r, metric) for r in rows]
        out[f"{prefix}_mean_{metric}"] = mean(vals)
        out[f"{prefix}_median_{metric}"] = quantile(vals, 0.50)
        out[f"{prefix}_p90_{metric}"] = quantile(vals, 0.90)
        out[f"{prefix}_max_{metric}"] = max(vals) if vals else 0.0
    # Collapse types as counts are often more legible than means.
    out[f"{prefix}_total_identity_melt_count"] = sum(int(r.metrics.get("identity_melt_count", 0)) for r in rows)
    out[f"{prefix}_total_affordance_corruption_count"] = sum(int(r.metrics.get("affordance_corruption_count", 0)) for r in rows)
    out[f"{prefix}_mean_frontier_quality"] = mean([r.frontier_quality for r in rows])
    return out


def row_metric(row: FrontierCandidateRow, metric: str) -> float:
    if metric == "readable_ontology_frontier":
        return float(row.readable_ontology_frontier)
    if metric == "score_total":
        return float(row.score_total)
    return float(row.metrics.get(metric, 0.0))


def hit_rate(rows: Sequence[FrontierCandidateRow], ontology: float, readability: float, repair: float) -> float:
    if not rows:
        return 0.0
    hits = 0
    for r in rows:
        m = r.metrics
        if (
            float(m.get("ontology_collapse_density", 0.0)) >= ontology
            and float(m.get("syntax_readability_proxy", 0.0)) >= readability
            and float(m.get("repair_pressure", 0.0)) <= repair
            and float(m.get("unfinished", 0.0)) <= 0.45
            and float(m.get("meta_leak", 0.0)) <= 0.01
        ):
            hits += 1
    return hits / len(rows)


def frontier_label(agg: Mapping[str, Any]) -> str:
    ont = float(agg.get("pool_mean_ontology_collapse_density", 0.0))
    read = float(agg.get("pool_mean_syntax_readability_proxy", 0.0))
    repair = float(agg.get("pool_mean_repair_pressure", 0.0))
    frontier = float(agg.get("pool_mean_readable_ontology_frontier", 0.0))
    hit = float(agg.get("pool_frontier_hit_rate", 0.0))
    unfinished = float(agg.get("pool_unfinished_rate", 0.0))
    if read < 0.52 or unfinished > 0.45:
        return "unreadable_or_truncated_pool"
    if frontier >= 0.11 and hit >= 0.20 and repair <= 0.35:
        return "readable_ontology_collapse_frontier"
    if ont < 0.18 and read > 0.65:
        return "readable_but_ontologically_stable_pool"
    if repair > 0.45:
        return "repair_dominated_pool"
    return "mixed_frontier_pool"


def compare_frontier_runs(runs: Sequence[FrontierRunAudit]) -> List[Dict[str, Any]]:
    if len(runs) < 2:
        return []
    base = runs[0]
    keys = (
        "pool_mean_readable_ontology_frontier",
        "pool_mean_ontology_collapse_density",
        "pool_mean_identity_melt_score",
        "pool_mean_affordance_corruption_score",
        "pool_mean_syntax_readability_proxy",
        "pool_mean_graph_integration",
        "pool_mean_repair_pressure",
        "pool_unfinished_rate",
        "picked_mean_readable_ontology_frontier",
        "picked_mean_ontology_collapse_density",
        "selection_lift_readable_ontology_frontier",
        "selection_lift_ontology_collapse_density",
    )
    comps: List[Dict[str, Any]] = []
    for other in runs[1:]:
        delta = {k: float(other.aggregate.get(k, 0.0)) - float(base.aggregate.get(k, 0.0)) for k in keys}
        comps.append(
            {
                "a": base.name,
                "b": other.name,
                "pool_shift_b_minus_a": delta,
                "interpretation": compare_interpretation(delta),
            }
        )
    return comps


def compare_interpretation(delta: Mapping[str, float]) -> str:
    ont = float(delta.get("pool_mean_ontology_collapse_density", 0.0))
    front = float(delta.get("pool_mean_readable_ontology_frontier", 0.0))
    read = float(delta.get("pool_mean_syntax_readability_proxy", 0.0))
    repair = float(delta.get("pool_mean_repair_pressure", 0.0))
    sel = float(delta.get("selection_lift_readable_ontology_frontier", 0.0))
    unfinished = float(delta.get("pool_unfinished_rate", 0.0))
    if front > 0.04 and ont > 0.07 and read > -0.12 and repair <= 0.10 and unfinished <= 0.20:
        return "candidate pool itself moved toward the readable ontology collapse frontier"
    if front <= 0.02 and sel > 0.05:
        return "selector lift dominates; candidate pool did not clearly shift"
    if ont > 0.07 and (read < -0.12 or unfinished > 0.20):
        return "ontology collapse increased, but the pool moved toward truncation/readability failure"
    if repair > 0.12:
        return "pool shift increased repair/explanation pressure"
    if front < -0.04:
        return "second pool moved away from the frontier"
    return "small or mixed frontier shift"


def compact_row(row: FrontierCandidateRow) -> Dict[str, Any]:
    m = row.metrics
    return {
        "run": row.run_name,
        "condition": row.condition,
        "step": row.step,
        "candidate_index": row.candidate_index,
        "picked": row.picked,
        "frontier": round(float(row.readable_ontology_frontier), 4),
        "ontology": round(float(m.get("ontology_collapse_density", 0.0)), 4),
        "readability": round(float(m.get("syntax_readability_proxy", 0.0)), 4),
        "graph_integration": round(float(m.get("graph_integration", 0.0)), 4),
        "repair": round(float(m.get("repair_pressure", 0.0)), 4),
        "unfinished": round(float(m.get("unfinished", 0.0)), 4),
        "identity_melt_events": m.get("identity_melt_events", [])[:3],
        "affordance_corruption_events": m.get("affordance_corruption_events", [])[:3],
        "text": row.text,
    }


def write_frontier_csv(report: FrontierAuditReport, path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "run_name",
        "condition",
        "path",
        "step",
        "candidate_index",
        "picked",
        "score_total",
        "readable_ontology_frontier",
        "frontier_quality",
        "ontology_collapse_density",
        "identity_melt_score",
        "affordance_corruption_score",
        "category_bleeding_score",
        "syntax_readability_proxy",
        "graph_integration",
        "graph_fragmentation",
        "repair_pressure",
        "atmospheric_conservation",
        "unfinished",
        "meta_leak",
        "identity_melt_count",
        "affordance_corruption_count",
        "text",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for run in report.runs:
            for row in run.rows:
                m = row.metrics
                w.writerow(
                    {
                        "run_name": row.run_name,
                        "condition": row.condition,
                        "path": row.path,
                        "step": row.step,
                        "candidate_index": row.candidate_index,
                        "picked": int(row.picked),
                        "score_total": row.score_total,
                        "readable_ontology_frontier": row.readable_ontology_frontier,
                        "frontier_quality": row.frontier_quality,
                        "ontology_collapse_density": m.get("ontology_collapse_density", 0.0),
                        "identity_melt_score": m.get("identity_melt_score", 0.0),
                        "affordance_corruption_score": m.get("affordance_corruption_score", 0.0),
                        "category_bleeding_score": m.get("category_bleeding_score", 0.0),
                        "syntax_readability_proxy": m.get("syntax_readability_proxy", 0.0),
                        "graph_integration": m.get("graph_integration", 0.0),
                        "graph_fragmentation": m.get("graph_fragmentation", 0.0),
                        "repair_pressure": m.get("repair_pressure", 0.0),
                        "atmospheric_conservation": m.get("atmospheric_conservation", 0.0),
                        "unfinished": m.get("unfinished", 0.0),
                        "meta_leak": m.get("meta_leak", 0.0),
                        "identity_melt_count": m.get("identity_melt_count", 0),
                        "affordance_corruption_count": m.get("affordance_corruption_count", 0),
                        "text": _csv_text(row.text),
                    }
                )


RATING_SHEET_FIELDS: Tuple[str, ...] = (
    "id",
    "kind",
    "run_name",
    "condition",
    "path",
    "step",
    "candidate_index",
    "picked",
    "readable_ontology_frontier",
    "frontier_quality",
    "ontology_collapse_density",
    "identity_melt_score",
    "affordance_corruption_score",
    "category_bleeding_score",
    "syntax_readability_proxy",
    "graph_integration",
    "repair_pressure",
    "unfinished",
    "meta_leak",
    "score_total",
    "human_score",
    "human_notes",
    "text",
)


def rating_sheet_rows(
    report: FrontierAuditReport,
    *,
    top_k: int = 3,
    include_picked: bool = True,
    include_top_frontier: bool = True,
) -> List[Dict[str, Any]]:
    """Return compact rows for human taste scoring.

    The sheet is intentionally redundant with machine metrics: the blank human
    columns are where the loop leaves heuristic discovery and returns to taste.
    """

    rows: List[Dict[str, Any]] = []
    seen: Dict[Tuple[str, str, int, int, str], int] = {}

    def add(row: FrontierCandidateRow, kind: str) -> None:
        key = (row.path, row.run_name, row.step, row.candidate_index, row.text)
        existing = seen.get(key)
        if existing is not None:
            kinds = set(str(rows[existing]["kind"]).split("+"))
            kinds.add(kind)
            rows[existing]["kind"] = "+".join(sorted(kinds))
            return
        m = row.metrics
        out = {
            "id": _rating_row_id(row, len(rows) + 1),
            "kind": kind,
            "run_name": row.run_name,
            "condition": row.condition,
            "path": row.path,
            "step": row.step,
            "candidate_index": row.candidate_index,
            "picked": int(row.picked),
            "readable_ontology_frontier": row.readable_ontology_frontier,
            "frontier_quality": row.frontier_quality,
            "ontology_collapse_density": m.get("ontology_collapse_density", 0.0),
            "identity_melt_score": m.get("identity_melt_score", 0.0),
            "affordance_corruption_score": m.get("affordance_corruption_score", 0.0),
            "category_bleeding_score": m.get("category_bleeding_score", 0.0),
            "syntax_readability_proxy": m.get("syntax_readability_proxy", 0.0),
            "graph_integration": m.get("graph_integration", 0.0),
            "repair_pressure": m.get("repair_pressure", 0.0),
            "unfinished": m.get("unfinished", 0.0),
            "meta_leak": m.get("meta_leak", 0.0),
            "score_total": row.score_total,
            "human_score": "",
            "human_notes": "",
            "text": _csv_text(row.text),
        }
        seen[key] = len(rows)
        rows.append(out)

    for run in report.runs:
        if include_picked:
            for row in sorted((r for r in run.rows if r.picked), key=lambda r: (r.step, r.candidate_index)):
                add(row, "picked")
        if include_top_frontier and top_k > 0:
            ranked = sorted(run.rows, key=lambda r: r.readable_ontology_frontier, reverse=True)
            for row in ranked[:top_k]:
                add(row, "top_frontier")
    return rows


def write_rating_sheet(rows: Sequence[Mapping[str, Any]], path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".jsonl":
        with out.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
        return
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(RATING_SHEET_FIELDS), lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({field: row.get(field, "") for field in RATING_SHEET_FIELDS})


def write_rating_markdown(rows: Sequence[Mapping[str, Any]], path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Human Rating Sheet",
        "",
        "Fill `human_score` and `human_notes` in the CSV/JSONL sheet. This Markdown view is for reading.",
        "",
    ]
    for i, row in enumerate(rows, 1):
        lines.extend(
            [
                f"## {i}. {row.get('id', '')}",
                "",
                (
                    f"kind={row.get('kind', '')} | condition={row.get('condition', '')} | "
                    f"step={row.get('step', '')} | candidate={row.get('candidate_index', '')} | "
                    f"picked={row.get('picked', '')}"
                ),
                (
                    f"frontier={float(row.get('readable_ontology_frontier') or 0.0):.3f} | "
                    f"ont={float(row.get('ontology_collapse_density') or 0.0):.3f} | "
                    f"read={float(row.get('syntax_readability_proxy') or 0.0):.3f} | "
                    f"repair={float(row.get('repair_pressure') or 0.0):.3f} | "
                    f"unfinished={float(row.get('unfinished') or 0.0):.3f}"
                ),
                "",
                "```text",
                str(row.get("text", "")),
                "```",
                "",
                "human_score:",
                "",
                "human_notes:",
                "",
            ]
        )
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _rating_row_id(row: FrontierCandidateRow, seq: int) -> str:
    base = f"{Path(row.path).stem or row.run_name}_s{row.step}_c{row.candidate_index}_{seq}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", base).strip("._") or f"rating_{seq}"


def _csv_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def write_frontier_plot(report: FrontierAuditReport, path: str) -> None:
    """Write one scatter plot: ontology collapse vs frontier quality.

    Small reports use a simple scatter.  Large sweeps are faceted by candidate
    count and token budget so run labels do not overwhelm the plot.
    """

    try:
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib.lines import Line2D  # type: ignore
    except Exception as e:  # pragma: no cover - optional dependency
        raise RuntimeError("--plot requires matplotlib") from e
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    parsed = [_plot_run_key(run) for run in report.runs]
    candidates = sorted({k[1] for k in parsed if k[1] is not None})
    tokens = sorted({k[2] for k in parsed if k[2] is not None})
    alphas = sorted({k[0] for k in parsed if k[0] is not None})
    can_facet = bool(
        candidates
        and tokens
        and alphas
        and len(report.runs) > 12
        and len(candidates) * len(tokens) <= 16
    )
    if can_facet:
        color_map = {alpha: plt.cm.viridis(i / max(len(alphas) - 1, 1)) for i, alpha in enumerate(alphas)}
        fig, axes = plt.subplots(
            len(candidates),
            len(tokens),
            figsize=(4.3 * len(tokens), 3.15 * len(candidates)),
            sharex=True,
            sharey=True,
            squeeze=False,
            constrained_layout=True,
        )
        for ax in axes.flat:
            ax.grid(True, color="#d8d8d8", linewidth=0.6, alpha=0.55)
            ax.set_xlim(-0.025, 1.025)
            ax.set_ylim(-0.025, 0.50)
        for run, key in zip(report.runs, parsed):
            alpha, candidate_count, max_tokens = key
            if alpha is None or candidate_count is None or max_tokens is None:
                continue
            row_idx = candidates.index(candidate_count)
            col_idx = tokens.index(max_tokens)
            ax = axes[row_idx][col_idx]
            color = color_map[alpha]
            xs = [float(r.metrics.get("ontology_collapse_density", 0.0)) for r in run.rows]
            ys = [float(r.frontier_quality) for r in run.rows]
            if not xs:
                continue
            ax.scatter(xs, ys, s=18, color=color, alpha=0.46, linewidths=0)
            px = [float(r.metrics.get("ontology_collapse_density", 0.0)) for r in run.rows if r.picked]
            py = [float(r.frontier_quality) for r in run.rows if r.picked]
            if px:
                ax.scatter(px, py, s=58, color=color, marker="x", linewidths=1.7, alpha=0.95)
        for i, candidate_count in enumerate(candidates):
            axes[i][0].set_ylabel(f"c={candidate_count}\nfrontier_quality")
        for j, max_tokens in enumerate(tokens):
            axes[-1][j].set_xlabel("ontology_collapse_density")
            axes[0][j].set_title(f"max_new_tokens={max_tokens}", fontsize=11)
        handles = [
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=color_map[a],
                markeredgewidth=0,
                markersize=7,
                label=f"alpha {a:g}",
            )
            for a in alphas
        ]
        handles.append(
            Line2D(
                [0],
                [0],
                marker="x",
                color="#222222",
                linestyle="none",
                markersize=8,
                label="picked",
            )
        )
        fig.suptitle("Readable Ontology Collapse Frontier", fontsize=15)
        fig.legend(handles=handles, loc="outside lower center", ncol=min(len(handles), 6), frameon=False)
        fig.savefig(out, dpi=170, bbox_inches="tight", pad_inches=0.22)
        plt.close(fig)
        return

    fig, ax = plt.subplots(figsize=(9.5, 6.2), constrained_layout=True)
    for run in report.runs:
        xs = [float(r.metrics.get("ontology_collapse_density", 0.0)) for r in run.rows]
        ys = [float(r.frontier_quality) for r in run.rows]
        if not xs:
            continue
        ax.scatter(xs, ys, label=run.name, alpha=0.78)
        px = [float(r.metrics.get("ontology_collapse_density", 0.0)) for r in run.rows if r.picked]
        py = [float(r.frontier_quality) for r in run.rows if r.picked]
        if px:
            ax.scatter(px, py, marker="x", label=f"{run.name} picked")
    ax.set_xlabel("ontology_collapse_density")
    ax.set_ylabel("frontier_quality = readability × integration × anti-repair")
    ax.set_title("Readable Ontology Collapse Frontier")
    ax.grid(True, color="#d8d8d8", linewidth=0.6, alpha=0.55)
    if any(run.rows for run in report.runs):
        ax.legend(fontsize=7, loc="center left", bbox_to_anchor=(1.02, 0.5))
    fig.savefig(out, dpi=160, bbox_inches="tight", pad_inches=0.16)
    plt.close(fig)


def _plot_run_key(run: FrontierRunAudit) -> Tuple[Optional[float], Optional[int], Optional[int]]:
    text = " ".join(part for part in (run.name, run.condition, Path(run.path).stem) if part)
    alpha_match = re.search(r"(?:selector|steer)_alpha_([^_\s]+)", text)
    candidate_match = re.search(r"_c(\d+)", text)
    token_match = re.search(r"_tok(\d+)", text)
    alpha = _parse_plot_float(alpha_match.group(1)) if alpha_match else None
    candidate_count = int(candidate_match.group(1)) if candidate_match else None
    max_tokens = int(token_match.group(1)) if token_match else None
    return alpha, candidate_count, max_tokens


def _parse_plot_float(label: str) -> Optional[float]:
    try:
        return float(label.replace("p", "."))
    except ValueError:
        return None


def format_frontier_report(report: FrontierAuditReport, *, top_k: int = 8) -> str:
    lines: List[str] = ["# Readable Ontology Collapse Frontier", ""]
    for run in report.runs:
        a = run.aggregate
        lines.append(f"## {run.name}")
        lines.append(
            " | ".join(
                [
                    f"condition={run.condition}",
                    f"label={a.get('phenomenon_label')}",
                    f"candidates={run.candidate_count}",
                    f"picked={run.picked_count}",
                    f"truncated_steps={run.truncated_steps}",
                ]
            )
        )
        lines.append(
            " | ".join(
                [
                    f"pool_frontier={a.get('pool_mean_readable_ontology_frontier', 0.0):.3f}",
                    f"pool_ont={a.get('pool_mean_ontology_collapse_density', 0.0):.3f}",
                    f"pool_read={a.get('pool_mean_syntax_readability_proxy', 0.0):.3f}",
                    f"pool_integr={a.get('pool_mean_graph_integration', 0.0):.3f}",
                    f"pool_repair={a.get('pool_mean_repair_pressure', 0.0):.3f}",
                    f"pool_unfinished={a.get('pool_unfinished_rate', 0.0):.3f}",
                    f"picked_frontier={a.get('picked_mean_readable_ontology_frontier', 0.0):.3f}",
                    f"selection_lift={a.get('selection_lift_readable_ontology_frontier', 0.0):+.3f}",
                ]
            )
        )
        if run.truncated_steps:
            lines.append("⚠ saved candidate pool appears truncated for at least one step; use --save-candidates >= --candidates for full pool geometry.")
        lines.append("")
    if report.comparisons:
        lines.append("## pool shifts")
        for comp in report.comparisons:
            delta = comp.get("pool_shift_b_minus_a", {})
            lines.append(f"### {comp.get('b')} - {comp.get('a')}")
            lines.append(str(comp.get("interpretation")))
            lines.append(
                " | ".join(
                    [
                        f"Δfrontier={float(delta.get('pool_mean_readable_ontology_frontier', 0.0)):+.3f}",
                        f"Δontology={float(delta.get('pool_mean_ontology_collapse_density', 0.0)):+.3f}",
                        f"Δidentity={float(delta.get('pool_mean_identity_melt_score', 0.0)):+.3f}",
                        f"Δread={float(delta.get('pool_mean_syntax_readability_proxy', 0.0)):+.3f}",
                        f"Δrepair={float(delta.get('pool_mean_repair_pressure', 0.0)):+.3f}",
                        f"Δunfinished={float(delta.get('pool_unfinished_rate', 0.0)):+.3f}",
                    ]
                )
            )
            lines.append("")
    if report.top_frontier_examples:
        lines.append("## top frontier examples")
        for ex in report.top_frontier_examples[:top_k]:
            lines.append(
                f"- {ex['run']} step {ex['step']} cand {ex['candidate_index']} "
                f"picked={ex['picked']} frontier={ex['frontier']:.3f} ont={ex['ontology']:.3f} read={ex['readability']:.3f}: "
                f"{truncate(ex['text'], 230)}"
            )
        lines.append("")
    if report.failure_examples:
        lines.append("## frontier failure examples")
        for ex in report.failure_examples[:top_k]:
            lines.append(
                f"- {ex['run']} step {ex['step']} cand {ex['candidate_index']} "
                f"picked={ex['picked']} ont={ex['ontology']:.3f} read={ex['readability']:.3f} repair={ex['repair']:.3f} unfinished={ex['unfinished']:.3f}: "
                f"{truncate(ex['text'], 230)}"
            )
        lines.append("")
    if report.notes:
        lines.append("## notes")
        lines.extend(f"- {n}" for n in report.notes)
    return "\n".join(lines).rstrip() + "\n"


def format_frontier_reading_report(report: FrontierAuditReport, *, top_k_per_run: int = 3) -> str:
    """Return a markdown report optimized for reading the generated prose."""

    lines: List[str] = [
        "# Frontier Sweep Texts",
        "",
        "Generated text is normalized for reading: model control tokens are stripped.",
        "",
        "## Index",
    ]
    for idx, run in enumerate(report.runs, 1):
        a = run.aggregate
        lines.append(
            "- "
            f"{idx}. {run.name} "
            f"(pool_frontier={a.get('pool_mean_readable_ontology_frontier', 0.0):.3f}, "
            f"picked_frontier={a.get('picked_mean_readable_ontology_frontier', 0.0):.3f}, "
            f"lift={a.get('selection_lift_readable_ontology_frontier', 0.0):+.3f})"
        )
    lines.append("")
    for idx, run in enumerate(report.runs, 1):
        a = run.aggregate
        picked_rows = sorted((r for r in run.rows if r.picked), key=lambda r: (r.step, r.candidate_index))
        top_rows = sorted(run.rows, key=lambda r: r.readable_ontology_frontier, reverse=True)[: max(0, top_k_per_run)]
        final_text = run.seed
        for row in picked_rows:
            final_text = join_like(final_text, row.text)

        lines.extend(
            [
                f"## {idx}. {run.name}",
                "",
                " | ".join(
                    [
                        f"condition={run.condition}",
                        f"candidates={run.candidate_count}",
                        f"picked={run.picked_count}",
                        f"pool_frontier={a.get('pool_mean_readable_ontology_frontier', 0.0):.3f}",
                        f"picked_frontier={a.get('picked_mean_readable_ontology_frontier', 0.0):.3f}",
                        f"lift={a.get('selection_lift_readable_ontology_frontier', 0.0):+.3f}",
                    ]
                ),
                "",
                "### Picked Final Text",
                "",
                "```text",
                final_text.strip(),
                "```",
                "",
            ]
        )
        if picked_rows:
            lines.extend(["### Picked Steps", ""])
            for row in picked_rows:
                lines.extend(
                    [
                        (
                            f"#### Step {row.step} candidate {row.candidate_index} "
                            f"(frontier={row.readable_ontology_frontier:.3f}, "
                            f"ont={float(row.metrics.get('ontology_collapse_density', 0.0)):.3f}, "
                            f"read={float(row.metrics.get('syntax_readability_proxy', 0.0)):.3f})"
                        ),
                        "",
                        "```text",
                        row.text.strip(),
                        "```",
                        "",
                    ]
                )
        if top_rows:
            lines.extend([f"### Top {len(top_rows)} Frontier Candidates", ""])
            for row in top_rows:
                picked_note = "picked" if row.picked else "not picked"
                lines.extend(
                    [
                        (
                            f"#### Step {row.step} candidate {row.candidate_index} ({picked_note}; "
                            f"frontier={row.readable_ontology_frontier:.3f}, "
                            f"ont={float(row.metrics.get('ontology_collapse_density', 0.0)):.3f}, "
                            f"read={float(row.metrics.get('syntax_readability_proxy', 0.0)):.3f})"
                        ),
                        "",
                        "```text",
                        row.text.strip(),
                        "```",
                        "",
                    ]
                )
    return "\n".join(lines).rstrip() + "\n"


def write_frontier_reading_report(
    report: FrontierAuditReport,
    path: str,
    *,
    top_k_per_run: int = 3,
) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(format_frontier_reading_report(report, top_k_per_run=top_k_per_run), encoding="utf-8")


def write_frontier_json(report: FrontierAuditReport, path: str, *, include_rows: bool = True) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(include_rows=include_rows), ensure_ascii=False, indent=2), encoding="utf-8")


def mean(vals: Sequence[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def quantile(vals: Sequence[float], q: float) -> float:
    if not vals:
        return 0.0
    xs = sorted(float(v) for v in vals)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * max(0.0, min(1.0, float(q)))
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def _condition_from_name(name: str) -> str:
    if ":" in name:
        return name.rsplit(":", 1)[-1]
    return ""


def truncate(text: str, n: int) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= n:
        return clean
    return clean[: max(0, n - 1)].rstrip() + "…"

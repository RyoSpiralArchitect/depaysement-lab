"""Post-hoc candidate-pool reselection.

This module reuses saved candidate pools without generating new text.  It is
therefore a selector laboratory, not a counterfactual trajectory simulator: by
default each step is rescored against the context that produced that step's
candidate pool.
"""

from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .frontier import clean_generated_text
from .ontology import join_like, load_run_records
from .proto_v2 import Candidate, DepaysementEngine, DummyGenerator, SelectorConfig, join_text
from .scorer_v07 import V07DepaysementScorer


@dataclass
class ReselectResult:
    name: str
    source_path: str
    source_name: str
    run: Dict[str, Any]
    changed_steps: int
    candidate_count: int
    notes: List[str] = field(default_factory=list)


@dataclass
class ReselectBatchResult:
    outputs: List[ReselectResult]
    paths: List[str]
    notes: List[str] = field(default_factory=list)


def posthoc_reselect_files(
    paths: Sequence[str],
    *,
    scorer: Optional[V07DepaysementScorer] = None,
    selector: Optional[SelectorConfig] = None,
    choose: str = "best",
    random_seed: int = 7,
    context_policy: str = "recorded",
) -> List[ReselectResult]:
    """Reselect saved run artifacts without new generation."""

    scorer = scorer or V07DepaysementScorer(lexicon_enabled=False, lexicon_prior_scale=0.0)
    selector = selector or SelectorConfig(objective="hybrid")
    results: List[ReselectResult] = []
    seen_names: Dict[str, int] = {}
    for path in paths:
        for source_name, run in load_run_records(path):
            base_name = f"{Path(source_name).stem}__{selector.objective}_{choose}"
            count = seen_names.get(base_name, 0)
            seen_names[base_name] = count + 1
            name = base_name if count == 0 else f"{base_name}_{count + 1}"
            results.append(
                posthoc_reselect_run(
                    run,
                    source_path=path,
                    source_name=source_name,
                    name=name,
                    scorer=scorer,
                    selector=selector,
                    choose=choose,
                    random_seed=random_seed,
                    context_policy=context_policy,
                )
            )
    return results


def posthoc_reselect_run(
    run: Mapping[str, Any],
    *,
    source_path: str = "",
    source_name: str = "run",
    name: str = "reselected_run",
    scorer: Optional[V07DepaysementScorer] = None,
    selector: Optional[SelectorConfig] = None,
    choose: str = "best",
    random_seed: int = 7,
    context_policy: str = "recorded",
) -> ReselectResult:
    """Return a new run dict with picked candidates replaced by selector choice."""

    if context_policy not in {"recorded", "reselected"}:
        raise ValueError("context_policy must be 'recorded' or 'reselected'")

    scorer = scorer or V07DepaysementScorer(lexicon_enabled=False, lexicon_prior_scale=0.0)
    selector = selector or SelectorConfig(objective="hybrid")
    rng = random.Random(random_seed)
    engine = DepaysementEngine(
        generator=DummyGenerator(rng),
        scorer=scorer,
        rng=rng,
        selector=selector,
    )

    seed = clean_generated_text(str(run.get("seed") or ""))
    original_recorded_context = seed
    reselected_context = seed
    new_steps: List[Dict[str, Any]] = []
    changed_steps = 0
    candidate_count = 0
    notes: List[str] = []

    for step_index, raw_step in enumerate(run.get("steps", []) or [], 1):
        if not isinstance(raw_step, Mapping):
            continue
        original_picked = raw_step.get("picked") if isinstance(raw_step.get("picked"), Mapping) else {}
        original_picked_text = clean_generated_text(str(original_picked.get("text") or raw_step.get("text") or ""))
        recorded_context = clean_generated_text(str(raw_step.get("context_before") or original_recorded_context))
        selector_context = recorded_context if context_policy == "recorded" else reselected_context
        raw_candidates = [c for c in list(raw_step.get("candidates", []) or []) if isinstance(c, Mapping)]
        if not raw_candidates and original_picked_text:
            raw_candidates = [original_picked]
            notes.append(f"{source_name} step {step_index}: no saved candidates; reusing picked text only")
        elif original_picked_text and not any(
            clean_generated_text(str(c.get("text") or "")) == original_picked_text for c in raw_candidates
        ):
            raw_candidates.append(original_picked)

        candidates = _candidate_objects(raw_candidates, scorer=scorer, context=selector_context)
        if not candidates:
            notes.append(f"{source_name} step {step_index}: no non-empty candidates")
            if original_picked_text:
                reselected_context = join_text(reselected_context, original_picked_text)
                original_recorded_context = join_like(original_recorded_context, original_picked_text)
            continue
        ranked = engine._rank_candidates_for_selection(candidates, context=selector_context)
        if selector.objective == "depaysement":
            for candidate in ranked:
                candidate.selector_score = float(candidate.score.total)
                candidate.selector_metrics = {
                    "objective": "depaysement",
                    "selector_score": float(candidate.score.total),
                    "depaysement_score": float(candidate.score.total),
                }
        for rank, candidate in enumerate(ranked, 1):
            candidate.selector_metrics["posthoc_rank"] = rank
            candidate.selector_metrics["posthoc_original_picked"] = candidate.text == original_picked_text

        picked = engine._pick(ranked, choose=choose, score_fn=engine._pick_score)
        if picked.text != original_picked_text:
            changed_steps += 1
        candidate_count += len(ranked)

        step = copy.deepcopy(dict(raw_step))
        step["context_before"] = selector_context
        step["posthoc_context_policy"] = context_policy
        step["posthoc_source_picked"] = dict(original_picked) if original_picked else {}
        step["picked"] = picked.to_dict()
        step["candidates"] = [c.to_dict() for c in ranked]
        new_steps.append(step)

        reselected_context = join_text(reselected_context, picked.text)
        if original_picked_text:
            original_recorded_context = join_like(original_recorded_context, original_picked_text)

    new_config = dict(run.get("config") if isinstance(run.get("config"), Mapping) else {})
    source_condition = str(new_config.get("condition") or Path(source_name).stem or source_name)
    new_config.update(
        {
            "condition": f"{source_condition}__reselect_{selector.objective}_{choose}",
            "posthoc_reselect": True,
            "posthoc_source_path": source_path,
            "posthoc_source_name": source_name,
            "posthoc_context_policy": context_policy,
            "choose": choose,
            "select_objective": selector.objective,
            "selector": selector.to_dict(),
        }
    )
    new_run: Dict[str, Any] = {
        "seed": seed,
        "final_text": reselected_context,
        "config": new_config,
        "steps": new_steps,
        "posthoc": {
            "source_path": source_path,
            "source_name": source_name,
            "context_policy": context_policy,
            "changed_steps": changed_steps,
            "candidate_count": candidate_count,
            "note": (
                "Post-hoc reselection reuses saved candidate pools. It does not regenerate downstream "
                "candidate pools after a changed pick."
            ),
        },
    }
    return ReselectResult(
        name=name,
        source_path=source_path,
        source_name=source_name,
        run=new_run,
        changed_steps=changed_steps,
        candidate_count=candidate_count,
        notes=notes,
    )


def write_posthoc_reselect_batch(results: Sequence[ReselectResult], out_dir: str) -> ReselectBatchResult:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: List[str] = []
    notes: List[str] = []
    for result in results:
        path = out / f"{safe_artifact_name(result.name)}.json"
        payload = dict(result.run)
        payload["posthoc"]["artifact_name"] = result.name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        paths.append(str(path))
        notes.extend(result.notes)
    return ReselectBatchResult(outputs=list(results), paths=paths, notes=notes)


def safe_artifact_name(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(name))
    return safe.strip("._") or "reselected_run"


def _candidate_objects(
    raw_candidates: Sequence[Mapping[str, Any]],
    *,
    scorer: V07DepaysementScorer,
    context: str,
) -> List[Candidate]:
    candidates: List[Candidate] = []
    seen = set()
    for raw in raw_candidates:
        text = clean_generated_text(str(raw.get("text") or ""))
        if not text.strip() or text in seen:
            continue
        seen.add(text)
        candidates.append(Candidate(text=text, score=scorer.score(text, context=context)))
    return candidates

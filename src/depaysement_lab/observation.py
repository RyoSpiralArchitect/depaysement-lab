from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import math
import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .proto_v2 import (
    BaseGenerator,
    Candidate,
    StepRecord,
    WriteRun,
    cleanup_continuation,
    join_text,
    normalize_text,
)
from .scorer_v07 import (
    DEFAULT_CONCEPT_FIELDS,
    V07DepaysementScorer,
    V07ScoreBreakdown,
    image_relation_graph,
)


# -----------------------------------------------------------------------------
# Plain baseline generation
# -----------------------------------------------------------------------------


def build_baseline_prompt(context: str) -> str:
    """Prompt for the ordinary-continuation control condition.

    This is deliberately not a depaysement prompt. It asks for a coherent next
    sentence and forbids assistant commentary, so the comparison is against the
    model's ordinary narrative/logical continuation rather than against a noisy
    free-generation baseline.
    """

    return (
        "Continue the fragment in English with a natural, coherent next sentence.\n"
        "Output only the continuation text. No Note:, no commentary, no labels, no analysis.\n"
        "Use one complete sentence, or two short complete sentences. Avoid unfinished endings.\n"
        f"Fragment:\n{context.strip()}\n"
        "Next sentence:\n"
    )


def run_baseline(
    *,
    generator: BaseGenerator,
    scorer: V07DepaysementScorer,
    seed: str,
    steps: int,
    temperature: float,
    top_p: float,
    max_new_tokens: int,
    trace: bool = False,
    include_prompt: bool = False,
) -> WriteRun:
    """Generate an ordinary baseline continuation, one candidate per step."""

    text = seed.strip()
    records: List[StepRecord] = []
    for step in range(1, steps + 1):
        prompt = build_baseline_prompt(text)
        raw = generator.generate(
            prompt,
            n=1,
            temperature=temperature,
            top_p=top_p,
            max_new_tokens=max_new_tokens,
        )
        cont = cleanup_continuation(raw[0] if raw else "")
        score = scorer.score(cont, context=text)
        picked = Candidate(cont, score)
        if trace:
            print(f"\n--- baseline step {step} ---")
            print(cont)
            print(score.compact())
        records.append(
            StepRecord(
                step=step,
                mode="baseline",
                motifs=(),
                picked=picked,
                candidates=[picked],
                prompt=prompt if include_prompt else "",
            )
        )
        text = join_text(text, cont)
    return WriteRun(
        seed=seed.strip(),
        final_text=text,
        steps=records,
        config={
            "condition": "baseline",
            "steps": steps,
            "temperature": temperature,
            "top_p": top_p,
            "max_new_tokens": max_new_tokens,
            "prompt_style": "ordinary_continuation",
        },
    )




def build_repair_prompt(context: str) -> str:
    """Prompt for a repair-inducing control condition.

    This condition deliberately asks the model to stabilize or explain strange
    details. It is useful as a contrast against depaysement selection, which
    should suppress repair pressure while keeping readability.
    """

    return (
        "Continue the fragment in English by making the scene feel narratively coherent.\n"
        "Stabilize the strange details if needed, but output only the continuation text. "
        "No Note:, no labels, no analysis. Use one or two complete sentences.\n"
        f"Fragment:\n{context.strip()}\n"
        "Next sentence:\n"
    )


def run_repair_control(
    *,
    generator: BaseGenerator,
    scorer: V07DepaysementScorer,
    seed: str,
    steps: int,
    temperature: float,
    top_p: float,
    max_new_tokens: int,
    trace: bool = False,
    include_prompt: bool = False,
) -> WriteRun:
    """Generate a repair-pressure control continuation."""

    text = seed.strip()
    records: List[StepRecord] = []
    for step in range(1, steps + 1):
        prompt = build_repair_prompt(text)
        raw = generator.generate(
            prompt,
            n=1,
            temperature=temperature,
            top_p=top_p,
            max_new_tokens=max_new_tokens,
        )
        cont = cleanup_continuation(raw[0] if raw else "")
        score = scorer.score(cont, context=text)
        picked = Candidate(cont, score)
        if trace:
            print(f"\n--- repair-control step {step} ---")
            print(cont)
            print(score.compact())
        records.append(
            StepRecord(
                step=step,
                mode="repair_control",
                motifs=(),
                picked=picked,
                candidates=[picked],
                prompt=prompt if include_prompt else "",
            )
        )
        text = join_text(text, cont)
    return WriteRun(
        seed=seed.strip(),
        final_text=text,
        steps=records,
        config={
            "condition": "repair_control",
            "steps": steps,
            "temperature": temperature,
            "top_p": top_p,
            "max_new_tokens": max_new_tokens,
            "prompt_style": "repair_inducing_continuation",
        },
    )


@contextlib.contextmanager
def steering_enabled(generator: BaseGenerator, enabled: bool):
    """Temporarily enable/disable HF or MLX steering without reloading weights.

    v0.8 observation often needs baseline and depaysement-rerank controls using
    the same loaded model object as the steered condition. HFGenerator and
    MLXLMGenerator both keep steering state in simple attributes, so alpha=0 is
    enough to turn injection off while preserving loaded vectors for the next run.
    """

    steering = getattr(generator, "steering", None)
    saved_alpha = None
    if steering is not None and hasattr(steering, "alpha"):
        saved_alpha = steering.alpha
        if not enabled:
            steering.alpha = 0.0
    try:
        yield generator
    finally:
        if steering is not None and saved_alpha is not None:
            steering.alpha = saved_alpha


# -----------------------------------------------------------------------------
# Vectorizers and distances
# -----------------------------------------------------------------------------


class TextVectorizer:
    mode = "none"

    def encode(self, texts: Sequence[str]) -> List[List[float]]:
        raise NotImplementedError

    def similarity(self, a: str, b: str) -> float:
        va, vb = self.encode([a, b])
        return cosine(va, vb)


class HashNgramVectorizer(TextVectorizer):
    """Dependency-free lexical vectorizer for diagnostics.

    This is not semantic embedding. It is a signed word/character n-gram sketch,
    kept so observe can run without external dependencies. The output payload
    names this mode `hash_ngram`, not `semantic`.
    """

    mode = "hash_ngram"

    def __init__(self, dim: int = 1024):
        self.dim = int(dim)

    def encode(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> List[float]:
        toks = [t.lower() for t in normalize_text(text).replace("'", " ").split() if t.strip()]
        feats: List[str] = []
        # word unigrams/bigrams plus character 3/4-grams provide some typo tolerance.
        feats.extend(f"w:{t}" for t in toks)
        feats.extend(f"wb:{toks[i]}_{toks[i+1]}" for i in range(max(0, len(toks) - 1)))
        low = normalize_text(text).lower()
        low = " ".join(low.split())
        for n in (3, 4):
            feats.extend(f"c{n}:{low[i:i+n]}" for i in range(max(0, len(low) - n + 1)))
        vec = [0.0] * self.dim
        for f in feats:
            h = hashlib.blake2b(f.encode("utf-8"), digest_size=8).digest()
            v = int.from_bytes(h, "little")
            idx = v % self.dim
            sign = 1.0 if ((v >> 11) & 1) else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


class SentenceTransformerVectorizer(TextVectorizer):
    mode = "sentence_transformer"

    def __init__(self, model_name: str, device: Optional[str] = None):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as e:  # pragma: no cover - optional dependency
            raise RuntimeError("--embed-model for observe requires: pip install sentence-transformers") from e
        self.model_name = model_name
        self.model = SentenceTransformer(model_name, device=device)

    def encode(self, texts: Sequence[str]) -> List[List[float]]:  # pragma: no cover - optional dependency
        arr = self.model.encode(list(texts), normalize_embeddings=True)
        return [[float(x) for x in row] for row in arr]


def make_vectorizer(embed_model: Optional[str] = None, device: Optional[str] = None, dim: int = 1024) -> TextVectorizer:
    if embed_model:
        return SentenceTransformerVectorizer(embed_model, device=device)
    return HashNgramVectorizer(dim=dim)


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    num = sum(a[i] * b[i] for i in range(n))
    da = math.sqrt(sum(a[i] * a[i] for i in range(n)))
    db = math.sqrt(sum(b[i] * b[i] for i in range(n)))
    return float(num / (da * db + 1e-12))


def js_divergence(p: Mapping[str, float], q: Mapping[str, float]) -> float:
    """Jensen-Shannon divergence in [0, 1] using log2."""

    keys = set(p) | set(q)
    if not keys:
        return 0.0
    pp = normalize_dist(p)
    qq = normalize_dist(q)
    m = {k: 0.5 * pp.get(k, 0.0) + 0.5 * qq.get(k, 0.0) for k in keys}
    return 0.5 * _kl(pp, m, keys) + 0.5 * _kl(qq, m, keys)


def _kl(p: Mapping[str, float], q: Mapping[str, float], keys: Iterable[str]) -> float:
    total = 0.0
    for k in keys:
        pk = float(p.get(k, 0.0))
        qk = float(q.get(k, 0.0))
        if pk > 0.0 and qk > 0.0:
            total += pk * math.log(pk / qk, 2)
    return total


def normalize_dist(d: Mapping[str, float]) -> Dict[str, float]:
    s = float(sum(max(0.0, v) for v in d.values()))
    if s <= 0.0:
        return {}
    return {k: max(0.0, float(v)) / s for k, v in d.items() if v > 0.0}


def concept_field_distribution(
    text: str,
    concept_fields: Mapping[str, Sequence[str]] = DEFAULT_CONCEPT_FIELDS,
) -> Dict[str, float]:
    """Lexicon-based concept-field distribution for audit, not scoring.

    v0.7 removed these fields from the default reward. v0.8 reuses them only as
    an interpretable diagnostic channel because the proposed observation asks for
    body/machine/bureaucracy/nature style field movement. Users can treat this as
    an authorial/lexical field audit rather than semantic truth.
    """

    low = f" {normalize_text(text).lower()} "
    counts: Counter[str] = Counter()
    for field_name, words in concept_fields.items():
        for word in words:
            w = str(word).lower().strip()
            if not w or len(w) < 3:
                continue
            # crude but safer than substring matching: split on non-letters/apostrophes.
            # Multi-word fields are rare in the built-in bank but still handled.
            pattern = " " + w + " "
            if pattern in low.replace("'", " "):
                counts[field_name] += 1
    return normalize_dist(counts)


# -----------------------------------------------------------------------------
# Observation metrics
# -----------------------------------------------------------------------------


@dataclass
class StepMetrics:
    step: int
    baseline_text: str
    variant_text: str
    vectorizer_mode: str
    field_mode: str
    semantic_continuity_baseline: float
    semantic_continuity_variant: float
    seed_similarity_baseline: float
    seed_similarity_variant: float
    baseline_variant_similarity: float
    coherence_loss: float
    concept_distance_from_baseline: float
    image_schema_gain: float
    relation_quantity_gain: float
    image_integration_gain: float
    ontology_leak_gain: float
    agency_inversion_gain: float
    graph_fragmentation_baseline: float
    graph_fragmentation_variant: float
    graph_fragmentation_delta: float
    semantic_collage_penalty_variant: float
    collapse_penalty_variant: float
    meta_leak_penalty_variant: float
    depaysement_lift: float
    baseline_graph: Dict[str, Any]
    variant_graph: Dict[str, Any]
    baseline_fields: Dict[str, float]
    variant_fields: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class ObservationResult:
    seed: str
    created_at: str
    config: Dict[str, Any]
    runs: Dict[str, Dict[str, Any]]
    comparisons: Dict[str, Dict[str, Any]]
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class DisplacementObserver:
    def __init__(
        self,
        *,
        scorer: V07DepaysementScorer,
        vectorizer: TextVectorizer,
        rng: random.Random,
        concept_fields: Mapping[str, Sequence[str]] = DEFAULT_CONCEPT_FIELDS,
        field_mode: str = "lexicon_audit",
    ):
        self.scorer = scorer
        self.vectorizer = vectorizer
        self.rng = rng
        self.concept_fields = concept_fields
        self.field_mode = field_mode

    def compare_runs(self, *, seed: str, baseline: WriteRun, variant: WriteRun) -> Dict[str, Any]:
        base_contexts = reconstruct_contexts(baseline)
        var_contexts = reconstruct_contexts(variant)
        step_metrics: List[StepMetrics] = []
        n = min(len(baseline.steps), len(variant.steps))
        for i in range(n):
            b_step = baseline.steps[i]
            v_step = variant.steps[i]
            b_text = b_step.picked.text
            v_text = v_step.picked.text
            b_context = base_contexts[i]
            v_context = var_contexts[i]
            b_score = ensure_score(self.scorer, b_step.picked.score, b_text, b_context)
            v_score = ensure_score(self.scorer, v_step.picked.score, v_text, v_context)
            metric = self.compare_texts(
                seed=seed,
                step=i + 1,
                baseline_context=b_context,
                variant_context=v_context,
                baseline_text=b_text,
                variant_text=v_text,
                baseline_score=b_score,
                variant_score=v_score,
            )
            step_metrics.append(metric)
        agg = aggregate_step_metrics(step_metrics)
        return {
            "variant": variant.config.get("condition", variant.config.get("mode", "variant")),
            "vectorizer_mode": self.vectorizer.mode,
            "field_mode": self.field_mode,
            "steps": [m.to_dict() for m in step_metrics],
            "aggregate": agg,
            "interpretation": interpret_aggregate(agg),
        }

    def compare_texts(
        self,
        *,
        seed: str,
        step: int,
        baseline_context: str,
        variant_context: str,
        baseline_text: str,
        variant_text: str,
        baseline_score: V07ScoreBreakdown,
        variant_score: V07ScoreBreakdown,
    ) -> StepMetrics:
        b_cont = self.vectorizer.similarity(baseline_context, baseline_text)
        v_cont = self.vectorizer.similarity(variant_context, variant_text)
        seed_b = self.vectorizer.similarity(seed, baseline_text)
        seed_v = self.vectorizer.similarity(seed, variant_text)
        b_v = self.vectorizer.similarity(baseline_text, variant_text)
        coherence_loss = max(0.0, b_cont - v_cont)

        b_fields = concept_field_distribution(baseline_text, self.concept_fields)
        v_fields = concept_field_distribution(variant_text, self.concept_fields)
        concept_distance = js_divergence(b_fields, v_fields)

        b_graph = image_relation_graph(baseline_text)
        v_graph = image_relation_graph(variant_text)
        b_frag = graph_fragmentation(b_graph)
        v_frag = graph_fragmentation(v_graph)
        frag_delta = max(0.0, v_frag - b_frag)

        image_schema_gain = variant_score.image_schema - baseline_score.image_schema
        rel_q_gain = variant_score.relation_quantity - baseline_score.relation_quantity
        integr_gain = variant_score.image_integration - baseline_score.image_integration
        leak_gain = variant_score.ontology_leak - baseline_score.ontology_leak
        agency_gain = variant_score.agency_inversion - baseline_score.agency_inversion
        sema_pen = max(0.0, -variant_score.anti_semantic_collage)
        collapse_pen = max(0.0, -variant_score.anti_collapse)
        meta_pen = max(0.0, -variant_score.anti_meta_leak)

        lift = (
            concept_distance
            + 0.55 * max(0.0, image_schema_gain)
            + 0.35 * max(0.0, rel_q_gain)
            + 0.70 * max(0.0, integr_gain)
            + 0.45 * max(0.0, leak_gain)
            + 0.35 * max(0.0, agency_gain)
            - 0.95 * coherence_loss
            - 0.70 * frag_delta
            - 0.55 * sema_pen
            - 0.65 * collapse_pen
            - 0.90 * meta_pen
        )

        return StepMetrics(
            step=step,
            baseline_text=baseline_text,
            variant_text=variant_text,
            vectorizer_mode=self.vectorizer.mode,
            field_mode=self.field_mode,
            semantic_continuity_baseline=b_cont,
            semantic_continuity_variant=v_cont,
            seed_similarity_baseline=seed_b,
            seed_similarity_variant=seed_v,
            baseline_variant_similarity=b_v,
            coherence_loss=coherence_loss,
            concept_distance_from_baseline=concept_distance,
            image_schema_gain=image_schema_gain,
            relation_quantity_gain=rel_q_gain,
            image_integration_gain=integr_gain,
            ontology_leak_gain=leak_gain,
            agency_inversion_gain=agency_gain,
            graph_fragmentation_baseline=b_frag,
            graph_fragmentation_variant=v_frag,
            graph_fragmentation_delta=frag_delta,
            semantic_collage_penalty_variant=sema_pen,
            collapse_penalty_variant=collapse_pen,
            meta_leak_penalty_variant=meta_pen,
            depaysement_lift=lift,
            baseline_graph=graph_dict(b_graph),
            variant_graph=graph_dict(v_graph),
            baseline_fields=b_fields,
            variant_fields=v_fields,
        )


def ensure_score(
    scorer: V07DepaysementScorer,
    score: Any,
    text: str,
    context: str,
) -> V07ScoreBreakdown:
    if isinstance(score, V07ScoreBreakdown):
        return score
    return scorer.score(text, context=context)


def reconstruct_contexts(run: WriteRun) -> List[str]:
    contexts = []
    text = run.seed
    for step in run.steps:
        contexts.append(text)
        text = join_text(text, step.picked.text)
    return contexts


def graph_fragmentation(graph) -> float:
    # 0 = well-integrated small staged image, 1 = sprawling loose object chain.
    weak_integration = 1.0 - graph.integration_score()
    return max(0.0, min(1.0, 0.55 * graph.cluster_sprawl_penalty() + 0.45 * weak_integration))


def graph_dict(graph) -> Dict[str, Any]:
    return {
        "object_count": graph.object_count,
        "relation_count": graph.relation_count,
        "component_count": graph.component_count,
        "giant_ratio": graph.giant_ratio,
        "relation_quantity": graph.relation_quantity_score(),
        "integration": graph.integration_score(),
        "cluster_sprawl": graph.cluster_sprawl_penalty(),
        "fragmentation": graph_fragmentation(graph),
        "objects": list(graph.object_terms),
        "edges": [list(e) for e in graph.edges],
        "components": [list(c) for c in graph.components],
    }


def aggregate_step_metrics(metrics: Sequence[StepMetrics]) -> Dict[str, Any]:
    if not metrics:
        return {}
    fields = [
        "semantic_continuity_baseline",
        "semantic_continuity_variant",
        "baseline_variant_similarity",
        "coherence_loss",
        "concept_distance_from_baseline",
        "image_schema_gain",
        "relation_quantity_gain",
        "image_integration_gain",
        "graph_fragmentation_delta",
        "semantic_collage_penalty_variant",
        "collapse_penalty_variant",
        "meta_leak_penalty_variant",
        "depaysement_lift",
    ]
    out: Dict[str, Any] = {"n_steps": len(metrics)}
    for f in fields:
        vals = [float(getattr(m, f)) for m in metrics]
        out[f"mean_{f}"] = sum(vals) / len(vals)
        out[f"max_{f}"] = max(vals)
    # A compact classifier for the target phenomenon.
    lift = out["mean_depaysement_lift"]
    continuity = out["mean_semantic_continuity_variant"]
    concept = out["mean_concept_distance_from_baseline"]
    frag = out["mean_graph_fragmentation_delta"]
    if lift > 0.35 and continuity > 0.08 and concept > 0.10 and frag < 0.38:
        label = "coherence_preserving_displacement"
    elif continuity <= 0.04 or out["mean_collapse_penalty_variant"] > 0.30:
        label = "coherence_collapse"
    elif concept <= 0.06:
        label = "too_close_to_baseline"
    elif frag >= 0.45 or out["mean_semantic_collage_penalty_variant"] > 0.45:
        label = "semantic_collage_or_sprawl"
    else:
        label = "mixed"
    out["phenomenon_label"] = label
    return out


def interpret_aggregate(agg: Mapping[str, Any]) -> str:
    label = agg.get("phenomenon_label", "mixed")
    if label == "coherence_preserving_displacement":
        return "concept field moved away from the ordinary baseline while continuity and relation integration stayed inside the window."
    if label == "coherence_collapse":
        return "the variant drifted too far from its context or collapsed into noisy generation."
    if label == "too_close_to_baseline":
        return "the variant remained too close to the ordinary continuation; displacement was weak."
    if label == "semantic_collage_or_sprawl":
        return "the variant displaced concepts but relation graph integration did not hold."
    return "mixed signal; inspect step-level metrics and candidate traces."


def run_to_observation_dict(
    run: WriteRun,
    *,
    condition: str,
    include_candidates: bool = True,
    include_prompt: bool = False,
) -> Dict[str, Any]:
    contexts = reconstruct_contexts(run)
    steps = []
    for ctx, step in zip(contexts, run.steps):
        step_dict = step.to_dict(include_candidates=include_candidates, include_prompt=include_prompt)
        step_dict["context_before"] = ctx
        step_dict["graph"] = graph_dict(image_relation_graph(step.picked.text))
        steps.append(step_dict)
    return {
        "condition": condition,
        "seed": run.seed,
        "final_text": run.final_text,
        "config": {**run.config, "condition": condition},
        "steps": steps,
    }


def write_observation_artifact(result: ObservationResult, path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = result.to_dict()
    if p.suffix.lower() == ".jsonl":
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    else:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def observation_summary_lines(result: ObservationResult) -> List[str]:
    lines: List[str] = []
    for name, comp in result.comparisons.items():
        agg = comp.get("aggregate", {})
        lines.append(
            f"{name}: lift={agg.get('mean_depaysement_lift', float('nan')):.3f} | "
            f"concept_dist={agg.get('mean_concept_distance_from_baseline', float('nan')):.3f} | "
            f"continuity={agg.get('mean_semantic_continuity_variant', float('nan')):.3f} | "
            f"frag_delta={agg.get('mean_graph_fragmentation_delta', float('nan')):.3f} | "
            f"label={agg.get('phenomenon_label', '-') }"
        )
    return lines

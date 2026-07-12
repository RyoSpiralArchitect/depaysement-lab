from __future__ import annotations

import argparse
import copy
import dataclasses
import json
import math
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .backends import (
    HTTPRetryConfig,
    MLXLMGenerator,
    OllamaGenerator,
    OpenAICompatGenerator,
    parse_jsonish,
)
from .mlx_intervention import MLXSteeringRuntimeConfig, collect_mlx_steering_vectors
from .model_policy import default_english_system_prompt, infer_model_policy
from .noun_graph import (
    AFFORDANCE_CLASS_ORDER,
    affordance_terms_for_classes,
    build_affordance_reroute_report,
    build_noun_graph_report,
    format_affordance_reroute_report,
    format_noun_graph_report,
    write_affordance_reroute_csv,
    write_affordance_reroute_json,
    write_noun_graph_json,
    write_noun_graph_nodes_csv,
)
from .ontology import audit_run_files, format_report
from .frontier import (
    audit_frontier_pool,
    audit_trajectory_runs,
    format_frontier_report,
    format_trajectory_report,
    rating_sheet_rows,
    write_rating_markdown,
    write_rating_sheet,
    write_frontier_csv,
    write_frontier_exemplar_store,
    write_frontier_json,
    write_frontier_plot,
    write_frontier_reading_report,
    write_trajectory_csv,
    write_trajectory_json,
)
from .observation import (
    DisplacementObserver,
    make_vectorizer,
    observation_summary_lines,
    run_baseline,
    run_repair_control,
    run_to_observation_dict,
    steering_enabled,
    write_observation_artifact,
    ObservationResult,
)
from .proto_v2 import (
    BankExpander,
    DepaysementEngine,
    DummyGenerator,
    HFGenerator,
    PromptBank,
    SELECT_OBJECTIVES,
    SelectorConfig,
    SteeringRuntimeConfig,
    collect_steering_vectors,
    parse_layer_list,
    print_intervention_sketch,
)
from .reselect import posthoc_reselect_files, write_posthoc_reselect_batch
from .ratings import (
    DEFAULT_RATING_METRICS,
    analyze_rating_rows,
    format_rating_analysis,
    load_rating_rows,
    merge_markdown_ratings,
    write_rating_rows,
)
from .resilience import (
    build_default_schedules,
    build_resilience_report,
    format_resilience_report,
    parse_schedule_specs,
    validate_paired_induction_prefixes,
    write_resilience_artifacts,
)
from .scorer_v07 import image_relation_graph, make_scorer_v07 as make_scorer


def resolve_model(args: argparse.Namespace) -> str:
    model = getattr(args, "model", None)
    if model:
        return model
    backend = getattr(args, "backend", "dummy")
    # English-first, instruction-tuned defaults. Users should still choose explicitly for real experiments.
    if backend == "mlx":
        return "mlx-community/Llama-3.2-3B-Instruct-4bit"
    if backend == "ollama":
        return "llama3.2"
    if backend in {"hf", "vllm", "openai-compatible"}:
        return "Qwen/Qwen2.5-3B-Instruct"
    return "dummy"


def resolve_system_prompt(args: argparse.Namespace) -> Optional[str]:
    raw = getattr(args, "system_prompt", None)
    if raw in {"none", "None", "NONE", "off", "OFF"}:
        return None
    if raw in {None, "auto"}:
        return default_english_system_prompt()
    return raw


def parse_ban_terms(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[,;\n]+", raw) if part.strip()]


def parse_affordance_classes(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[,;\n]+", raw) if part.strip()]


def selector_hard_ban_terms(args: argparse.Namespace) -> List[str]:
    terms = parse_ban_terms(getattr(args, "hard_ban_terms", None))
    class_terms = affordance_terms_for_classes(
        parse_affordance_classes(getattr(args, "hard_ban_affordance_classes", None))
    )
    out: List[str] = []
    seen: set[str] = set()
    for term in [*terms, *class_terms]:
        if term not in seen:
            seen.add(term)
            out.append(term)
    return out


def emit_model_policy(args: argparse.Namespace, *, stream=None) -> None:
    if stream is None:
        stream = sys.stderr
    backend = getattr(args, "backend", "dummy")
    if backend == "dummy":
        return
    model = resolve_model(args)
    policy = infer_model_policy(model)
    if policy.kind == "base":
        print(
            f"[model-policy] {model!r} looks like a base/pre-RLHF model. "
            "Treat it as a control; main depaysement steering is recommended on instruct/chat models.",
            file=stream,
        )
    elif policy.kind == "unknown":
        print(
            f"[model-policy] {model!r} has unknown tuning style. "
            "For the main experiment, prefer an instruct/chat model and use base models as controls.",
            file=stream,
        )


def _parse_float_sequence(raw: Optional[str]) -> List[float]:
    vals: List[float] = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        vals.append(float(part))
    return vals


def _effective_steer_alpha(args: argparse.Namespace) -> float:
    alpha = float(getattr(args, "steer_alpha", 0.0) or 0.0)
    schedule = _parse_float_sequence(getattr(args, "steer_schedule", None))
    if abs(alpha) <= 1e-12 and schedule:
        return max(schedule, key=lambda value: abs(float(value)))
    return alpha


def _active_steering_request(args: argparse.Namespace) -> bool:
    return (
        not bool(getattr(args, "disable_steering", False))
        and bool(getattr(args, "vectors", None))
        and abs(_effective_steer_alpha(args)) > 1e-12
    )


def _candidate_vector_paths(path: str, backend: str) -> List[Path]:
    p = Path(path)
    out = [p]
    if backend == "mlx" and p.suffix != ".npz":
        out.append(Path(str(p) + ".npz"))
    elif backend == "hf" and p.suffix not in {".pt", ".pth"}:
        out.append(Path(str(p) + ".pt"))
    # Avoid duplicates while preserving order.
    seen = set()
    unique: List[Path] = []
    for item in out:
        key = str(item)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _collect_vectors_hint(args: argparse.Namespace) -> str:
    backend = getattr(args, "backend", "dummy")
    model = resolve_model(args)
    if backend == "mlx":
        layers = getattr(args, "steer_layers", None) or "4-18"
        chat_flag = " --chat-template" if getattr(args, "chat_template", False) else ""
        return (
            "To enable MLX steering, collect vectors first, for example: "
            "mkdir -p experiments && "
            f"depaysement-lab collect-mlx-vectors --model {model} "
            "--bank data/depaysement_bank_en_v3.json "
            "--out experiments/depaysement_mlx_vectors.npz "
            f"--layers {layers}{chat_flag}"
        )
    if backend == "hf":
        layers = getattr(args, "steer_layers", None) or "4-18"
        return (
            "To enable HF steering, collect vectors first, for example: "
            "mkdir -p experiments && "
            f"depaysement-lab collect-vectors --model {model} "
            "--bank data/depaysement_bank_en_v3.json "
            "--out experiments/depaysement_vectors.pt "
            f"--layers {layers}"
        )
    return "Activation steering is currently implemented only for the hf and mlx backends."


def prepare_steering_args(args: argparse.Namespace, *, stream=None) -> argparse.Namespace:
    """Validate generation-time steering arguments and degrade gracefully.

    v0.8 loaded MLX vectors during generator construction, so ``observe`` failed
    before it could run the baseline/depaysement controls when a vector file was
    missing.  This preflight keeps steering strict only when explicitly requested:
    by default, a missing vector file disables the steered condition while letting
    the observer continue.
    """

    if getattr(args, "_steering_preflight_done", False):
        return args
    setattr(args, "_steering_preflight_done", True)
    setattr(args, "_steering_preflight_note", None)
    setattr(args, "_steering_preflight_usable", False)

    if not _active_steering_request(args):
        return args

    backend = getattr(args, "backend", "dummy")
    if backend not in {"hf", "mlx"}:
        note = (
            f"Activation steering is not available for backend={backend!r} through this adapter; "
            "steering was disabled and only baseline/rerank conditions will run. "
            + _collect_vectors_hint(args)
        )
        if getattr(args, "strict_steering", False):
            raise RuntimeError(note)
        args.vectors = None
        args.steer_alpha = 0.0
        setattr(args, "_steering_preflight_note", note)
        if stream is not None:
            print(f"[steering] {note}", file=stream)
        return args

    raw_path = str(getattr(args, "vectors"))
    for candidate in _candidate_vector_paths(raw_path, backend):
        if candidate.exists():
            args.vectors = str(candidate)
            setattr(args, "_steering_preflight_usable", True)
            return args

    tried = ", ".join(str(p) for p in _candidate_vector_paths(raw_path, backend))
    note = (
        f"Steering vector file not found: {raw_path} (tried: {tried}). "
        "Steering was disabled for this run, so the steered condition will be skipped. "
        + _collect_vectors_hint(args)
    )
    if getattr(args, "strict_steering", False):
        raise FileNotFoundError(note)
    args.vectors = None
    args.steer_alpha = 0.0
    setattr(args, "_steering_preflight_note", note)
    if stream is not None:
        print(f"[steering] {note}", file=stream)
    return args


def make_generator(args: argparse.Namespace, rng: random.Random):
    prepare_steering_args(args, stream=sys.stderr)
    retry = HTTPRetryConfig(retries=args.http_retries, timeout=args.http_timeout)
    model = resolve_model(args)
    system_prompt = resolve_system_prompt(args)
    if args.backend == "dummy":
        return DummyGenerator(rng)
    if args.backend == "hf":
        layers = parse_layer_list(getattr(args, "steer_layers", None))
        steering = SteeringRuntimeConfig(
            vectors_path=None if getattr(args, "disable_steering", False) else getattr(args, "vectors", None),
            alpha=0.0 if getattr(args, "disable_steering", False) or not getattr(args, "vectors", None) else _effective_steer_alpha(args),
            layers=layers,
            position=getattr(args, "steer_position", "last"),
        )
        return HFGenerator(model, device=args.device, steering=steering)
    if args.backend == "vllm":
        return OpenAICompatGenerator(
            model=model,
            base_url=args.base_url or "http://localhost:8000/v1",
            api_key=args.api_key or "EMPTY",
            system_prompt=system_prompt,
            extra_body=parse_jsonish(args.extra_body),
            retry=retry,
        )
    if args.backend == "openai-compatible":
        return OpenAICompatGenerator(
            model=model,
            base_url=args.base_url,
            api_key=args.api_key or "EMPTY",
            system_prompt=system_prompt,
            extra_body=parse_jsonish(args.extra_body),
            retry=retry,
        )
    if args.backend == "ollama":
        return OllamaGenerator(
            model=model,
            base_url=args.base_url or "http://localhost:11434",
            system_prompt=system_prompt,
            keep_alive=args.keep_alive,
            options=parse_jsonish(args.ollama_options),
            retry=retry,
        )
    if args.backend == "mlx":
        layers = parse_layer_list(getattr(args, "steer_layers", None))
        mlx_steering = MLXSteeringRuntimeConfig(
            vectors_path=None if getattr(args, "disable_steering", False) else getattr(args, "vectors", None),
            alpha=0.0 if getattr(args, "disable_steering", False) or not getattr(args, "vectors", None) else _effective_steer_alpha(args),
            layers=layers,
            position=getattr(args, "steer_position", "last"),
            apply_on=getattr(args, "mlx_steer_apply_on", "decode_only"),
        )
        return MLXLMGenerator(
            model_name=model,
            chat_template=args.chat_template,
            system_prompt=system_prompt,
            tokenizer_config=parse_jsonish(args.tokenizer_config),
            trust_remote_code=args.trust_remote_code,
            seed=args.random_seed,
            steering=mlx_steering,
        )
    raise ValueError(f"Unknown backend: {args.backend}")


def add_common_generation_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--backend", choices=["dummy", "hf", "vllm", "openai-compatible", "ollama", "mlx"], default="dummy")
    p.add_argument("--model", default=None, help="model id/name for selected backend; defaults to an instruction-tuned English-first preset per backend")
    p.add_argument("--device", default=None, help="HF only: cpu / cuda / auto(None)")
    p.add_argument("--bank", default=None, help="prompt bank JSON; defaults to built-in bank")
    p.add_argument("--lexicon", default=None, help="optional concept lexicon JSON")
    p.add_argument("--disable-lexicon", action="store_true")
    p.add_argument("--enable-lexicon", action="store_true", help="opt into concept lexicon priors; structural default keeps them off")
    p.add_argument("--lexicon-prior-scale", type=float, default=None, help="scale for optional lexical/aesthetic prior; structural default is 0")
    p.add_argument("--scorer-profile", choices=["structural", "aesthetic", "legacy"], default="structural", help="structural keeps vocabulary priors off by default")
    p.add_argument("--no-bank-score", action="store_true")
    p.add_argument("--bank-score-mode", choices=["auto", "off", "hash", "embed"], default="auto", help="auto uses embeddings only when --embed-model is provided; hash is lexical")
    p.add_argument("--bank-weight", type=float, default=None, help="override bank contrast weight; hash bank is lexical, embed bank is semantic")
    p.add_argument("--embed-model", default=None, help="optional HF encoder for semantic bank contrast")
    # HF / MLX activation steering
    p.add_argument("--vectors", default=None, help="steering vectors: .pt for HF, .npz for MLX")
    p.add_argument("--steer-alpha", type=float, default=0.0)
    p.add_argument("--disable-steering", action="store_true", help="ablation: keep same generation settings but do not inject vectors")
    p.add_argument("--strict-steering", action="store_true", help="fail if --vectors is requested but missing/unsupported; default is to skip the steered condition")
    p.add_argument("--steer-layers", default=None, help="comma/range list, e.g. 4,5,6 or 4-8")
    p.add_argument("--steer-position", choices=["last", "all"], default="last")
    p.add_argument(
        "--mlx-steer-apply-on",
        choices=["decode_only", "all", "prefill_only"],
        default="decode_only",
        help="MLX only: when to inject vectors during generation",
    )
    # HTTP backends
    p.add_argument("--base-url", default=None, help="vLLM/OpenAI-compatible/Ollama base URL")
    p.add_argument("--api-key", default=None, help="vLLM/OpenAI-compatible API key")
    p.add_argument("--system-prompt", default="auto", help="chat backends only: auto / none / custom system prompt")
    p.add_argument("--extra-body", default=None, help='JSON merged into OpenAI-compatible payload, e.g. \'{"top_k":50}\'')
    p.add_argument("--ollama-options", default=None, help="JSON merged into Ollama options")
    p.add_argument("--keep-alive", default=None, help="Ollama keep_alive, e.g. 10m")
    p.add_argument("--http-timeout", type=float, default=120.0)
    p.add_argument("--http-retries", type=int, default=2)
    # MLX
    p.add_argument("--chat-template", action="store_true", help="MLX only: apply tokenizer chat template")
    p.add_argument("--tokenizer-config", default=None, help="MLX only: JSON tokenizer_config")
    p.add_argument("--trust-remote-code", action="store_true", help="MLX tokenizer_config trust_remote_code")
    p.add_argument("--random-seed", type=int, default=7)
    p.add_argument("--ban-terms", default=None, help="comma/semicolon-separated words or phrases to forbid in depaysement prompts")


def add_selector_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--select-objective",
        choices=list(SELECT_OBJECTIVES),
        default="depaysement",
        help="candidate-pick objective: legacy score, readable frontier, banded frontier, weighted hybrid, or Pareto front",
    )
    p.add_argument("--frontier-weight", type=float, default=1.0, help="hybrid selector weight for readable ontology frontier")
    p.add_argument("--ontology-weight", type=float, default=0.35, help="hybrid selector weight for ontology collapse inside the target band")
    p.add_argument("--unfinished-weight", type=float, default=0.80, help="hybrid selector penalty for unfinished/truncated tails")
    p.add_argument("--repair-weight", type=float, default=0.60, help="hybrid selector penalty for repair/explanation pressure")
    p.add_argument("--repetition-weight", type=float, default=0.30, help="hybrid selector penalty for repetition loops")
    p.add_argument("--sprawl-weight", type=float, default=0.20, help="hybrid selector penalty for graph/sprawl fragmentation")
    p.add_argument("--semantic-loop-weight", type=float, default=0.0, help="optional selector penalty for semantic object/concept loops")
    p.add_argument("--lineage-diversity-weight", type=float, default=0.0, help="optional selector penalty when candidates do not introduce new content terms")
    p.add_argument("--lineage-diversity-min", type=float, default=0.25, help="minimum content-term novelty used by --lineage-diversity-weight")
    p.add_argument("--cliche-weight", type=float, default=0.0, help="optional selector penalty for generic magic-realist vocabulary attractors")
    p.add_argument("--soft-style-cliche-weight", type=float, default=0.0, help="optional selector penalty for soft style cliche diction such as ethereal/fog/mist")
    p.add_argument("--fantasy-prop-weight", type=float, default=0.0, help="optional selector penalty for stock antique/miniature/porcelain props")
    p.add_argument("--ordinary-anchor-weight", type=float, default=0.0, help="optional selector penalty when candidates drop mundane context anchors")
    p.add_argument("--ordinary-anchor-min", type=float, default=0.0, help="minimum ordinary-anchor retention when --ordinary-anchor-weight is used")
    p.add_argument("--ontology-min", type=float, default=0.20, help="frontier selector lower band for ontology collapse density")
    p.add_argument("--ontology-max", type=float, default=0.60, help="frontier selector upper band for ontology collapse density")
    p.add_argument("--selector-readability-min", type=float, default=0.55, help="frontier selector readability floor")
    p.add_argument("--selector-frontier-quality-min", type=float, default=0.20, help="frontier selector quality floor")
    p.add_argument("--selector-repair-max", type=float, default=0.45, help="frontier selector repair-pressure ceiling")
    p.add_argument("--selector-unfinished-max", type=float, default=0.50, help="frontier selector unfinished/truncation ceiling")
    p.add_argument("--hard-unfinished-max", type=float, default=-1.0, help="hard reject candidates above this unfinished score; negative disables the gate")
    p.add_argument("--hard-ban-terms", default=None, help="comma/semicolon-separated terms to hard-reject during candidate selection")
    p.add_argument(
        "--hard-ban-affordance-classes",
        default=None,
        help=(
            "comma/semicolon-separated affordance classes to expand into hard-ban terms; "
            f"known: {', '.join(AFFORDANCE_CLASS_ORDER)}"
        ),
    )


def add_trajectory_stop_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--trajectory-stop", action="store_true", help="stop a live run when the picked trajectory begins to decay")
    p.add_argument("--trajectory-min-steps", type=int, default=3, help="minimum steps before trajectory stopping can trigger")
    p.add_argument("--trajectory-frontier-drop", type=float, default=0.08, help="stop if frontier falls this far below the previous peak")
    p.add_argument("--trajectory-unfinished-stop-max", type=float, default=0.05, help="stop if picked unfinished exceeds this value")
    p.add_argument("--trajectory-repetition-stop-max", type=float, default=0.55, help="stop if picked repetition pressure exceeds this value")
    p.add_argument("--trajectory-sprawl-stop-max", type=float, default=0.65, help="stop if picked sprawl pressure exceeds this value")


def add_trajectory_steering_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--steer-schedule",
        default=None,
        help="comma-separated per-step steering alpha values; the last value repeats after the schedule ends",
    )
    p.add_argument("--adaptive-steering", action="store_true", help="adapt the next step's steering alpha from picked trajectory health")
    p.add_argument("--adaptive-steering-min-alpha", type=float, default=0.0)
    p.add_argument("--adaptive-steering-max-alpha", type=float, default=None)
    p.add_argument("--adaptive-steering-frontier-min", type=float, default=0.12)
    p.add_argument("--adaptive-steering-unfinished-max", type=float, default=0.05)
    p.add_argument("--adaptive-steering-loop-max", type=float, default=0.50)
    p.add_argument("--adaptive-steering-boost", type=float, default=0.08)
    p.add_argument("--adaptive-steering-dampen", type=float, default=0.12)


def add_scorer_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--bank", default=None)
    p.add_argument("--lexicon", default=None)
    p.add_argument("--disable-lexicon", action="store_true")
    p.add_argument("--enable-lexicon", action="store_true")
    p.add_argument("--lexicon-prior-scale", type=float, default=None)
    p.add_argument("--scorer-profile", choices=["structural", "aesthetic", "legacy"], default="structural")
    p.add_argument("--no-bank-score", action="store_true")
    p.add_argument("--bank-score-mode", choices=["auto", "off", "hash", "embed"], default="auto")
    p.add_argument("--bank-weight", type=float, default=None)
    p.add_argument("--embed-model", default=None)
    p.add_argument("--device", default=None)


def make_selector_config(args: argparse.Namespace) -> SelectorConfig:
    return SelectorConfig(
        objective=getattr(args, "select_objective", "depaysement"),
        frontier_weight=float(getattr(args, "frontier_weight", 1.0)),
        ontology_weight=float(getattr(args, "ontology_weight", 0.35)),
        unfinished_weight=float(getattr(args, "unfinished_weight", 0.80)),
        repair_weight=float(getattr(args, "repair_weight", 0.60)),
        repetition_weight=float(getattr(args, "repetition_weight", 0.30)),
        sprawl_weight=float(getattr(args, "sprawl_weight", 0.20)),
        semantic_loop_weight=float(getattr(args, "semantic_loop_weight", 0.0)),
        lineage_diversity_weight=float(getattr(args, "lineage_diversity_weight", 0.0)),
        lineage_diversity_min=float(getattr(args, "lineage_diversity_min", 0.25)),
        cliche_weight=float(getattr(args, "cliche_weight", 0.0)),
        soft_style_cliche_weight=float(getattr(args, "soft_style_cliche_weight", 0.0)),
        fantasy_prop_weight=float(getattr(args, "fantasy_prop_weight", 0.0)),
        ordinary_anchor_weight=float(getattr(args, "ordinary_anchor_weight", 0.0)),
        ordinary_anchor_min=float(getattr(args, "ordinary_anchor_min", 0.0)),
        ontology_min=float(getattr(args, "ontology_min", 0.20)),
        ontology_max=float(getattr(args, "ontology_max", 0.60)),
        readability_min=float(getattr(args, "selector_readability_min", 0.55)),
        frontier_quality_min=float(getattr(args, "selector_frontier_quality_min", 0.20)),
        repair_max=float(getattr(args, "selector_repair_max", 0.45)),
        unfinished_max=float(getattr(args, "selector_unfinished_max", 0.50)),
        hard_unfinished_max=float(getattr(args, "hard_unfinished_max", -1.0)),
        hard_ban_terms=tuple(selector_hard_ban_terms(args)),
    )


def trajectory_stop_kwargs(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "trajectory_stop": bool(getattr(args, "trajectory_stop", False)),
        "trajectory_min_steps": int(getattr(args, "trajectory_min_steps", 3)),
        "trajectory_frontier_drop": float(getattr(args, "trajectory_frontier_drop", 0.08)),
        "trajectory_unfinished_max": float(getattr(args, "trajectory_unfinished_stop_max", 0.05)),
        "trajectory_repetition_max": float(getattr(args, "trajectory_repetition_stop_max", 0.55)),
        "trajectory_sprawl_max": float(getattr(args, "trajectory_sprawl_stop_max", 0.65)),
    }


def trajectory_steering_kwargs(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "steer_schedule": _parse_float_sequence(getattr(args, "steer_schedule", None)),
        "adaptive_steering": bool(getattr(args, "adaptive_steering", False)),
        "adaptive_steering_min_alpha": float(getattr(args, "adaptive_steering_min_alpha", 0.0)),
        "adaptive_steering_max_alpha": getattr(args, "adaptive_steering_max_alpha", None),
        "adaptive_steering_frontier_min": float(getattr(args, "adaptive_steering_frontier_min", 0.12)),
        "adaptive_steering_unfinished_max": float(getattr(args, "adaptive_steering_unfinished_max", 0.05)),
        "adaptive_steering_loop_max": float(getattr(args, "adaptive_steering_loop_max", 0.50)),
        "adaptive_steering_boost": float(getattr(args, "adaptive_steering_boost", 0.08)),
        "adaptive_steering_dampen": float(getattr(args, "adaptive_steering_dampen", 0.12)),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Depaysement Lab multi-backend CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    w = sub.add_parser("write", help="multi-step depaysement / automatic writing")
    add_common_generation_args(w)
    add_selector_args(w)
    add_trajectory_stop_args(w)
    add_trajectory_steering_args(w)
    w.add_argument("--seed", default="A forgotten umbrella at the station")
    w.add_argument("--mode", choices=["depaysement", "automatic"], default="depaysement")
    w.add_argument("--steps", type=int, default=5)
    w.add_argument("--candidates", type=int, default=12)
    w.add_argument("--temperature", type=float, default=1.05)
    w.add_argument("--top-p", type=float, default=0.92)
    w.add_argument("--max-new-tokens", type=int, default=120)
    w.add_argument("--choose", choices=["best", "softmax", "random_top3"], default="softmax")
    w.add_argument("--motif-jitter", type=float, default=0.38)
    w.add_argument("--prompt-style", choices=["scene", "legacy"], default="scene", help="scene avoids theory/meta words in the prompt; legacy keeps the older explicit depaysement prompt")
    w.add_argument("--out", default=None, help="write run result to a file (.json, .jsonl, .txt, or use --out-format)")
    w.add_argument("--out-format", choices=["auto", "json", "jsonl", "txt"], default="auto")
    w.add_argument("--save-candidates", type=int, default=8, help="when --out is set, save top N scored candidates per step")
    w.add_argument("--include-prompt", action="store_true", help="include the exact prompts in JSON/JSONL output")
    w.add_argument("--trace", action="store_true")

    r = sub.add_parser("rank", help="rank candidates for one continuation step")
    add_common_generation_args(r)
    r.add_argument("--seed", default="A forgotten umbrella at the station")
    r.add_argument("--candidates", type=int, default=12)
    r.add_argument("--temperature", type=float, default=1.05)
    r.add_argument("--top-p", type=float, default=0.92)
    r.add_argument("--max-new-tokens", type=int, default=120)
    r.add_argument("--prompt-style", choices=["scene", "legacy"], default="scene")

    e = sub.add_parser("expand-bank", help="generate/rerank positive and negative prompt-bank examples")
    add_common_generation_args(e)
    e.add_argument("--out", required=True)
    e.add_argument("--positive", type=int, default=24)
    e.add_argument("--negative", type=int, default=16)
    e.add_argument("--temperature", type=float, default=1.12)
    e.add_argument("--top-p", type=float, default=0.94)
    e.add_argument("--max-new-tokens", type=int, default=80)
    e.add_argument("--trace", action="store_true")

    c = sub.add_parser("collect-vectors", help="HF only: collect layer-wise positive-negative activation steering vectors")
    c.add_argument("--model", required=True)
    c.add_argument("--bank", default=None)
    c.add_argument("--out", required=True)
    c.add_argument("--device", default=None)
    c.add_argument("--batch-size", type=int, default=4)
    c.add_argument("--layers", default=None)
    c.add_argument("--token-strategy", choices=["mean", "last"], default="mean")

    cm = sub.add_parser("collect-mlx-vectors", help="MLX only: collect layer-wise positive-negative activation steering vectors")
    cm.add_argument("--model", required=True)
    cm.add_argument("--bank", default=None)
    cm.add_argument("--out", required=True, help="output .npz path; .json metadata sidecar is also written")
    cm.add_argument("--layers", default=None, help="comma/range list, e.g. 4,5,6 or 4-8")
    cm.add_argument("--token-strategy", choices=["mean", "last"], default="mean")
    cm.add_argument("--chat-template", action="store_true")
    cm.add_argument("--tokenizer-config", default=None, help="MLX tokenizer_config JSON")
    cm.add_argument("--trust-remote-code", action="store_true")
    cm.add_argument("--max-length", type=int, default=None, help="optional left-truncation length for vector collection")
    cm.add_argument("--verbose", action="store_true")

    s = sub.add_parser("score", help="score a single fragment")
    s.add_argument("text", nargs="?", default="The umbrella becomes a small theater; rain's teeth sit in every seat.")
    s.add_argument("--context", default="")
    s.add_argument("--bank", default=None)
    s.add_argument("--lexicon", default=None)
    s.add_argument("--disable-lexicon", action="store_true")
    s.add_argument("--enable-lexicon", action="store_true")
    s.add_argument("--lexicon-prior-scale", type=float, default=None)
    s.add_argument("--scorer-profile", choices=["structural", "aesthetic", "legacy"], default="structural")
    s.add_argument("--no-bank-score", action="store_true")
    s.add_argument("--bank-score-mode", choices=["auto", "off", "hash", "embed"], default="auto")
    s.add_argument("--bank-weight", type=float, default=None)
    s.add_argument("--embed-model", default=None)
    s.add_argument("--device", default=None)
    s.add_argument("--json", action="store_true", help="print full score breakdown as JSON")
    s.add_argument("--graph", action="store_true", help="print relation graph diagnostic")

    ar = sub.add_parser("audit-run", help="rescore a saved --out run JSON with the current v0.7 structural scorer")
    ar.add_argument("run_json")
    ar.add_argument("--bank", default=None)
    ar.add_argument("--lexicon", default=None)
    ar.add_argument("--disable-lexicon", action="store_true")
    ar.add_argument("--enable-lexicon", action="store_true")
    ar.add_argument("--lexicon-prior-scale", type=float, default=None)
    ar.add_argument("--scorer-profile", choices=["structural", "aesthetic", "legacy"], default="structural")
    ar.add_argument("--no-bank-score", action="store_true")
    ar.add_argument("--bank-score-mode", choices=["auto", "off", "hash", "embed"], default="auto")
    ar.add_argument("--bank-weight", type=float, default=None)
    ar.add_argument("--embed-model", default=None)
    ar.add_argument("--device", default=None)
    ar.add_argument("--json", action="store_true")

    oa = sub.add_parser("ontology-audit", help="audit ontology collapse density, repair pressure, and readable-surreal frontier for run JSON/JSONL files")
    oa.add_argument("runs", nargs="+", help="one or more write/observe JSON or JSONL artifacts")
    oa.add_argument("--out", default=None, help="write report to .json or text/markdown file")
    oa.add_argument("--json", action="store_true", help="print JSON report")
    oa.add_argument("--show-events", action="store_true", help="include matched identity/affordance events in text report")
    oa.add_argument("--bank", default=None)
    oa.add_argument("--lexicon", default=None)
    oa.add_argument("--disable-lexicon", action="store_true")
    oa.add_argument("--enable-lexicon", action="store_true")
    oa.add_argument("--lexicon-prior-scale", type=float, default=None)
    oa.add_argument("--scorer-profile", choices=["structural", "aesthetic", "legacy"], default="structural")
    oa.add_argument("--no-bank-score", action="store_true")
    oa.add_argument("--bank-score-mode", choices=["auto", "off", "hash", "embed"], default="auto")
    oa.add_argument("--bank-weight", type=float, default=None)
    oa.add_argument("--embed-model", default=None)
    oa.add_argument("--device", default=None)

    ev = sub.add_parser("export-eval-set", help="export candidate texts from a run JSON/JSONL for human rating")
    ev.add_argument("run_file")
    ev.add_argument("--out", required=True)
    ev.add_argument("--top-k", type=int, default=3)

    ec = sub.add_parser("eval-correlate", help="compute Pearson/Spearman correlation between model_total and human_score in a JSONL eval file")
    ec.add_argument("ratings_jsonl")

    hr = sub.add_parser("export-rating-sheet", help="export picked and top-frontier candidates for human taste scoring")
    hr.add_argument("runs", nargs="+", help="saved run JSON/JSONL artifacts with candidates")
    hr.add_argument("--out", required=True, help="write .csv or .jsonl rating sheet")
    hr.add_argument("--markdown-out", default=None, help="optional Markdown reading view")
    hr.add_argument("--top-k", type=int, default=3, help="top frontier candidates per run to include")
    hr.add_argument("--no-picked", action="store_true", help="do not include picked candidates")
    hr.add_argument("--no-top-frontier", action="store_true", help="do not include top frontier candidates")
    hr.add_argument("--ontology-threshold", type=float, default=0.23)
    hr.add_argument("--readability-threshold", type=float, default=0.58)
    hr.add_argument("--repair-threshold", type=float, default=0.35)
    add_scorer_args(hr)

    ra = sub.add_parser("rating-analyze", help="analyze human_score correlations in a rating sheet")
    ra.add_argument("rating_sheet", help="CSV or JSONL rating sheet with human_score values")
    ra.add_argument("--markdown-ratings", default=None, help="merge scores/notes from a Markdown reading view")
    ra.add_argument("--update-sheet", action="store_true", help="write merged Markdown ratings back to rating_sheet")
    ra.add_argument("--out", default=None, help="write Markdown analysis report")
    ra.add_argument("--json-out", default=None, help="write JSON analysis report")
    ra.add_argument(
        "--metrics",
        default=",".join(DEFAULT_RATING_METRICS),
        help="comma-separated numeric metric columns to correlate with human_score",
    )

    ob = sub.add_parser("observe", help="run baseline vs depaysement rerank vs steering+rerank and measure coherence-preserving displacement")
    add_common_generation_args(ob)
    add_selector_args(ob)
    add_trajectory_steering_args(ob)
    ob.add_argument("--seed", default="A forgotten umbrella at the station")
    ob.add_argument("--steps", type=int, default=4)
    ob.add_argument("--candidates", type=int, default=8)
    ob.add_argument("--temperature", type=float, default=0.90, help="ordinary baseline temperature")
    ob.add_argument("--depaysement-temperature", type=float, default=1.05, help="rerank condition temperature")
    ob.add_argument("--include-repair-control", action="store_true", help="add a repair-inducing control condition that asks the model to stabilize/explain strange details")
    ob.add_argument("--repair-temperature", type=float, default=0.35, help="temperature for the repair-inducing control")
    ob.add_argument("--top-p", type=float, default=0.92)
    ob.add_argument("--max-new-tokens", type=int, default=120)
    ob.add_argument("--choose", choices=["best", "softmax", "random_top3"], default="softmax")
    ob.add_argument("--motif-jitter", type=float, default=0.38)
    ob.add_argument("--prompt-style", choices=["scene", "legacy"], default="scene")
    ob.add_argument("--skip-steered", action="store_true", help="only run baseline and external rerank")
    ob.add_argument("--out", default=None, help="write observation artifact (.json or .jsonl)")
    ob.add_argument("--save-candidates", type=int, default=999)
    ob.add_argument("--include-prompt", action="store_true")
    ob.add_argument("--trace", action="store_true")

    pa = sub.add_parser("pool-audit", help="audit saved candidate-pool geometry for the Readable Ontology Collapse Frontier")
    pa.add_argument("runs", nargs="+", help="write/observe JSON or JSONL artifacts with saved candidates")
    pa.add_argument("--out", default=None, help="write markdown/text report")
    pa.add_argument("--json-out", default=None, help="write full JSON report")
    pa.add_argument("--csv", default=None, help="write candidate-level CSV")
    pa.add_argument("--plot", default=None, help="write frontier scatter plot PNG; requires matplotlib")
    pa.add_argument("--texts-out", default=None, help="write markdown reading report with picked final texts and top frontier candidates")
    pa.add_argument("--exemplars-out", default=None, help="write markdown/json store of examples from the frontier-maximized band")
    pa.add_argument("--exemplars-json-out", default=None, help="optional JSON copy of the frontier exemplar store")
    pa.add_argument("--json", action="store_true", help="print full JSON report")
    pa.add_argument("--top-k", type=int, default=8)
    pa.add_argument("--ontology-threshold", type=float, default=0.23)
    pa.add_argument("--readability-threshold", type=float, default=0.58)
    pa.add_argument("--repair-threshold", type=float, default=0.35)
    pa.add_argument("--bank", default=None)
    pa.add_argument("--lexicon", default=None)
    pa.add_argument("--disable-lexicon", action="store_true")
    pa.add_argument("--enable-lexicon", action="store_true")
    pa.add_argument("--lexicon-prior-scale", type=float, default=None)
    pa.add_argument("--scorer-profile", choices=["structural", "aesthetic", "legacy"], default="structural")
    pa.add_argument("--no-bank-score", action="store_true")
    pa.add_argument("--bank-score-mode", choices=["auto", "off", "hash", "embed"], default="auto")
    pa.add_argument("--bank-weight", type=float, default=None)
    pa.add_argument("--embed-model", default=None)
    pa.add_argument("--device", default=None)

    ng = sub.add_parser("noun-graph", help="build a heuristic noun co-occurrence graph from frontier-band candidates")
    ng.add_argument("runs", nargs="+", help="write/observe/reselect JSON or JSONL artifacts with saved candidates")
    ng.add_argument("--out", default=None, help="write markdown noun graph report")
    ng.add_argument("--json-out", default=None, help="write structured noun graph JSON")
    ng.add_argument("--nodes-csv", default=None, help="write node-level centrality CSV")
    ng.add_argument("--top-k", type=int, default=24)
    ng.add_argument("--max-nodes", type=int, default=120)
    ng.add_argument("--frontier-band-ratio", type=float, default=0.60)
    ng.add_argument("--frontier-band-width", type=float, default=0.08)
    ng.add_argument("--no-dedupe-texts", action="store_true", help="keep duplicate candidate texts when building the graph")
    ng.add_argument("--ontology-threshold", type=float, default=0.23)
    ng.add_argument("--readability-threshold", type=float, default=0.58)
    ng.add_argument("--repair-threshold", type=float, default=0.35)
    ng.add_argument("--bank", default=None)
    ng.add_argument("--lexicon", default=None)
    ng.add_argument("--disable-lexicon", action="store_true")
    ng.add_argument("--enable-lexicon", action="store_true")
    ng.add_argument("--lexicon-prior-scale", type=float, default=None)
    ng.add_argument("--scorer-profile", choices=["structural", "aesthetic", "legacy"], default="structural")
    ng.add_argument("--no-bank-score", action="store_true")
    ng.add_argument("--bank-score-mode", choices=["auto", "off", "hash", "embed"], default="auto")
    ng.add_argument("--bank-weight", type=float, default=None)
    ng.add_argument("--embed-model", default=None)
    ng.add_argument("--device", default=None)

    ar = sub.add_parser("affordance-reroute", help="compare affordance-class rerouting between matched frontier artifacts")
    ar.add_argument("--base", nargs="+", required=True, help="baseline/control write JSON artifacts")
    ar.add_argument("--ablation", nargs="+", required=True, help="ablation/write JSON artifacts to compare against --base")
    ar.add_argument("--base-label", default="base")
    ar.add_argument("--ablation-label", default="ablation")
    ar.add_argument("--out", default=None, help="write markdown reroute matrix report")
    ar.add_argument("--json-out", default=None, help="write structured reroute matrix JSON")
    ar.add_argument("--csv", default=None, help="write condition/class reroute matrix CSV")
    ar.add_argument("--top-k", type=int, default=18)
    ar.add_argument("--frontier-band-ratio", type=float, default=0.60)
    ar.add_argument("--frontier-band-width", type=float, default=0.08)
    ar.add_argument("--no-dedupe-texts", action="store_true", help="keep duplicate candidate texts in class-rate denominators")
    ar.add_argument("--compliant-only", action="store_true", help="drop candidates marked hard_ban_failed before computing the matrix")
    ar.add_argument("--ontology-threshold", type=float, default=0.23)
    ar.add_argument("--readability-threshold", type=float, default=0.58)
    ar.add_argument("--repair-threshold", type=float, default=0.35)
    ar.add_argument("--bank", default=None)
    ar.add_argument("--lexicon", default=None)
    ar.add_argument("--disable-lexicon", action="store_true")
    ar.add_argument("--enable-lexicon", action="store_true")
    ar.add_argument("--lexicon-prior-scale", type=float, default=None)
    ar.add_argument("--scorer-profile", choices=["structural", "aesthetic", "legacy"], default="structural")
    ar.add_argument("--no-bank-score", action="store_true")
    ar.add_argument("--bank-score-mode", choices=["auto", "off", "hash", "embed"], default="auto")
    ar.add_argument("--bank-weight", type=float, default=None)
    ar.add_argument("--embed-model", default=None)
    ar.add_argument("--device", default=None)

    ta = sub.add_parser("trajectory-audit", help="audit picked trajectories without generating new text")
    ta.add_argument("runs", nargs="+", help="write/observe/reselect JSON or JSONL artifacts with picked steps")
    ta.add_argument("--out", default=None, help="write markdown/text report")
    ta.add_argument("--json-out", default=None, help="write full JSON report")
    ta.add_argument("--csv", default=None, help="write run-level trajectory CSV")
    ta.add_argument("--json", action="store_true", help="print full JSON report")
    ta.add_argument("--top-k", type=int, default=8)
    ta.add_argument("--bank", default=None)
    ta.add_argument("--lexicon", default=None)
    ta.add_argument("--disable-lexicon", action="store_true")
    ta.add_argument("--enable-lexicon", action="store_true")
    ta.add_argument("--lexicon-prior-scale", type=float, default=None)
    ta.add_argument("--scorer-profile", choices=["structural", "aesthetic", "legacy"], default="structural")
    ta.add_argument("--no-bank-score", action="store_true")
    ta.add_argument("--bank-score-mode", choices=["auto", "off", "hash", "embed"], default="auto")
    ta.add_argument("--bank-weight", type=float, default=None)
    ta.add_argument("--embed-model", default=None)
    ta.add_argument("--device", default=None)

    rs = sub.add_parser("reselect", help="post-hoc reselect saved candidate pools without new generation")
    add_selector_args(rs)
    add_scorer_args(rs)
    rs.add_argument("runs", nargs="+", help="saved write/observe/sweep JSON or JSONL artifacts with candidates")
    rs.add_argument("--out-dir", required=True)
    rs.add_argument(
        "--select-objectives",
        default=None,
        help="comma-separated selector objectives; overrides --select-objective, e.g. depaysement,frontier,hybrid,pareto",
    )
    rs.add_argument("--choose", choices=["best", "softmax", "random_top3"], default="best")
    rs.add_argument(
        "--context-policy",
        choices=["recorded", "reselected"],
        default="recorded",
        help="score each saved pool against its recorded context, or against the post-hoc reselected running context",
    )
    rs.add_argument("--include-original", action="store_true", help="include source runs in the comparison report")
    rs.add_argument("--random-seed", type=int, default=7)
    rs.add_argument("--top-k", type=int, default=12)
    rs.add_argument("--ontology-threshold", type=float, default=0.23)
    rs.add_argument("--readability-threshold", type=float, default=0.58)
    rs.add_argument("--repair-threshold", type=float, default=0.35)

    fs = sub.add_parser("frontier-sweep", help="run alpha/candidate/token sweeps and audit the readable ontology collapse frontier")
    add_common_generation_args(fs)
    add_selector_args(fs)
    add_trajectory_stop_args(fs)
    add_trajectory_steering_args(fs)
    fs.add_argument("--seed", default="A forgotten umbrella at the station")
    fs.add_argument("--seed-bank", default=None, help="optional JSON/TXT seed bank; JSON may be a list or contain a 'seeds' list")
    fs.add_argument("--seed-limit", type=int, default=0, help="limit loaded seed-bank entries; 0 means use all")
    fs.add_argument("--steps", type=int, default=4)
    fs.add_argument("--alphas", default="0,0.3,0.6,0.9", help="comma-separated steering alpha values")
    fs.add_argument("--candidate-grid", default="8,12", help="comma-separated candidate counts")
    fs.add_argument("--max-token-grid", default="120,160", help="comma-separated max_new_tokens values")
    fs.add_argument("--temperature", type=float, default=1.05)
    fs.add_argument("--top-p", type=float, default=0.92)
    fs.add_argument("--choose", choices=["best", "softmax", "random_top3"], default="softmax")
    fs.add_argument("--motif-jitter", type=float, default=0.38)
    fs.add_argument("--prompt-style", choices=["scene", "legacy"], default="scene")
    fs.add_argument("--out-dir", required=True)
    fs.add_argument("--save-candidates", type=int, default=0, help="0 means save the full candidate pool for each step")
    fs.add_argument("--resume", action="store_true", help="skip existing run JSONs in --out-dir and include them in the final audit")
    fs.add_argument("--run-limit", type=int, default=0, help="maximum new run JSONs to generate in this invocation; 0 means no limit")
    fs.add_argument("--include-baseline-control", action="store_true", help="also save ordinary baseline runs for each max-token setting")
    fs.add_argument("--include-prompt", action="store_true")
    fs.add_argument("--trace", action="store_true")

    resilience = sub.add_parser(
        "resilience-sweep",
        help="compare induce, release, reverse, and cycle steering schedules against a paired alpha-zero baseline",
    )
    add_common_generation_args(resilience)
    add_selector_args(resilience)
    resilience.add_argument("--seed", default="A forgotten umbrella at the station")
    resilience.add_argument("--seed-bank", default=None, help="optional JSON/TXT seed bank")
    resilience.add_argument("--seed-limit", type=int, default=0, help="limit seed-bank entries; 0 means all")
    resilience.add_argument("--steps", type=int, default=5)
    resilience.add_argument("--induction-steps", type=int, default=3)
    resilience.add_argument("--induce-alpha", type=float, default=0.60)
    resilience.add_argument(
        "--schedule",
        action="append",
        default=None,
        metavar="NAME=A,B,C",
        help="repeatable custom named schedule; supplying any replaces the five canonical schedules",
    )
    resilience.add_argument("--minimum-induction-gap", type=float, default=0.02)
    resilience.add_argument("--candidates", type=int, default=12)
    resilience.add_argument("--temperature", type=float, default=1.05)
    resilience.add_argument("--top-p", type=float, default=0.92)
    resilience.add_argument("--max-new-tokens", type=int, default=140)
    resilience.add_argument("--choose", choices=["best", "softmax", "random_top3"], default="best")
    resilience.add_argument("--motif-jitter", type=float, default=0.38)
    resilience.add_argument("--prompt-style", choices=["scene", "legacy"], default="scene")
    resilience.add_argument("--out-dir", required=True)
    resilience.add_argument("--save-candidates", type=int, default=0, help="0 saves each full candidate pool")
    resilience.add_argument("--resume", action="store_true", help="reuse existing condition/seed run JSONs")
    resilience.add_argument("--run-limit", type=int, default=0, help="maximum new runs; 0 means no limit")
    resilience.add_argument("--include-prompt", action="store_true")
    resilience.add_argument("--trace", action="store_true")
    resilience.set_defaults(select_objective="banded-frontier")

    b = sub.add_parser("show-bank", help="print or write the default/current prompt bank")
    b.add_argument("--bank", default=None)
    b.add_argument("--out", default=None)

    mc = sub.add_parser("model-check", help="classify a model name as instruct/base/unknown for this experiment")
    mc.add_argument("--model", default=None)
    mc.add_argument("--backend", choices=["hf", "vllm", "openai-compatible", "ollama", "mlx", "dummy"], default="hf")

    sub.add_parser("intervention-sketch", help="print internal-intervention sketch")
    return parser


def infer_out_format(path: str, requested: str) -> str:
    if requested != "auto":
        return requested
    suffix = Path(path).suffix.lower()
    if suffix == ".jsonl":
        return "jsonl"
    if suffix == ".json":
        return "json"
    return "txt"


def write_run_artifact(run, path: str, fmt: str = "auto", *, include_candidates: bool = True, include_prompt: bool = False) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    resolved = infer_out_format(path, fmt)
    payload = run.to_dict(include_candidates=include_candidates, include_prompt=include_prompt)
    payload["created_at"] = datetime.now(timezone.utc).isoformat()
    if resolved == "json":
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    elif resolved == "jsonl":
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    elif resolved == "txt":
        lines = [payload["final_text"], ""]
        for step in payload.get("steps", []):
            picked = step.get("picked", {})
            lines.append(f"--- step {step.get('step')} ---")
            lines.append(str(picked.get("text", "")))
            lines.append(str(picked.get("score_compact", "")))
            lines.append("")
        out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    else:
        raise ValueError(f"Unknown output format: {fmt}")


def cmd_write(args: argparse.Namespace) -> None:
    emit_model_policy(args)
    rng = random.Random(args.random_seed)
    generator = make_generator(args, rng)
    scorer = make_scorer(args)
    engine = DepaysementEngine(
        generator=generator,
        scorer=scorer,
        rng=rng,
        motif_jitter=args.motif_jitter,
        selector=make_selector_config(args),
    )
    run = engine.write_run(
        seed=args.seed,
        steps=args.steps,
        mode=args.mode,
        candidates_per_step=args.candidates,
        temperature=args.temperature,
        top_p=args.top_p,
        max_new_tokens=args.max_new_tokens,
        choose=args.choose,
        trace=args.trace,
        prompt_style=args.prompt_style,
        ban_terms=parse_ban_terms(args.ban_terms),
        keep_candidates=(args.save_candidates if args.out else 0),
        include_prompt=bool(args.include_prompt),
        **trajectory_stop_kwargs(args),
        **trajectory_steering_kwargs(args),
    )
    print("\n=== result ===")
    print(run.final_text)
    if args.out:
        write_run_artifact(run, args.out, args.out_format, include_candidates=args.save_candidates > 0, include_prompt=args.include_prompt)
        print(f"\n[written] {args.out}", file=sys.stderr)

def cmd_rank(args: argparse.Namespace) -> None:
    emit_model_policy(args)
    rng = random.Random(args.random_seed)
    generator = make_generator(args, rng)
    scorer = make_scorer(args)
    engine = DepaysementEngine(generator=generator, scorer=scorer, rng=rng)
    ranked = engine.rank(
        args.seed,
        n=args.candidates,
        temperature=args.temperature,
        top_p=args.top_p,
        max_new_tokens=args.max_new_tokens,
        prompt_style=args.prompt_style,
        ban_terms=parse_ban_terms(args.ban_terms),
    )
    for i, c in enumerate(ranked, 1):
        print(f"\n#{i} {c.score.compact()}\n{c.text}")


def cmd_expand_bank(args: argparse.Namespace) -> None:
    emit_model_policy(args)
    rng = random.Random(args.random_seed)
    bank = PromptBank.from_file(args.bank)
    generator = make_generator(args, rng)
    scorer = make_scorer(args)
    expander = BankExpander(generator, scorer, rng)
    result = expander.expand(bank, positive_n=args.positive, negative_n=args.negative, temperature=args.temperature, top_p=args.top_p, max_new_tokens=args.max_new_tokens)
    result.bank.write(args.out)
    print(f"Wrote prompt bank: {args.out}")
    print(f"positive_depaysement={len(result.bank.positive_depaysement)}")
    print(f"negative_realist_repair={len(result.bank.negative_realist_repair)}")
    print(f"negative_weird_noise={len(result.bank.negative_weird_noise)}")
    if args.trace:
        print("\nTop positive candidates:")
        for c in result.positive_ranked[:10]:
            print(f"- {c.text} :: {c.score.compact()}")
        print("\nTop negative candidates:")
        for n in result.negative_ranked[:10]:
            print(f"- {n}")


def cmd_collect_vectors(args: argparse.Namespace) -> None:
    bank = PromptBank.from_file(args.bank)
    layers = parse_layer_list(args.layers)
    collect_steering_vectors(
        model_name=args.model,
        bank=bank,
        out_path=args.out,
        device=args.device,
        batch_size=args.batch_size,
        layers=layers,
        token_strategy=args.token_strategy,
    )
    print(f"Wrote steering vectors: {args.out}")


def cmd_collect_mlx_vectors(args: argparse.Namespace) -> None:
    bank = PromptBank.from_file(args.bank)
    layers = parse_layer_list(args.layers)
    out = collect_mlx_steering_vectors(
        model_name=args.model,
        bank=bank,
        out_path=args.out,
        layers=layers,
        token_strategy=args.token_strategy,
        chat_template=args.chat_template,
        tokenizer_config=parse_jsonish(args.tokenizer_config),
        trust_remote_code=args.trust_remote_code,
        max_length=args.max_length,
        verbose=args.verbose,
    )
    print(f"Wrote MLX steering vectors: {out}")
    print(f"Wrote MLX steering metadata: {out}.json")
    print(f"Wrote MLX steering checksum: {out}.sha256")


def _pearson(xs: List[float], ys: List[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return float("nan")
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (denx * deny + 1e-12)


def _rankdata(xs: List[float]) -> List[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _read_run_records(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if p.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def cmd_audit_run(args: argparse.Namespace) -> None:
    scorer = make_scorer(args)
    rows = []
    for run_idx, run in enumerate(_read_run_records(args.run_json)):
        for step in run.get("steps", []):
            picked = step.get("picked", {})
            text = picked.get("text", "")
            context = step.get("context_before", "")
            score = scorer.score(text, context=context)
            rows.append({
                "run": run_idx,
                "step": step.get("step"),
                "text": text,
                "score": dataclasses.asdict(score),
                "compact": score.compact(),
            })
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for r in rows:
        print(f"\nrun={r['run']} step={r['step']} :: {r['compact']}\n{r['text']}")


def cmd_export_eval_set(args: argparse.Namespace) -> None:
    records = _read_run_records(args.run_file)
    out_rows = []
    for run_idx, run in enumerate(records):
        for step in run.get("steps", []):
            candidates = []
            if step.get("picked"):
                candidates.append(("picked", step["picked"]))
            for i, cand in enumerate(step.get("ranked_top", [])[: max(0, args.top_k)]):
                candidates.append((f"ranked_{i+1}", cand))
            for label, cand in candidates:
                score = cand.get("score", {})
                out_rows.append({
                    "id": f"run{run_idx}_step{step.get('step')}_{label}",
                    "run": run_idx,
                    "step": step.get("step"),
                    "kind": label,
                    "text": cand.get("text", ""),
                    "model_total": score.get("total"),
                    "human_score": None,
                    "human_notes": "",
                })
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote eval template: {out} ({len(out_rows)} rows)")


def cmd_eval_correlate(args: argparse.Namespace) -> None:
    rows = []
    for line in Path(args.ratings_jsonl).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("human_score") is None or row.get("model_total") is None:
            continue
        rows.append(row)
    xs = [float(r["model_total"]) for r in rows]
    ys = [float(r["human_score"]) for r in rows]
    result = {
        "n": len(rows),
        "pearson": _pearson(xs, ys),
        "spearman": _pearson(_rankdata(xs), _rankdata(ys)) if len(rows) >= 2 else float("nan"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_ontology_audit(args: argparse.Namespace) -> None:
    scorer = make_scorer(args)
    report = audit_run_files(args.runs, scorer=scorer)
    if args.json:
        payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    else:
        payload = format_report(report, show_events=args.show_events)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.suffix.lower() == ".json":
            out.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            out.write_text(payload, encoding="utf-8")
        print(f"Wrote ontology audit: {out}")
    else:
        print(payload)


def cmd_score(args: argparse.Namespace) -> None:
    scorer = make_scorer(args)
    score = scorer.score(args.text, context=args.context)
    if getattr(args, "json", False):
        print(json.dumps(dataclasses.asdict(score), ensure_ascii=False, indent=2))
        return
    print(score.compact())
    if getattr(args, "graph", False):
        graph = image_relation_graph(args.text)
        print(f"graph={graph.compact()}")
        print(json.dumps({
            "objects": graph.object_terms,
            "edges": graph.edges,
            "components": graph.components,
            "of_chain_count": graph.of_chain_count,
            "dangling_clause_count": graph.dangling_clause_count,
        }, ensure_ascii=False, indent=2))



def cmd_observe(args: argparse.Namespace) -> None:
    emit_model_policy(args)
    rng = random.Random(args.random_seed)
    generator = make_generator(args, rng)
    scorer = make_scorer(args)
    vectorizer = make_vectorizer(getattr(args, "embed_model", None), device=getattr(args, "device", None))
    observer = DisplacementObserver(scorer=scorer, vectorizer=vectorizer, rng=rng)

    # Use one loaded generator where possible. Steering is disabled for controls
    # and re-enabled only for the steering+rerank condition.
    with steering_enabled(generator, False):
        baseline_run = run_baseline(
            generator=generator,
            scorer=scorer,
            seed=args.seed,
            steps=args.steps,
            temperature=args.temperature,
            top_p=args.top_p,
            max_new_tokens=args.max_new_tokens,
            trace=args.trace,
            include_prompt=args.include_prompt,
        )
        dep_engine = DepaysementEngine(
            generator=generator,
            scorer=scorer,
            rng=rng,
            motif_jitter=args.motif_jitter,
            selector=make_selector_config(args),
        )
        dep_run = dep_engine.write_run(
            seed=args.seed,
            steps=args.steps,
            mode="depaysement",
            candidates_per_step=args.candidates,
            temperature=args.depaysement_temperature,
            top_p=args.top_p,
            max_new_tokens=args.max_new_tokens,
            choose=args.choose,
            trace=args.trace,
            prompt_style=args.prompt_style,
            keep_candidates=args.save_candidates,
            include_prompt=args.include_prompt,
        )
        dep_run.config["condition"] = "depaysement_rerank"
        repair_run = None
        if args.include_repair_control:
            repair_run = run_repair_control(
                generator=generator,
                scorer=scorer,
                seed=args.seed,
                steps=args.steps,
                temperature=args.repair_temperature,
                top_p=args.top_p,
                max_new_tokens=args.max_new_tokens,
                trace=args.trace,
                include_prompt=args.include_prompt,
            )

    runs = {
        "baseline": run_to_observation_dict(
            baseline_run,
            condition="baseline",
            include_candidates=True,
            include_prompt=args.include_prompt,
        ),
        "depaysement_rerank": run_to_observation_dict(
            dep_run,
            condition="depaysement_rerank",
            include_candidates=args.save_candidates > 0,
            include_prompt=args.include_prompt,
        ),
    }
    comparisons = {
        "depaysement_rerank_vs_baseline": observer.compare_runs(
            seed=args.seed,
            baseline=baseline_run,
            variant=dep_run,
        )
    }
    if repair_run is not None:
        runs["repair_control"] = run_to_observation_dict(
            repair_run,
            condition="repair_control",
            include_candidates=True,
            include_prompt=args.include_prompt,
        )
        comparisons["repair_control_vs_baseline"] = observer.compare_runs(
            seed=args.seed,
            baseline=baseline_run,
            variant=repair_run,
        )
    notes = [
        "Hash n-gram vectorizer is lexical, not semantic. Pass --embed-model with sentence-transformers for a semantic embedding channel.",
        "Concept-field distance is a diagnostic lexicon audit, not a reward term.",
    ]
    if getattr(args, "_steering_preflight_note", None):
        notes.append(str(getattr(args, "_steering_preflight_note")))

    steering_requested = (
        bool(getattr(args, "_steering_preflight_usable", False))
        and not bool(getattr(args, "disable_steering", False))
        and abs(_effective_steer_alpha(args)) > 1e-12
    )
    if not args.skip_steered and steering_requested:
        with steering_enabled(generator, True):
            st_engine = DepaysementEngine(
                generator=generator,
                scorer=scorer,
                rng=rng,
                motif_jitter=args.motif_jitter,
                selector=make_selector_config(args),
            )
            st_run = st_engine.write_run(
                seed=args.seed,
                steps=args.steps,
                mode="depaysement",
                candidates_per_step=args.candidates,
                temperature=args.depaysement_temperature,
                top_p=args.top_p,
                max_new_tokens=args.max_new_tokens,
                choose=args.choose,
                trace=args.trace,
                prompt_style=args.prompt_style,
                keep_candidates=args.save_candidates,
                include_prompt=args.include_prompt,
                **trajectory_steering_kwargs(args),
            )
            st_run.config["condition"] = "steering_plus_rerank"
        runs["steering_plus_rerank"] = run_to_observation_dict(
            st_run,
            condition="steering_plus_rerank",
            include_candidates=args.save_candidates > 0,
            include_prompt=args.include_prompt,
        )
        comparisons["steering_plus_rerank_vs_baseline"] = observer.compare_runs(
            seed=args.seed,
            baseline=baseline_run,
            variant=st_run,
        )
    elif not args.skip_steered:
        notes.append("Steered condition was skipped because --vectors and nonzero --steer-alpha were not provided, or steering was disabled.")

    result = ObservationResult(
        seed=args.seed,
        created_at=datetime.now(timezone.utc).isoformat(),
        config={
            "backend": args.backend,
            "model": resolve_model(args),
            "steps": args.steps,
            "candidates": args.candidates,
            "temperature": args.temperature,
            "depaysement_temperature": args.depaysement_temperature,
            "include_repair_control": bool(args.include_repair_control),
            "repair_temperature": args.repair_temperature,
            "top_p": args.top_p,
            "max_new_tokens": args.max_new_tokens,
            "choose": args.choose,
            "select_objective": args.select_objective,
            "selector": make_selector_config(args).to_dict(),
            "prompt_style": args.prompt_style,
            "vectorizer_mode": vectorizer.mode,
            "scorer_profile": getattr(args, "scorer_profile", "structural"),
            "bank_score_mode": getattr(args, "bank_score_mode", "auto"),
            "lexicon_prior_enabled": bool(getattr(scorer, "lexicon_enabled", False)),
            "steering_requested": steering_requested,
        },
        runs=runs,
        comparisons=comparisons,
        notes=notes,
    )

    print("\n=== observation summary ===")
    for line in observation_summary_lines(result):
        print(line)
    if args.out:
        write_observation_artifact(result, args.out)
        print(f"\n[written] {args.out}", file=sys.stderr)




def parse_float_grid(raw: str) -> List[float]:
    vals: List[float] = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        vals.append(float(part))
    return vals or [0.0]


def parse_int_grid(raw: str) -> List[int]:
    vals: List[int] = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        vals.append(int(part))
    return vals or [1]


def load_seed_bank(path: Optional[str], fallback_seed: str, *, limit: int = 0) -> List[str]:
    if not path:
        return [str(fallback_seed or "").strip()]
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    seeds: List[str]
    if p.suffix.lower() == ".json":
        data = json.loads(raw)
        if isinstance(data, list):
            seeds = [str(x).strip() for x in data]
        elif isinstance(data, dict):
            values = data.get("seeds")
            if values is None:
                values = data.get("mundane_seeds")
            if values is None:
                values = data.get("items")
            if values is None:
                values = []
                for item in data.values():
                    if isinstance(item, list):
                        values.extend(item)
            seeds = [str(x).strip() for x in values]
        else:
            raise ValueError(f"seed bank must be a JSON list or object: {path}")
    else:
        seeds = [line.strip() for line in raw.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    out: List[str] = []
    seen = set()
    for seed in seeds:
        if not seed or seed in seen:
            continue
        seen.add(seed)
        out.append(seed)
        if limit and len(out) >= int(limit):
            break
    if not out:
        raise ValueError(f"seed bank contained no usable seeds: {path}")
    return out


def parse_objective_grid(raw: Optional[str], fallback: str) -> List[str]:
    allowed = set(SELECT_OBJECTIVES)
    vals: List[str] = []
    for part in str(raw or fallback or "").split(","):
        value = part.strip()
        if not value:
            continue
        if value not in allowed:
            raise ValueError(f"unknown select objective: {value!r}")
        if value not in vals:
            vals.append(value)
    return vals or [fallback]


def safe_float_label(x: float) -> str:
    txt = f"{float(x):.3f}".rstrip("0").rstrip(".")
    return txt.replace("-", "neg").replace(".", "p") or "0"


def safe_seed_label(seed: str, idx: int) -> str:
    words = re.findall(r"[A-Za-z0-9]+", str(seed).lower())
    label = "_".join(words[:7]) or "seed"
    return f"seed{idx:02d}_{label[:72].strip('_')}"


def cmd_pool_audit(args: argparse.Namespace) -> None:
    scorer = make_scorer(args)
    report = audit_frontier_pool(
        args.runs,
        scorer=scorer,
        top_k=args.top_k,
        ontology_threshold=args.ontology_threshold,
        readability_threshold=args.readability_threshold,
        repair_threshold=args.repair_threshold,
    )
    if args.json_out:
        write_frontier_json(report, args.json_out, include_rows=True)
        print(f"Wrote frontier JSON: {args.json_out}", file=sys.stderr)
    if args.csv:
        write_frontier_csv(report, args.csv)
        print(f"Wrote frontier CSV: {args.csv}", file=sys.stderr)
    if args.plot:
        write_frontier_plot(report, args.plot)
        print(f"Wrote frontier plot: {args.plot}", file=sys.stderr)
    if args.texts_out:
        write_frontier_reading_report(report, args.texts_out)
        print(f"Wrote frontier reading report: {args.texts_out}", file=sys.stderr)
    if args.exemplars_out:
        write_frontier_exemplar_store(
            report,
            args.exemplars_out,
            json_path=args.exemplars_json_out,
            top_k=max(args.top_k, 1),
        )
        print(f"Wrote frontier exemplar store: {args.exemplars_out}", file=sys.stderr)
        if args.exemplars_json_out:
            print(f"Wrote frontier exemplar JSON: {args.exemplars_json_out}", file=sys.stderr)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(format_frontier_report(report, top_k=args.top_k), encoding="utf-8")
        print(f"Wrote frontier report: {args.out}", file=sys.stderr)
    if args.json and not args.out:
        print(json.dumps(report.to_dict(include_rows=True), ensure_ascii=False, indent=2))
    elif not args.out:
        print(format_frontier_report(report, top_k=args.top_k))


def cmd_trajectory_audit(args: argparse.Namespace) -> None:
    scorer = make_scorer(args)
    report = audit_trajectory_runs(args.runs, scorer=scorer, top_k=args.top_k)
    if args.json_out:
        write_trajectory_json(report, args.json_out, include_steps=True)
        print(f"Wrote trajectory JSON: {args.json_out}", file=sys.stderr)
    if args.csv:
        write_trajectory_csv(report, args.csv)
        print(f"Wrote trajectory CSV: {args.csv}", file=sys.stderr)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(format_trajectory_report(report, top_k=args.top_k), encoding="utf-8")
        print(f"Wrote trajectory report: {args.out}", file=sys.stderr)
    if args.json and not args.out:
        print(json.dumps(report.to_dict(include_steps=True), ensure_ascii=False, indent=2))
    elif not args.out:
        print(format_trajectory_report(report, top_k=args.top_k))


def cmd_noun_graph(args: argparse.Namespace) -> None:
    scorer = make_scorer(args)
    frontier_report = audit_frontier_pool(
        args.runs,
        scorer=scorer,
        top_k=max(args.top_k, 1),
        ontology_threshold=args.ontology_threshold,
        readability_threshold=args.readability_threshold,
        repair_threshold=args.repair_threshold,
    )
    report = build_noun_graph_report(
        frontier_report,
        top_k=max(args.top_k, 1),
        max_nodes=max(args.max_nodes, 1),
        frontier_band_ratio=args.frontier_band_ratio,
        frontier_band_width=args.frontier_band_width,
        dedupe_texts=not args.no_dedupe_texts,
    )
    if args.json_out:
        write_noun_graph_json(report, args.json_out)
        print(f"Wrote noun graph JSON: {args.json_out}", file=sys.stderr)
    if args.nodes_csv:
        write_noun_graph_nodes_csv(report, args.nodes_csv)
        print(f"Wrote noun graph nodes CSV: {args.nodes_csv}", file=sys.stderr)
    rendered = format_noun_graph_report(report, top_k=args.top_k)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
        print(f"Wrote noun graph report: {args.out}", file=sys.stderr)
    else:
        print(rendered)


def cmd_affordance_reroute(args: argparse.Namespace) -> None:
    scorer = make_scorer(args)
    base_frontier = audit_frontier_pool(
        args.base,
        scorer=scorer,
        top_k=max(args.top_k, 1),
        ontology_threshold=args.ontology_threshold,
        readability_threshold=args.readability_threshold,
        repair_threshold=args.repair_threshold,
    )
    ablation_frontier = audit_frontier_pool(
        args.ablation,
        scorer=scorer,
        top_k=max(args.top_k, 1),
        ontology_threshold=args.ontology_threshold,
        readability_threshold=args.readability_threshold,
        repair_threshold=args.repair_threshold,
    )
    report = build_affordance_reroute_report(
        base_frontier,
        ablation_frontier,
        base_label=args.base_label,
        ablation_label=args.ablation_label,
        frontier_band_ratio=args.frontier_band_ratio,
        frontier_band_width=args.frontier_band_width,
        dedupe_texts=not args.no_dedupe_texts,
        compliant_only=bool(args.compliant_only),
        top_k=max(args.top_k, 1),
    )
    if args.json_out:
        write_affordance_reroute_json(report, args.json_out)
        print(f"Wrote affordance reroute JSON: {args.json_out}", file=sys.stderr)
    if args.csv:
        write_affordance_reroute_csv(report, args.csv)
        print(f"Wrote affordance reroute CSV: {args.csv}", file=sys.stderr)
    rendered = format_affordance_reroute_report(report, top_k=args.top_k)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
        print(f"Wrote affordance reroute report: {args.out}", file=sys.stderr)
    else:
        print(rendered)


def cmd_export_rating_sheet(args: argparse.Namespace) -> None:
    scorer = make_scorer(args)
    report = audit_frontier_pool(
        args.runs,
        scorer=scorer,
        top_k=max(args.top_k, 1),
        ontology_threshold=args.ontology_threshold,
        readability_threshold=args.readability_threshold,
        repair_threshold=args.repair_threshold,
    )
    rows = rating_sheet_rows(
        report,
        top_k=args.top_k,
        include_picked=not args.no_picked,
        include_top_frontier=not args.no_top_frontier,
    )
    write_rating_sheet(rows, args.out)
    if args.markdown_out:
        write_rating_markdown(rows, args.markdown_out)
    print(f"Wrote rating sheet: {args.out} ({len(rows)} rows)")
    if args.markdown_out:
        print(f"Wrote rating reading view: {args.markdown_out}")


def cmd_rating_analyze(args: argparse.Namespace) -> None:
    rows, fieldnames = load_rating_rows(args.rating_sheet)
    merged_fields = 0
    if args.markdown_ratings:
        merged_fields = merge_markdown_ratings(rows, args.markdown_ratings)
        if args.update_sheet:
            write_rating_rows(args.rating_sheet, rows, fieldnames)
            print(f"Updated rating sheet: {args.rating_sheet} ({merged_fields} merged fields)")
    metrics = [m.strip() for m in str(args.metrics or "").split(",") if m.strip()]
    analysis = analyze_rating_rows(rows, metrics=metrics, source=args.rating_sheet)
    analysis["markdown_ratings"] = args.markdown_ratings
    analysis["merged_fields"] = merged_fields
    markdown = format_rating_analysis(analysis)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
        print(f"Wrote rating analysis: {out}")
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote rating analysis JSON: {out}")
    if not args.out and not args.json_out:
        print(markdown)


def cmd_reselect(args: argparse.Namespace) -> None:
    scorer = make_scorer(args)
    objectives = parse_objective_grid(args.select_objectives, args.select_objective)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    selector_configs: Dict[str, Any] = {}
    for objective in objectives:
        obj_args = copy.copy(args)
        obj_args.select_objective = objective
        selector = make_selector_config(obj_args)
        selector_configs[objective] = selector.to_dict()
        all_results.extend(
            posthoc_reselect_files(
                args.runs,
                scorer=scorer,
                selector=selector,
                choose=args.choose,
                random_seed=args.random_seed,
                context_policy=args.context_policy,
            )
        )

    batch = write_posthoc_reselect_batch(all_results, str(out_dir))
    audit_paths = list(args.runs) if args.include_original else []
    audit_paths.extend(batch.paths)
    report = audit_frontier_pool(
        audit_paths,
        scorer=scorer,
        top_k=args.top_k,
        ontology_threshold=args.ontology_threshold,
        readability_threshold=args.readability_threshold,
        repair_threshold=args.repair_threshold,
    )

    md_path = out_dir / "posthoc_reselect_report.md"
    json_path = out_dir / "posthoc_reselect_report.json"
    csv_path = out_dir / "posthoc_reselect_candidates.csv"
    plot_path = out_dir / "posthoc_reselect.png"
    texts_path = out_dir / "posthoc_reselect_texts.md"
    md_path.write_text(format_frontier_report(report, top_k=args.top_k), encoding="utf-8")
    write_frontier_json(report, str(json_path), include_rows=True)
    write_frontier_csv(report, str(csv_path))
    write_frontier_reading_report(report, str(texts_path))
    try:
        write_frontier_plot(report, str(plot_path))
    except RuntimeError as e:
        print(f"[reselect] plot skipped: {e}", file=sys.stderr)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_runs": list(args.runs),
        "output_runs": batch.paths,
        "objectives": objectives,
        "choose": args.choose,
        "context_policy": args.context_policy,
        "include_original": bool(args.include_original),
        "selector": selector_configs,
        "report_md": str(md_path),
        "report_json": str(json_path),
        "candidate_csv": str(csv_path),
        "plot": str(plot_path) if plot_path.exists() else None,
        "texts": str(texts_path),
        "notes": [
            "Post-hoc reselection reuses saved candidate pools and performs no new generation.",
            "With context-policy=recorded, each candidate is rescored against the context that produced its pool.",
            "With context-policy=reselected, downstream candidate pools are still the originally saved pools.",
            *batch.notes,
        ],
    }
    (out_dir / "posthoc_reselect_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(format_frontier_report(report, top_k=min(args.top_k, 8)))
    print(f"\n[reselect] wrote {out_dir}", file=sys.stderr)


def cmd_frontier_sweep(args: argparse.Namespace) -> None:
    emit_model_policy(args)
    alphas = parse_float_grid(args.alphas)
    steer_schedule = _parse_float_sequence(getattr(args, "steer_schedule", None))
    candidate_grid = parse_int_grid(args.candidate_grid)
    token_grid = parse_int_grid(args.max_token_grid)
    seeds = load_seed_bank(args.seed_bank, args.seed, limit=int(getattr(args, "seed_limit", 0) or 0))
    ban_terms = parse_ban_terms(args.ban_terms)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load the model once.  If vectors are available, initialize at max alpha so
    # the backend loads vector files; individual runs overwrite steering.alpha.
    gen_args = copy.copy(args)
    steering_alpha_values = [abs(float(a)) for a in alphas] + [abs(float(a)) for a in steer_schedule]
    max_alpha = max(steering_alpha_values) if steering_alpha_values else 0.0
    gen_args.steer_alpha = max_alpha
    if max_alpha <= 1e-12:
        gen_args.disable_steering = True
    # Reset preflight sentinels in case the caller object was reused.
    for name in ("_steering_preflight_done", "_steering_preflight_note", "_steering_preflight_usable"):
        if hasattr(gen_args, name):
            delattr(gen_args, name)
    rng = random.Random(args.random_seed)
    generator = make_generator(gen_args, rng)
    scorer = make_scorer(args)
    produced_paths: List[str] = []
    new_run_limit = max(0, int(getattr(args, "run_limit", 0) or 0))
    new_runs = 0
    stop_sweep = False
    total_runs = len(seeds) * len(token_grid) * len(candidate_grid) * len(alphas)
    if args.include_baseline_control:
        total_runs += len(seeds) * len(token_grid)

    for seed_idx, seed in enumerate(seeds, 1):
        if stop_sweep:
            break
        seed_label = safe_seed_label(seed, seed_idx)
        multi_seed_suffix = f"_{seed_label}" if len(seeds) > 1 else ""
        for max_tokens in token_grid:
            if stop_sweep:
                break
            if args.include_baseline_control:
                bpath = out_dir / f"baseline_tokens_{max_tokens}{multi_seed_suffix}.json"
                if args.resume and bpath.exists():
                    produced_paths.append(str(bpath))
                    print(f"[sweep] resume skip existing {bpath}", file=sys.stderr)
                else:
                    if new_run_limit and new_runs >= new_run_limit:
                        stop_sweep = True
                        break
                    print(
                        f"[sweep] running {len(produced_paths) + 1}/{total_runs}: "
                        f"baseline_tokens_{max_tokens}{multi_seed_suffix}",
                        file=sys.stderr,
                    )
                    with steering_enabled(generator, False):
                        baseline = run_baseline(
                            generator=generator,
                            scorer=scorer,
                            seed=seed,
                            steps=args.steps,
                            temperature=max(0.0, min(args.temperature, 0.90)),
                            top_p=args.top_p,
                            max_new_tokens=max_tokens,
                            trace=args.trace,
                            include_prompt=args.include_prompt,
                        )
                    baseline.config["condition"] = f"baseline_tokens_{max_tokens}"
                    baseline.config["seed_index"] = int(seed_idx)
                    baseline.config["seed_label"] = seed_label
                    write_run_artifact(baseline, str(bpath), "json", include_candidates=True, include_prompt=args.include_prompt)
                    produced_paths.append(str(bpath))
                    new_runs += 1
                    print(f"[sweep] wrote {bpath}", file=sys.stderr)

            for candidates in candidate_grid:
                if stop_sweep:
                    break
                for alpha in alphas:
                    steering_available = bool(getattr(gen_args, "_steering_preflight_usable", False))
                    trajectory_alpha_requested = any(abs(float(value)) > 1e-12 for value in steer_schedule)
                    steering_requested = (
                        (abs(float(alpha)) > 1e-12 or trajectory_alpha_requested)
                        and steering_available
                        and not bool(getattr(args, "disable_steering", False))
                    )
                    steering = getattr(generator, "steering", None)
                    if steering is not None and hasattr(steering, "alpha"):
                        steering.alpha = float(alpha) if steering_requested else 0.0
                    condition = (
                        f"steer_alpha_{safe_float_label(alpha)}"
                        if steering_requested
                        else f"selector_alpha_{safe_float_label(alpha)}"
                    )
                    if steer_schedule:
                        condition = f"{condition}_traj"
                    save_candidates = candidates if int(args.save_candidates) <= 0 else min(int(args.save_candidates), candidates)
                    path = out_dir / f"{condition}_c{candidates}_tok{max_tokens}{multi_seed_suffix}.json"
                    if args.resume and path.exists():
                        produced_paths.append(str(path))
                        print(f"[sweep] resume skip existing {path}", file=sys.stderr)
                        continue
                    if new_run_limit and new_runs >= new_run_limit:
                        stop_sweep = True
                        break
                    print(
                        f"[sweep] running {len(produced_paths) + 1}/{total_runs}: "
                        f"{condition}_c{candidates}_tok{max_tokens}{multi_seed_suffix}",
                        file=sys.stderr,
                    )
                    with steering_enabled(generator, steering_requested):
                        engine = DepaysementEngine(
                            generator=generator,
                            scorer=scorer,
                            rng=rng,
                            motif_jitter=args.motif_jitter,
                            selector=make_selector_config(args),
                        )
                        run = engine.write_run(
                            seed=seed,
                            steps=args.steps,
                            mode="depaysement",
                            candidates_per_step=candidates,
                            temperature=args.temperature,
                            top_p=args.top_p,
                            max_new_tokens=max_tokens,
                            choose=args.choose,
                            trace=args.trace,
                            prompt_style=args.prompt_style,
                            ban_terms=ban_terms,
                            keep_candidates=save_candidates,
                            include_prompt=args.include_prompt,
                            **trajectory_stop_kwargs(args),
                            **trajectory_steering_kwargs(args),
                        )
                    run.config["condition"] = condition
                    run.config["sweep_alpha"] = float(alpha)
                    run.config["sweep_steer_schedule"] = list(steer_schedule)
                    run.config["candidate_count"] = int(candidates)
                    run.config["max_new_tokens"] = int(max_tokens)
                    run.config["seed_index"] = int(seed_idx)
                    run.config["seed_label"] = seed_label
                    if abs(float(alpha)) > 1e-12 and not steering_requested:
                        run.config["steering_note"] = "alpha was requested but activation steering was unavailable or disabled"
                    write_run_artifact(run, str(path), "json", include_candidates=True, include_prompt=args.include_prompt)
                    produced_paths.append(str(path))
                    new_runs += 1
                    print(f"[sweep] wrote {path}", file=sys.stderr)

    if not produced_paths:
        raise SystemExit("[sweep] no run artifacts were produced or found; relax --run-limit or disable --resume")
    if stop_sweep:
        print(f"[sweep] run limit reached after {new_runs} new run(s)", file=sys.stderr)

    report = audit_frontier_pool(produced_paths, scorer=scorer, top_k=12)
    md_path = out_dir / "frontier_sweep_report.md"
    json_path = out_dir / "frontier_sweep_report.json"
    csv_path = out_dir / "frontier_sweep_candidates.csv"
    plot_path = out_dir / "frontier_sweep.png"
    texts_path = out_dir / "frontier_sweep_texts.md"
    exemplars_path = out_dir / "frontier_exemplars.md"
    exemplars_json_path = out_dir / "frontier_exemplars.json"
    md_path.write_text(format_frontier_report(report, top_k=12), encoding="utf-8")
    write_frontier_json(report, str(json_path), include_rows=True)
    write_frontier_csv(report, str(csv_path))
    write_frontier_reading_report(report, str(texts_path))
    write_frontier_exemplar_store(report, str(exemplars_path), json_path=str(exemplars_json_path), top_k=24)
    try:
        write_frontier_plot(report, str(plot_path))
    except RuntimeError as e:
        print(f"[sweep] plot skipped: {e}", file=sys.stderr)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed if not args.seed_bank else None,
        "seed_bank": args.seed_bank,
        "seeds": seeds,
        "backend": args.backend,
        "model": resolve_model(args),
        "alphas": alphas,
        "steer_schedule": list(steer_schedule),
        "adaptive_steering": bool(getattr(args, "adaptive_steering", False)),
        "candidate_grid": candidate_grid,
        "max_token_grid": token_grid,
        "select_objective": args.select_objective,
        "selector": make_selector_config(args).to_dict(),
        "ban_terms": list(ban_terms),
        "resume": bool(args.resume),
        "run_limit": int(new_run_limit),
        "new_runs": int(new_runs),
        "runs": produced_paths,
        "report_md": str(md_path),
        "report_json": str(json_path),
        "candidate_csv": str(csv_path),
        "plot": str(plot_path) if plot_path.exists() else None,
        "texts": str(texts_path),
        "frontier_exemplars": str(exemplars_path),
        "frontier_exemplars_json": str(exemplars_json_path),
        "notes": [getattr(gen_args, "_steering_preflight_note", None)],
    }
    (out_dir / "frontier_sweep_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(format_frontier_report(report, top_k=6))
    print(f"\n[frontier-sweep] wrote {out_dir}", file=sys.stderr)


def cmd_resilience_sweep(args: argparse.Namespace) -> None:
    emit_model_policy(args)
    if not 1 <= int(args.induction_steps) < int(args.steps):
        raise SystemExit("[resilience-sweep] --induction-steps must be between 1 and --steps - 1")
    schedules = (
        parse_schedule_specs(args.schedule, steps=args.steps)
        if args.schedule
        else build_default_schedules(
            steps=args.steps,
            induce_alpha=args.induce_alpha,
            induction_steps=args.induction_steps,
        )
    )
    if "baseline" not in schedules:
        raise SystemExit("[resilience-sweep] schedules must include an all-zero 'baseline' condition")
    if any(abs(float(value)) > 1e-12 for value in schedules["baseline"]):
        raise SystemExit("[resilience-sweep] the 'baseline' schedule must contain only zeros")
    seeds = load_seed_bank(args.seed_bank, args.seed, limit=int(args.seed_limit or 0))
    out_dir = Path(args.out_dir)
    runs_dir = out_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    ban_terms = parse_ban_terms(args.ban_terms)

    gen_args = copy.copy(args)
    max_alpha = max(abs(float(value)) for schedule in schedules.values() for value in schedule)
    gen_args.steer_alpha = max_alpha
    if max_alpha <= 1e-12:
        gen_args.disable_steering = True
    for name in ("_steering_preflight_done", "_steering_preflight_note", "_steering_preflight_usable"):
        if hasattr(gen_args, name):
            delattr(gen_args, name)
    generator = make_generator(gen_args, random.Random(args.random_seed))
    steering_available = bool(getattr(gen_args, "_steering_preflight_usable", False))
    if max_alpha > 1e-12 and (not steering_available or bool(args.disable_steering)):
        note = getattr(gen_args, "_steering_preflight_note", None) or "activation steering is unavailable"
        raise SystemExit(f"[resilience-sweep] nonzero schedules require usable steering vectors: {note}")

    scorer = make_scorer(args)
    selector = make_selector_config(args)
    produced_paths: List[str] = []
    run_limit = max(0, int(args.run_limit or 0))
    new_runs = 0
    total_runs = len(seeds) * len(schedules)
    stop = False
    rng_reset_supported: Optional[bool] = None

    for seed_idx, seed in enumerate(seeds, 1):
        if stop:
            break
        seed_label = safe_seed_label(seed, seed_idx)
        run_seed = int(args.random_seed) + seed_idx * 1009
        for condition, schedule in schedules.items():
            path = runs_dir / f"{condition}_{seed_label}.json"
            if args.resume and path.exists():
                existing = json.loads(path.read_text(encoding="utf-8"))
                existing_config = existing.get("config") if isinstance(existing.get("config"), dict) else {}
                existing_reset = bool(existing_config.get("generation_rng_reset", False))
                rng_reset_supported = (
                    existing_reset
                    if rng_reset_supported is None
                    else (rng_reset_supported and existing_reset)
                )
                produced_paths.append(str(path))
                print(f"[resilience] resume skip existing {path}", file=sys.stderr)
                continue
            if run_limit and new_runs >= run_limit:
                stop = True
                break
            print(
                f"[resilience] running {len(produced_paths) + 1}/{total_runs}: "
                f"{condition}/{seed_label} schedule={','.join(f'{value:g}' for value in schedule)}",
                file=sys.stderr,
            )
            reset_done = bool(generator.reset_seed(run_seed))
            rng_reset_supported = reset_done if rng_reset_supported is None else (rng_reset_supported and reset_done)
            engine = DepaysementEngine(
                generator=generator,
                scorer=scorer,
                rng=random.Random(run_seed),
                motif_jitter=args.motif_jitter,
                selector=selector,
            )
            save_candidates = args.candidates if int(args.save_candidates) <= 0 else min(int(args.save_candidates), args.candidates)
            steering_requested = any(abs(float(value)) > 1e-12 for value in schedule)
            with steering_enabled(generator, steering_requested):
                run = engine.write_run(
                    seed=seed,
                    steps=args.steps,
                    mode="depaysement",
                    candidates_per_step=args.candidates,
                    temperature=args.temperature,
                    top_p=args.top_p,
                    max_new_tokens=args.max_new_tokens,
                    choose=args.choose,
                    trace=args.trace,
                    prompt_style=args.prompt_style,
                    ban_terms=ban_terms,
                    keep_candidates=save_candidates,
                    include_prompt=args.include_prompt,
                    trajectory_stop=False,
                    steer_schedule=schedule,
                    adaptive_steering=False,
                )
            run.config.update(
                {
                    "condition": condition,
                    "resilience_schedule": list(schedule),
                    "resilience_induction_steps": int(args.induction_steps),
                    "candidate_count": int(args.candidates),
                    "max_new_tokens": int(args.max_new_tokens),
                    "seed_index": int(seed_idx),
                    "seed_label": seed_label,
                    "run_seed": int(run_seed),
                    "generation_rng_reset": bool(reset_done),
                }
            )
            write_run_artifact(
                run,
                str(path),
                "json",
                include_candidates=True,
                include_prompt=args.include_prompt,
            )
            produced_paths.append(str(path))
            new_runs += 1
            print(f"[resilience] wrote {path}", file=sys.stderr)

    if not produced_paths:
        raise SystemExit("[resilience-sweep] no run artifacts were produced or found")
    if stop:
        print(f"[resilience] run limit reached after {new_runs} new run(s)", file=sys.stderr)

    trajectory_report = audit_trajectory_runs(produced_paths, scorer=scorer, top_k=12)
    report = build_resilience_report(
        trajectory_report,
        schedules=schedules,
        induction_steps=args.induction_steps,
        minimum_induction_gap=args.minimum_induction_gap,
    )
    paired_validation = validate_paired_induction_prefixes(
        produced_paths,
        induction_steps=args.induction_steps,
    )
    report["paired_design_validation"] = paired_validation
    artifact_paths = write_resilience_artifacts(report, str(out_dir))
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backend": args.backend,
        "model": resolve_model(args),
        "seed": args.seed if not args.seed_bank else None,
        "seed_bank": args.seed_bank,
        "seeds": seeds,
        "schedules": schedules,
        "induction_steps": int(args.induction_steps),
        "minimum_induction_gap": float(args.minimum_induction_gap),
        "candidates": int(args.candidates),
        "max_new_tokens": int(args.max_new_tokens),
        "temperature": float(args.temperature),
        "top_p": float(args.top_p),
        "choose": args.choose,
        "selector": selector.to_dict(),
        "ban_terms": ban_terms,
        "paired_generation_rng_reset": bool(rng_reset_supported),
        "paired_design_validation": paired_validation,
        "resume": bool(args.resume),
        "run_limit": int(run_limit),
        "run_count": len(produced_paths),
        "new_runs": int(new_runs),
        "resumed_runs": len(produced_paths) - int(new_runs),
        "runs": produced_paths,
        **artifact_paths,
        "notes": [getattr(gen_args, "_steering_preflight_note", None)],
    }
    manifest_path = out_dir / "resilience_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(format_resilience_report(report))
    print(f"[resilience-sweep] wrote {out_dir}", file=sys.stderr)


def cmd_show_bank(args: argparse.Namespace) -> None:
    bank = PromptBank.from_file(args.bank)
    data = bank.to_dict()
    if args.out:
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote prompt bank: {args.out}")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_model_check(args: argparse.Namespace) -> None:
    model = resolve_model(args)
    policy = infer_model_policy(model)
    print(json.dumps(policy.as_dict(), ensure_ascii=False, indent=2))



def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "write":
        cmd_write(args)
    elif args.command == "rank":
        cmd_rank(args)
    elif args.command == "expand-bank":
        cmd_expand_bank(args)
    elif args.command == "collect-vectors":
        cmd_collect_vectors(args)
    elif args.command == "collect-mlx-vectors":
        cmd_collect_mlx_vectors(args)
    elif args.command == "score":
        cmd_score(args)
    elif args.command == "audit-run":
        cmd_audit_run(args)
    elif args.command == "ontology-audit":
        cmd_ontology_audit(args)
    elif args.command == "export-eval-set":
        cmd_export_eval_set(args)
    elif args.command == "eval-correlate":
        cmd_eval_correlate(args)
    elif args.command == "export-rating-sheet":
        cmd_export_rating_sheet(args)
    elif args.command == "rating-analyze":
        cmd_rating_analyze(args)
    elif args.command == "observe":
        cmd_observe(args)
    elif args.command == "pool-audit":
        cmd_pool_audit(args)
    elif args.command == "noun-graph":
        cmd_noun_graph(args)
    elif args.command == "affordance-reroute":
        cmd_affordance_reroute(args)
    elif args.command == "trajectory-audit":
        cmd_trajectory_audit(args)
    elif args.command == "reselect":
        cmd_reselect(args)
    elif args.command == "frontier-sweep":
        cmd_frontier_sweep(args)
    elif args.command == "resilience-sweep":
        cmd_resilience_sweep(args)
    elif args.command == "show-bank":
        cmd_show_bank(args)
    elif args.command == "model-check":
        cmd_model_check(args)
    elif args.command == "intervention-sketch":
        print_intervention_sketch()
    else:
        parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()

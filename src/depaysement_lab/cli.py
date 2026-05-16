from __future__ import annotations

import argparse
import copy
import dataclasses
import json
import math
import random
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
from .ontology import audit_run_files, format_report
from .frontier import (
    audit_frontier_pool,
    format_frontier_report,
    write_frontier_csv,
    write_frontier_json,
    write_frontier_plot,
    write_frontier_reading_report,
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
    SelectorConfig,
    SteeringRuntimeConfig,
    collect_steering_vectors,
    parse_layer_list,
    print_intervention_sketch,
)
from .reselect import posthoc_reselect_files, write_posthoc_reselect_batch
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


def _active_steering_request(args: argparse.Namespace) -> bool:
    return (
        not bool(getattr(args, "disable_steering", False))
        and bool(getattr(args, "vectors", None))
        and abs(float(getattr(args, "steer_alpha", 0.0) or 0.0)) > 1e-12
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
            alpha=0.0 if getattr(args, "disable_steering", False) else float(getattr(args, "steer_alpha", 0.0) or 0.0),
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
            alpha=0.0 if getattr(args, "disable_steering", False) else float(getattr(args, "steer_alpha", 0.0) or 0.0),
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


def add_selector_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--select-objective",
        choices=["depaysement", "frontier", "hybrid", "pareto"],
        default="depaysement",
        help="candidate-pick objective: legacy score, readable frontier, weighted hybrid, or Pareto front",
    )
    p.add_argument("--frontier-weight", type=float, default=1.0, help="hybrid selector weight for readable ontology frontier")
    p.add_argument("--ontology-weight", type=float, default=0.35, help="hybrid selector weight for ontology collapse inside the target band")
    p.add_argument("--unfinished-weight", type=float, default=0.80, help="hybrid selector penalty for unfinished/truncated tails")
    p.add_argument("--repair-weight", type=float, default=0.60, help="hybrid selector penalty for repair/explanation pressure")
    p.add_argument("--repetition-weight", type=float, default=0.30, help="hybrid selector penalty for repetition loops")
    p.add_argument("--sprawl-weight", type=float, default=0.20, help="hybrid selector penalty for graph/sprawl fragmentation")
    p.add_argument("--ontology-min", type=float, default=0.20, help="frontier selector lower band for ontology collapse density")
    p.add_argument("--ontology-max", type=float, default=0.60, help="frontier selector upper band for ontology collapse density")
    p.add_argument("--selector-readability-min", type=float, default=0.55, help="frontier selector readability floor")
    p.add_argument("--selector-frontier-quality-min", type=float, default=0.20, help="frontier selector quality floor")
    p.add_argument("--selector-repair-max", type=float, default=0.45, help="frontier selector repair-pressure ceiling")
    p.add_argument("--selector-unfinished-max", type=float, default=0.50, help="frontier selector unfinished/truncation ceiling")


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
        ontology_min=float(getattr(args, "ontology_min", 0.20)),
        ontology_max=float(getattr(args, "ontology_max", 0.60)),
        readability_min=float(getattr(args, "selector_readability_min", 0.55)),
        frontier_quality_min=float(getattr(args, "selector_frontier_quality_min", 0.20)),
        repair_max=float(getattr(args, "selector_repair_max", 0.45)),
        unfinished_max=float(getattr(args, "selector_unfinished_max", 0.50)),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Depaysement Lab multi-backend CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    w = sub.add_parser("write", help="multi-step depaysement / automatic writing")
    add_common_generation_args(w)
    add_selector_args(w)
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


    ob = sub.add_parser("observe", help="run baseline vs depaysement rerank vs steering+rerank and measure coherence-preserving displacement")
    add_common_generation_args(ob)
    add_selector_args(ob)
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
    fs.add_argument("--seed", default="A forgotten umbrella at the station")
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
    fs.add_argument("--include-baseline-control", action="store_true", help="also save ordinary baseline runs for each max-token setting")
    fs.add_argument("--include-prompt", action="store_true")
    fs.add_argument("--trace", action="store_true")

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
        keep_candidates=(args.save_candidates if args.out else 0),
        include_prompt=bool(args.include_prompt),
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
    ranked = engine.rank(args.seed, n=args.candidates, temperature=args.temperature, top_p=args.top_p, max_new_tokens=args.max_new_tokens, prompt_style=args.prompt_style)
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

    steering_requested = bool(getattr(args, "_steering_preflight_usable", False)) and not bool(getattr(args, "disable_steering", False)) and float(getattr(args, "steer_alpha", 0.0) or 0.0) != 0.0
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


def parse_objective_grid(raw: Optional[str], fallback: str) -> List[str]:
    allowed = {"depaysement", "frontier", "hybrid", "pareto"}
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
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(format_frontier_report(report, top_k=args.top_k), encoding="utf-8")
        print(f"Wrote frontier report: {args.out}", file=sys.stderr)
    if args.json and not args.out:
        print(json.dumps(report.to_dict(include_rows=True), ensure_ascii=False, indent=2))
    elif not args.out:
        print(format_frontier_report(report, top_k=args.top_k))


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
    candidate_grid = parse_int_grid(args.candidate_grid)
    token_grid = parse_int_grid(args.max_token_grid)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load the model once.  If vectors are available, initialize at max alpha so
    # the backend loads vector files; individual runs overwrite steering.alpha.
    gen_args = copy.copy(args)
    max_alpha = max(abs(a) for a in alphas) if alphas else 0.0
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

    for max_tokens in token_grid:
        if args.include_baseline_control:
            with steering_enabled(generator, False):
                baseline = run_baseline(
                    generator=generator,
                    scorer=scorer,
                    seed=args.seed,
                    steps=args.steps,
                    temperature=max(0.0, min(args.temperature, 0.90)),
                    top_p=args.top_p,
                    max_new_tokens=max_tokens,
                    trace=args.trace,
                    include_prompt=args.include_prompt,
                )
            baseline.config["condition"] = f"baseline_tokens_{max_tokens}"
            bpath = out_dir / f"baseline_tokens_{max_tokens}.json"
            write_run_artifact(baseline, str(bpath), "json", include_candidates=True, include_prompt=args.include_prompt)
            produced_paths.append(str(bpath))

        for candidates in candidate_grid:
            for alpha in alphas:
                steering_available = bool(getattr(gen_args, "_steering_preflight_usable", False))
                steering_requested = abs(float(alpha)) > 1e-12 and steering_available and not bool(getattr(args, "disable_steering", False))
                steering = getattr(generator, "steering", None)
                if steering is not None and hasattr(steering, "alpha"):
                    steering.alpha = float(alpha) if steering_requested else 0.0
                condition = (
                    f"steer_alpha_{safe_float_label(alpha)}"
                    if steering_requested
                    else f"selector_alpha_{safe_float_label(alpha)}"
                )
                save_candidates = candidates if int(args.save_candidates) <= 0 else min(int(args.save_candidates), candidates)
                with steering_enabled(generator, steering_requested):
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
                        mode="depaysement",
                        candidates_per_step=candidates,
                        temperature=args.temperature,
                        top_p=args.top_p,
                        max_new_tokens=max_tokens,
                        choose=args.choose,
                        trace=args.trace,
                        prompt_style=args.prompt_style,
                        keep_candidates=save_candidates,
                        include_prompt=args.include_prompt,
                    )
                run.config["condition"] = condition
                run.config["sweep_alpha"] = float(alpha)
                run.config["candidate_count"] = int(candidates)
                run.config["max_new_tokens"] = int(max_tokens)
                if abs(float(alpha)) > 1e-12 and not steering_requested:
                    run.config["steering_note"] = "alpha was requested but activation steering was unavailable or disabled"
                path = out_dir / f"{condition}_c{candidates}_tok{max_tokens}.json"
                write_run_artifact(run, str(path), "json", include_candidates=True, include_prompt=args.include_prompt)
                produced_paths.append(str(path))
                print(f"[sweep] wrote {path}", file=sys.stderr)

    report = audit_frontier_pool(produced_paths, scorer=scorer, top_k=12)
    md_path = out_dir / "frontier_sweep_report.md"
    json_path = out_dir / "frontier_sweep_report.json"
    csv_path = out_dir / "frontier_sweep_candidates.csv"
    plot_path = out_dir / "frontier_sweep.png"
    texts_path = out_dir / "frontier_sweep_texts.md"
    md_path.write_text(format_frontier_report(report, top_k=12), encoding="utf-8")
    write_frontier_json(report, str(json_path), include_rows=True)
    write_frontier_csv(report, str(csv_path))
    write_frontier_reading_report(report, str(texts_path))
    try:
        write_frontier_plot(report, str(plot_path))
    except RuntimeError as e:
        print(f"[sweep] plot skipped: {e}", file=sys.stderr)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "backend": args.backend,
        "model": resolve_model(args),
        "alphas": alphas,
        "candidate_grid": candidate_grid,
        "max_token_grid": token_grid,
        "select_objective": args.select_objective,
        "selector": make_selector_config(args).to_dict(),
        "runs": produced_paths,
        "report_md": str(md_path),
        "report_json": str(json_path),
        "candidate_csv": str(csv_path),
        "plot": str(plot_path) if plot_path.exists() else None,
        "texts": str(texts_path),
        "notes": [getattr(gen_args, "_steering_preflight_note", None)],
    }
    (out_dir / "frontier_sweep_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(format_frontier_report(report, top_k=6))
    print(f"\n[frontier-sweep] wrote {out_dir}", file=sys.stderr)


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
    elif args.command == "observe":
        cmd_observe(args)
    elif args.command == "pool-audit":
        cmd_pool_audit(args)
    elif args.command == "reselect":
        cmd_reselect(args)
    elif args.command == "frontier-sweep":
        cmd_frontier_sweep(args)
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

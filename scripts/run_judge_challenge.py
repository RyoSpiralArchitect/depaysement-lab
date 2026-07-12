#!/usr/bin/env python3
"""Build or run the blind literary-judge challenge one provider at a time."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Mapping

from depaysement_lab.judge_challenge import (
    DEFAULT_MODELS,
    analyze_provider_result,
    build_challenge,
    call_judge_provider,
    cross_provider_agreement,
    load_human_rating_items,
    sanitize_provider_call,
    write_judge_plot,
    write_judge_report,
)


ENV_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
}
CALL_NAMES = (
    "absolute_forward",
    "absolute_reverse",
    "pair_forward",
    "pair_swapped",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rating-sheet",
        default="experiments/frontier_sweep_banded_frontier_focus/human_rating_sheet.csv",
    )
    parser.add_argument("--out-dir", default="experiments/judge_challenge_v1")
    parser.add_argument("--pair-count", type=int, default=18)
    parser.add_argument("--provider", choices=list(DEFAULT_MODELS), default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--api-key-stdin",
        action="store_true",
        help="read one provider key from stdin; useful with pbpaste and avoids shell history",
    )
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="write the blind prompts without API calls")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    items = load_human_rating_items(args.rating_sheet)
    challenge = build_challenge(items, pair_count=args.pair_count)
    out_dir = Path(args.out_dir)
    raw_dir = out_dir / "raw"
    prompt_dir = out_dir / "prompts"
    raw_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "judge_challenge.json").write_text(
        json.dumps(challenge, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for name, prompt in challenge["prompts"].items():
        (prompt_dir / f"{name}.txt").write_text(str(prompt) + "\n", encoding="utf-8")

    if args.dry_run or not args.provider:
        results = _refresh_existing_results(out_dir, challenge)
        print(
            json.dumps(
                {
                    "items": len(items),
                    "pairs": len(challenge["pairs"]),
                    "out_dir": str(out_dir),
                    "api_calls": 0,
                    "existing_provider_results": len(results),
                },
                indent=2,
            )
        )
        return

    provider = str(args.provider)
    model = str(args.model or DEFAULT_MODELS[provider])
    expected_paths = [raw_dir / f"{provider}_{name}.json" for name in CALL_NAMES]
    needs_api_key = not args.resume or not all(path.exists() for path in expected_paths)
    api_key = _read_api_key(provider, from_stdin=bool(args.api_key_stdin)) if needs_api_key else ""
    calls: Dict[str, Mapping[str, Any]] = {}
    for name in CALL_NAMES:
        path = raw_dir / f"{provider}_{name}.json"
        if args.resume and path.exists():
            saved = json.loads(path.read_text(encoding="utf-8"))
            calls[name] = sanitize_provider_call(saved)
            path.write_text(
                json.dumps(calls[name], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"[judge] resume {provider}/{name}", file=sys.stderr)
            continue
        print(f"[judge] calling {provider}/{model}: {name}", file=sys.stderr)
        result = call_judge_provider(
            provider,
            api_key=api_key,
            model=model,
            prompt=str(challenge["prompts"][name]),
            timeout=args.timeout,
            retries=args.retries,
        )
        result["task"] = name
        result = sanitize_provider_call(result)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        calls[name] = result

    provider_result = analyze_provider_result(
        challenge,
        calls,
        provider=provider,
        model=model,
    )
    provider_path = out_dir / f"judge_result_{provider}.json"
    provider_path.write_text(
        json.dumps(provider_result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    results = _refresh_existing_results(out_dir, challenge)
    absolute = provider_result["absolute"]
    pairwise = provider_result["pairwise"]
    print(
        json.dumps(
            {
                "provider": provider,
                "model": model,
                "items": provider_result["item_count"],
                "pearson": absolute["pearson_averaged"],
                "spearman": absolute["spearman_averaged"],
                "absolute_order_mad": absolute["order_mean_absolute_delta"],
                "pair_accuracy": pairwise["accuracy"],
                "pair_order_consistency": pairwise["order_consistency"],
            },
            indent=2,
        )
    )


def _read_api_key(provider: str, *, from_stdin: bool) -> str:
    if from_stdin:
        key = sys.stdin.read().strip()
    else:
        key = str(os.environ.get(ENV_KEYS[provider]) or "").strip()
    if not key:
        source = "stdin" if from_stdin else ENV_KEYS[provider]
        raise SystemExit(f"missing {provider} API key from {source}")
    return key


def _compact_result(result: Mapping[str, Any]) -> Dict[str, Any]:
    absolute = result["absolute"]
    pairwise = result["pairwise"]
    return {
        "provider": result["provider"],
        "model": result["model"],
        "item_count": result["item_count"],
        "absolute": {key: value for key, value in absolute.items() if key != "item_rows"},
        "pairwise": {key: value for key, value in pairwise.items() if key != "rows"},
        "heuristic_correlations": result.get("heuristic_correlations", {}),
        "limitations": result.get("limitations", []),
    }


def _refresh_existing_results(
    out_dir: Path,
    challenge: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    raw_dir = out_dir / "raw"
    results = []
    for provider in DEFAULT_MODELS:
        paths = {name: raw_dir / f"{provider}_{name}.json" for name in CALL_NAMES}
        if not all(path.exists() for path in paths.values()):
            continue
        calls = {}
        for name, path in paths.items():
            value = sanitize_provider_call(json.loads(path.read_text(encoding="utf-8")))
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            calls[name] = value
        model = str(calls[CALL_NAMES[0]].get("model") or DEFAULT_MODELS[provider])
        result = analyze_provider_result(
            challenge,
            calls,
            provider=provider,
            model=model,
        )
        (out_dir / f"judge_result_{provider}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        results.append(result)
    results.sort(key=lambda result: str(result["provider"]))
    (out_dir / "judge_summary.json").write_text(
        json.dumps(
            {
                "results": [_compact_result(result) for result in results],
                "cross_provider": cross_provider_agreement(results),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_judge_report(results, str(out_dir / "judge_report.md"))
    write_judge_plot(results, str(out_dir / "judge_challenge.png"))
    return results


if __name__ == "__main__":
    main()

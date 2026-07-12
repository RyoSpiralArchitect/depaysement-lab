"""Blind cross-provider challenge for subtle literary judgments.

The challenge does not treat an LLM judge as ground truth. It asks whether a
judge reproduces one documented human taste pass, remains stable when item
order is reversed, and chooses the same underlying item when pair positions are
swapped. The small human sample calibrates an experimental instrument; it does
not estimate population-level literary preference.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


DEFAULT_MODELS = {
    "openai": "gpt-5.2",
    "anthropic": "claude-sonnet-5",
    "google": "gemini-3.5-flash",
}

SYSTEM_PROMPT = """You are evaluating short experimental prose.
Judge only the supplied text. Do not reward polish by itself. Prefer a readable,
specific displacement whose object or relation becomes genuinely strange while
remaining traceable. Penalize stock magical-realist props, predictable logic,
decorative gorgeousness, semantic loops, noun accumulation, and interrupted
tails. Return only the requested JSON object. Do not mention this rubric."""


def load_human_rating_items(path: str) -> List[Dict[str, Any]]:
    rows = list(csv.DictReader(Path(path).open(encoding="utf-8")))
    items: List[Dict[str, Any]] = []
    for row in rows:
        raw_score = str(row.get("human_score") or "").strip()
        if not raw_score:
            continue
        try:
            score = float(raw_score)
        except ValueError as exc:
            raise ValueError(f"invalid human_score={raw_score!r} for {row.get('id')}") from exc
        text = str(row.get("text") or "").strip()
        if not text:
            raise ValueError(f"rating row {row.get('id')} has no text")
        items.append(
            {
                "id": str(row.get("id") or f"item_{len(items) + 1}"),
                "text": text,
                "human_score": score,
                "human_notes": str(row.get("human_notes") or "").strip(),
                "heuristics": {
                    key: _optional_float(row.get(key))
                    for key in (
                        "readable_ontology_frontier",
                        "frontier_quality",
                        "ontology_collapse_density",
                        "syntax_readability_proxy",
                        "graph_integration",
                        "repair_pressure",
                        "unfinished",
                        "score_total",
                    )
                },
            }
        )
    if len(items) < 3:
        raise ValueError("judge challenge requires at least three human-rated items")
    return items


def build_pair_challenge(items: Sequence[Mapping[str, Any]], count: int = 18) -> List[Dict[str, Any]]:
    """Select deterministic near, middle, and far human-score contrasts."""

    candidates: List[Dict[str, Any]] = []
    for left_index, left in enumerate(items):
        for right in items[left_index + 1 :]:
            gap = abs(float(left["human_score"]) - float(right["human_score"]))
            if gap <= 1e-12:
                continue
            low, high = sorted((str(left["id"]), str(right["id"])))
            pair_id = f"{low}__{high}"
            digest = hashlib.sha256(pair_id.encode("utf-8")).digest()
            a, b = (left, right) if digest[0] % 2 == 0 else (right, left)
            human_winner = (
                str(left["id"])
                if float(left["human_score"]) > float(right["human_score"])
                else str(right["id"])
            )
            candidates.append(
                {
                    "pair_id": pair_id,
                    "a_id": str(a["id"]),
                    "b_id": str(b["id"]),
                    "a_text": str(a["text"]),
                    "b_text": str(b["text"]),
                    "human_winner": human_winner,
                    "human_gap": gap,
                }
            )
    candidates.sort(key=lambda row: (float(row["human_gap"]), str(row["pair_id"])))
    if not candidates:
        raise ValueError("no non-tied human-score pairs are available")
    target = min(max(1, int(count)), len(candidates))
    bins = _three_bins(candidates)
    selected: List[Dict[str, Any]] = []
    base, remainder = divmod(target, 3)
    for index, rows in enumerate(bins):
        take = base + (1 if index < remainder else 0)
        selected.extend(_spread_sample(rows, take))
    if len(selected) < target:
        chosen = {row["pair_id"] for row in selected}
        selected.extend(row for row in candidates if row["pair_id"] not in chosen)
    return selected[:target]


def build_challenge(items: Sequence[Mapping[str, Any]], pair_count: int = 18) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "blind_items": [{"id": item["id"], "text": item["text"]} for item in items],
        "human_reference": [dict(item) for item in items],
        "pairs": build_pair_challenge(items, count=pair_count),
        "prompts": {
            "absolute_forward": build_absolute_prompt(items),
            "absolute_reverse": build_absolute_prompt(list(reversed(items))),
            "pair_forward": build_pair_prompt(build_pair_challenge(items, count=pair_count), swapped=False),
            "pair_swapped": build_pair_prompt(build_pair_challenge(items, count=pair_count), swapped=True),
        },
        "notes": [
            "Human scores and notes are excluded from every judge prompt.",
            "Absolute item order and pair A/B positions are both reversed in matched calls.",
            "The reference is one rater's documented taste pass, not population ground truth.",
        ],
    }


def build_absolute_prompt(items: Sequence[Mapping[str, Any]]) -> str:
    payload = [{"id": str(item["id"]), "text": str(item["text"])} for item in items]
    return f"""Rate every item independently. Use the full 0-10 range when warranted.

Fields:
- preference_score: overall literary preference under the rubric, 0-10.
- readable_displacement: specific, traceable semantic displacement that remains readable, 0-10.
- completion: syntactic and narrative completion, 0-10.
- cliche_pressure: stock atmosphere, props, or overly accomplished metaphor, 0-10 (higher is worse).
- confidence: confidence in this rating, 0-1.
- reason: at most 24 words, grounded in the text.

Return JSON exactly in this shape:
{{"ratings":[{{"id":"...","preference_score":0,"readable_displacement":0,"completion":0,"cliche_pressure":0,"confidence":0,"reason":"..."}}]}}

Items:
{json.dumps(payload, ensure_ascii=False, indent=2)}"""


def build_pair_prompt(pairs: Sequence[Mapping[str, Any]], *, swapped: bool) -> str:
    payload = []
    for pair in pairs:
        if swapped:
            a_id, a_text = pair["b_id"], pair["b_text"]
            b_id, b_text = pair["a_id"], pair["a_text"]
        else:
            a_id, a_text = pair["a_id"], pair["a_text"]
            b_id, b_text = pair["b_id"], pair["b_text"]
        payload.append(
            {
                "pair_id": pair["pair_id"],
                "A": {"id": a_id, "text": a_text},
                "B": {"id": b_id, "text": b_text},
            }
        )
    return f"""For every pair, choose the prose sample you prefer under the rubric.
Use tie only when the distinction is genuinely unresolved. Judge each pair independently.

Return JSON exactly in this shape:
{{"choices":[{{"pair_id":"...","winner":"A","confidence":0,"reason":"at most 20 words"}}]}}
winner must be A, B, or tie.

Pairs:
{json.dumps(payload, ensure_ascii=False, indent=2)}"""


def call_judge_provider(
    provider: str,
    *,
    api_key: str,
    model: str,
    prompt: str,
    timeout: float = 300.0,
    retries: int = 2,
) -> Dict[str, Any]:
    if not api_key:
        raise ValueError(f"missing API key for {provider}")
    if provider == "openai":
        url = "https://api.openai.com/v1/responses"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "model": model,
            "instructions": SYSTEM_PROMPT,
            "input": prompt,
            "max_output_tokens": 8000,
            "store": False,
            "text": {"format": {"type": "json_object"}},
        }
        raw = _post_json(url, payload, headers=headers, timeout=timeout, retries=retries)
        text = str(raw.get("output_text") or "") or _openai_output_text(raw)
    elif provider == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": model,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8000,
        }
        raw = _post_json(url, payload, headers=headers, timeout=timeout, retries=retries)
        text = "".join(
            str(part.get("text") or "")
            for part in raw.get("content", [])
            if isinstance(part, Mapping) and part.get("type") == "text"
        )
    elif provider == "google":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {"x-goog-api-key": api_key}
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": 8000,
            },
        }
        raw = _post_json(url, payload, headers=headers, timeout=timeout, retries=retries)
        candidates = raw.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(str(part.get("text") or "") for part in parts if isinstance(part, Mapping))
    else:
        raise ValueError(f"unknown judge provider: {provider!r}")
    parsed = parse_json_response(text)
    return {
        "provider": provider,
        "model": model,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "parsed": parsed,
        "response_text": text,
        "api_metadata": _provider_metadata(provider, raw),
    }


def parse_json_response(text: str) -> Mapping[str, Any]:
    stripped = str(text).strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("judge response does not contain a JSON object")
        payload = json.loads(stripped[start : end + 1])
    if not isinstance(payload, Mapping):
        raise ValueError("judge response must be a JSON object")
    return payload


def sanitize_provider_call(call: Mapping[str, Any]) -> Dict[str, Any]:
    """Drop provider envelopes and retain only auditable, non-secret fields."""

    out = {
        key: call[key]
        for key in (
            "provider",
            "model",
            "task",
            "prompt_sha256",
            "parsed",
            "response_text",
            "api_metadata",
        )
        if key in call
    }
    raw = call.get("api_response")
    provider = str(call.get("provider") or "")
    if "api_metadata" not in out and isinstance(raw, Mapping) and provider:
        out["api_metadata"] = _provider_metadata(provider, raw)
    return out


def analyze_provider_result(
    challenge: Mapping[str, Any],
    calls: Mapping[str, Mapping[str, Any]],
    *,
    provider: str,
    model: str,
) -> Dict[str, Any]:
    items = {str(item["id"]): item for item in challenge["human_reference"]}
    forward = _absolute_map(calls["absolute_forward"])
    reverse = _absolute_map(calls["absolute_reverse"])
    shared_ids = [item_id for item_id in items if item_id in forward and item_id in reverse]
    human = [float(items[item_id]["human_score"]) for item_id in shared_ids]
    forward_scores = [float(forward[item_id]["preference_score"]) for item_id in shared_ids]
    reverse_scores = [float(reverse[item_id]["preference_score"]) for item_id in shared_ids]
    averaged = [(left + right) / 2.0 for left, right in zip(forward_scores, reverse_scores)]
    order_mad = _mean(abs(left - right) for left, right in zip(forward_scores, reverse_scores))

    pairs = {str(pair["pair_id"]): pair for pair in challenge["pairs"]}
    pair_forward = _pair_map(calls["pair_forward"])
    pair_swapped = _pair_map(calls["pair_swapped"])
    pair_rows: List[Dict[str, Any]] = []
    for pair_id, pair in pairs.items():
        forward_choice = _underlying_pair_choice(pair, pair_forward.get(pair_id), swapped=False)
        swapped_choice = _underlying_pair_choice(pair, pair_swapped.get(pair_id), swapped=True)
        pair_rows.append(
            {
                "pair_id": pair_id,
                "human_winner": pair["human_winner"],
                "human_gap": float(pair["human_gap"]),
                "forward_choice": forward_choice,
                "swapped_choice": swapped_choice,
                "order_consistent": forward_choice == swapped_choice,
                "forward_correct": forward_choice == pair["human_winner"],
                "swapped_correct": swapped_choice == pair["human_winner"],
                "forward_position": str(pair_forward.get(pair_id, {}).get("winner") or "missing"),
                "swapped_position": str(pair_swapped.get(pair_id, {}).get("winner") or "missing"),
            }
        )

    pooled_correct = [
        value
        for row in pair_rows
        for value in (bool(row["forward_correct"]), bool(row["swapped_correct"]))
        if row["forward_choice"] != "missing" and row["swapped_choice"] != "missing"
    ]
    position_labels = [
        label
        for row in pair_rows
        for label in (row["forward_position"], row["swapped_position"])
        if label in {"A", "B", "tie"}
    ]
    heuristic_correlations = {}
    for metric in next(iter(items.values())).get("heuristics", {}):
        values = [items[item_id]["heuristics"].get(metric) for item_id in shared_ids]
        if all(value is not None for value in values):
            heuristic_correlations[metric] = {
                "pearson": pearson_correlation(human, [float(value) for value in values]),
                "spearman": spearman_correlation(human, [float(value) for value in values]),
            }

    return {
        "provider": provider,
        "model": model,
        "item_count": len(shared_ids),
        "absolute": {
            "pearson_forward": pearson_correlation(human, forward_scores),
            "pearson_reverse": pearson_correlation(human, reverse_scores),
            "pearson_averaged": pearson_correlation(human, averaged),
            "spearman_forward": spearman_correlation(human, forward_scores),
            "spearman_reverse": spearman_correlation(human, reverse_scores),
            "spearman_averaged": spearman_correlation(human, averaged),
            "mae_averaged": _mean(abs(expected - observed) for expected, observed in zip(human, averaged)),
            "order_mean_absolute_delta": order_mad,
            "item_rows": [
                {
                    "id": item_id,
                    "human_score": human[index],
                    "judge_forward": forward_scores[index],
                    "judge_reverse": reverse_scores[index],
                    "judge_averaged": averaged[index],
                }
                for index, item_id in enumerate(shared_ids)
            ],
        },
        "pairwise": {
            "pair_count": len(pair_rows),
            "accuracy": _mean(1.0 if value else 0.0 for value in pooled_correct),
            "order_consistency": _mean(1.0 if row["order_consistent"] else 0.0 for row in pair_rows),
            "position_a_rate": _mean(1.0 if label == "A" else 0.0 for label in position_labels),
            "tie_rate": _mean(1.0 if label == "tie" else 0.0 for label in position_labels),
            "rows": pair_rows,
        },
        "heuristic_correlations": heuristic_correlations,
        "calls": dict(calls),
        "limitations": [
            "Twelve texts and one human rater provide calibration evidence, not population validity.",
            "Provider models and APIs can drift; raw responses and exact model IDs are retained.",
            "A high correlation would support supplemental use, not replacement of human literary judgment.",
        ],
    }


def write_judge_report(results: Sequence[Mapping[str, Any]], path: str) -> None:
    lines = [
        "# LLM Judge Challenge",
        "",
        "Blind absolute ratings were repeated in reverse item order. Pairwise choices were repeated with A/B positions swapped.",
        "",
        "| provider | model | n | Pearson | Spearman | abs order MAD | pair accuracy | pair consistency | A rate |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        absolute = result["absolute"]
        pairwise = result["pairwise"]
        lines.append(
            f"| {result['provider']} | {result['model']} | {result['item_count']} | "
            f"{_fmt(absolute['pearson_averaged'])} | {_fmt(absolute['spearman_averaged'])} | "
            f"{absolute['order_mean_absolute_delta']:.3f} | {pairwise['accuracy']:.3f} | "
            f"{pairwise['order_consistency']:.3f} | {pairwise['position_a_rate']:.3f} |"
        )
    cross_rows = cross_provider_agreement(results)
    if cross_rows:
        lines.extend(
            [
                "",
                "## Cross-Provider Agreement",
                "",
                "| providers | absolute Pearson | absolute Spearman | pair-choice agreement |",
                "|---|---:|---:|---:|",
            ]
        )
        for row in cross_rows:
            lines.append(
                f"| {row['left']} / {row['right']} | {_fmt(row['pearson'])} | "
                f"{_fmt(row['spearman'])} | {row['pair_agreement']:.3f} |"
            )
    if results:
        lines.extend(
            [
                "",
                "## Frozen Observer Reference",
                "",
                "The same 12-item human pass gives the following correlations for deterministic observer components.",
                "",
                "| metric | Pearson | Spearman |",
                "|---|---:|---:|",
            ]
        )
        for metric, values in results[0].get("heuristic_correlations", {}).items():
            lines.append(f"| {metric} | {_fmt(values.get('pearson'))} | {_fmt(values.get('spearman'))} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The deterministic observer is retained because it is frozen, decomposable, replayable over full candidate pools, and independent of provider drift. The judge challenge tests convergent validity and instability; it does not promote either the heuristic observer or an API judge to literary ground truth.",
            "",
            "This is a small, single-rater calibration pass. Broader claims about taste require more raters, explicit sampling, and inter-rater analysis.",
        ]
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def cross_provider_agreement(results: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    ordered = sorted(results, key=lambda result: str(result["provider"]))
    for left_index, left in enumerate(ordered):
        for right in ordered[left_index + 1 :]:
            left_scores = {
                str(row["id"]): float(row["judge_averaged"]) for row in left["absolute"]["item_rows"]
            }
            right_scores = {
                str(row["id"]): float(row["judge_averaged"]) for row in right["absolute"]["item_rows"]
            }
            shared_items = sorted(set(left_scores) & set(right_scores))
            left_pairs = {str(row["pair_id"]): row for row in left["pairwise"]["rows"]}
            right_pairs = {str(row["pair_id"]): row for row in right["pairwise"]["rows"]}
            pair_matches = []
            for pair_id in sorted(set(left_pairs) & set(right_pairs)):
                pair_matches.extend(
                    [
                        left_pairs[pair_id]["forward_choice"] == right_pairs[pair_id]["forward_choice"],
                        left_pairs[pair_id]["swapped_choice"] == right_pairs[pair_id]["swapped_choice"],
                    ]
                )
            rows.append(
                {
                    "left": str(left["provider"]),
                    "right": str(right["provider"]),
                    "pearson": pearson_correlation(
                        [left_scores[item_id] for item_id in shared_items],
                        [right_scores[item_id] for item_id in shared_items],
                    ),
                    "spearman": spearman_correlation(
                        [left_scores[item_id] for item_id in shared_items],
                        [right_scores[item_id] for item_id in shared_items],
                    ),
                    "pair_agreement": _mean(1.0 if value else 0.0 for value in pair_matches),
                }
            )
    return rows


def write_judge_plot(results: Sequence[Mapping[str, Any]], path: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - optional plotting dependency
        raise RuntimeError("judge challenge plotting requires matplotlib") from exc

    if not results:
        return
    colors = {
        "openai": "#236A8D",
        "anthropic": "#D1495B",
        "google": "#3A7D44",
    }
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4), constrained_layout=True)
    ax = axes[0]
    for result in results:
        rows = result["absolute"]["item_rows"]
        provider = str(result["provider"])
        ax.scatter(
            [row["human_score"] for row in rows],
            [row["judge_averaged"] for row in rows],
            label=provider,
            color=colors.get(provider),
            alpha=0.78,
            s=42,
        )
    ax.plot([0, 10], [0, 10], color="#777777", linestyle="--", linewidth=1, label="equal scale")
    ax.set_xlim(4.5, 9.0)
    ax.set_ylim(0.0, 10.0)
    ax.set_xlabel("human taste score")
    ax.set_ylabel("judge preference score")
    ax.set_title("Blind absolute ratings")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1]
    providers = [str(result["provider"]) for result in results]
    positions = list(range(len(providers)))
    width = 0.24
    series = (
        ("pair accuracy", [float(result["pairwise"]["accuracy"]) for result in results], -width),
        ("A/B consistency", [float(result["pairwise"]["order_consistency"]) for result in results], 0.0),
        (
            "Spearman",
            [float(result["absolute"]["spearman_averaged"] or 0.0) for result in results],
            width,
        ),
    )
    for label, values, offset in series:
        ax.bar([position + offset for position in positions], values, width=width, label=label)
    ax.axhline(0.5, color="#777777", linestyle="--", linewidth=1, label="pair chance")
    ax.axhline(0.0, color="#444444", linewidth=0.8)
    ax.set_xticks(positions, providers)
    ax.set_ylim(-0.15, 1.0)
    ax.set_ylabel("score")
    ax.set_title("Agreement and presentation stability")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _post_json(
    url: str,
    payload: Mapping[str, Any],
    *,
    headers: Mapping[str, str],
    timeout: float,
    retries: int,
) -> Mapping[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **dict(headers)}
    last_error: Optional[BaseException] = None
    for attempt in range(int(retries) + 1):
        request = urllib.request.Request(url, data=body, headers=request_headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=float(timeout)) as response:
                value = json.loads(response.read().decode("utf-8"))
            if not isinstance(value, Mapping):
                raise ValueError("provider response was not a JSON object")
            return value
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"HTTP {exc.code} from provider: {detail}")
            if exc.code < 500 and exc.code != 429:
                break
        except Exception as exc:  # pragma: no cover - network-specific
            last_error = exc
        if attempt < int(retries):
            time.sleep(1.0 * (2**attempt))
    raise RuntimeError(f"judge provider request failed: {last_error}")


def _openai_output_text(raw: Mapping[str, Any]) -> str:
    values = []
    for item in raw.get("output", []):
        if not isinstance(item, Mapping):
            continue
        for part in item.get("content", []):
            if isinstance(part, Mapping) and part.get("type") == "output_text":
                values.append(str(part.get("text") or ""))
    return "".join(values)


def _provider_metadata(provider: str, raw: Mapping[str, Any]) -> Dict[str, Any]:
    if provider == "openai":
        return {
            "response_id": raw.get("id"),
            "model": raw.get("model"),
            "status": raw.get("status"),
            "usage": raw.get("usage"),
        }
    if provider == "anthropic":
        return {
            "response_id": raw.get("id"),
            "model": raw.get("model"),
            "stop_reason": raw.get("stop_reason"),
            "usage": raw.get("usage"),
        }
    return {
        "response_id": raw.get("responseId"),
        "model": raw.get("modelVersion"),
        "usage": raw.get("usageMetadata"),
    }


def _absolute_map(call: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    parsed = call.get("parsed") if isinstance(call.get("parsed"), Mapping) else call
    ratings = parsed.get("ratings", []) if isinstance(parsed, Mapping) else []
    out = {}
    for rating in ratings:
        if not isinstance(rating, Mapping) or not rating.get("id"):
            continue
        try:
            score = float(rating.get("preference_score"))
        except (TypeError, ValueError):
            continue
        value = dict(rating)
        value["preference_score"] = score
        out[str(rating["id"])] = value
    return out


def _pair_map(call: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    parsed = call.get("parsed") if isinstance(call.get("parsed"), Mapping) else call
    choices = parsed.get("choices", []) if isinstance(parsed, Mapping) else []
    return {
        str(choice["pair_id"]): choice
        for choice in choices
        if isinstance(choice, Mapping) and choice.get("pair_id")
    }


def _underlying_pair_choice(
    pair: Mapping[str, Any],
    choice: Optional[Mapping[str, Any]],
    *,
    swapped: bool,
) -> str:
    if choice is None:
        return "missing"
    winner = str(choice.get("winner") or "").strip()
    if winner.lower() == "tie":
        return "tie"
    if winner not in {"A", "B"}:
        return "missing"
    if swapped:
        return str(pair["b_id"] if winner == "A" else pair["a_id"])
    return str(pair["a_id"] if winner == "A" else pair["b_id"])


def pearson_correlation(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    if len(x) != len(y) or len(x) < 2:
        return None
    x_mean, y_mean = _mean(x), _mean(y)
    numerator = sum((a - x_mean) * (b - y_mean) for a, b in zip(x, y))
    x_scale = math.sqrt(sum((a - x_mean) ** 2 for a in x))
    y_scale = math.sqrt(sum((b - y_mean) ** 2 for b in y))
    if x_scale <= 0.0 or y_scale <= 0.0:
        return None
    return numerator / (x_scale * y_scale)


def spearman_correlation(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    return pearson_correlation(_average_ranks(x), _average_ranks(y))


def _average_ranks(values: Sequence[float]) -> List[float]:
    indexed = sorted(enumerate(float(value) for value in values), key=lambda item: item[1])
    ranks = [0.0] * len(indexed)
    start = 0
    while start < len(indexed):
        end = start + 1
        while end < len(indexed) and indexed[end][1] == indexed[start][1]:
            end += 1
        rank = (start + 1 + end) / 2.0
        for index in range(start, end):
            ranks[indexed[index][0]] = rank
        start = end
    return ranks


def _three_bins(rows: Sequence[Mapping[str, Any]]) -> List[List[Mapping[str, Any]]]:
    first = max(1, len(rows) // 3)
    second = max(first + 1, (2 * len(rows)) // 3)
    return [list(rows[:first]), list(rows[first:second]), list(rows[second:])]


def _spread_sample(rows: Sequence[Mapping[str, Any]], count: int) -> List[Dict[str, Any]]:
    if count <= 0 or not rows:
        return []
    if count >= len(rows):
        return [dict(row) for row in rows]
    if count == 1:
        return [dict(rows[len(rows) // 2])]
    indices = [round(index * (len(rows) - 1) / (count - 1)) for index in range(count)]
    return [dict(rows[index]) for index in indices]


def _optional_float(value: Any) -> Optional[float]:
    try:
        return float(value) if str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _mean(values: Iterable[float]) -> float:
    collected = [float(value) for value in values]
    return sum(collected) / len(collected) if collected else 0.0


def _fmt(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{float(value):.3f}"

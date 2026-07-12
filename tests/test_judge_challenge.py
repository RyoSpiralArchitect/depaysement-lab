import pytest

from depaysement_lab.judge_challenge import (
    analyze_provider_result,
    build_challenge,
    build_pair_challenge,
    parse_json_response,
    pearson_correlation,
    sanitize_provider_call,
    spearman_correlation,
)


def _items():
    return [
        {"id": "low", "text": "Plain text.", "human_score": 4.0, "human_notes": "", "heuristics": {}},
        {
            "id": "middle",
            "text": "A cup becomes a hinge.",
            "human_score": 6.0,
            "human_notes": "",
            "heuristics": {},
        },
        {
            "id": "high",
            "text": "A receipt opens into weather.",
            "human_score": 9.0,
            "human_notes": "",
            "heuristics": {},
        },
        {
            "id": "near",
            "text": "A drawer keeps the rain.",
            "human_score": 8.0,
            "human_notes": "",
            "heuristics": {},
        },
    ]


def test_parse_json_response_accepts_fenced_json():
    assert parse_json_response('```json\n{"ratings": []}\n```') == {"ratings": []}


def test_sanitize_provider_call_drops_provider_envelope():
    call = sanitize_provider_call(
        {
            "provider": "google",
            "model": "gemini-test",
            "parsed": {"ratings": []},
            "response_text": "{}",
            "api_response": {
                "responseId": "response-1",
                "modelVersion": "gemini-test-001",
                "usageMetadata": {"totalTokenCount": 10},
                "candidates": [{"thoughtSignature": "opaque"}],
            },
        }
    )

    assert "api_response" not in call
    assert "thoughtSignature" not in str(call)
    assert call["api_metadata"]["response_id"] == "response-1"


def test_pair_challenge_is_deterministic_and_excludes_human_ties():
    first = build_pair_challenge(_items(), count=5)
    second = build_pair_challenge(_items(), count=5)
    assert first == second
    assert len(first) == 5
    assert all(pair["human_gap"] > 0 for pair in first)


def test_correlations_handle_ties():
    assert pearson_correlation([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert spearman_correlation([1, 2, 2, 4], [1, 3, 3, 5]) == pytest.approx(1.0)


def test_analyze_provider_result_recovers_swapped_underlying_choices():
    challenge = build_challenge(_items(), pair_count=4)
    ratings = [{"id": item["id"], "preference_score": item["human_score"]} for item in _items()]
    forward_choices = []
    swapped_choices = []
    for pair in challenge["pairs"]:
        forward_choices.append(
            {
                "pair_id": pair["pair_id"],
                "winner": "A" if pair["human_winner"] == pair["a_id"] else "B",
            }
        )
        swapped_choices.append(
            {
                "pair_id": pair["pair_id"],
                "winner": "A" if pair["human_winner"] == pair["b_id"] else "B",
            }
        )
    calls = {
        "absolute_forward": {"parsed": {"ratings": ratings}},
        "absolute_reverse": {"parsed": {"ratings": list(reversed(ratings))}},
        "pair_forward": {"parsed": {"choices": forward_choices}},
        "pair_swapped": {"parsed": {"choices": swapped_choices}},
    }

    result = analyze_provider_result(challenge, calls, provider="test", model="test-model")

    assert result["absolute"]["spearman_averaged"] == pytest.approx(1.0)
    assert result["pairwise"]["accuracy"] == 1.0
    assert result["pairwise"]["order_consistency"] == 1.0

# Hard-Gated Mundane Reselect

This pass tests whether the selector can avoid the two strongest failure modes
seen in the mundane-seed probe without generating any new text:

- stock-prop attractors: antique music boxes, porcelain dolls, miniatures,
  pocket watches, leather-bound books;
- unfinished tails: comma chains and truncated image streams.

The source pools are the saved steered mundane-seed sweep:

```text
experiments/frontier_sweep_mundane_seed_probe/steer_alpha_*.json
```

## Implementation Changes

The cliche audit is now split into:

- `stock_prop_attractor_score`
- `soft_style_cliche_score`
- the previous combined `cliche_attractor_score`

The selector also has:

- `--soft-style-cliche-weight`
- `--hard-unfinished-max`

`hard_unfinished_max` is disabled by default. When enabled, candidates above
the threshold receive a very large selector penalty and are marked with
`hard_gate_failed`. If every saved candidate in a step fails the gate, the run
still falls back to the best available failed candidate because post-hoc
reselection cannot regenerate a clean pool.

The audit regex helper `wordish_pattern()` is cached with `lru_cache`. This does
not change scores, but it makes large pool audits practical; the first uncached
attempt spent more than 25 minutes in repeated regex compilation.

## Command

```bash
PYTHONPATH=src python3 -m depaysement_lab.cli reselect \
  experiments/frontier_sweep_mundane_seed_probe/steer_alpha_*.json \
  --select-objective banded-frontier \
  --choose best \
  --context-policy recorded \
  --selector-unfinished-max 0.50 \
  --hard-unfinished-max 0.05 \
  --unfinished-weight 1.40 \
  --repetition-weight 0.45 \
  --sprawl-weight 0.60 \
  --cliche-weight 0.0 \
  --soft-style-cliche-weight 0.25 \
  --fantasy-prop-weight 1.10 \
  --ordinary-anchor-weight 0.45 \
  --ordinary-anchor-min 0.30 \
  --out-dir experiments/posthoc_reselect_mundane_hard_gate
```

The initial `reselect` was interrupted after writing the 40 reselected JSON
artifacts because full report generation was too slow before regex caching.
After adding the cache, the report was generated from those JSON files with:

```bash
PYTHONPATH=src python3 -m depaysement_lab.cli pool-audit \
  experiments/posthoc_reselect_mundane_hard_gate/*.json \
  --top-k 12 \
  --out experiments/posthoc_reselect_mundane_hard_gate/posthoc_reselect_report.md \
  --json-out experiments/posthoc_reselect_mundane_hard_gate/posthoc_reselect_report.json \
  --csv experiments/posthoc_reselect_mundane_hard_gate/posthoc_reselect_candidates.csv \
  --texts-out experiments/posthoc_reselect_mundane_hard_gate/posthoc_reselect_texts.md
```

## Picked-Text Comparison

All rows below are picked continuations only, re-audited with the current
metrics. Each selector contributes 40 runs and 200 picked steps.

| selector | frontier | anchor | cliche | stock | soft | prop | unfinished rate | unfinished mean | read | ontology | repair |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| original | 0.143 | 0.700 | 0.892 | 0.758 | 0.453 | 0.839 | 0.500 | 0.199 | 0.684 | 0.529 | 0.003 |
| cliche / prop guard | 0.126 | 0.681 | 0.768 | 0.530 | 0.425 | 0.606 | 0.555 | 0.221 | 0.664 | 0.498 | 0.000 |
| dual guard | 0.122 | 0.743 | 0.772 | 0.537 | 0.417 | 0.617 | 0.585 | 0.233 | 0.652 | 0.501 | 0.000 |
| balanced guard | 0.118 | 0.720 | 0.745 | 0.495 | 0.408 | 0.570 | 0.590 | 0.235 | 0.652 | 0.483 | 0.003 |
| hard gate | 0.120 | 0.701 | 0.718 | 0.507 | 0.370 | 0.584 | 0.310 | 0.124 | 0.682 | 0.418 | 0.007 |

## Read

The hard gate is doing the intended work:

- unfinished rate drops from about `0.59` in the previous guard variants to
  `0.31`;
- unfinished mean drops from about `0.235` to `0.124`;
- soft-style cliche drops from `0.408` to `0.370`;
- combined cliche drops from `0.745` to `0.718`;
- readability recovers from `0.652` to `0.682`.

The cost is that ontology intensity drops:

- ontology falls from `0.483` in the balanced guard to `0.418`;
- frontier recovers only slightly, from `0.118` to `0.120`;
- stock prop pressure rises a little relative to balanced guard, from `0.495`
  to `0.507`.

That means the current saved pools contain many attractive but unfinished
candidates. The selector can refuse them when a clean alternative exists, but
post-hoc reselection cannot invent clean candidates for steps where every saved
candidate is already truncated.

## Human Reading Sheet

A focused 20-row reading sheet was exported:

```text
experiments/posthoc_reselect_mundane_hard_gate/human_rating_sheet_hard_gate_focus.csv
experiments/posthoc_reselect_mundane_hard_gate/human_rating_sheet_hard_gate_focus.md
```

It intentionally mixes:

- clean picked candidates ranked by a taste-probe score;
- clean not-picked top-frontier candidates;
- picked fallback candidates where the saved pool still forced an unfinished
  choice.

This should make the next human pass diagnostic: the not-picked top-frontier
examples often have excellent numerical frontier but are visibly stock-prop
heavy, while the clean picked examples are usually less intense but more local.

## Next Step

Run a short live generation sweep with the hard gate enabled, not merely
post-hoc reselection. The point is to see whether clean choices early in the
trajectory improve later candidate pools.

Suggested narrow sweep:

```bash
PYTHONPATH=src python3 -m depaysement_lab.cli frontier-sweep \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --chat-template \
  --vectors experiments/depaysement_mlx_vectors_mundane_v2.npz \
  --steer-layers 4-18 \
  --seed-bank data/mundane_seed_bank_v1.json \
  --seed-limit 8 \
  --steps 4 \
  --alphas 0.66,0.77,0.88 \
  --candidate-grid 19 \
  --max-token-grid 110,125 \
  --select-objective banded-frontier \
  --choose best \
  --selector-unfinished-max 0.50 \
  --hard-unfinished-max 0.05 \
  --unfinished-weight 1.40 \
  --repetition-weight 0.45 \
  --sprawl-weight 0.60 \
  --soft-style-cliche-weight 0.25 \
  --fantasy-prop-weight 1.10 \
  --ordinary-anchor-weight 0.45 \
  --ordinary-anchor-min 0.30 \
  --out-dir experiments/frontier_sweep_mundane_hard_gate_live
```

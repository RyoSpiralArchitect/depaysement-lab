# Research Note: Actual Banded-Frontier Generation

Date: 2026-05-16

## Question

The post-hoc selector lab showed that `banded-frontier` could recover more
frontier material from saved candidate pools while avoiding some pure-frontier
overshoot. The next question was whether this holds when the selector is used
during actual MLX generation.

## Experimental Setup

Command:

```bash
python3 -m depaysement_lab.cli frontier-sweep \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --chat-template \
  --vectors experiments/depaysement_mlx_vectors.npz \
  --steer-layers 6-16 \
  --seed "A forgotten umbrella at the station" \
  --steps 5 \
  --alphas 0.45,0.6 \
  --candidate-grid 12 \
  --max-token-grid 140 \
  --select-objective banded-frontier \
  --choose best \
  --unfinished-weight 1.10 \
  --repetition-weight 0.45 \
  --sprawl-weight 0.30 \
  --out-dir experiments/frontier_sweep_banded_frontier_focus
```

Artifacts:

- [report](../../experiments/frontier_sweep_banded_frontier_focus/frontier_sweep_report.md)
- [generated text reading report](../../experiments/frontier_sweep_banded_frontier_focus/frontier_sweep_texts.md)
- [candidate CSV](../../experiments/frontier_sweep_banded_frontier_focus/frontier_sweep_candidates.csv)
- [plot](../../experiments/frontier_sweep_banded_frontier_focus/frontier_sweep.png)
- [rating sheet CSV](../../experiments/frontier_sweep_banded_frontier_focus/human_rating_sheet.csv)
- [rating sheet reading view](../../experiments/frontier_sweep_banded_frontier_focus/human_rating_sheet.md)
- [manifest](../../experiments/frontier_sweep_banded_frontier_focus/frontier_sweep_manifest.json)

## Results

Compared to the previous `hybrid` generation sweep:

| selector | alpha | pool frontier | picked frontier | lift | picked ontology | picked readability | picked unfinished | picked hit rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `hybrid` | `0.45` | 0.029 | 0.122 | +0.093 | 0.485 | 0.600 | 0.160 | 0.40 |
| `hybrid` | `0.60` | 0.046 | 0.123 | +0.078 | 0.344 | 0.695 | 0.080 | 0.60 |
| `banded-frontier` | `0.45` | 0.039 | 0.137 | +0.098 | 0.537 | 0.587 | 0.160 | 0.60 |
| `banded-frontier` | `0.60` | 0.038 | 0.170 | +0.132 | 0.500 | 0.745 | 0.080 | 1.00 |

The strongest setting is:

```text
alpha = 0.60
selector = banded-frontier
picked_frontier = 0.170
selection_lift = +0.132
picked_ontology = 0.500
picked_readability = 0.745
picked_frontier_hit_rate = 1.00
```

## Interpretation

This is the first actual generation result where the selector improvement
clearly transfers from post-hoc analysis back into live generation.

The `alpha=0.60` banded-frontier run does not show a stronger mean candidate-pool
frontier than the previous hybrid run. In fact, its pool frontier is slightly
lower than the previous `alpha=0.60` hybrid pool. The important result is
selection lift: `banded-frontier` finds a much stronger picked path inside the
pool.

The best picked examples are concentrated at the readable band:

```text
ontology around 0.55
readability around 0.90 on the strongest picked steps
repair pressure near 0
```

Qualitatively, the `alpha=0.60` thread is more coherent than the earlier
liquefaction-prone runs. It builds around an umbrella, a small bird, a stranger,
and a leather-bound book. The ontology shift is less explosive than pure
frontier, but more legible as a scene.

## Remaining Problem

The late-step tail is still fragile. The `alpha=0.60` run has strong first and
fifth picked candidates by metric, but the reading report shows incomplete or
quote-tail endings in the final assembled text.

This suggests the next bottleneck is no longer selector discovery. It is tail
control:

```text
hard truncation
quote-tail
malformed final phrase
sentence-boundary cutoff
```

The current coarse `unfinished` metric is too blunt to separate these cases.

## Working Claim

`banded-frontier` should replace `hybrid` as the next live-generation selector
for this seed/model setup.

The current best live setting is:

```text
alpha = 0.60
candidates = 12
max_new_tokens = 140
selector = banded-frontier
choose = best
```

The next technical step is not more alpha search. It is tail-aware finishing:
detect malformed endings separately and either penalize them more sharply or
repair only the final boundary without explaining the image.

## Next Steps

1. Split `unfinished` into hard truncation, quote-tail, malformed tail, comma
   chain, and repetition loop.
2. Add a selector penalty specifically for hard truncation and quote-tail.
3. Try `max_new_tokens=120` and `140` with the same banded selector to see
   whether shorter continuation windows preserve frontier while reducing tails.
4. Human-rate the 12-row actual-generation sheet before scaling to more seeds.

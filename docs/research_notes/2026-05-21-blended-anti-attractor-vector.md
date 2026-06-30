# Original + Soft Anti-attractor Blend Probe

Date: 2026-05-21

## Question

The hard and soft anti-attractor vectors both suppress the stock-prop basin
(`antique music box`, `porcelain`, `miniature`, `clock`, `leather-bound`), but
they also make the candidate pool rougher. The next question is whether a small
amount of anti-attractor direction can be blended into the original vector while
preserving the original vector's fluency.

## Hypothesis

If the stock-prop basin is a separable subdirection inside the original steering
vector, then a small blend should keep the readable scene manifold while reducing
the fantasy-prop/cliche attractor:

```text
blend = unit_normalize(original + lambda * soft_anti_attractor_v2)
```

If the basin is entangled with the original vector's fluency scaffold, then
blending should recover readability but also bring the basin back.

## Setup

Blended vectors:

- `experiments/depaysement_mlx_vectors_l4_18_blend_orig_softanti_lam0p1.npz`
- `experiments/depaysement_mlx_vectors_l4_18_blend_orig_softanti_lam0p2.npz`
- `experiments/depaysement_mlx_vectors_l4_18_blend_orig_softanti_lam0p35.npz`

Comparison summary:

- `experiments/frontier_sweep_mundane_blend_orig_softanti_comparison_summary.md`

Sweep:

- model: local `mlx-community/Llama-3.2-3B-Instruct-4bit` snapshot
- layers: `4-18`
- seed bank: `data/mundane_seed_bank_en_v1.json`
- seed limit: `4`
- steps: `3`
- alphas: `0.55,0.66`
- candidates: `12`
- max tokens: `120`
- selector: hybrid anchor guard

## Results

Overall candidate-pool behavior:

| condition | pool read | pool cliche | pool fantasy_prop | pool unfinished-rate | music_box | porcelain | miniature/tiny | antique | leather_bound |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| original vector | 0.750 | 0.231 | 0.222 | 0.087 | 21 | 29 | 62 | 23 | 24 |
| soft anti-attractor v2 | 0.606 | 0.026 | 0.015 | 0.157 | 1 | 1 | 7 | 5 | 4 |
| blend lambda 0.10 | 0.717 | 0.130 | 0.122 | 0.087 | 13 | 12 | 35 | 19 | 12 |
| blend lambda 0.20 | 0.722 | 0.208 | 0.209 | 0.087 | 20 | 25 | 34 | 19 | 39 |
| blend lambda 0.35 | 0.668 | 0.131 | 0.118 | 0.128 | 4 | 13 | 42 | 11 | 20 |

Picked-output behavior:

| condition | picked read | picked cliche | picked fantasy_prop | tracked stock-prop note |
|---|---:|---:|---:|---|
| original vector | 0.825 | 0.069 | 0.017 | `miniature/tiny` survives in 5 picked rows |
| soft anti-attractor v2 | 0.726 | 0.019 | 0.000 | tracked stock props mostly removed |
| blend lambda 0.10 | 0.861 | 0.014 | 0.000 | tracked stock props removed from picked rows |
| blend lambda 0.20 | 0.816 | 0.097 | 0.062 | `miniature/tiny`, `leather-bound` survive |
| blend lambda 0.35 | 0.763 | 0.014 | 0.037 | `porcelain`, `miniature/tiny`, `clock/watch` survive |

## Interpretation

The blend recovers fluency, but it also revives the basin. This supports the
entanglement hypothesis: the stock-prop attractor is not a cleanly separable bad
direction inside the original vector. It appears to be part of the small model's
fluent surreal-object manifold.

`lambda=0.10` is the most useful production blend in this probe. It has high
picked readability and keeps the selected outputs mostly clean. But it does not
solve the candidate-pool problem: the pool still contains frequent
`music box`, `porcelain`, `miniature/tiny`, `antique`, and `leather-bound`
returns.

`lambda=0.20` is worse than expected. It increases cliche/fantasy-prop pressure
instead of suppressing it, suggesting that this blend path is not monotonic.

`lambda=0.35` suppresses `music box` more than the smaller blends but loses
readability and still leaks other stock props. It is not a clean improvement.

## Current Production Read

The best near-term strategy is not stronger anti-vector steering. It is:

1. Use the original vector or `lambda=0.10` blend to preserve fluent scene
   generation.
2. Keep the anchor-guard selector.
3. Add a second-pass stock-prop filter or human taste pass over selected rows.
4. Treat hard/soft anti-attractor vectors as causal instruments rather than
   production vectors.

## Next Human Eval Slice

The most informative human-eval comparison is now:

- original vector picked rows;
- soft anti-attractor picked rows;
- blend `lambda=0.10` picked rows;
- a small sample of rejected high-frontier stock-prop rows from each condition.

That slice should test whether the machine-level improvement on picked rows
actually tracks taste, or whether the selector is merely hiding roughness and
stock-prop pressure from the final outputs.

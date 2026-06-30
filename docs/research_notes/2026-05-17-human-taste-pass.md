# Research Note: First Human Taste Pass

Date: 2026-05-17

## Question

The banded-frontier selector improved live generation metrics, but the real
question is whether the selected outputs match human taste. This pass adds
manual human scores to the 12-row rating sheet from the actual
`banded-frontier` MLX sweep.

## Artifacts

- [rating sheet CSV](../../experiments/frontier_sweep_banded_frontier_focus/human_rating_sheet.csv)
- [rating reading view](../../experiments/frontier_sweep_banded_frontier_focus/human_rating_sheet.md)
- [human taste analysis](../../experiments/frontier_sweep_banded_frontier_focus/human_rating_analysis.md)
- [human taste analysis JSON](../../experiments/frontier_sweep_banded_frontier_focus/human_rating_analysis.json)

## Result

The strongest signal is that human taste is not identical to the current
machine frontier score.

| metric | pearson with human score | spearman with human score |
|---|---:|---:|
| `readable_ontology_frontier` | 0.447 | 0.389 |
| `frontier_quality` | 0.487 | 0.209 |
| `graph_integration` | 0.639 | 0.486 |
| `unfinished` | -0.648 | -0.593 |
| `score_total` | 0.287 | 0.117 |

This is small-n, so the point is not final calibration. The point is direction:
the observer is finding some of the right territory, but it is not yet a taste
model.

## Highest-Rated Examples

| id | picked | human | frontier | ontology | readability | note |
|---|---:|---:|---:|---:|---:|---|
| `steer_alpha_0p45_c12_tok140_s3_c4_6` | 0 | 8.5 | 0.217 | 0.718 | 0.614 | neicelt distorted |
| `steer_alpha_0p6_c12_tok140_s1_c2_12` | 0 | 8.5 | 0.223 | 0.569 | 0.717 | odd |
| `steer_alpha_0p6_c12_tok140_s2_c1_8` | 1 | 8.0 | 0.089 | 0.274 | 0.658 | daydreaming |
| `steer_alpha_0p6_c12_tok140_s5_c1_11` | 1 | 8.0 | 0.253 | 0.561 | 0.915 | plain but not bad |

Two of the top four rows were not picked by the selector. This is the most
useful failure: the candidate pool already contains material closer to the
human taste target than the current picked path.

## Interpretation

The human notes prefer:

- oddness
- daydream drift
- distorted but still readable image motion
- plainness when it produces pressure rather than ornament

The human notes penalize:

- metaphors that are too well-made
- predictable logical threads
- writing that is too polished
- cliche
- hard interruption
- ornamental over-gorgeousness

That means the next selector should not simply maximize readability or frontier
quality. A very high readability score can coincide with predictability, and a
high frontier score can still feel too polished.

The current best taste hypothesis is:

```text
human-interest frontier =
  readable ontology movement
  + graph integration
  + affordance/category disturbance
  + oddness / daydream pressure
  - hard truncation
  - cliche/polish/ornament pressure
  - over-predictable narrative continuity
```

## Selector Implication

`banded-frontier` remains the best live selector so far, but the first human
rating pass suggests a new layer on top of it:

```text
banded-frontier first:
  keep text readable and non-broken

human-taste rerank second:
  prefer odd, distorted, less predictable candidates inside that safe band
```

The clean next experiment is not a larger alpha sweep. It is a taste-aware
post-hoc reselection over the existing saved pool, followed by one focused live
generation run if the human-taste reranker looks promising.

## Caveat

The Markdown reading view is the human-facing surface and can be edited by hand.
The CSV and JSON run artifacts remain the canonical generated text. If a reading
view text is manually changed while rating, treat the score as a taste note that
may need a second pass against the canonical generated candidate.

# Research Note: Post-hoc Selector Lab

Date: 2026-05-16

## Question

The focused frontier sweep used `hybrid` with `choose=best`. The next question
was whether the saved candidate pools already contained stronger readable
frontier candidates that a different selector would have picked.

This experiment performs no new generation. It reuses the three focused sweep
runs and reselects each saved step with four objectives:

```text
depaysement
frontier
hybrid
pareto
```

## Experimental Setup

Command:

```bash
python3 -m depaysement_lab.cli reselect \
  experiments/frontier_sweep_steered_hybrid_focus_best/steer_alpha_0p45_c12_tok140.json \
  experiments/frontier_sweep_steered_hybrid_focus_best/steer_alpha_0p6_c12_tok140.json \
  experiments/frontier_sweep_steered_hybrid_focus_best/steer_alpha_0p75_c12_tok140.json \
  --select-objectives depaysement,frontier,hybrid,pareto \
  --choose best \
  --include-original \
  --unfinished-weight 1.10 \
  --repetition-weight 0.45 \
  --sprawl-weight 0.30 \
  --out-dir experiments/posthoc_reselect_focus_best_lab
```

Artifacts:

- [report](../../experiments/posthoc_reselect_focus_best_lab/posthoc_reselect_report.md)
- [generated text reading report](../../experiments/posthoc_reselect_focus_best_lab/posthoc_reselect_texts.md)
- [candidate CSV](../../experiments/posthoc_reselect_focus_best_lab/posthoc_reselect_candidates.csv)
- [plot](../../experiments/posthoc_reselect_focus_best_lab/posthoc_reselect.png)
- [manifest](../../experiments/posthoc_reselect_focus_best_lab/posthoc_reselect_manifest.json)

## Results

| condition | picked frontier | lift | picked ontology | picked readability | picked unfinished | picked hit rate |
|---|---:|---:|---:|---:|---:|---:|
| `alpha=0.45 original hybrid` | 0.122 | +0.093 | 0.485 | 0.600 | 0.160 | 0.40 |
| `alpha=0.45 depaysement` | 0.015 | -0.014 | 0.117 | 0.615 | 0.160 | 0.00 |
| `alpha=0.45 frontier` | 0.160 | +0.130 | 0.647 | 0.591 | 0.160 | 0.60 |
| `alpha=0.45 pareto` | 0.155 | +0.125 | 0.592 | 0.598 | 0.160 | 0.60 |
| `alpha=0.60 original hybrid` | 0.123 | +0.078 | 0.344 | 0.695 | 0.080 | 0.60 |
| `alpha=0.60 depaysement` | 0.005 | -0.040 | 0.018 | 0.693 | 0.160 | 0.00 |
| `alpha=0.60 frontier` | 0.194 | +0.149 | 0.620 | 0.659 | 0.080 | 0.80 |
| `alpha=0.60 pareto` | 0.111 | +0.065 | 0.313 | 0.694 | 0.080 | 0.80 |
| `alpha=0.75 original hybrid` | 0.102 | +0.069 | 0.307 | 0.660 | 0.000 | 1.00 |
| `alpha=0.75 depaysement` | 0.061 | +0.028 | 0.208 | 0.648 | 0.160 | 0.80 |
| `alpha=0.75 frontier` | 0.110 | +0.076 | 0.429 | 0.618 | 0.080 | 0.80 |
| `alpha=0.75 pareto` | 0.102 | +0.069 | 0.307 | 0.660 | 0.000 | 1.00 |

Changed steps:

| source alpha | depaysement | frontier | hybrid | pareto |
|---|---:|---:|---:|---:|
| `0.45` | 3 / 5 | 2 / 5 | 0 / 5 | 1 / 5 |
| `0.60` | 3 / 5 | 3 / 5 | 0 / 5 | 2 / 5 |
| `0.75` | 3 / 5 | 2 / 5 | 0 / 5 | 0 / 5 |

## Interpretation

The old depaysement objective is clearly not frontier-aware. On the two most
interesting pools, it collapses picked frontier quality:

```text
alpha=0.45: 0.122 -> 0.015
alpha=0.60: 0.123 -> 0.005
```

This is a useful negative control. It shows that high structural depaysement
score is not the same thing as readable ontology collapse.

The pure `frontier` objective finds stronger frontier candidates in all three
source pools, with the largest gain at `alpha=0.60`:

```text
alpha=0.60 frontier reselect:
picked_frontier = 0.194
selection_lift = +0.149
picked_ontology = 0.620
picked_readability = 0.659
picked_unfinished = 0.080
```

That is the clearest evidence so far that the candidate pool contains more
frontier material than the current production selector is willing to pick.

The `hybrid` result is identical to the original focused sweep because the
source artifacts were generated with `hybrid` and deterministic `choose=best`.
This is a good reproducibility check.

`pareto` is mixed. It nearly matches pure frontier at `alpha=0.45`, but is more
conservative at `alpha=0.60`. This suggests that Pareto front eligibility may be
useful as a filter, but needs a sharper tie-breaker if the goal is to walk the
upper frontier envelope.

## Working Claim

The generator and steering are already producing readable frontier candidates.
The main bottleneck is now selector policy:

```text
generation: sufficient to produce candidates
steering: moves the pool
selector: decides whether frontier material is surfaced
human reading: decides whether the surfaced text is actually good
```

The most promising next selector is not pure `frontier`, because pure frontier
can still pick high-collapse, low-readability tails. The next version should be
a banded frontier selector:

```text
maximize readable_ontology_frontier
inside an ontology/readability/unfinished/repair band
with a stronger penalty for malformed tails
```

## Caveats

- This is not a counterfactual generation trajectory. If step 2 changes, step 3
  is still selected from the originally saved step 3 candidate pool.
- The experiment uses one seed and one model.
- The `unfinished` signal remains coarse.
- The frontier metric should be treated as a discovery instrument. The reading
  report is still necessary for taste-level evaluation.

## Next Steps

1. Add a `banded-frontier` objective or tune `hybrid` toward frontier recovery
   while preserving the readability band.
2. Export a compact human-rating sheet from original, frontier, hybrid, and
   Pareto picked texts.
3. Repeat the no-generation reselect lab across 3-5 seeds before spending more
   time on new MLX generation.
4. Split unfinished detection into hard truncation, malformed tail, quote-tail,
   comma chain, and repetition loop.

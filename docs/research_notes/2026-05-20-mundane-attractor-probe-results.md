# Research Note: Mundane Attractor Probe Results

Date: 2026-05-20

## Question

The pre-result design note asked whether the attractor cluster

```text
antique / music box / porcelain / miniature / forgotten / clock / leather-bound
```

comes from base-model/prompt prior, the original steering vector, selector
affordance, or recursive context amplification.

This note records the first causal probe results.

## Artifacts

- Pre-result design:
  [2026-05-20-mundane-attractor-causal-probe.md](2026-05-20-mundane-attractor-causal-probe.md)
- Probe 1, steering disabled:
  [summary](../../experiments/frontier_sweep_mundane_base_control_small/attractor_probe_summary.md)
- Probe 2, original vector + anchor guard:
  [summary](../../experiments/frontier_sweep_mundane_anchor_guard_small/attractor_probe_summary.md)
- Probe 1 vs Probe 2:
  [comparison](../../experiments/frontier_sweep_mundane_anchor_guard_small/base_vs_steered_comparison.md)
- Probe 3, anti-attractor vector:
  [summary](../../experiments/frontier_sweep_mundane_anti_attractor_small/attractor_probe_summary.md)
- All-vector comparison:
  [comparison](../../experiments/frontier_sweep_mundane_anti_attractor_small/vector_comparison_summary.md)
- Probe 4, one-step contamination check:
  [summary](../../experiments/frontier_sweep_mundane_step1_contamination_check/step1_attractor_summary.md)
- Anti-attractor vector metadata:
  [metadata](../../experiments/depaysement_mlx_vectors_l4_18_anti_attractor.npz.json)

## Setup

All three probes used:

- model: local snapshot of `mlx-community/Llama-3.2-3B-Instruct-4bit`
- layers: `4-18`
- seed bank: `data/mundane_seed_bank_en_v1.json`
- seed limit: `4`
- steps: `3`
- candidates: `12`
- max new tokens: `120`
- selector: `hybrid`
- choose: `best`
- anchor guard:

```text
cliche_weight = 0.25
fantasy_prop_weight = 1.10
ordinary_anchor_weight = 0.90
ordinary_anchor_min = 0.35
unfinished_weight = 1.25
repetition_weight = 0.55
sprawl_weight = 0.75
```

The conditions were:

| probe | vector condition | alphas |
|---|---|---|
| Probe 1 | steering disabled | `0.66` selector label only |
| Probe 2 | original `depaysement_mlx_vectors_l4_18.npz` | `0.66,0.77` |
| Probe 3 | `depaysement_mlx_vectors_l4_18_anti_attractor.npz` | `0.40,0.55,0.66` |

## Main Quantitative Result

| condition | kind | rows | frontier | read | cliche | fantasy_prop | ordinary_anchor | unfinished_rate | music_box | porcelain | miniature/tiny | antique | leather_bound |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| steering disabled | pool | 143 | 0.007 | 0.713 | 0.054 | 0.017 | 0.508 | 0.056 | 0 | 2 | 2 | 3 | 0 |
| steering disabled | picked | 12 | 0.019 | 0.774 | 0.056 | 0.000 | 0.639 | 0.000 | 0 | 0 | 0 | 0 | 0 |
| original vector | pool | 288 | 0.014 | 0.750 | 0.231 | 0.222 | 0.569 | 0.087 | 21 | 29 | 62 | 23 | 24 |
| original vector | picked | 24 | 0.030 | 0.825 | 0.069 | 0.017 | 0.712 | 0.000 | 0 | 0 | 5 | 0 | 0 |
| anti-attractor vector | pool | 432 | 0.011 | 0.616 | 0.005 | 0.002 | 0.624 | 0.150 | 0 | 1 | 6 | 0 | 0 |
| anti-attractor vector | picked | 36 | 0.023 | 0.709 | 0.000 | 0.000 | 0.690 | 0.056 | 0 | 0 | 0 | 0 | 0 |

## Interpretation

The disabled-steering control weakens a pure base-prior explanation. With the
same model, prompt style, seeds, and selector, the candidate pool had very low
fantasy-prop pressure:

```text
pool fantasy_prop = 0.017
picked fantasy_prop = 0.000
music_box pool hits = 0
```

The original vector strongly increases the stock-prop basin in the candidate
pool:

```text
pool fantasy_prop: 0.017 -> 0.222
pool cliche:       0.054 -> 0.231
music_box hits:    0 -> 21
porcelain hits:    2 -> 29
miniature/tiny:    2 -> 62
leather_bound:     0 -> 24
```

The anchor guard then prevents most of those candidates from being picked:

```text
original vector picked fantasy_prop = 0.017
original vector picked music_box = 0
original vector picked porcelain = 0
```

So the selector is not the source of the basin, but it can either expose or
hide it.

The anti-attractor vector is the strongest causal result. It moves the candidate
pool itself away from the antique/music-box/porcelain basin:

```text
original vector pool fantasy_prop = 0.222
anti-attractor pool fantasy_prop = 0.002

original vector pool cliche = 0.231
anti-attractor pool cliche = 0.005

original vector music_box hits = 21
anti-attractor music_box hits = 0
```

This supports the original-vector hypothesis: vector geometry is a major cause
of the attractor cluster, not merely downstream selection.

## Cost Of The Anti-attractor Vector

The anti-attractor vector is not simply better. It suppresses stock props, but
also makes the text less fluent:

```text
original vector pool readability = 0.750
anti-attractor pool readability = 0.616

original vector pool unfinished = 0.087
anti-attractor pool unfinished = 0.150
```

Qualitatively, the anti-attractor top frontier candidates return toward ordinary
objects such as receipt, folder, paper, hinge, ladder, bag, and highlighter, but
they more often become rough, procedural, or broken.

This means the anti-attractor vector is useful as a causal instrument, but not
yet as a production steering vector.

## Hypothesis Update

### H1: Base-Prior Hypothesis

Weakened. The base/prompt condition can produce occasional generic terms, but
not the strong repeated basin seen under the original vector.

### H2: Original-Vector Hypothesis

Strengthened. The original vector substantially increases candidate-pool hits
for music box, porcelain, miniature/tiny, antique, and leather-bound.

### H3: Prompt-Manifold Hypothesis

Still plausible as a background factor, but not sufficient by itself in this
small control. The prompt may provide the shape of the task; the vector appears
to move the model into the stock-prop neighborhood.

### H4: Selector-Affordance Hypothesis

Strengthened but clarified. The selector is not the origin of the basin. It is a
surface policy: without anchor guard, it may surface stock-prop candidates
because they are readable and relation-rich; with anchor guard, it can avoid
most of them.

### H5: Recursion-Amplification Hypothesis

Weakened as a root-cause explanation, but still plausible as an amplifier. The
one-step contamination check shows that the basin already appears in the first
candidate pool under the original vector.

## One-step Contamination Check

Probe 4 used only one generation step, with 8 mundane seeds and 24 candidates
per seed. This isolates the first candidate pool before any generated context
can recursively contaminate later steps.

| alpha | kind | rows | frontier | read | cliche | fantasy_prop | music_box | porcelain | miniature/tiny | forgotten | clock/watch | leather_bound | antique |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.00` | pool | 192 | 0.010 | 0.675 | 0.023 | 0.014 | 0 | 0 | 10 | 4 | 4 | 1 | 3 |
| `0.66` | pool | 192 | 0.012 | 0.708 | 0.274 | 0.281 | 17 | 29 | 46 | 12 | 15 | 18 | 25 |
| `0.77` | pool | 192 | 0.012 | 0.743 | 0.316 | 0.315 | 28 | 29 | 47 | 28 | 22 | 14 | 39 |
| `0.00` | picked | 8 | 0.008 | 0.803 | 0.000 | 0.000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `0.66` | picked | 8 | 0.001 | 0.829 | 0.167 | 0.222 | 0 | 2 | 3 | 0 | 0 | 0 | 0 |
| `0.77` | picked | 8 | 0.005 | 0.860 | 0.208 | 0.172 | 0 | 2 | 2 | 1 | 1 | 0 | 0 |

This is the cleanest evidence so far that recursion is not required to start the
attractor basin. The original vector moves the first candidate pool toward the
stock-prop register immediately:

```text
step-1 pool fantasy_prop:
alpha 0.00 = 0.014
alpha 0.66 = 0.281
alpha 0.77 = 0.315

step-1 pool music_box:
alpha 0.00 = 0
alpha 0.66 = 17
alpha 0.77 = 28

step-1 pool porcelain:
alpha 0.00 = 0
alpha 0.66 = 29
alpha 0.77 = 29
```

The picked rows also show some contamination because Probe 4 intentionally used
the documented selector command without the later anchor-guard weights. This is
useful: it shows why anchor guard matters as an output hygiene layer, even
though it is not the causal source of the basin.

## Working Claim After Probes 1-3

The best current explanation is:

```text
The original vector pushes Llama-3.2-3B-Instruct-4bit toward a
time/object/memory miniature-prop region. The prompt gives that region a
visible-scene task. The model fills the region with familiar antique,
porcelain, music-box, miniature, and leather-bound affordances. The selector can
surface or suppress those candidates, but the distribution shift is already
present in the first candidate pool.
```

The anti-attractor vector proves that this distribution is steerable, but it
overcorrects into lower readability and more unfinished text.

## Next Steps

1. Try a softer anti-attractor vector:
   - fewer weird-noise negatives;
   - keep anti-prop negatives, but remove repetition-heavy lines;
   - possibly use only `0.35-0.55` alpha.
2. Try vector blending or two-stage selection:
   - original vector for frontier lift;
   - anti-attractor penalty for selection;
   - human reading pass on ordinary-anchor survivors.
3. Add a small result sheet with example pairs:
   - original vector failure;
   - anti-attractor correction;
   - anti-attractor overcorrection.

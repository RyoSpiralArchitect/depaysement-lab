# Research Note: Soft Anti-attractor Vector

Date: 2026-05-21

## Question

The hard anti-attractor vector almost eliminated the
`antique / music box / porcelain / miniature / leather-bound` basin, but it also
lowered readability and increased unfinished pressure.

This probe asks whether that roughness came mainly from overly noisy negative
examples.

## Change From The Hard Bank

The hard bank used eight stock-prop negatives, including repetition-heavy lines:

```text
Porcelain, antique, velvet, clockwork, crystal, miniature, miniature, miniature.
mist mist moonlit mist, ornate ornate porcelain, the end.
```

The soft v2 bank removes those repetition/noise negatives. It keeps only fluent
stock-prop negatives, and adds more ordinary-object positives:

- receipt, folder, bus ticket, mug, printer tray, grocery bag;
- elevator button, delivery label, refrigerator shelf, stapler;
- fluent negatives about antique music boxes, porcelain dolls, leather-bound
  diaries, miniature clockwork gardens, velvet cases, and pocket watches.

Bank:

- `data/anti_attractor_bank_en_v2_soft.json`
- `configs/anti_attractor_bank_en_v2_soft.json`

Vector:

- `experiments/depaysement_mlx_vectors_l4_18_anti_attractor_soft_v2.npz`
- `experiments/depaysement_mlx_vectors_l4_18_anti_attractor_soft_v2.npz.json`

## Setup

Command:

```bash
PYTHONPATH=src PYTHONNOUSERSITE=1 python3 -m depaysement_lab.cli frontier-sweep \
  --backend mlx \
  --model /Users/ryospiralarchitect/.hf_home/hub/models--mlx-community--Llama-3.2-3B-Instruct-4bit/snapshots/7f0dc925e0d0afb0322d96f9255cfddf2ba5636e \
  --vectors experiments/depaysement_mlx_vectors_l4_18_anti_attractor_soft_v2.npz \
  --steer-layers 4-18 \
  --seed-bank data/mundane_seed_bank_en_v1.json \
  --seed-limit 4 \
  --steps 3 \
  --alphas 0.35,0.45,0.55 \
  --candidate-grid 12 \
  --max-token-grid 120 \
  --select-objective hybrid \
  --choose best \
  --save-candidates 12 \
  --cliche-weight 0.25 \
  --fantasy-prop-weight 1.10 \
  --ordinary-anchor-weight 0.90 \
  --ordinary-anchor-min 0.35 \
  --unfinished-weight 1.25 \
  --repetition-weight 0.55 \
  --sprawl-weight 0.75 \
  --out-dir experiments/frontier_sweep_mundane_anti_attractor_soft_v2_small
```

Artifacts:

- [soft vector comparison](../../experiments/frontier_sweep_mundane_anti_attractor_soft_v2_small/soft_vector_comparison_summary.md)
- [soft vector summary](../../experiments/frontier_sweep_mundane_anti_attractor_soft_v2_small/attractor_probe_summary.md)
- [reading report](../../experiments/frontier_sweep_mundane_anti_attractor_soft_v2_small/frontier_sweep_texts.md)
- [manifest](../../experiments/frontier_sweep_mundane_anti_attractor_soft_v2_small/frontier_sweep_manifest.json)

## Result

| condition | kind | rows | frontier | read | cliche | fantasy_prop | ordinary_anchor | unfinished_rate | music_box | porcelain | miniature/tiny | antique | leather_bound |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base control | pool | 143 | 0.007 | 0.713 | 0.054 | 0.017 | 0.508 | 0.056 | 0 | 2 | 2 | 3 | 0 |
| original vector | pool | 288 | 0.014 | 0.750 | 0.231 | 0.222 | 0.569 | 0.087 | 21 | 29 | 62 | 23 | 24 |
| hard anti-attractor | pool | 432 | 0.011 | 0.616 | 0.005 | 0.002 | 0.624 | 0.150 | 0 | 1 | 6 | 0 | 0 |
| soft anti-attractor v2 | pool | 432 | 0.009 | 0.606 | 0.026 | 0.015 | 0.673 | 0.157 | 1 | 1 | 7 | 5 | 4 |

Picked rows stayed clean under anchor guard:

| condition | picked read | picked cliche | picked fantasy_prop | picked unfinished |
|---|---:|---:|---:|---:|
| original vector | 0.825 | 0.069 | 0.017 | 0.000 |
| hard anti-attractor | 0.709 | 0.000 | 0.000 | 0.056 |
| soft anti-attractor v2 | 0.726 | 0.019 | 0.000 | 0.000 |

Soft v2 by alpha:

| alpha | pool read | pool cliche | pool fantasy_prop | pool unfinished | picked read | picked fantasy_prop |
|---|---:|---:|---:|---:|---:|---:|
| `0.35` | 0.641 | 0.028 | 0.018 | 0.188 | 0.796 | 0.000 |
| `0.45` | 0.615 | 0.044 | 0.021 | 0.097 | 0.710 | 0.000 |
| `0.55` | 0.563 | 0.007 | 0.006 | 0.188 | 0.671 | 0.000 |

## Interpretation

Soft v2 did suppress the attractor basin:

```text
original vector pool fantasy_prop = 0.222
soft v2 pool fantasy_prop        = 0.015
```

But it did not recover fluency:

```text
base control pool readability    = 0.713
original vector pool readability = 0.750
hard anti-attractor readability  = 0.616
soft v2 readability              = 0.606
```

It also did not improve unfinished pressure:

```text
base control unfinished    = 0.056
original vector unfinished = 0.087
hard anti-attractor        = 0.150
soft v2                    = 0.157
```

This weakens the hypothesis that the hard vector's roughness came mainly from
repetition-heavy negative examples. The roughness appears to be tied to the
anti-attractor direction itself: pushing away from the stock-prop manifold also
pushes away from a region where this small model has fluent, ready-made scene
syntax.

## Qualitative Read

The best soft-v2 examples are closer to ordinary objects than the original
vector:

```text
As the folder opens its flaps a small wave rises above the surface...
Inside the folder a paper and pen are stuck together with glue.
```

```text
A blue mug on the countertop has become a temporary home for a small,
forgotten notebook...
```

But failures often become procedural, list-like, or syntactically strained:

```text
a hand holds up a paper with the name scribbled on it and 2 fingers are
inserted into the pencil...
```

So the vector is successful as avoidance, but not yet as production style.

## Updated Claim

The antique/music-box/porcelain basin is not merely a bad word list. It is a
fluent local manifold for this model: it supplies object affordances, scene
syntax, and memory/time cues. Removing it by vector steering also removes some
of the model's easiest fluency scaffold.

The next production strategy should not be "stronger anti-attractor vector."
It should preserve the original vector's fluency while controlling the basin at
selection or composition time.

## Next Step

The next most promising direction is a two-stage or blended strategy:

1. Generate with the original vector, because it has the best readability.
2. Select with anchor guard, because it keeps picked rows mostly clean.
3. Add a second-pass ordinary-anchor/tail filter or human rating sheet focused
   on picked survivors.

A second possible direction is vector blending:

```text
blend = normalize(original_vector + lambda * anti_attractor_vector)
```

with small `lambda`, then sweep `lambda` rather than only alpha. This may keep
the original vector's fluent scene manifold while nudging away from stock props.

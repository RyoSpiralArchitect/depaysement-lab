# Research Note: Mundane Attractor Causal Probe

Date: 2026-05-20

## Question

The mundane seed probe surfaced a repeated attractor cluster:

```text
antique / music box / porcelain / miniature / forgotten / clock / leather-bound
```

The next goal is not only to suppress these words. The goal is to explain why a
steered Llama-3.2-3B-Instruct-4bit run reaches this cluster from ordinary seeds.

We want to separate four possible causes:

1. the base model already prefers this stock magic-realist register;
2. the original steering vector points toward time/object/memory props;
3. the prompt asks for a visible ontology shift in a way that invites familiar
   miniature-antique props;
4. the selector rewards legible frontier candidates, and these props are an easy
   way to make high-displacement text readable.

## Prior Evidence

The first mundane sweep completed 40 steered conditions:

- vectors: `experiments/depaysement_mlx_vectors_l4_18.npz`
- model: `mlx-community/Llama-3.2-3B-Instruct-4bit`
- layers: `4-18`
- seed bank: `data/mundane_seed_bank_en_v1.json`
- alphas: `0.66,0.72,0.77,0.82,0.88`
- selector: `banded-frontier`

Important observations from that run:

- The positive bank contains `clock`, but does not directly contain `music box`,
  `porcelain`, `miniature`, or `leather-bound`.
- The mundane seed bank does not contain the tracked attractor terms.
- Attractor words appear already in step 1 picked continuations, so recursion
  from earlier selected text cannot be the only cause.
- Higher alpha did not cleanly increase useful frontier quality; it increased
  cliche and unfinished pressure.

Post-hoc selector probes then showed:

- A high `cliche_weight` can reduce generic magic-realist vocabulary, but it also
  lowers frontier/readability.
- The newer anchor guard, which combines `fantasy_prop_weight` with
  `ordinary_anchor_weight`, can choose away from some attractor candidates inside
  the saved pool. In the existing 40-run pool, `music box` picked-row hits fell
  from `93` to `58`, and `porcelain` from `115` to `59` under the strongest
  hybrid anchor-guard setting.

This is evidence that the saved candidate pools contain alternatives, but also
that the frontier metric and the stock-prop basin are entangled.

## What We Are Going To Look At

We will look at three readout levels rather than only final prose:

1. candidate-pool distribution: how often the attractor terms are generated at
   all;
2. picked-row distribution: what the selector surfaces;
3. text-level reading: whether lower attractor counts still preserve
   depaysement rather than collapsing into plain realism.

The main quantitative readouts are:

- `readable_ontology_frontier`
- `syntax_readability_proxy`
- `ontology_collapse_density`
- `cliche_attractor_score`
- `fantasy_prop_score`
- `ordinary_anchor_retention`
- unfinished/truncation rate
- picked-row and candidate-row hits for:

```text
music box
porcelain
miniature/tiny
forgotten
clock/watch/clockwork
leather-bound
antique
doll/ballerina
velvet/crystal
```

The qualitative reading question is:

```text
Does the candidate still transform the ordinary seed object, or does it replace
the seed with a familiar literary prop?
```

## Why These Settings

The alpha band starts around `0.66-0.77` because the mundane probe showed that
this was the strongest practical region for the original vector. Above `0.82`,
unfinished and cliche-heavy candidates rose without a clean frontier benefit.

The candidate count is reduced from `19` to `12` for small causal probes. We are
not trying to maximize the best possible candidate yet. We are trying to compare
conditions cheaply while keeping enough pool diversity to see whether the
attractor is generated before selection.

The step count is reduced from `5` to `3` for most probes, and to `1` for the
contamination check. The attractor already appears in step 1, so long recursive
runs are unnecessary for the first causal separation.

The anchor-guard selector uses:

```text
cliche_weight = 0.25
fantasy_prop_weight = 1.10
ordinary_anchor_weight = 0.90
ordinary_anchor_min = 0.35
unfinished_weight = 1.25
repetition_weight = 0.55
sprawl_weight = 0.75
```

The intent is not to ban the words outright. The intent is to penalize the stock
miniature-antique basin while requiring the candidate to keep some pressure from
the mundane seed. `forgotten` and plain `clock` are not treated as hard fantasy
props because they can be ordinary seed material or direct vector material.

The anti-attractor bank is built with:

- positive examples: ordinary objects undergoing concrete depaysement;
- negative realist examples: plain repair/explanation;
- negative weird-noise examples: antique/music-box/porcelain/miniature stock
  props and repetition.

This makes the vector test stricter. If the anti-attractor vector lowers the
candidate-pool hit rate, then generation itself can be moved away from the basin.
If it only changes picks, the selector is doing most of the work.

## Hypotheses

### H1: Base-Prior Hypothesis

Llama-3.2-3B-Instruct-4bit already treats visible surreal continuation as a
route toward antique, miniature, porcelain, clockwork, and leather-bound props.

Expected evidence:

- disabled-steering control still produces many attractor terms;
- alpha does not strongly predict candidate-pool attractor rate;
- anchor guard reduces picked terms but candidate pools remain saturated.

### H2: Original-Vector Hypothesis

The original positive-minus-negative vector pushes toward a time/object/memory
region. `clock` is directly present in the positive bank, and the model fills
nearby latent space with music boxes, porcelain figures, and leather-bound books.

Expected evidence:

- alpha `0.66-0.77` increases candidate-pool attractor rate versus alpha `0`;
- the increase is visible already at step 1;
- anti-attractor vectors reduce candidate-pool hit rates more than selector-only
  changes do.

### H3: Prompt-Manifold Hypothesis

The scene prompt asks for unlike things in one concrete place, no explanation,
and a visible relation. That instruction resembles a familiar magic-realist
writing task, so the model reaches for compact props that can carry memory,
agency, containment, and transformation.

Expected evidence:

- disabled-steering runs still show the register;
- prompt or ban-list ablations change candidate-pool terms even with the same
  vector;
- attractors are more common in candidates with high readability and high
  relation structure.

### H4: Selector-Affordance Hypothesis

The selector is not causing the words to be generated, but it prefers them
because they cheaply satisfy readable ontology collapse. A music box can open,
sing, contain a doll, mark time, remember, and sit in a scene with little syntax
risk.

Expected evidence:

- candidate pools contain alternatives with fewer fantasy props;
- anchor guard changes picked rows more than it changes pool rows;
- fantasy-prop reduction comes with some frontier loss, showing that the
  attractor was propping up metric-friendly displacement.

### H5: Recursion-Amplification Hypothesis

Once an attractor appears in step 1, motif selection and running context make it
more likely to persist in later steps.

Expected evidence:

- step-1 hit rates are lower than full-run hit rates;
- changing step-1 selection changes downstream terms in live generation;
- post-hoc reselection helps less than live reselection, because downstream
  candidate pools were generated from the original context.

## Probe Matrix

| probe | condition | what it separates |
|---|---|---|
| base control | original prompt, steering disabled | base-model/prompt prior vs vector effect |
| original vector + anchor guard | original vector, new selector | selection hygiene vs generator distribution |
| anti-attractor vector | new bank, new vector, anchor guard | whether vector geometry can move generation away from stock props |
| step-1 contamination check | one-step runs at alpha `0,0.66,0.77` | initial generation prior vs recursive context amplification |

## Commands

### Probe 1: Base Prior Control

```bash
PYTHONPATH=src PYTHONNOUSERSITE=1 python3 -m depaysement_lab.cli frontier-sweep \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --vectors experiments/depaysement_mlx_vectors_l4_18.npz \
  --disable-steering \
  --seed-bank data/mundane_seed_bank_en_v1.json \
  --seed-limit 4 \
  --steps 3 \
  --alphas 0.66 \
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
  --out-dir experiments/frontier_sweep_mundane_base_control_small
```

### Probe 2: Original Vector With Anchor Guard

```bash
PYTHONPATH=src PYTHONNOUSERSITE=1 python3 -m depaysement_lab.cli frontier-sweep \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --vectors experiments/depaysement_mlx_vectors_l4_18.npz \
  --steer-layers 4-18 \
  --seed-bank data/mundane_seed_bank_en_v1.json \
  --seed-limit 4 \
  --steps 3 \
  --alphas 0.66,0.77 \
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
  --out-dir experiments/frontier_sweep_mundane_anchor_guard_small
```

### Probe 3: Anti-attractor Vector

Collect vectors:

```bash
PYTHONPATH=src PYTHONNOUSERSITE=1 python3 -m depaysement_lab.cli collect-mlx-vectors \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --bank data/anti_attractor_bank_en_v1.json \
  --out experiments/depaysement_mlx_vectors_l4_18_anti_attractor.npz \
  --layers 4-18 \
  --token-strategy mean
```

Run the small sweep:

```bash
PYTHONPATH=src PYTHONNOUSERSITE=1 python3 -m depaysement_lab.cli frontier-sweep \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --vectors experiments/depaysement_mlx_vectors_l4_18_anti_attractor.npz \
  --steer-layers 4-18 \
  --seed-bank data/mundane_seed_bank_en_v1.json \
  --seed-limit 4 \
  --steps 3 \
  --alphas 0.40,0.55,0.66 \
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
  --out-dir experiments/frontier_sweep_mundane_anti_attractor_small
```

### Probe 4: One-step Contamination Check

```bash
PYTHONPATH=src PYTHONNOUSERSITE=1 python3 -m depaysement_lab.cli frontier-sweep \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --vectors experiments/depaysement_mlx_vectors_l4_18.npz \
  --steer-layers 4-18 \
  --seed-bank data/mundane_seed_bank_en_v1.json \
  --seed-limit 8 \
  --steps 1 \
  --alphas 0,0.66,0.77 \
  --candidate-grid 24 \
  --max-token-grid 120 \
  --select-objective hybrid \
  --choose best \
  --save-candidates 24 \
  --out-dir experiments/frontier_sweep_mundane_step1_contamination_check
```

## Interpretation Table

| result pattern | likely reading |
|---|---|
| high attractors with steering disabled | base-prior or prompt-manifold effect is strong |
| low disabled-steering attractors, high steered attractors | original vector is a major cause |
| anchor guard lowers picked rows but not pool rows | selector can hide the issue, but generation still sits in the basin |
| anti-attractor vector lowers pool rows | vector geometry can move the generator away from the basin |
| step-1 hits already high | recursion is an amplifier, not the root cause |
| step-1 hits low but later hits high | motif/context recursion is a major cause |
| fantasy-prop score drops while frontier collapses | current frontier depends too much on stock prop affordances |
| fantasy-prop score drops while frontier survives | ordinary-object depaysement can be selected cleanly |

## Pre-result Working Claim

The most likely explanation is an interaction:

```text
original vector pushes toward time/object/memory displacement
+ scene prompt asks for legible non-explanatory transformation
+ Llama fills that neighborhood with stock antique miniature props
+ selector rewards them because they are readable and relation-rich
+ recursive context preserves them once picked
```

This claim should be weakened if disabled-steering controls show the same
attractor rate as steered runs. It should be strengthened if anti-attractor
vectors reduce candidate-pool hits, especially in step 1.

## Reporting Plan

After running probes, each result note should include:

- command and manifest path;
- candidate-pool hit rates and picked-row hit rates;
- frontier/readability/ontology/fantasy/anchor summary table;
- three good examples where ordinary anchors survive;
- three failure examples where the attractor persists;
- a short update to the hypothesis table above.

The final research narrative should distinguish:

```text
avoidance as output hygiene
vs.
causal explanation of the attractor basin
```

Those are related, but not the same result.

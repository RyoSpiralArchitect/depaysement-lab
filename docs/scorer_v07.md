# v0.7 structural scorer notes

v0.7 responds to the main audit point in v0.6: the scorer claimed to target the **structure** of depaysement, but several central features still depended on a hard-coded concept lexicon. This made the Magritte/Kafka-ish vocabulary into part of the reward surface.

The current CLI uses `depaysement_lab.scorer_v07.make_scorer_v07` by default. The old `proto_v2.DepaysementScorer` remains in the repo as a legacy/internal compatibility class, but the package CLI routes scoring through the v0.7 structural scorer.

## What changed

### 1. Lexicon is no longer the default skeleton

In the structural profile, lexicon prior is off by default.

```bash
depaysement-lab score "In the hospital corridor, the sea sleeps under a white sheet."
```

The trace should show:

```text
concepts=0.00 | pairs=0.00 | agency=0.00 | aesthetic=0.00
```

To explicitly opt into the old vocabulary/taste prior:

```bash
depaysement-lab score "..." --enable-lexicon --lexicon-prior-scale 0.18
```

`PAIR_BONUS` should be read as an authorial aesthetic prior, not a theoretical conclusion. It is valid as a taste profile only when the experiment declares it.

### 2. Bank scoring is explicit

Hash bank scoring is labeled lexical. It is not semantic contrast.

Default:

```text
bank_off=0.00
```

Lexical hash bank:

```bash
depaysement-lab score "..." --bank-score-mode hash
```

Embedding bank:

```bash
depaysement-lab score "..." --bank-score-mode embed --embed-model sentence-transformers/all-MiniLM-L6-v2
```

### 3. Relation quantity and relation integration are separated

v0.6 mostly counted whether relation schema types existed. v0.7 builds a rough anchor-relation-anchor graph.

Trace fields:

```text
rel_q   relation quantity
integr  graph integration: how much of the scene sits in one connected image
sprawl  penalty for too many weakly integrated object clusters
```

Example:

```bash
depaysement-lab score \
  "The umbrella's handle is now also wrapped around a miniature skyscraper constructed from discarded keys, tangled in a morass of sparklers, next to a dog's kennel made of rusted train car wheels, inside which a deceased pigeon lies, its eyes glued shut with a faint blue paint." \
  --graph
```

This should show high relation quantity but also high `sema_col` / `sprawl`, matching the audit: relation verbs exist, but the image becomes an of-chain / parallel object chain.

### 4. Run audit and human-eval scaffolds

Rescore a saved run under v0.7:

```bash
depaysement-lab audit-run experiments/umbrella_run.json
```

Export a human-rating template:

```bash
depaysement-lab export-eval-set experiments/umbrella_run.json \
  --out experiments/eval_umbrella.jsonl \
  --top-k 3
```

Fill `human_score` manually, then compute correlation:

```bash
depaysement-lab eval-correlate experiments/eval_umbrella.jsonl
```

This is meant to break the circularity where the scorer is both training target and evaluation target.

## Suggested ablations

For MLX generation without activation steering:

```bash
depaysement-lab write \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --chat-template \
  --disable-steering \
  --seed "A forgotten umbrella at the station" \
  --out experiments/no_steer.json
```

With activation steering:

```bash
depaysement-lab write \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --chat-template \
  --vectors experiments/depaysement_mlx_vectors.npz \
  --steer-alpha 0.6 \
  --steer-layers 6-16 \
  --seed "A forgotten umbrella at the station" \
  --out experiments/steer_alpha_0_6.json
```

Then compare:

```bash
depaysement-lab audit-run experiments/no_steer.json
depaysement-lab audit-run experiments/steer_alpha_0_6.json
```

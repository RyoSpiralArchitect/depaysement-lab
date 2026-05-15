# v0.8: coherence-preserving displacement observer

v0.8 turns the prototype from only a surreal image generator into an observation device for:

```text
controlled semantic displacement without coherence collapse
```

The phenomenon of interest is not “maximum weirdness.” It is:

```text
local heterogeneous collision
+ preserved scene/relation structure
+ preserved medium-range continuity
- ordinary realist/narrative repair
- semantic collage sprawl
```

## Command

```bash
depaysement-lab observe \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --chat-template \
  --vectors experiments/depaysement_mlx_vectors.npz \
  --steer-alpha 0.6 \
  --steer-layers 6-16 \
  --seed "A forgotten umbrella at the station" \
  --steps 4 \
  --candidates 8 \
  --out experiments/observe_umbrella.json
```

The command runs three conditions from the same seed:

1. `baseline`: ordinary coherent continuation.
2. `depaysement_rerank`: generate candidates, then select by the structural depaysement scorer.
3. `steering_plus_rerank`: activation steering plus the same external rerank, when vectors and a nonzero `--steer-alpha` are provided.

If vectors are not provided, the steered condition is skipped and the artifact records that explicitly.

## Metrics

For each step, v0.8 compares baseline and variant continuations.

### 1. semantic_continuity

```text
sim(context, continuation)
```

This asks whether the continuation still belongs to the local coherence manifold.

Important caveat: without `--embed-model`, this is `hash_ngram`, a lexical sketch. It is useful for smoke tests and rough continuity checks, but it is not semantic embedding. Pass `--embed-model sentence-transformers/...` for an actual embedding channel.

### 2. concept_distance_from_baseline

```text
JS(field_distribution(baseline), field_distribution(variant))
```

This is an audit-only concept-field channel using the built-in body/machine/nature/bureaucracy/etc. field lexicon. It is not part of the default scorer reward. Its job is to expose whether the variant moved away from the model’s ordinary continuation in concept-field topology.

### 3. relation graph preservation

The observer reuses the v0.7 `image_relation_graph`:

```text
object_count
relation_count
component_count
giant_ratio
relation_quantity
integration
cluster_sprawl
fragmentation
```

This separates “many relation words” from “one integrated visible image.” A candidate can have many `of`, `inside`, `wrapped`, and `tangled` relations while still being a loose object chain.

### 4. depaysement_lift

The compact observation score is:

```text
depaysement_lift =
  concept_distance_from_baseline
  + positive image_schema / relation / integration / ontology gains
  - coherence_loss
  - graph_fragmentation_delta
  - semantic_collage_penalty
  - collapse_penalty
  - meta_leak_penalty
```

This is not a final aesthetic truth. It is a diagnostic for the target window:

```text
concept_distance ↑
semantic_continuity maintained
relation_integration maintained
graph_fragmentation low
meta leak low
```

The artifact gives a coarse label:

```text
coherence_preserving_displacement
coherence_collapse
too_close_to_baseline
semantic_collage_or_sprawl
mixed
```

## Output artifact

`observe` writes JSON or JSONL:

```json
{
  "seed": "A forgotten umbrella at the station",
  "config": {"vectorizer_mode": "hash_ngram", "...": "..."},
  "runs": {
    "baseline": {...},
    "depaysement_rerank": {...},
    "steering_plus_rerank": {...}
  },
  "comparisons": {
    "depaysement_rerank_vs_baseline": {
      "steps": [...],
      "aggregate": {...},
      "interpretation": "..."
    }
  },
  "notes": [...]
}
```

Each run includes `context_before`, picked candidate scores, and graph diagnostics. With `--save-candidates N`, the top-N reranked candidates are stored for audit.

## Steering ablation

To test whether steering is doing more than the rerank shell:

```bash
depaysement-lab observe ... \
  --vectors experiments/depaysement_mlx_vectors.npz \
  --steer-alpha 0.6 \
  --out experiments/observe_with_steer.json

depaysement-lab observe ... \
  --skip-steered \
  --out experiments/observe_rerank_only.json
```

On tiny 3B/4bit models, expect the rerank shell to dominate. The steered condition becomes more meaningful on larger instruction-tuned models where positive-negative activation directions are less brittle.

## Mechanistic next step

The next module should capture token-wise hidden-state trajectories for:

```text
baseline generation
external-rerank selected candidate
steered+rerank selected candidate
```

The target diagnostic would be layer-by-layer divergence and reintegration:

```text
middle layers: concept displacement increases
later layers: syntactic / scene coherence re-integrates
```

v0.8 does not yet claim this mechanistic result. It only creates the saved artifacts and metrics needed to select promising runs for that deeper trajectory analysis.

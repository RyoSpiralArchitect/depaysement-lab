# MLX intervention module

v0.5 added an experimental MLX-specific internal intervention path.

The HF path uses PyTorch forward hooks. MLX does not mirror that interface, so this module uses a **swap-and-restore wrapper**:

```text
find layer sequence, e.g. model.model.layers
for selected layer i:
  original = layers[i]
  layers[i] = MLXPatchedLayer(original, i, vector=v_i, alpha=alpha)
run mlx_lm.generate(...)
restore originals
```

The wrapper assumes each transformer block returns either:

```text
hidden
(hidden, ...aux)
[hidden, ...aux]
```

It edits only the first hidden-like object and reconstructs the original return shape.

## Vector collection

```bash
depaysement-lab collect-mlx-vectors \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --bank data/depaysement_bank_en_v3.json \
  --out experiments/depaysement_mlx_vectors.npz \
  --layers 4-18 \
  --token-strategy mean \
  --chat-template \
  --verbose
```

This computes:

```text
v_l = mean_hidden_l(positive_depaysement)
    - mean_hidden_l(negative_realist_repair + negative_weird_noise)
v_l <- unit_normalize(v_l)
```

The vector archive contains arrays named `layer_0`, `layer_1`, etc. A JSON metadata sidecar is written beside it:

```text
experiments/depaysement_mlx_vectors.npz
experiments/depaysement_mlx_vectors.npz.json
```

## Generation-time injection

```bash
depaysement-lab write \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --vectors experiments/depaysement_mlx_vectors.npz \
  --steer-alpha 0.8 \
  --steer-layers 6-16 \
  --mlx-steer-apply-on decode_only \
  --chat-template \
  --seed "A forgotten umbrella at the station" \
  --steps 4 \
  --candidates 8 \
  --trace
```

The injection rule is:

```text
h_l <- h_l + alpha * v_l
```

`--steer-position last` edits only the last sequence position of the current forward pass. `--steer-position all` edits every position.

`--mlx-steer-apply-on` controls *when* the edit fires:

```text
decode_only   sequence length <= 1; conservative default for cached decoding
all           prefill and decode; stronger but can distort the prompt manifold
prefill_only  diagnostic mode
```

## Practical sweep

Start conservative:

```text
layers: middle third of the model
alpha: 0.3, 0.6, 0.9, 1.2
apply_on: decode_only
position: last
```

Then compare against:

```text
same seed + no vectors
same seed + external rerank only
same seed + apply_on all
```

## Caveats

This is model-specific by nature. It should work with common `mlx-lm` models exposing mutable layer sequences such as `model.model.layers`, `model.layers`, `transformer.h`, or `decoder.layers`. If a model hides or freezes its layer container, add the path in `_COMMON_LAYER_PATHS` or implement a small adapter.

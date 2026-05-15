# v0.8.1 steering vector preflight

`observe` should be able to compare the ordinary baseline and the external depaysement-rerank condition even when activation steering vectors have not been collected yet.

In v0.8.0, passing `--vectors experiments/depaysement_mlx_vectors.npz` caused `MLXLMGenerator` to load that file during construction. If the file was missing, the command crashed before baseline and rerank conditions could run.

v0.8.1 adds a CLI preflight:

```text
active steering request = --vectors is set AND --steer-alpha != 0 AND --disable-steering is false
```

For active requests:

- `backend=mlx` looks for the exact path and then the same path with `.npz` appended.
- `backend=hf` looks for the exact path and then the same path with `.pt` appended.
- unsupported backends disable activation steering because vLLM/Ollama/OpenAI-compatible adapters do not expose hidden states through the normal API.

Default behavior is graceful degradation:

```text
missing vector file -> warn -> set vectors=None -> set steer_alpha=0 -> skip steered condition
```

Use `--strict-steering` to restore fail-fast behavior.

## Collect MLX vectors

```bash
mkdir -p experiments

depaysement-lab collect-mlx-vectors \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --bank data/depaysement_bank_en_v3.json \
  --out experiments/depaysement_mlx_vectors.npz \
  --layers 4-18 \
  --chat-template \
  --verbose
```

Then run:

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
  --max-new-tokens 120 \
  --out experiments/observe_umbrella.json
```

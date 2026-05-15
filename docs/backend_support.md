# Backend support notes

## Core distinction

Depaysement Lab has two different steering levels:

1. **External steering shell**
   - Generate K candidates.
   - Score each candidate using depaysement/image-schema/anti-repair / anti-semantic-collage metrics.
   - Select or softmax-sample from the top candidates.
   - Works with any backend that can return text completions.

2. **Internal activation steering**
   - Collect hidden states from positive and negative prompt banks.
   - Build layer-wise vectors.
   - Inject vectors during generation.
   - Requires direct access to model internals.

This means MLX/vLLM/Ollama support is not symmetric.

## MLX

MLX LM is suitable for Apple Silicon local generation. The current adapter wraps `mlx_lm.load` and `mlx_lm.generate`.

Current status:

- external rerank steering: yes
- activation vector collection: yes, experimental wrapper capture
- activation vector injection: yes, experimental wrapper injection

Implementation:

- Locate a mutable transformer block sequence such as `model.model.layers`, `model.layers`, `transformer.h`, or `decoder.layers`.
- Temporarily swap selected blocks with `MLXPatchedLayer`.
- Capture or edit the first hidden-state tensor returned by each block.
- Restore originals immediately after collection/generation.

Caveat:

- This is more model-specific than the HF hook path. Add a layer path or adapter if a model hides its blocks.

## vLLM

vLLM is currently supported through its OpenAI-compatible server mode. The CLI backend names are `vllm` and `openai-compatible`, both using `/v1/chat/completions`.

Current status:

- external rerank steering: yes
- activation vector collection: no
- activation vector injection: not in this prototype

Possible next step:

- Implement a custom vLLM model runner/plugin if we want hidden-state hooks.
- Keep external reranking for high-throughput sweeps through the OpenAI-compatible server.

## Ollama

Ollama is very convenient for local model orchestration and quick model-family comparison.

Current status:

- external rerank steering: yes
- activation vector collection: no
- activation vector injection: no

Reason:

- The API returns generated text and metrics, not internal hidden activations.

Best use:

- Compare model families quickly.
- Expand prompt banks.
- Run many seeds locally without worrying about Python model loading code.

## Recommended experimental path

1. Use Ollama or MLX for fast qualitative sweeps.
2. Use vLLM server for high-throughput candidate generation.
3. Use HF local for the cleanest PyTorch-hook mechanistic intervention.
4. Use MLX local for Apple Silicon layer-wrapper vector sweeps.
5. Keep base/pre-RLHF models as controls, not main conditions.
6. Feed discoveries from HF/MLX back into the external scorer and English prompt bank so every backend benefits.


## v0.5 model policy

Use English-first instruction-tuned/chat models for the main condition. Base models such as GPT-2 are useful controls because they are often already surreal; they do not provide the same realist-repair surface for depaysement to rebel against.


## v0.6 note

v0.6 keeps the English/instruction-tuned policy, adds meta-leak filtering (`meta` trace component), raises the default write/rank token budget to 120, and adds structured run artifacts through `--out`.

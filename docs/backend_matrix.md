# Backend matrix

| backend | generation | external rerank steering | prompt-bank expansion | hidden-state vector collection | activation injection | recommended use |
|---|---:|---:|---:|---:|---:|---|
| dummy | yes | yes | yes | no | no | scoring sanity checks |
| hf | yes | yes | yes | yes | yes | PyTorch hooks / activation vectors |
| mlx | yes via `mlx-lm` | yes | yes | yes, experimental wrapper capture | yes, experimental wrapper injection | Apple Silicon intervention |
| ollama | yes via `/api/chat` | yes | yes | no by normal HTTP | no by normal HTTP | local candidate generation |
| vllm | yes via OpenAI-compatible HTTP | yes | yes | no by normal HTTP | no by normal HTTP | high-throughput candidate generation |
| openai-compatible | yes via `/v1/chat/completions` | yes | yes | no by normal HTTP | no by normal HTTP | any compatible server |

The key distinction remains **external steering** vs **internal intervention**.

External steering:

```text
generate K candidates -> score depaysement -> reject repair/collapse/semantic-collage -> sample top candidates
```

Internal intervention:

```text
v_l = mean(h_l | positive_depaysement) - mean(h_l | negative_repair/noise/collage)
h_l <- h_l + alpha * normalize(v_l)
```

v0.5 recommends instruction-tuned/chat models for the main experiment and base/pre-RLHF models as controls. The scorer and prompt bank are English-first by default.


## v0.6 note

v0.6 keeps the English/instruction-tuned policy, adds meta-leak filtering (`meta` trace component), raises the default write/rank token budget to 120, and adds structured run artifacts through `--out`.

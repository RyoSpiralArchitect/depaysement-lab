# English-first / instruction-tuned-first policy

v0.5 changes the default experimental regime.

## Observation

Small local models under internal steering often produced Japanese semantic collage: vivid concept words arranged side by side without a stable scene. The output was strange, but not necessarily depaysement.

GPT-2 and other base/pre-RLHF checkpoints create a second problem. They are already odd, discontinuous, and weakly normed. That means the experiment loses its contrast: depaysement is a revolt against an ordered linguistic surface, but a base LM often has no strong ordered surface to revolt against.

## Policy

Main condition:

```text
English prompt bank
English seed
English lexicon
instruction-tuned/chat model
external reranker kept on
```

Control condition:

```text
base/pre-RLHF model, e.g. GPT-2
same English bank and seed
same scorer
no claim that steering is the main effect unless it beats the control
```

## New CLI helper

```bash
depaysement-lab model-check --model gpt2
```

Returns `base` and recommends using the model as a control.

```bash
depaysement-lab model-check --backend mlx
```

With no explicit model, MLX resolves to `mlx-community/Llama-3.2-3B-Instruct-4bit` and returns `instruct`.

## Semantic collage penalty

v0.5 adds `semantic_collage_penalty`, displayed as `sema_col` in score traces. It is triggered by:

- repeated noun lists
- long `of ... of ... of ...` chains
- many concept anchors with few scene relations
- many anchors with little action / transformation

The target is not to kill collage entirely. The target is to prevent the scorer from mistaking a bag of surreal nouns for a staged image.

## Practical rule

A good line should be weird **and** placeable as an image:

```text
In the hospital corridor, the sea sleeps under a white sheet.
```

A weak line is merely saturated:

```text
Umbrella, moon, bone, ticket, fish, window, stamp, tongue, sea, sea, sea.
```


## v0.6 note

v0.6 keeps the English/instruction-tuned policy, adds meta-leak filtering (`meta` trace component), raises the default write/rank token budget to 120, and adds structured run artifacts through `--out`.

# Fixed-Prefix Counter-Steering Decomposition

Date: 2026-07-12

## Question

The semantic-resilience pilot found that negative steering crossed the
alpha-zero ontology observer without restoring the mundane scene. This probe
separates the text already emitted during positive induction from the
activation intervention applied to future decode states.

The experiment is a 2 x 3 factorial:

- prefix: paired alpha-zero reference vs persistent-steering induced text,
  each frozen after step 3;
- future steering: alpha = -0.60, 0, +0.60.

Every cell resets the MLX RNG to the same seed. Four paired Llama 3.2-3B
resilience seeds are used, with four candidates and a 96-token budget per cell.
All candidate text is retained.

## Intervention Semantics

The MLX intervention defaults to `apply_on=decode_only`. A prompt prefill has
sequence length greater than one, so the activation patch does not modify it.
Steering begins only during cached one-token decoding. Therefore, for a fixed
prefix, the probability distribution of the first continuation token should be
identical across alpha. The reference and induced prefixes may already produce
different first-token distributions before steering can act.

The new `prefix-probe` command evaluates this prediction directly by running a
full prompt forward pass and retaining the vocabulary logits before generation.

## First-Token Result

| diagnostic | value |
|---|---:|
| maximum within-prefix alpha JSD | 0.000000 |
| mean reference-vs-induced prefix JSD | 0.095930 bits |
| decode-only prefill expectation met | yes |

The sign and magnitude of alpha do not alter the first continuation
distribution for a fixed prefix. The already-emitted text does. This localizes
one source of failed recovery: negative steering cannot erase the induced text
that remains in the autoregressive context.

This is an implementation-level consequence of decode-only steering, not a
claim that the model has a globally irreversible hidden-state trajectory.

## Behavioral Result

Picked means across four seeds:

| prefix | alpha | frontier | ontology | readability | original-seed anchor | traceable transport |
|---|---:|---:|---:|---:|---:|---:|
| reference | -0.60 | 0.055 | 0.224 | 0.580 | 0.271 | 0.093 |
| reference | 0.00 | 0.049 | 0.193 | 0.578 | 0.333 | 0.061 |
| reference | +0.60 | 0.057 | 0.222 | 0.552 | 0.188 | 0.046 |
| induced | -0.60 | 0.119 | 0.358 | 0.659 | 0.521 | 0.061 |
| induced | 0.00 | 0.095 | 0.419 | 0.533 | 0.396 | 0.070 |
| induced | +0.60 | 0.027 | 0.216 | 0.485 | 0.458 | 0.080 |

Negative steering after an induced prefix does not reproduce the reference
prefix behavior. Instead, in this compact sample it improves readability,
frontier score, and original-seed anchor retention relative to release, while
retaining substantial ontological motion. It behaves more like a future-state
regularizer than an inverse semantic transport map.

One selected induced/-0.60 continuation remains explicitly displaced while
recovering the mundane object:

> The blue mug, now an inextricable part of the sink's facade, is given over to
> its symbolic ministrations by a family member, who attaches a charming
> wristlet to its surviving shape ...

Another compresses a stock trajectory into a short implicit transformation:

> The umbra of the umbrella's design becomes a miniaturized etching on the
> coffee stain-strewn pages of the manuscript, resembling a cryptic handshake
> between lovers and enemies alike.

These are not clean returns to everyday description. They are altered
continuations within an already displaced register.

## Interpretation

The failure of `-v` to restore the scene has three separable causes:

1. **Textual path dependence.** Positive induction has already written a new
   scene into context. The cross-prefix first-token JSD measures this effect
   before the future intervention is applied.
2. **Decode-local action.** With `decode_only`, `-v` edits future one-token
   decode states. It does not rewrite the prompt prefill or delete prior text.
3. **Directional non-invertibility.** A contrastive centroid direction is a
   control direction, not a learned inverse transition operator. Negating its
   coefficient need not reconstruct the earlier semantic state.

The result changes the controller target. A useful next intervention is not a
larger negative coefficient. It is a separately estimated, context-conditioned
landing direction or a controller that optimizes anchor recovery and readable
transport after induction.

## Artifacts

- `experiments/prefix_counter_probe_llama3p2_3b_seed4/prefix_counter_probe.json`
- `experiments/prefix_counter_probe_llama3p2_3b_seed4/prefix_counter_probe.md`
- `experiments/prefix_counter_probe_llama3p2_3b_seed4/prefix_counter_probe_reading.md`
- `experiments/prefix_counter_probe_llama3p2_3b_seed4/prefix_counter_probe.png`

All observer values are deterministic output-side heuristics. The four-seed
factorial is a mechanistic implementation diagnostic and a qualitative pilot,
not a population estimate.

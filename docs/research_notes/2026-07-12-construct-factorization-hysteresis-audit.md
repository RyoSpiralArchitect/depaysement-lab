# Construct, Factorization, and Hysteresis Audit

Date: 2026-07-12

This note records three linked diagnostics added after the prompt x steering
contrast: a blinded human construct audit, a factorized-vector pilot, and a
matched adaptive-controller pilot. The common result is methodological. A
controller cannot be evaluated independently of the observer it regulates, and
activation-space geometry does not by itself establish a usable control axis.

## 1. Blind human construct audit

The completed sheet contains 36 representative texts from six source scenes,
crossed over two prompts and three alphas. Conditions and machine metrics were
hidden during rating. Every row has valid values for:

- anchor traceability;
- role or affordance change;
- merely decorative displacement;
- readability; and
- stock, loop, or sprawl failure.

The descriptive score averages the aligned dimensions. Classification is
non-compensatory:

- permissive positive: every aligned dimension is at least `0.5`;
- strict positive: every aligned dimension is `1.0`.

This prevents fluent surface form from compensating for absent transport,
unreadability, or degeneration.

### Result

| quantity | value |
|---|---:|
| human permissive positives | 6 |
| human strict positives | 2 |
| observer `readable_transport` positives | 4 |
| overlap, permissive | 0 |
| overlap, strict | 0 |
| F_ROC Spearman vs descriptive human mean | -0.399 |
| ontology Spearman vs descriptive human mean | -0.384 |
| traceable-transport Spearman vs descriptive human mean | +0.136 |

The zero overlap is a construct-validity failure in this sample. The observer
detects explicit transformation-like syntax and surface failure families; it is
not a validated literary-quality function. It misses human-positive implicit or
unusual transport and accepts some explicit transformations that the rater found
cliched, overloaded, unpicturable, or loop-like.

The audit is one-rater and condition-balanced, with only six source scenes. It
does not estimate population taste or the prevalence of successful depaysement
in the full candidate pool. It does establish that the current machine label
cannot be used as an item-level synonym for the stated human construct.

Artifact:
`experiments/prompt_steering_contrast_llama3p2_seed12/human_construct_analysis.md`

## 2. Factorized vector geometry

Five matched contrast banks were collected for Llama 3.2 3B Instruct over
layers 6-16:

- semantic transition;
- anchor lineage;
- hygiene;
- anti-meta;
- anti-stock.

The transition direction was projected away from hygiene, anti-meta, and
anti-stock. A fixed pilot composition then added anchor (`0.25`), hygiene
(`0.12`), anti-meta (`0.08`), and anti-stock (`0.10`) support. A deterministic
unit-norm random vector supplied a first null control.

### Geometry

| pair | mean layer-wise cosine |
|---|---:|
| endpoint / transition | -0.358 |
| transition / anchor | +0.011 |
| transition / hygiene | +0.526 |
| transition / anti-meta | +0.538 |
| hygiene / anti-meta | +0.899 |
| hygiene / anti-stock | +0.602 |

Projection retained 82.7% of transition norm on average, increasing from 67.8%
at layer 6 to 91.9% at layer 16. The named contrasts are geometrically
entangled, and the original endpoint vector is not interchangeable with the
matched transition vector. Orthogonalization is an intervention on measured
directions, not evidence of functional independence.

Artifact:
`experiments/factorized_vectors_llama3p2/factorized_vector_geometry.md`

## 3. Selector-free factorized corridor pilot

The endpoint, transition, projected, composed, and random conditions were run
with the operational prompt over four mundane scenes, four candidates, 96
maximum new tokens, no selector, and alphas `0,.3,.6,.9,1.2`. Alpha-zero
candidate text is exactly identical across all five conditions.

At alpha `0.9`:

| condition | ontology | full anchor | readability | failure |
|---|---:|---:|---:|---:|
| endpoint | .227 | .625 | .697 | .250 |
| transition | .050 | .062 | .667 | .688 |
| projected | .177 | .125 | .680 | .688 |
| factorized | .111 | .125 | .673 | .750 |
| random | .053 | .562 | .681 | .125 |

The endpoint produces a specific ontology-observer response beyond this random
control. The matched transition, projection, and first composition do not widen
the corridor; they primarily lose anchors as alpha rises. Diagnostic exemplars
also include high-ontology false positives under both factorized and random
conditions. These results support neither a pure transition axis nor a
successful factorized controller.

Artifact:
`experiments/factorized_corridor_pilot/factorized_corridor_comparison.md`

## 4. Candidate-step hysteresis

The new controller carries an action state across completed trajectory steps.
It enters boost below a lower ontology threshold, enters dampening above an
upper threshold or failure guard, and releases those states at separate margins.
This is candidate-step adaptation, not token-level feedback.

The matched pilot uses four seeds, three steps, three candidates, 64 maximum new
tokens, and deterministic per-run seed resets. Step-one picked text is identical
for all four seeds across fixed, legacy, and hysteretic conditions.

With default guards, max repetition/sprawl pressure is `1.0` at every picked
step. Legacy and hysteretic policies therefore dampen after every step and
produce identical outputs. This is observer saturation, not evidence that the
control laws are equivalent.

Relaxing the guard for law isolation makes hysteresis take 5 boost, 5 dampen,
and 2 hold actions:

| condition | alpha | ontology | readability | frontier | unfinished |
|---|---:|---:|---:|---:|---:|
| fixed | .600 | .178 | .574 | .030 | .182 |
| legacy relaxed | .673 | .140 | .663 | .038 | .133 |
| hysteresis relaxed | .650 | .139 | .621 | .038 | .167 |

The feedback laws now diverge mechanically, but neither establishes a clear
corridor gain. A controller can faithfully regulate a saturated or
miscalibrated observer without improving the target text.

Artifact:
`experiments/hysteresis_controller_law_isolation/adaptive_controller_comparison.md`

## 5. Literal bank-overlap boundary

The primary bank contains zero exact matches from the current canonical-stock
and soft-style lexicons in all positive and negative partitions. This rules out
direct lexical copying only for the tracked phrases and current bank version.
It does not rule out synonym, phrase-level, semantic, stylistic, or
corpus-mediated contamination, and it does not imply a latent surreal concept.

Artifact:
`experiments/factorized_vectors_llama3p2/primary_bank_lexical_overlap.md`

## Claim boundary

Supported by these pilots:

- the endpoint vector changes the measured candidate distribution;
- the current human construct and `readable_transport` rule label are disjoint
  in the audited 36 items;
- independently named contrast vectors remain geometrically entangled;
- the first projected/composed controller loses anchors rather than widening
  the selector-free corridor;
- default adaptive guards can saturate and erase policy differences;
- relaxing the guard reveals policy differences without a clear quality gain.

Not supported:

- F_ROC as a literary-quality score;
- a pure or universal depaysement direction;
- functional independence from activation-space orthogonality;
- a successful factorized or hysteretic controller;
- a random-vector null distribution from one deterministic random vector;
- a latent semantic manifold or internal affordance graph.

## Next confirmatory move

The next controller study should calibrate observer components against held-out,
blinded human construct labels before expanding controller complexity. Vector
banks should match predicates and terminal states, not only vocabulary, and
should be evaluated with multiple random vectors, shuffled-label contrasts,
preregistered mundane seeds, and explicit anchor constraints.

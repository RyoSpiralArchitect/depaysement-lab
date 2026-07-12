# Measurement Instrument v1.1

This note makes the current Readable Ontology Collapse Frontier observer and
the primary contrastive steering vector reproducible from the implementation.
It supersedes the simplified formulas in the v0.9/v1.0 design notes when those
formulas differ from the code.

## What the observer is, and is not

The frontier observer is deterministic. It does not use an LLM-as-a-judge,
embedding similarity, a learned grammar model, or a POS parser. It uses regular
expressions, finite audit lexicons, surface-form failure detectors, and a small
relation graph extracted from the generated text. Human ratings remain a
separate calibration surface.

"Ontology collapse" is an output-side operational label. It does not claim that
the model's internal ontology has been identified.

All component scores below are clipped to `[0, 1]`. Let `n` be the rough token
count and `s = max(1, n / 55)`.

## Ontology term

```text
D_identity   = clip(identity_melt_event_count / s)
D_affordance = clip(affordance_corruption_event_count / s)

D_ont = clip(
    0.55 * D_identity
  + 0.25 * D_affordance
  + 0.20 * D_category
)
```

### Identity melt

An event is a regex match of either:

```text
X, now a/an/the Y
X becomes/turns into/melts into/dissolves into/condenses into/
  materializes as/unfolds into Y
```

The source and target must differ, and targets containing only a small list of
qualities such as `faded`, `soft`, or `spectral` are rejected as attribute drift.

### Affordance corruption

The detector looks for a term from a finite inanimate-subject list followed,
within a 110-character local window, by an agency or impossible-affordance verb.
A clause boundary or a new subordinate subject cancels the match. Examples
include `the vent sings` and `the clock listens`. This is a lexicon/window rule,
not semantic-role labeling.

### Category bleeding

Text is split into clauses at punctuation, commas, and temporal/subordinate
connectors. Terms are tagged into audit fields such as body, architecture,
nature, machine, domestic, bureaucracy, and abstract. For a clause containing
`f >= 2` fields:

```text
degree = min(1, (f - 1) / 3) * (0.5 + 0.5 * normalized_field_entropy)
```

`D_category` is the mean degree over mixed clauses, multiplied by the clipped
density of mixed clauses in the text. The field lexicon is audit-only.

## Readability and frontier quality

The syntax-readability name is historical; it is a surface failure proxy, not a
syntactic acceptability model:

```text
R_syntax = clip(1 - 0.80*P_collapse - 0.70*U - 0.35*Rep - M)
```

`P_collapse` detects empty/very short text, symbol density, repeated-character runs,
punctuation bursts, and very long unpunctuated spans. `U` detects open tails from
terminal punctuation, dangling function words, and long unpunctuated fragments.
`Rep` combines character-trigram duplication with repeated rough tokens. `M`
matches assistant/meta commentary such as prompt or instruction discussion.

The relation graph treats filtered content words as nodes and explicit relation
prepositions, relation verbs, and possessives as edges. With `E` edges, `K`
connected components, and `g` the largest-component node ratio:

```text
relation_density = clip(E / 3)
giant_component  = clip((g - 0.34) / 0.62)
component_penalty = clip((K - 1) / 4)

I_graph = clip(
    0.58 * giant_component
  + 0.42 * relation_density
  - 0.22 * component_penalty
)
graph_factor = 0.50 + 0.50 * I_graph
```

Repair pressure is the number of unique explicit explanation, symbolism, and
closure markers divided by `max(2, n / 55)`, then clipped. Atmosphere
conservation is the Jaccard overlap of a finite atmosphere lexicon with the
prior context; an isolated text receives only a capped density fallback.

The reported observer is exactly:

```text
Q_read = clip(
    R_syntax
  * (0.50 + 0.50 * I_graph)
  * (1 - P_repair)
  * (1 - U)
  * (1 - M)
)

F_ROC = clip(D_ont * Q_read * (0.82 + 0.18 * A))
```

Here `ROC` means Readable Ontology Collapse, not receiver operating
characteristic. The nonzero offsets keep graph integration and atmosphere as
stabilizers rather than hard requirements.

## Recursive generation and selection

At each trajectory step, the generator samples `K` continuations from the seed
plus all previously picked continuations. The selector scores all candidates,
picks one, appends it to the context, and repeats. A five-step, 12-candidate run
therefore contains 60 candidate texts when the complete pool is saved.

The default `banded-frontier` eligibility region is:

```text
0.20 <= D_ont <= 0.60
R_syntax >= 0.55
Q_read >= 0.20
P_repair <= 0.45
U <= 0.50
```

Eligible candidates receive a fixed bonus and are ranked by frontier score plus
a small ontology-band bonus, minus explicit band-violation, repetition, sprawl,
and configured lexical penalties. Every run manifest stores the exact weights.

## Trajectory diagnostics

Semantic-loop pressure is lexical rather than embedding-based. Content terms are
lowercased, lightly singularized, and filtered. Let `d` be repeated-term excess
divided by term count, `c` the fraction of term occurrences covered by repeated
terms, and `g` the strongest normalized repeated 2-, 3-, or 4-gram pressure:

```text
P_loop = clip(0.55 * clip(d / 0.22) + 0.25 * c + 0.20 * g)
```

Lineage diversity is the fraction of unique current content terms absent from
the last four context spans. Object-lineage continuity is noun-term overlap with
the preceding picked continuation. Anchor survival is lexical retention from the
original seed. These rules do not resolve synonyms, paraphrase, or implicit
coreference.

### Traceable transport extension

The July 2026 controller adds relation-bearing lineage diagnostics to separate
semantic transport from two failure modes: recurrence through the same state
and disconnected noun growth. The extension still uses the same finite lexical
normalization and relation graph. It does not use embeddings, dependency
parsing, coreference resolution, or a learned judge.

Let `C` be normalized graph objects in the candidate, `H` the objects from the
last four context spans, `N = C - H` new objects, and `S = C intersect H` shared
objects. A new object is *bridged* when its connected component in the candidate
relation graph also contains an object from `S`. Let `B` and `U_b` be the
bridged and unbridged subsets of `N`:

```text
shared_presence = clip(|S| / 2)
bridged_ratio    = |B| / max(1, |N|)

lineage_bridge = clip(
    0.25 * shared_presence
  + 0.75 * bridged_ratio * 1[|N| > 0]
)

unbridged_novelty = clip(
  (|N| / max(1, |C|)) * (|U_b| / max(1, |N|))
)
```

The object-budget pressure counts excess new objects, excess unbridged objects,
and excess disconnected new-object components:

```text
P_budget = clip(
    0.45 * clip((|N|   - 4) / 8)
  + 0.35 * clip((|U_b| - 2) / 6)
  + 0.20 * clip((K_u   - 1) / 4)
)
```

`K_u` is the number of candidate components containing unbridged new objects.
Trajectory revisit pressure is the maximum recent-window similarity over the
last six spans and their length-2/3 concatenations. When both windows contain
relation pairs, similarity is `0.30` object-set Jaccard plus `0.70` relation-pair
Jaccard; otherwise it is `0.45` object-set Jaccard. Matches with fewer than two
shared objects and no shared relation pair are multiplied by `0.35`.

Let `E_new` be the fraction of current relation pairs not seen in those recent
windows, `L_div` lineage diversity, and `P_unbridged` the value above:

```text
useful_novelty = max(L_div, E_new) * (1 - P_unbridged)

traceable_transport = clip(
    (1 - P_loop)
  * (0.25 + 0.75 * lineage_bridge)
  * (0.25 + 0.75 * useful_novelty)
  * (1 - 0.70 * P_revisit)
  * (1 - 0.70 * P_budget)
)
```

All selector weights for this extension default to zero. Earlier artifacts are
therefore unchanged unless the controller is enabled explicitly. The Mistral
factorial in `experiments/mistral7b_traceable_factorial_seed4_compact/` audits
both the metrics and the generated prose; elided subjects and implicit
relations remain known lexical-observer blind spots.

## Fixed-prefix intervention diagnostic

The MLX activation patch used by the primary experiments has
`apply_on=decode_only`. Prompt prefill has sequence length greater than one and
is not patched; steering begins during cached one-token decoding. For a fixed
prefix, the full-vocabulary distribution of the first continuation token must
therefore be invariant across steering alpha. Different textual prefixes can
already produce different first-token distributions before the intervention
acts.

`prefix-probe` stores the full-vocabulary logits, their SHA-256 digest, top-token
diagnostics, and base-2 Jensen-Shannon divergence before generating matched
continuations. In the four-seed Llama diagnostic, maximum within-prefix JSD
across `alpha=-0.6,0,+0.6` was `0.000000`, while mean reference-vs-induced
prefix JSD was `0.095930` bits. This verifies decode-local implementation
semantics and identifies textual path dependence. It does not demonstrate a
globally irreversible hidden-state trajectory.

## Why the primary observer is not an LLM judge

The choice is empirical as well as architectural. A blind challenge retained
the same 12 human-rated texts while hiding scores, notes, steering conditions,
and heuristic values from three API judges. Each judge rated the items in
forward and reverse order and judged 18 non-tied pairs in both A/B orientations.

| judge | Pearson with human | Spearman with human | rating order MAD | pair accuracy | A/B consistency |
|---|---:|---:|---:|---:|---:|
| OpenAI GPT-5.2 | 0.368 | 0.276 | 0.583 | 0.500 | 0.833 |
| Anthropic Claude Sonnet 5 | 0.059 | -0.007 | 0.583 | 0.583 | 0.611 |
| Google Gemini 3.5 Flash | 0.348 | 0.275 | 1.125 | 0.694 | 0.833 |

The three judges agreed strongly with each other on absolute score ordering
despite weak agreement with the documented human pass. This supports a layered
measurement policy rather than the claim that LLMs cannot evaluate writing:

1. use the frozen deterministic observer to navigate and replay every candidate
   pool;
2. use small targeted human passes to reveal proxy failures and calibrate the
   construct;
3. use LLM judges as a convergent stress test and disagreement surface, not as
   an opaque criterion replacement.

This is exploratory evidence from one rater and 12 texts. Confirmatory literary
preference claims still require blinded multi-rater evaluation, sampling logic,
and inter-rater analysis. Exact prompts and sanitized provider responses are
retained in `experiments/judge_challenge_v1/`.

## Contrastive vector construction

The primary Llama vector uses
`data/depaysement_bank_en_v3.json`. The bank contains 10 positive examples,
8 realist/repair negatives, and 6 degenerate/noise negatives. These are
bank-level classes, not 1:1 sentence pairs.

For prompt `p`, `g_l(p)` is the mean layer-`l` block output over prompt tokens
after applying the model's chat template. The class centroids and layer vector
are:

```text
mu_l_pos = mean_i g_l(p_i_pos)
mu_l_neg = mean_j g_l(p_j_neg)
v_l      = unit_normalize(mu_l_pos - mu_l_neg)
```

Representative bank entries:

| bank | example |
|---|---|
| positive | `In the hospital corridor, the sea sleeps under a white sheet.` |
| positive | `The umbrella becomes a small theater; rain's teeth sit in every seat.` |
| realist/repair negative | `The hospital corridor is quiet, and patients wait for their turn.` |
| realist/repair negative | `This symbolizes loneliness and explains the protagonist's inner state.` |
| noise negative | `Meaning explodes without relation: chair salt invoice eyelid volcano.` |

The primary Llama archive stores unit-normalized vectors for 0-based blocks
6-16. Generation uses `position=last` and `apply_on=decode_only`, so the prompt
prefill is not edited. The bank's canonical content hash is:

```text
b8428f00361bac7a59c6b7a777e42a3b6cbde6d1feb257639dc0cd784fe692f4
```

New vector sidecars embed this canonical hash, the complete ordered bank
(including duplicates), class counts, chat-template usage, token pooling,
selected layers, pre-normalization norms, and the vector archive checksum.

## Interpretation limit

Because the negative centroid mixes realistic/repair prose with degenerate
noise, the resulting vector is not a pure axis of literary depaysement. It also
contains pressure away from explanation and collapse. Shuffled labels,
separately constructed realism and anti-noise contrasts, norm-matched random
vectors, and independently collected banks are required to factor those effects.

Implementation references:

- `src/depaysement_lab/ontology.py`
- `src/depaysement_lab/frontier.py`
- `src/depaysement_lab/scorer_v07.py`
- `src/depaysement_lab/mlx_intervention.py`
- `src/depaysement_lab/proto_v2.py`
- `src/depaysement_lab/prefix_probe.py`
- `src/depaysement_lab/judge_challenge.py`

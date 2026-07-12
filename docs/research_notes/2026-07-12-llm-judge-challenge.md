# LLM Judge Challenge for Human Taste Calibration

Date: 2026-07-12

## Motivation

The frontier observer deliberately uses frozen, transparent heuristics rather
than an LLM-as-a-judge. Transparency alone does not establish validity, so this
challenge asks whether current API judges provide a more stable replacement on
the existing 12-item human taste pass.

The intended conclusion is not fixed in advance. A strong and stable judge
would support using it as a supplemental observer. A weak or presentation-
sensitive judge would support retaining deterministic full-pool metrics and
using human reading for criterion validity.

## Design

The challenge uses the 12 generated texts previously rated by one author on a
1-10 taste scale. The API judges never receive human scores, human notes,
condition labels, steering values, or heuristic metrics.

The shared rubric was derived from the qualitative evaluation target before
the calls. It prefers specific, readable, traceable displacement and penalizes
predictable logic, stock magical-realist props, decorative gorgeousness,
semantic loops, noun accumulation, and interrupted tails. This disclosure is
important: the prompt is a calibrated construct definition, not a neutral
request for generic writing quality.

Each provider receives four matched calls:

1. absolute ratings in the original item order;
2. the same absolute ratings in reverse item order;
3. 18 stratified non-tied human-score pairs;
4. the same pairs with A/B positions swapped.

The models were:

- OpenAI `gpt-5.2`;
- Anthropic `claude-sonnet-5`;
- Google `gemini-3.5-flash`.

The exact blind prompts, raw API responses, parsed JSON, usage metadata, and
model IDs are retained. API keys are never written to artifacts.

## Results

| provider | Pearson | Spearman | absolute-order MAD | pair accuracy | A/B consistency |
|---|---:|---:|---:|---:|---:|
| OpenAI GPT-5.2 | 0.368 | 0.276 | 0.583 | 0.500 | 0.833 |
| Anthropic Claude Sonnet 5 | 0.059 | -0.007 | 0.583 | 0.583 | 0.611 |
| Google Gemini 3.5 Flash | 0.348 | 0.275 | 1.125 | 0.694 | 0.833 |

Pearson and Spearman use each model's average score across the forward and
reverse item order. Absolute-order MAD is the mean absolute change in rating
caused only by reversing presentation order. Pair accuracy pools the original
and A/B-swapped decisions; because the two orientations are paired rather than
independent, the values are descriptive and should not be treated as 36
independent trials.

Gemini is the strongest pairwise judge in this small set, but its absolute
ratings move by more than one point on average when item order reverses. OpenAI
is the most correlated absolute judge, but only modestly, and its pair accuracy
is at chance. Claude's absolute ranking is effectively unrelated to this human
pass and its pair decisions are the least position-stable.

The judges agree strongly with each other on absolute score ordering despite
their weak agreement with the human rater:

| providers | absolute Pearson | absolute Spearman | pair-choice agreement |
|---|---:|---:|---:|
| Anthropic / Google | 0.788 | 0.818 | 0.639 |
| Anthropic / OpenAI | 0.842 | 0.865 | 0.611 |
| Google / OpenAI | 0.907 | 0.903 | 0.583 |

This is more informative than a simple "LLMs cannot judge" claim. The models
share a fairly coherent preference prior, but that prior differs from the one
documented human taste pass. Pair-level decisions are also less mutually stable
than their absolute rankings.

## Comparison with the Frozen Observer

On the same 12 texts, deterministic graph integration correlates with the
human score at Pearson 0.639 / Spearman 0.486, while unfinished pressure is
-0.648 / -0.593. The aggregate selector score is much weaker at 0.287 / 0.117.

This does not show that the heuristic observer "understands literature" better
than the API models. It shows that a few transparent components capture known
preferences of this rater, while aggregate scores and general-purpose judges
miss other parts. Because those components are frozen and inspectable, their
failure can be localized rather than hidden in a single model judgment.

## Measurement Policy

The resulting methodology has three layers:

1. **Deterministic observer:** cheap, replayable, decomposable navigation over
   every candidate pool. It measures explicit constructs and failure modes.
2. **Targeted human calibration:** a small reading pass is enough to expose
   observer blind spots and prevent metric optimization from becoming the
   literary objective.
3. **LLM judge stress test:** useful for convergent evidence, pair triage, and
   disagreement discovery, but not a stable criterion or human replacement.

This makes a narrow claim about exploratory instrument development. It does not
show that large human studies are unnecessary. Confirmatory claims about
literary preference still require blinded multi-rater evaluation, sampling
logic, and inter-rater analysis.

## Artifacts

- `experiments/judge_challenge_v1/judge_challenge.json`
- `experiments/judge_challenge_v1/judge_report.md`
- `experiments/judge_challenge_v1/judge_summary.json`
- `experiments/judge_challenge_v1/judge_challenge.png`
- `experiments/judge_challenge_v1/prompts/`
- `experiments/judge_challenge_v1/raw/`

Related methodological evidence on LLM judge validity and presentation effects
is discussed in MetricEval, CheckEval, and work on position bias. The paper
should frame the present challenge as a small empirical stress test, not a
benchmark comparison among provider models.

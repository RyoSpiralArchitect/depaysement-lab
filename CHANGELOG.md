# Changelog

## v1.0.0

- Added `pool-audit` for saved candidate-pool geometry under the **Readable Ontology Collapse Frontier**.
- Added candidate-level `readable_ontology_frontier` and `frontier_quality` metrics.
- Added pool-level `pool_shift` to distinguish distribution movement from selector-only cherry-picking.
- Added `selection_lift_*` metrics comparing picked candidates against their saved candidate pool.
- Added candidate CSV and scatter plot outputs for frontier visualization.
- Added `frontier-sweep` for alpha / candidate-count / max-token sweeps with one model load per command.
- Updated `observe --save-candidates` default to save the full common candidate pool for downstream audit.
- Added docs in `docs/readable_ontology_collapse_frontier_v10.md` and tests for pool auditing.

## v0.9.0

- Added `ontology-audit` for ontology collapse density, collapse type decomposition, repair pressure, and readable-surreal frontier.
- Added audit-only channels for identity melt, affordance corruption, category bleeding, atmospheric conservation, narrative anti-resolution, and syntax readability.
- Added pairwise run comparison for `no_steer` vs `with_steer` style artifacts.
- Added optional `observe --include-repair-control` / `--repair-temperature` to create a repair-inducing comparison condition.
- Added docs in `docs/ontology_collapse_observer_v09.md`.
- Kept ontology metrics as diagnostics, not scorer reward terms.

## v0.8.1

- Added steering-vector preflight for `write`, `rank`, and `observe`. Missing generation-time vector files now disable steering gracefully by default instead of crashing during MLX generator construction.
- Added `--strict-steering` to preserve fail-fast behavior when desired.
- `observe` now records a note when the steered condition is skipped because vectors are missing or unsupported.
- Vector paths without suffix now resolve to `.npz` for MLX and `.pt` for HF when that file exists.
- Added tests for missing vectors, strict mode, suffix resolution, and unsupported steering backends.

## v0.8.0

- Added `depaysement-lab observe` for the three-condition experiment: ordinary baseline, depaysement rerank, and steering+rerank when vectors are available.
- Added `depaysement_lab.observation` with dependency-free hash n-gram continuity diagnostics and optional `sentence-transformers` embedding mode via `--embed-model`.
- Added concept-field JS divergence as an audit-only channel, separate from the scorer reward.
- Added relation-preservation comparison metrics: relation graph integration, graph fragmentation delta, semantic collage penalty, and meta-leak penalty.
- Added `depaysement_lift` as a diagnostic for controlled semantic displacement without coherence collapse.
- Observation artifacts now store runs, contexts, picked scores, graph diagnostics, step-level comparisons, aggregate labels, and notes about metric limitations.
- Added `docs/coherence_displacement_observer_v08.md` and observation metric tests.

## v0.7.0

- Added `depaysement_lab.scorer_v07`: structural-first scorer used by the package CLI.
- Lexicon-derived concept dispersion / pair bonuses / agency inversion are no longer the default skeleton; they are opt-in via `--enable-lexicon` / `--lexicon-prior-scale`.
- Made `PAIR_BONUS` explicitly an authorial aesthetic prior, not a theoretical result.
- Bank scoring is explicit: default `bank_off`, `--bank-score-mode hash` for lexical n-gram bank, `--bank-score-mode embed --embed-model ...` for semantic embedding contrast.
- Added relation-graph diagnostics: `rel_q`, `integr`, `sprawl`, relation objects, edges, and connected components.
- Strengthened semantic-collage detection for of-chains and weakly integrated object clusters.
- Added `depaysement-lab score --json --graph`.
- Added `depaysement-lab audit-run` to rescore saved run artifacts.
- Added `depaysement-lab export-eval-set` and `depaysement-lab eval-correlate` for small human-evaluation audits.
- Kept 3B/4bit MLX models as a practical smoke-test condition; recommended 7B/8B-class instruct models for serious activation-steering sweeps when resources allow.

## v0.7.0

- Made the default scorer **structural-first**: lexical concept fields are off by default.
- Documented `PAIR_BONUS` as an authorial/aesthetic prior rather than a theoretical result.
- Made hash prompt-bank scoring opt-in; embedding bank contrast is used only with `--embed-model` / `--bank-score-mode embed`.
- Added a lexicon-free relation graph to separate relation quantity (`rel_q`) from image integration (`integr`).
- Added cluster/semantic-collage penalties for of-chains, disconnected object clusters, and parallel accumulation.
- Added `--disable-steering` for steering ablations.
- Added run-audit and human-eval helpers: `audit-run`, `export-eval-set`, and `eval-correlate`.
- Added `docs/structural_scorer_v07.md`.

## v0.6.0

- Added meta-leak penalties for `Note:`, prompt/instruction references, and assistant commentary.
- Hardened continuation cleanup for note leaks and dangling token-limit tails.
- Switched write/rank default `--max-new-tokens` to 120.
- Added run artifacts via `--out`, `--out-format`, `--save-candidates`, and `--include-prompt`.

## v0.5.0

- Switched defaults to English-first prompt bank, lexicon, seed, and generation prompts.
- Added model policy helper: instruction-tuned/chat models are the main condition; base/pre-RLHF models are controls.
- Added semantic collage penalty.

## v0.4.0

- Added experimental MLX layer-wrapper intervention and MLX vector collection.

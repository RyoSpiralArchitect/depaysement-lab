# Local Paper Draft

This directory is the local drafting and publication surface for the
depaysement paper. The experimental evidence and research notes remain tracked
in the repository, while the working `*.tex`, rendered PDF, and generated arXiv
bundle remain local. Release metadata and the bundle builder are tracked.

The current local entry point is expected at:

```text
paper/depaysement_frontier_draft.tex
```

Compile from the repository root with an available LaTeX toolchain:

```bash
latexmk -pdf -output-directory=paper/build paper/depaysement_frontier_draft.tex
```

Codex can also compile the manuscript through its bundled LaTeX helper when a
system `latexmk` or Tectonic binary is not directly available.

Build the self-contained arXiv upload after the manuscript compiles:

```bash
python3 scripts/build_arxiv_bundle.py \
  paper/depaysement_frontier_draft.tex \
  --out-dir paper/arxiv_submission \
  --archive paper/arxiv_submission.zip \
  --repo-root .
```

Then compile `paper/arxiv_submission/main.tex` from inside that directory. See
[`docs/release_and_arxiv.md`](../docs/release_and_arxiv.md) for the release,
Zenodo, and submission checklist.

## Evidence Map

| Paper role | Repository evidence |
|---|---|
| Prompt-only, medium-steering, and oversteering contrast | `docs/research_notes/2026-07-12-prompt-steering-contrast.md`, `experiments/prompt_steering_contrast_llama3p2_seed12/` |
| Frontier definition and initial sweep | `docs/readable_ontology_collapse_frontier_v10.md`, `docs/research_notes/2026-05-16-banded-frontier-generation.md` |
| Exact observer formulas and vector-bank provenance | `docs/measurement_instrument_v11.md` |
| Human taste calibration | `docs/research_notes/2026-05-17-human-taste-pass.md` |
| Blind LLM-judge challenge | `docs/research_notes/2026-07-12-llm-judge-challenge.md` |
| Mundane-seed controls and lexical attractors | `docs/research_notes/2026-05-20-mundane-attractor-causal-probe.md`, `docs/research_notes/2026-05-20-mundane-attractor-probe-results.md` |
| Semantic hubs and noun graph | `docs/research_notes/2026-06-14-noun-graph-semantic-hubs.md` |
| Hard hub ablation and affordance rerouting | `docs/research_notes/2026-06-14-affordance-reroute-hard-gate.md`, `docs/research_notes/2026-06-14-affordance-class-knockout.md` |
| Trajectory and lineage diagnostics | `docs/research_notes/2026-06-14-trajectory-audit.md`, `docs/research_notes/2026-06-30-trajectory-lineage-scoring.md` |
| Model comparison | `docs/research_notes/2026-07-06-model-compare-large-probe.md` |
| Semantic-loop guard | `docs/research_notes/2026-07-07-semantic-loop-guard.md`, `docs/research_notes/2026-07-11-live-semantic-loop-guard.md` |
| Mistral traceable-transport factorial | `docs/research_notes/2026-07-12-traceable-transport-controller.md` |
| Gemma transition-vector layer probe | `docs/research_notes/2026-07-12-gemma-transition-layer-probe.md` |
| Fixed-prefix counter-steering decomposition | `docs/research_notes/2026-07-12-fixed-prefix-counter-steering.md` |

Primary tracked figures for the draft:

- `experiments/prompt_steering_contrast_llama3p2_seed12/prompt_steering_contrast.png`
- `experiments/frontier_sweep_steered_hybrid_focus_best/frontier_sweep.png`
- `experiments/model_compare_large_probe/model_compare_frontier.png`
- `experiments/mistral7b_live_semantic_loop_guard_compare/live_guard_comparison.png`
- `experiments/prefix_counter_probe_llama3p2_3b_seed4/prefix_counter_probe.png`
- `experiments/judge_challenge_v1/judge_challenge.png`
- `experiments/mistral7b_traceable_factorial_seed4_compact/factorial_plot.png`
- `experiments/gemma2_transition_layer_probe_seed4/gemma_transition_delta_response.png`

## Claim Discipline

- Treat frontier, ontology collapse, readability, loop, lineage, and affordance
  scores as heuristic instruments calibrated by text inspection and limited
  human ratings.
- Distinguish candidate-pool movement from selector lift.
- Describe cross-run comparisons as independent stochastic replicates unless
  the candidate pools are demonstrably paired.
- Treat canonical surreal props as high-availability carriers of transport
  affordances, not as necessary causes.
- Describe model-specific results as observed generation-distribution behavior;
  do not infer a unique internal manifold or causal mechanism without direct
  representation-level evidence.

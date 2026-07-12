# Traceable Transport Controller Factorial

This report compares live selection pressure on two axes: semantic-loop/revisit pressure and lineage-bridge/object-budget pressure. Means pool all saved candidates or all picked steps. Because each live pick changes the next prompt context, downstream pools are controller-conditioned trajectories rather than a fixed paired candidate set.

## Picked Means

| condition | N | frontier | read | loop | revisit | bridge | unbridged | budget | traceable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 12 | 0.040 | 0.784 | 0.157 | 0.055 | 0.258 | 0.697 | 0.490 | 0.120 |
| Loop pressure | 12 | 0.051 | 0.750 | 0.093 | 0.024 | 0.198 | 0.791 | 0.590 | 0.097 |
| Bridge + budget | 12 | 0.037 | 0.767 | 0.260 | 0.077 | 0.334 | 0.585 | 0.277 | 0.188 |
| Combined | 12 | 0.039 | 0.793 | 0.159 | 0.070 | 0.325 | 0.607 | 0.407 | 0.189 |

## Picked 2x2 Contrasts

`interaction = combined - loop - bridge + baseline` on pooled picked means.

| metric | loop effect | bridge effect | combined effect | interaction |
|---|---:|---:|---:|---:|
| readable_ontology_frontier | +0.011 | -0.003 | -0.001 | -0.009 |
| syntax_readability_proxy | -0.034 | -0.017 | +0.009 | +0.060 |
| semantic_loop_pressure | -0.064 | +0.103 | +0.002 | -0.037 |
| trajectory_revisit_pressure | -0.031 | +0.022 | +0.015 | +0.024 |
| lineage_bridge | -0.060 | +0.076 | +0.068 | +0.051 |
| unbridged_novelty | +0.094 | -0.112 | -0.089 | -0.072 |
| object_budget_pressure | +0.100 | -0.213 | -0.083 | +0.031 |
| traceable_transport_score | -0.024 | +0.068 | +0.068 | +0.024 |

## Interpretation Boundary

- The factorial isolates selector configuration at step 1, but later candidate pools diverge because selected text is appended to the next prompt.
- A low loop score is not accepted as successful transport when unbridged novelty or object-budget pressure rises.
- A low-budget closed semantic cycle is not accepted as successful transport when loop or trajectory-revisit pressure rises.
- These deterministic lexical metrics are observer outputs, not human taste labels; the picked text store is part of the audit.

## Sources

- Baseline: `experiments/frontier_sweep_mistral7b_traceable_factorial_baseline_seed4_compact/frontier_sweep_report.json`
- Loop pressure: `experiments/frontier_sweep_mistral7b_traceable_factorial_loop_seed4_compact/frontier_sweep_report.json`
- Bridge + budget: `experiments/frontier_sweep_mistral7b_traceable_factorial_bridge_seed4_compact/frontier_sweep_report.json`
- Combined: `experiments/frontier_sweep_mistral7b_traceable_factorial_combined_seed4_compact/frontier_sweep_report.json`

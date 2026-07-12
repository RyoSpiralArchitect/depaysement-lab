# Gemma Transition-Vector Layer-Window Probe

This probe compares the original endpoint-surreal centroid direction with a lexically matched transition direction. Early, middle, and late windows contain seven layers each. Values below pool all picked steps across four mundane seeds.

## Picked Dose Response

| probe | alpha | N | frontier | ontology | read | bridge | unbridged | budget | traceable | stock |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Endpoint, layers 9-15 | 0 | 12 | 0.020 | 0.063 | 0.808 | 0.339 | 0.504 | 0.061 | 0.247 | 0.056 |
| Endpoint, layers 9-15 | 0.8 | 12 | 0.012 | 0.033 | 0.813 | 0.262 | 0.674 | 0.314 | 0.211 | 0.000 |
| Endpoint, layers 9-15 | 1.1 | 12 | 0.007 | 0.017 | 0.830 | 0.523 | 0.375 | 0.067 | 0.499 | 0.000 |
| Endpoint, layers 9-15 | 1.4 | 12 | 0.011 | 0.034 | 0.822 | 0.241 | 0.665 | 0.304 | 0.189 | 0.000 |
| Transition, layers 2-8 | 0 | 12 | 0.020 | 0.059 | 0.771 | 0.481 | 0.412 | 0.099 | 0.377 | 0.028 |
| Transition, layers 2-8 | 0.8 | 12 | 0.001 | 0.004 | 0.829 | 0.405 | 0.470 | 0.157 | 0.323 | 0.000 |
| Transition, layers 2-8 | 1.1 | 12 | 0.010 | 0.024 | 0.841 | 0.447 | 0.481 | 0.154 | 0.380 | 0.000 |
| Transition, layers 2-8 | 1.4 | 12 | 0.000 | 0.000 | 0.895 | 0.127 | 0.753 | 0.240 | 0.119 | 0.000 |
| Transition, layers 9-15 | 0 | 12 | 0.036 | 0.099 | 0.867 | 0.289 | 0.619 | 0.246 | 0.184 | 0.000 |
| Transition, layers 9-15 | 0.8 | 12 | 0.012 | 0.034 | 0.841 | 0.267 | 0.686 | 0.398 | 0.197 | 0.000 |
| Transition, layers 9-15 | 1.1 | 12 | 0.006 | 0.014 | 0.853 | 0.223 | 0.717 | 0.231 | 0.211 | 0.000 |
| Transition, layers 9-15 | 1.4 | 12 | 0.010 | 0.026 | 0.847 | 0.222 | 0.753 | 0.277 | 0.172 | 0.000 |
| Transition, layers 16-22 | 0 | 12 | 0.016 | 0.051 | 0.874 | 0.271 | 0.645 | 0.236 | 0.211 | 0.000 |
| Transition, layers 16-22 | 0.8 | 12 | 0.027 | 0.062 | 0.897 | 0.160 | 0.761 | 0.254 | 0.135 | 0.028 |
| Transition, layers 16-22 | 1.1 | 12 | 0.068 | 0.118 | 0.915 | 0.332 | 0.588 | 0.260 | 0.270 | 0.000 |
| Transition, layers 16-22 | 1.4 | 12 | 0.007 | 0.017 | 0.810 | 0.341 | 0.566 | 0.170 | 0.259 | 0.000 |

## Direction Geometry

Across shared layers, endpoint/transition cosine has mean `0.137`, minimum `-0.003`, and maximum `0.239`.

## Within-Probe Peak

The late transition window has a narrow response peak at `alpha=1.1`:

- frontier: `0.016 -> 0.068`
- ontology: `0.051 -> 0.118`
- readability: `0.874 -> 0.915`
- traceable transport: `0.211 -> 0.270`

At the same middle layers and dose, the endpoint direction does not show that response:

- endpoint frontier: `0.020 -> 0.007`
- endpoint ontology: `0.063 -> 0.017`

## Late-Window Seed Decomposition

| seed | frontier delta | ontology delta | readability delta |
|---|---:|---:|---:|
| A blue mug near the sink | +0.048 | -0.009 | +0.211 |
| I am waiting for the printer | +0.038 | +0.092 | +0.006 |
| The laundry basket by the door | +0.120 | +0.183 | -0.098 |
| The spreadsheet was still open | +0.000 | +0.000 | +0.045 |

## Interpretation Boundary

- Independent MLX runs are stochastic; their alpha-zero pools are not identical paired controls.
- The late-window peak is dose-localized and direction-specific, but the highest-scoring texts include shallow color/state substitutions and stock-like cat/rose/notebook motifs.
- The result supports a layer-local transition response, not a claim that Gemma's readable depaysement problem is solved.
- The full picked-text store is part of the audit because observer maxima can overstate qualitative transformation.

## Sources

- Endpoint, layers 9-15: `experiments/frontier_sweep_gemma2_endpoint_mid_l9_15_seed4/frontier_sweep_report.json`
- Transition, layers 2-8: `experiments/frontier_sweep_gemma2_transition_early_l2_8_seed4/frontier_sweep_report.json`
- Transition, layers 9-15: `experiments/frontier_sweep_gemma2_transition_mid_l9_15_seed4/frontier_sweep_report.json`
- Transition, layers 16-22: `experiments/frontier_sweep_gemma2_transition_late_l16_22_seed4/frontier_sweep_report.json`

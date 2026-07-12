# Candidate-Step Adaptive Steering Pilot

Conditions: `fixed, legacy_relaxed, hysteresis_relaxed`
Seeds: `4`
Step-one picked texts identical: `4` / `4` seeds

## Condition Means

| condition | runs | alpha | ontology | readability | frontier | unfinished | loop | stock | guard | boost / dampen / hold / legacy / fixed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed | 4 | 0.600 | 0.178 | 0.574 | 0.030 | 0.182 | 1.000 | 0.532 | 1.000 | 0 / 0 / 0 / 0 / 12 |
| legacy_relaxed | 4 | 0.673 | 0.140 | 0.663 | 0.038 | 0.133 | 0.999 | 0.473 | 0.999 | 0 / 0 / 0 / 12 / 0 |
| hysteresis_relaxed | 4 | 0.650 | 0.139 | 0.621 | 0.038 | 0.167 | 1.000 | 0.515 | 1.000 | 5 / 5 / 2 / 0 / 0 |

## Seed-Paired Deltas vs fixed

| condition | metric | seed pairs | mean delta | median delta |
|---|---|---:|---:|---:|
| legacy_relaxed | mean_alpha | 4 | +0.073 | +0.080 |
| legacy_relaxed | mean_ontology_collapse_density | 4 | -0.039 | -0.006 |
| legacy_relaxed | mean_syntax_readability_proxy | 4 | +0.090 | +0.102 |
| legacy_relaxed | mean_readable_ontology_frontier | 4 | +0.008 | +0.003 |
| legacy_relaxed | mean_unfinished | 4 | -0.048 | -0.097 |
| legacy_relaxed | mean_loop_pressure | 4 | -0.001 | +0.000 |
| legacy_relaxed | mean_stock_pressure | 4 | -0.059 | -0.040 |
| legacy_relaxed | mean_guard_pressure | 4 | -0.001 | +0.000 |
| hysteresis_relaxed | mean_alpha | 4 | +0.050 | +0.053 |
| hysteresis_relaxed | mean_ontology_collapse_density | 4 | -0.040 | -0.050 |
| hysteresis_relaxed | mean_syntax_readability_proxy | 4 | +0.047 | +0.102 |
| hysteresis_relaxed | mean_readable_ontology_frontier | 4 | +0.008 | +0.008 |
| hysteresis_relaxed | mean_unfinished | 4 | -0.015 | -0.097 |
| hysteresis_relaxed | mean_loop_pressure | 4 | +0.000 | +0.000 |
| hysteresis_relaxed | mean_stock_pressure | 4 | -0.017 | -0.104 |
| hysteresis_relaxed | mean_guard_pressure | 4 | +0.000 | +0.000 |

## Interpretation Boundary

- The seed, not the trajectory step or candidate, is the comparison unit.
- This is a four-seed controller pilot and does not estimate population literary quality.
- Controller feedback uses a deterministic observer that failed the separate human construct audit.
- The controller acts between completed candidate-selection steps, not during token decoding.
- A controller can faithfully regulate a miscalibrated observer and still worsen the text.

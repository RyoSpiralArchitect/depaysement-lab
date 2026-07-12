# Candidate-Step Adaptive Steering Pilot

Conditions: `fixed, legacy, hysteresis`
Seeds: `4`
Step-one picked texts identical: `4` / `4` seeds

## Condition Means

| condition | runs | alpha | ontology | readability | frontier | unfinished | loop | stock | guard | boost / dampen / hold / legacy / fixed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed | 4 | 0.600 | 0.178 | 0.574 | 0.030 | 0.182 | 1.000 | 0.532 | 1.000 | 0 / 0 / 0 / 0 / 12 |
| legacy | 4 | 0.480 | 0.134 | 0.624 | 0.028 | 0.117 | 1.000 | 0.452 | 1.000 | 0 / 0 / 0 / 12 / 0 |
| hysteresis | 4 | 0.480 | 0.134 | 0.624 | 0.028 | 0.117 | 1.000 | 0.452 | 1.000 | 0 / 12 / 0 / 0 / 0 |

## Seed-Paired Deltas vs fixed

| condition | metric | seed pairs | mean delta | median delta |
|---|---|---:|---:|---:|
| legacy | mean_alpha | 4 | -0.120 | -0.120 |
| legacy | mean_ontology_collapse_density | 4 | -0.044 | -0.014 |
| legacy | mean_syntax_readability_proxy | 4 | +0.050 | +0.075 |
| legacy | mean_readable_ontology_frontier | 4 | -0.002 | -0.006 |
| legacy | mean_unfinished | 4 | -0.065 | -0.100 |
| legacy | mean_loop_pressure | 4 | +0.000 | +0.000 |
| legacy | mean_stock_pressure | 4 | -0.080 | -0.069 |
| legacy | mean_guard_pressure | 4 | +0.000 | +0.000 |
| hysteresis | mean_alpha | 4 | -0.120 | -0.120 |
| hysteresis | mean_ontology_collapse_density | 4 | -0.044 | -0.014 |
| hysteresis | mean_syntax_readability_proxy | 4 | +0.050 | +0.075 |
| hysteresis | mean_readable_ontology_frontier | 4 | -0.002 | -0.006 |
| hysteresis | mean_unfinished | 4 | -0.065 | -0.100 |
| hysteresis | mean_loop_pressure | 4 | +0.000 | +0.000 |
| hysteresis | mean_stock_pressure | 4 | -0.080 | -0.069 |
| hysteresis | mean_guard_pressure | 4 | +0.000 | +0.000 |

## Interpretation Boundary

- The seed, not the trajectory step or candidate, is the comparison unit.
- This is a four-seed controller pilot and does not estimate population literary quality.
- Controller feedback uses a deterministic observer that failed the separate human construct audit.
- The controller acts between completed candidate-selection steps, not during token decoding.
- A controller can faithfully regulate a miscalibrated observer and still worsen the text.

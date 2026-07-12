# Prompt x Steering Contrast

This one-step experiment compares raw candidate pools. The generator receives either a naive surreal/depaysement instruction or an operational definition of traceable role change. No selector chooses the reported outcomes.

## Pool Summary

| prompt | alpha | seeds | candidates | anchor | full anchor | ontology | read | frontier | traceable | surface | decorative | near miss | transport | failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| naive | 0.00 | 12 | 96 | 0.901 | 0.677 | 0.091 | 0.662 | 0.030 | 0.052 | 0.271 | 0.143 | 0.344 | 0.125 | 0.188 |
| naive | 0.60 | 12 | 96 | 0.862 | 0.646 | 0.206 | 0.674 | 0.063 | 0.049 | 0.330 | 0.159 | 0.250 | 0.219 | 0.427 |
| naive | 1.20 | 12 | 96 | 0.812 | 0.531 | 0.392 | 0.651 | 0.116 | 0.044 | 0.316 | 0.101 | 0.052 | 0.198 | 0.708 |
| operational | 0.00 | 12 | 96 | 0.880 | 0.677 | 0.059 | 0.669 | 0.020 | 0.060 | 0.035 | 0.019 | 0.073 | 0.052 | 0.177 |
| operational | 0.60 | 12 | 96 | 0.901 | 0.688 | 0.086 | 0.692 | 0.030 | 0.062 | 0.115 | 0.064 | 0.208 | 0.125 | 0.104 |
| operational | 1.20 | 12 | 96 | 0.789 | 0.500 | 0.299 | 0.712 | 0.101 | 0.054 | 0.104 | 0.039 | 0.031 | 0.167 | 0.625 |

## Exact-Anchor Matched Subset

Only candidates containing every required anchor phrase are retained below.

| prompt | alpha | matched / all | ontology | read | frontier | near miss | transport | failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| naive | 0.00 | 65 (0.677) | 0.113 | 0.654 | 0.037 | 0.369 | 0.154 | 0.138 |
| naive | 0.60 | 62 (0.646) | 0.264 | 0.670 | 0.081 | 0.274 | 0.323 | 0.290 |
| naive | 1.20 | 51 (0.531) | 0.444 | 0.692 | 0.149 | 0.078 | 0.235 | 0.608 |
| operational | 0.00 | 65 (0.677) | 0.058 | 0.667 | 0.019 | 0.108 | 0.046 | 0.077 |
| operational | 0.60 | 66 (0.688) | 0.074 | 0.688 | 0.025 | 0.242 | 0.121 | 0.030 |
| operational | 1.20 | 48 (0.500) | 0.313 | 0.692 | 0.107 | 0.042 | 0.229 | 0.479 |

## Pooled Descriptive Contrasts

### Operational Prompt Gain At Zero

`operational alpha=0.00` minus `naive alpha=0.00`

| metric | delta |
|---|---:|
| anchor_phrase_coverage | -0.021 |
| ontology_collapse_density | -0.032 |
| syntax_readability_proxy | +0.007 |
| decoration_without_transport | -0.124 |
| decorative_near_miss_rate | -0.271 |
| readable_transport_rate | -0.073 |
| failure_rate | -0.010 |

### Naive Corridor Steering Gain

`naive alpha=0.60` minus `naive alpha=0.00`

| metric | delta |
|---|---:|
| anchor_phrase_coverage | -0.039 |
| ontology_collapse_density | +0.114 |
| syntax_readability_proxy | +0.012 |
| decoration_without_transport | +0.016 |
| decorative_near_miss_rate | -0.094 |
| readable_transport_rate | +0.094 |
| failure_rate | +0.240 |

### Operational Corridor Steering Gain

`operational alpha=0.60` minus `operational alpha=0.00`

| metric | delta |
|---|---:|
| anchor_phrase_coverage | +0.021 |
| ontology_collapse_density | +0.026 |
| syntax_readability_proxy | +0.023 |
| decoration_without_transport | +0.045 |
| decorative_near_miss_rate | +0.135 |
| readable_transport_rate | +0.073 |
| failure_rate | -0.073 |

### Naive High Alpha Change

`naive alpha=1.20` minus `naive alpha=0.60`

| metric | delta |
|---|---:|
| anchor_phrase_coverage | -0.049 |
| ontology_collapse_density | +0.187 |
| syntax_readability_proxy | -0.024 |
| decoration_without_transport | -0.059 |
| decorative_near_miss_rate | -0.198 |
| readable_transport_rate | -0.021 |
| failure_rate | +0.281 |

### Operational High Alpha Change

`operational alpha=1.20` minus `operational alpha=0.60`

| metric | delta |
|---|---:|
| anchor_phrase_coverage | -0.112 |
| ontology_collapse_density | +0.213 |
| syntax_readability_proxy | +0.020 |
| decoration_without_transport | -0.026 |
| decorative_near_miss_rate | -0.177 |
| readable_transport_rate | +0.042 |
| failure_rate | +0.521 |

### Prompt X Corridor Interaction

`operational corridor gain` minus `naive corridor gain`

| metric | delta |
|---|---:|
| anchor_phrase_coverage | +0.060 |
| ontology_collapse_density | -0.088 |
| syntax_readability_proxy | +0.011 |
| decoration_without_transport | +0.029 |
| decorative_near_miss_rate | +0.229 |
| readable_transport_rate | -0.021 |
| failure_rate | -0.312 |

## Seed-Paired Contrasts

### Operational Prompt Gain At Zero

`operational alpha=0.00` minus `naive alpha=0.00`

| metric | seed pairs | mean delta | bootstrap 95% CI | positive seeds |
|---|---:|---:|---:|---:|
| anchor_phrase_coverage | 12 | -0.021 | [-0.055, +0.016] | 0.333 |
| ontology_collapse_density | 12 | -0.032 | [-0.079, +0.015] | 0.417 |
| readable_transport_rate | 12 | -0.073 | [-0.156, +0.010] | 0.167 |
| failure_rate | 12 | -0.010 | [-0.083, +0.062] | 0.250 |

### Naive Corridor Steering Gain

`naive alpha=0.60` minus `naive alpha=0.00`

| metric | seed pairs | mean delta | bootstrap 95% CI | positive seeds |
|---|---:|---:|---:|---:|
| anchor_phrase_coverage | 12 | -0.039 | [-0.081, +0.003] | 0.250 |
| ontology_collapse_density | 12 | +0.114 | [+0.033, +0.191] | 0.833 |
| readable_transport_rate | 12 | +0.094 | [-0.000, +0.188] | 0.583 |
| failure_rate | 12 | +0.240 | [+0.135, +0.333] | 0.750 |

### Operational Corridor Steering Gain

`operational alpha=0.60` minus `operational alpha=0.00`

| metric | seed pairs | mean delta | bootstrap 95% CI | positive seeds |
|---|---:|---:|---:|---:|
| anchor_phrase_coverage | 12 | +0.021 | [-0.029, +0.068] | 0.417 |
| ontology_collapse_density | 12 | +0.026 | [-0.007, +0.059] | 0.667 |
| readable_transport_rate | 12 | +0.073 | [+0.000, +0.156] | 0.333 |
| failure_rate | 12 | -0.073 | [-0.167, +0.021] | 0.250 |

### Naive High Alpha Change

`naive alpha=1.20` minus `naive alpha=0.60`

| metric | seed pairs | mean delta | bootstrap 95% CI | positive seeds |
|---|---:|---:|---:|---:|
| anchor_phrase_coverage | 12 | -0.049 | [-0.096, -0.005] | 0.167 |
| ontology_collapse_density | 12 | +0.187 | [+0.119, +0.252] | 0.917 |
| readable_transport_rate | 12 | -0.021 | [-0.083, +0.042] | 0.167 |
| failure_rate | 12 | +0.281 | [+0.177, +0.396] | 0.833 |

### Operational High Alpha Change

`operational alpha=1.20` minus `operational alpha=0.60`

| metric | seed pairs | mean delta | bootstrap 95% CI | positive seeds |
|---|---:|---:|---:|---:|
| anchor_phrase_coverage | 12 | -0.112 | [-0.182, -0.052] | 0.167 |
| ontology_collapse_density | 12 | +0.213 | [+0.136, +0.293] | 0.917 |
| readable_transport_rate | 12 | +0.042 | [-0.094, +0.188] | 0.417 |
| failure_rate | 12 | +0.521 | [+0.365, +0.667] | 0.833 |

### Prompt X Corridor Interaction

`operational corridor gain` minus `naive corridor gain`

| metric | seed pairs | mean delta | bootstrap 95% CI | positive seeds |
|---|---:|---:|---:|---:|
| anchor_phrase_coverage | 12 | +0.060 | [-0.010, +0.133] | 0.667 |
| ontology_collapse_density | 12 | -0.088 | [-0.152, -0.017] | 0.250 |
| readable_transport_rate | 12 | -0.021 | [-0.146, +0.104] | 0.333 |
| failure_rate | 12 | -0.312 | [-0.469, -0.177] | 0.000 |

## Seed-Paired Exact-Anchor Contrasts

### Operational Prompt Gain At Zero

`operational alpha=0.00` minus `naive alpha=0.00`

| metric | seed pairs | mean delta | bootstrap 95% CI | positive seeds |
|---|---:|---:|---:|---:|
| anchor_phrase_coverage | 12 | +0.000 | [+0.000, +0.000] | 0.000 |
| ontology_collapse_density | 12 | -0.036 | [-0.073, -0.001] | 0.333 |
| readable_transport_rate | 12 | -0.070 | [-0.146, +0.002] | 0.167 |
| failure_rate | 12 | -0.056 | [-0.162, +0.046] | 0.250 |

### Naive Corridor Steering Gain

`naive alpha=0.60` minus `naive alpha=0.00`

| metric | seed pairs | mean delta | bootstrap 95% CI | positive seeds |
|---|---:|---:|---:|---:|
| anchor_phrase_coverage | 12 | +0.000 | [+0.000, +0.000] | 0.000 |
| ontology_collapse_density | 12 | +0.159 | [+0.060, +0.249] | 0.833 |
| readable_transport_rate | 12 | +0.200 | [+0.048, +0.336] | 0.750 |
| failure_rate | 12 | +0.180 | [+0.075, +0.284] | 0.750 |

### Operational Corridor Steering Gain

`operational alpha=0.60` minus `operational alpha=0.00`

| metric | seed pairs | mean delta | bootstrap 95% CI | positive seeds |
|---|---:|---:|---:|---:|
| anchor_phrase_coverage | 12 | +0.000 | [+0.000, +0.000] | 0.000 |
| ontology_collapse_density | 12 | +0.015 | [-0.046, +0.079] | 0.500 |
| readable_transport_rate | 12 | +0.067 | [-0.047, +0.188] | 0.333 |
| failure_rate | 12 | -0.044 | [-0.107, +0.012] | 0.083 |

### Naive High Alpha Change

`naive alpha=1.20` minus `naive alpha=0.60`

| metric | seed pairs | mean delta | bootstrap 95% CI | positive seeds |
|---|---:|---:|---:|---:|
| anchor_phrase_coverage | 12 | +0.000 | [+0.000, +0.000] | 0.000 |
| ontology_collapse_density | 12 | +0.205 | [+0.094, +0.314] | 0.750 |
| readable_transport_rate | 12 | -0.080 | [-0.241, +0.084] | 0.333 |
| failure_rate | 12 | +0.304 | [+0.169, +0.451] | 0.833 |

### Operational High Alpha Change

`operational alpha=1.20` minus `operational alpha=0.60`

| metric | seed pairs | mean delta | bootstrap 95% CI | positive seeds |
|---|---:|---:|---:|---:|
| anchor_phrase_coverage | 12 | +0.000 | [+0.000, +0.000] | 0.000 |
| ontology_collapse_density | 12 | +0.285 | [+0.200, +0.371] | 1.000 |
| readable_transport_rate | 12 | +0.077 | [-0.115, +0.290] | 0.333 |
| failure_rate | 12 | +0.545 | [+0.307, +0.768] | 0.750 |

### Prompt X Corridor Interaction

`operational corridor gain` minus `naive corridor gain`

| metric | seed pairs | mean delta | bootstrap 95% CI | positive seeds |
|---|---:|---:|---:|---:|
| anchor_phrase_coverage | 12 | +0.000 | [+0.000, +0.000] | 0.000 |
| ontology_collapse_density | 12 | -0.145 | [-0.236, -0.054] | 0.167 |
| readable_transport_rate | 12 | -0.133 | [-0.294, +0.032] | 0.250 |
| failure_rate | 12 | -0.224 | [-0.364, -0.094] | 0.167 |

## Representative Same-Prompt Triptych

Seed: `An apartment key lies on the windowsill between a plant pot and the half-closed blinds.`

Anchors: apartment key, windowsill, plant pot, blinds

### Prompt only | alpha=0.00

Observer label: `ontologically_stable` | all anchors matched: `yes`

anchor=1.000 | ontology=0.015 | read=0.692 | frontier=0.005

```text
The apartment key remained, once again, forgotten, this time on the windowsill between the small, antique teacup now housing a single, wilted fern and the half-closed blinds that had never been fully raised. Nearby, the once-familiar plant pot now sat empty and dusty, a faint scent of fresh lavender still clinging to its ceramic rim.
```

### Steered corridor | alpha=0.60

Observer label: `readable_transport` | all anchors matched: `yes`

anchor=1.000 | ontology=0.272 | read=0.669 | frontier=0.095

```text
As the apartment key, once a trusted companion, now collects dust and a small inscription on its surface whispers forgotten promises, a forgotten briefcase with a faded label lies on the windowsill, between the same plant pot that has been watering the office plants of a distant tenant, and the half-closed blinds filter the afternoon sun.
```

### High alpha | alpha=1.20

Observer label: `stock_loop_or_sprawl_failure` | all anchors matched: `yes`

anchor=1.000 | ontology=0.432 | read=0.591 | frontier=0.131

```text
As morning light creeps in, the apartment key, now a small, delicate key, subtly opens, and a sliver of morning light begins to seep into the apartment, casting an ethereal glow on the windowsill, where a small, antique globe, once a plant pot, now subtly begins to grow, its leaves unfolding like tiny, delicate fans, above the half-closed blinds, where a small, leather-bound book, once a desk, begins to write, its ink scribing a morning sonnet, as the blinds creak open, releasing a warm, morning mist.
```

## Interpretation Boundary

- Prompt-only is treated as a strong competitor, not a deliberately weak straw baseline.
- Seed-paired bootstrap intervals use the 12 mundane scenes as units; candidates are not treated as independent observations.
- The triptych is deterministic but illustrative; condition-level claims must use the complete pools.
- Observer labels are operational near-miss/transport/failure categories, not final literary judgments.
- The blinded human sheet tests anchor traceability, role change, decoration, readability, and failure separately.

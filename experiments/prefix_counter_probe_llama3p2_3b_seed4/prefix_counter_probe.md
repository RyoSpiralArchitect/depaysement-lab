# Fixed-Prefix Counter-Steering Probe

## Design

Paired prefixes: reference vs induced after 3 steps; alpha=[-0.6, 0.0, 0.6]; candidates=4; apply_on=decode_only.

The probe asks whether counter-steering changes the first continuation distribution, or only later decode states after an already-induced text prefix has entered context.

## First-Token Decomposition

| diagnostic | value |
|---|---:|
| max within-prefix alpha JSD | 0 |
| mean cross-prefix JSD | 0.095930 |
| first token invariant across alpha | true |

## Behavioral Summary

| prefix | alpha | n | pool frontier | picked frontier | picked ontology | picked read | picked seed anchor | picked traceable | picked loop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reference | -0.600 | 4 | 0.023 | 0.055 | 0.224 | 0.580 | 0.271 | 0.093 | 0.113 |
| reference | 0.000 | 4 | 0.014 | 0.049 | 0.193 | 0.578 | 0.333 | 0.061 | 0.152 |
| reference | 0.600 | 4 | 0.016 | 0.057 | 0.222 | 0.552 | 0.188 | 0.046 | 0.065 |
| induced | -0.600 | 4 | 0.037 | 0.119 | 0.358 | 0.659 | 0.521 | 0.061 | 0.090 |
| induced | 0.000 | 4 | 0.033 | 0.095 | 0.419 | 0.533 | 0.396 | 0.070 | 0.104 |
| induced | 0.600 | 4 | 0.014 | 0.027 | 0.216 | 0.485 | 0.458 | 0.080 | 0.077 |

## Interpretation Boundary

If decode-only first-token logits remain invariant across alpha while they differ across prefixes, the failed soft landing is localized to autoregressive path dependence plus future-state steering. It does not establish that the hidden-state trajectory is globally irreversible.

See `prefix_counter_probe_reading.md` for every selected continuation and its source prefix.

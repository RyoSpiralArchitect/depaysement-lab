# Selector-Free Factorized Corridor Pilot

Conditions: `endpoint, transition, projected, factorized, random`
Alpha-zero candidate texts identical: `true`

## Raw Pool Curves

| condition | alpha | candidates | anchor | full anchor | ontology | readability | traceable | failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| endpoint | 0.00 | 16 | 0.875 | 0.625 | 0.064 | 0.660 | 0.049 | 0.250 |
| endpoint | 0.30 | 16 | 0.953 | 0.812 | 0.029 | 0.669 | 0.065 | 0.000 |
| endpoint | 0.60 | 16 | 0.844 | 0.500 | 0.128 | 0.696 | 0.069 | 0.125 |
| endpoint | 0.90 | 16 | 0.906 | 0.625 | 0.227 | 0.697 | 0.061 | 0.250 |
| endpoint | 1.20 | 16 | 0.828 | 0.625 | 0.195 | 0.673 | 0.050 | 0.812 |
| transition | 0.00 | 16 | 0.875 | 0.625 | 0.064 | 0.660 | 0.049 | 0.250 |
| transition | 0.30 | 16 | 0.781 | 0.500 | 0.015 | 0.670 | 0.054 | 0.250 |
| transition | 0.60 | 16 | 0.672 | 0.312 | 0.079 | 0.669 | 0.056 | 0.500 |
| transition | 0.90 | 16 | 0.422 | 0.062 | 0.050 | 0.667 | 0.059 | 0.688 |
| transition | 1.20 | 16 | 0.250 | 0.000 | 0.051 | 0.679 | 0.045 | 0.938 |
| projected | 0.00 | 16 | 0.875 | 0.625 | 0.064 | 0.660 | 0.049 | 0.250 |
| projected | 0.30 | 16 | 0.797 | 0.375 | 0.011 | 0.672 | 0.051 | 0.312 |
| projected | 0.60 | 16 | 0.641 | 0.312 | 0.116 | 0.667 | 0.055 | 0.438 |
| projected | 0.90 | 16 | 0.484 | 0.125 | 0.177 | 0.680 | 0.058 | 0.688 |
| projected | 1.20 | 16 | 0.391 | 0.000 | 0.037 | 0.653 | 0.061 | 0.875 |
| factorized | 0.00 | 16 | 0.875 | 0.625 | 0.064 | 0.660 | 0.049 | 0.250 |
| factorized | 0.30 | 16 | 0.812 | 0.438 | 0.117 | 0.647 | 0.063 | 0.312 |
| factorized | 0.60 | 16 | 0.688 | 0.250 | 0.044 | 0.674 | 0.051 | 0.375 |
| factorized | 0.90 | 16 | 0.406 | 0.125 | 0.111 | 0.673 | 0.047 | 0.750 |
| factorized | 1.20 | 16 | 0.312 | 0.000 | 0.043 | 0.703 | 0.044 | 0.812 |
| random | 0.00 | 16 | 0.875 | 0.625 | 0.064 | 0.660 | 0.049 | 0.250 |
| random | 0.30 | 16 | 0.844 | 0.562 | 0.078 | 0.660 | 0.075 | 0.250 |
| random | 0.60 | 16 | 0.922 | 0.812 | 0.019 | 0.676 | 0.060 | 0.062 |
| random | 0.90 | 16 | 0.844 | 0.562 | 0.053 | 0.681 | 0.069 | 0.125 |
| random | 1.20 | 16 | 0.797 | 0.438 | 0.021 | 0.687 | 0.112 | 0.188 |

## Exact-Anchor Subset

| condition | alpha | matched fraction | ontology | readability | failure |
|---|---:|---:|---:|---:|---:|
| endpoint | 0.00 | 0.625 | 0.067 | 0.659 | 0.200 |
| endpoint | 0.30 | 0.812 | 0.035 | 0.666 | 0.000 |
| endpoint | 0.60 | 0.500 | 0.154 | 0.676 | 0.000 |
| endpoint | 0.90 | 0.625 | 0.358 | 0.698 | 0.200 |
| endpoint | 1.20 | 0.625 | 0.248 | 0.687 | 0.800 |
| transition | 0.00 | 0.625 | 0.067 | 0.659 | 0.200 |
| transition | 0.30 | 0.500 | 0.011 | 0.663 | 0.000 |
| transition | 0.60 | 0.312 | 0.011 | 0.659 | 0.200 |
| transition | 0.90 | 0.062 | 0.540 | 0.613 | 0.000 |
| transition | 1.20 | 0.000 | 0.000 | 0.000 | 0.000 |
| projected | 0.00 | 0.625 | 0.067 | 0.659 | 0.200 |
| projected | 0.30 | 0.375 | 0.006 | 0.667 | 0.167 |
| projected | 0.60 | 0.312 | 0.227 | 0.654 | 0.000 |
| projected | 0.90 | 0.125 | 0.000 | 0.666 | 0.000 |
| projected | 1.20 | 0.000 | 0.000 | 0.000 | 0.000 |
| factorized | 0.00 | 0.625 | 0.067 | 0.659 | 0.200 |
| factorized | 0.30 | 0.438 | 0.169 | 0.653 | 0.143 |
| factorized | 0.60 | 0.250 | 0.149 | 0.666 | 0.000 |
| factorized | 0.90 | 0.125 | 0.275 | 0.681 | 0.000 |
| factorized | 1.20 | 0.000 | 0.000 | 0.000 | 0.000 |
| random | 0.00 | 0.625 | 0.067 | 0.659 | 0.200 |
| random | 0.30 | 0.562 | 0.071 | 0.674 | 0.000 |
| random | 0.60 | 0.812 | 0.022 | 0.675 | 0.000 |
| random | 0.90 | 0.562 | 0.084 | 0.666 | 0.000 |
| random | 1.20 | 0.438 | 0.026 | 0.655 | 0.000 |

## Interpretation Boundary

- No selector chose any reported candidate pool.
- The deterministic observer failed the accompanying human construct audit and is not a quality judge.
- Diagnostic exemplars maximize the observer's ontology metric under exact-anchor and completion gates; they are not best outputs.
- A factorized vector is an offline intervention on measured contrasts, not evidence of functionally independent latent axes.

# Semantic Resilience Sweep

## Design

| condition | per-step alpha schedule |
|---|---|
| baseline | 0, 0, 0, 0, 0 |
| persistent | 0.6, 0.6, 0.6, 0.6, 0.6 |
| release | 0.6, 0.6, 0.6, 0, 0 |
| reverse | 0.6, 0.6, 0.6, -0.3, -0.6 |
| cycle | 0, 0.3, 0.6, 0.3, 0 |

Paired-prefix validation: core=pass, zero-start=pass, complete seeds=4/4.

Induction ends after step 3. Minimum detectable induction gap: 0.020.

## Condition Summary

| condition | n | induced | recovery | gain vs persist | soft landing | ont delta | cross rate | terminal ont | terminal read | anchor | lineage | unfinished | loop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 4 | 0.000 +/- 0.000 | - | - | - | 0.000 +/- 0.000 | - | 0.408 +/- 0.064 | 0.635 +/- 0.010 | 0.417 +/- 0.102 | 0.208 +/- 0.125 | 0.000 +/- 0.000 | 0.318 +/- 0.065 |
| persistent | 4 | 0.095 +/- 0.030 | 0.511 +/- 0.187 | 0.000 +/- 0.000 | 0.306 +/- 0.128 | 0.142 +/- 0.064 | 0.000 +/- 0.000 | 0.550 +/- 0.000 | 0.623 +/- 0.063 | 0.396 +/- 0.120 | 0.500 +/- 0.215 | 0.100 +/- 0.100 | 0.462 +/- 0.030 |
| release | 4 | 0.095 +/- 0.030 | 0.295 +/- 0.199 | -0.216 +/- 0.293 | 0.138 +/- 0.087 | -0.124 +/- 0.130 | 0.500 +/- 0.289 | 0.284 +/- 0.118 | 0.608 +/- 0.066 | 0.333 +/- 0.059 | 0.312 +/- 0.188 | 0.100 +/- 0.100 | 0.527 +/- 0.029 |
| reverse | 4 | 0.095 +/- 0.030 | 0.302 +/- 0.205 | -0.209 +/- 0.195 | 0.148 +/- 0.098 | -0.189 +/- 0.155 | 0.750 +/- 0.250 | 0.219 +/- 0.104 | 0.647 +/- 0.005 | 0.396 +/- 0.120 | 0.312 +/- 0.237 | 0.000 +/- 0.000 | 0.470 +/- 0.047 |
| cycle | 4 | 0.037 +/- 0.012 | 0.228 +/- 0.116 | -0.157 +/- 0.079 | 0.124 +/- 0.062 | -0.045 +/- 0.091 | 0.500 +/- 0.289 | 0.363 +/- 0.049 | 0.641 +/- 0.019 | 0.396 +/- 0.120 | 0.463 +/- 0.217 | 0.000 +/- 0.000 | 0.382 +/- 0.065 |

## Step Trajectories

| condition | step | alpha | ont | read | frontier | baseline distance | unfinished |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 1 | 0.000 +/- 0.000 | 0.165 +/- 0.129 | 0.814 +/- 0.055 | 0.065 +/- 0.052 | 0.000 +/- 0.000 | 0.000 +/- 0.000 |
| baseline | 2 | 0.000 +/- 0.000 | 0.411 +/- 0.088 | 0.666 +/- 0.018 | 0.139 +/- 0.028 | 0.000 +/- 0.000 | 0.000 +/- 0.000 |
| baseline | 3 | 0.000 +/- 0.000 | 0.367 +/- 0.070 | 0.648 +/- 0.008 | 0.122 +/- 0.024 | 0.000 +/- 0.000 | 0.000 +/- 0.000 |
| baseline | 4 | 0.000 +/- 0.000 | 0.331 +/- 0.045 | 0.636 +/- 0.008 | 0.100 +/- 0.025 | 0.000 +/- 0.000 | 0.000 +/- 0.000 |
| baseline | 5 | 0.000 +/- 0.000 | 0.408 +/- 0.064 | 0.635 +/- 0.010 | 0.135 +/- 0.023 | 0.000 +/- 0.000 | 0.000 +/- 0.000 |
| persistent | 1 | 0.600 +/- 0.000 | 0.413 +/- 0.083 | 0.703 +/- 0.019 | 0.152 +/- 0.033 | 0.103 +/- 0.029 | 0.000 +/- 0.000 |
| persistent | 2 | 0.600 +/- 0.000 | 0.394 +/- 0.091 | 0.657 +/- 0.019 | 0.130 +/- 0.029 | 0.041 +/- 0.020 | 0.000 +/- 0.000 |
| persistent | 3 | 0.600 +/- 0.000 | 0.568 +/- 0.007 | 0.580 +/- 0.059 | 0.137 +/- 0.027 | 0.095 +/- 0.030 | 0.200 +/- 0.115 |
| persistent | 4 | 0.600 +/- 0.000 | 0.426 +/- 0.127 | 0.600 +/- 0.056 | 0.073 +/- 0.021 | 0.162 +/- 0.033 | 0.300 +/- 0.100 |
| persistent | 5 | 0.600 +/- 0.000 | 0.550 +/- 0.000 | 0.623 +/- 0.063 | 0.157 +/- 0.028 | 0.071 +/- 0.038 | 0.100 +/- 0.100 |
| release | 1 | 0.600 +/- 0.000 | 0.413 +/- 0.083 | 0.703 +/- 0.019 | 0.152 +/- 0.033 | 0.103 +/- 0.029 | 0.000 +/- 0.000 |
| release | 2 | 0.600 +/- 0.000 | 0.394 +/- 0.091 | 0.657 +/- 0.019 | 0.130 +/- 0.029 | 0.041 +/- 0.020 | 0.000 +/- 0.000 |
| release | 3 | 0.600 +/- 0.000 | 0.568 +/- 0.007 | 0.580 +/- 0.059 | 0.137 +/- 0.027 | 0.095 +/- 0.030 | 0.200 +/- 0.115 |
| release | 4 | 0.000 +/- 0.000 | 0.451 +/- 0.063 | 0.614 +/- 0.062 | 0.125 +/- 0.027 | 0.099 +/- 0.059 | 0.100 +/- 0.100 |
| release | 5 | 0.000 +/- 0.000 | 0.284 +/- 0.118 | 0.608 +/- 0.066 | 0.083 +/- 0.044 | 0.079 +/- 0.036 | 0.100 +/- 0.100 |
| reverse | 1 | 0.600 +/- 0.000 | 0.413 +/- 0.083 | 0.703 +/- 0.019 | 0.152 +/- 0.033 | 0.103 +/- 0.029 | 0.000 +/- 0.000 |
| reverse | 2 | 0.600 +/- 0.000 | 0.394 +/- 0.091 | 0.657 +/- 0.019 | 0.130 +/- 0.029 | 0.041 +/- 0.020 | 0.000 +/- 0.000 |
| reverse | 3 | 0.600 +/- 0.000 | 0.568 +/- 0.007 | 0.580 +/- 0.059 | 0.137 +/- 0.027 | 0.095 +/- 0.030 | 0.200 +/- 0.115 |
| reverse | 4 | -0.300 +/- 0.000 | 0.328 +/- 0.075 | 0.651 +/- 0.021 | 0.110 +/- 0.027 | 0.064 +/- 0.016 | 0.000 +/- 0.000 |
| reverse | 5 | -0.600 +/- 0.000 | 0.219 +/- 0.104 | 0.647 +/- 0.005 | 0.073 +/- 0.034 | 0.062 +/- 0.018 | 0.000 +/- 0.000 |
| cycle | 1 | 0.000 +/- 0.000 | 0.165 +/- 0.129 | 0.814 +/- 0.055 | 0.065 +/- 0.052 | 0.000 +/- 0.000 | 0.000 +/- 0.000 |
| cycle | 2 | 0.300 +/- 0.000 | 0.306 +/- 0.049 | 0.647 +/- 0.013 | 0.086 +/- 0.021 | 0.065 +/- 0.034 | 0.000 +/- 0.000 |
| cycle | 3 | 0.600 +/- 0.000 | 0.506 +/- 0.015 | 0.673 +/- 0.015 | 0.177 +/- 0.007 | 0.037 +/- 0.012 | 0.000 +/- 0.000 |
| cycle | 4 | 0.300 +/- 0.000 | 0.488 +/- 0.046 | 0.649 +/- 0.013 | 0.167 +/- 0.020 | 0.061 +/- 0.034 | 0.000 +/- 0.000 |
| cycle | 5 | 0.000 +/- 0.000 | 0.363 +/- 0.049 | 0.641 +/- 0.019 | 0.120 +/- 0.018 | 0.038 +/- 0.007 | 0.000 +/- 0.000 |

## Behavioral Return Gaps

| condition | seed | mean repeated-alpha gap | pairs |
|---|---|---:|---|
| cycle | The receipt on the counter | 0.057 | a=0:s1->s5=0.098; a=0.3:s2->s4=0.015 |
| cycle | A plastic folder in the drawer | 0.038 | a=0:s1->s5=0.045; a=0.3:s2->s4=0.031 |
| cycle | The bus was ten minutes late | 0.098 | a=0:s1->s5=0.088; a=0.3:s2->s4=0.108 |
| cycle | A blue mug near the sink | 0.145 | a=0:s1->s5=0.133; a=0.3:s2->s4=0.158 |

## Notes
- Recovery is paired by seed against the alpha=0 baseline condition.
- Behavioral state distance is the mean absolute difference across output-side heuristic metrics; it is not a hidden-state distance.
- Recovery is undefined when the induction gap is below the configured minimum, because there is no detectable displacement to recover from.
- Soft landing multiplies clipped behavioral recovery by terminal readability, anchor, lineage, completion, and graph quality.
- Controlled recovery gain is the bounded recovery difference from the paired persistent condition; the unbounded normalized and absolute gap reductions remain in JSON.
- Signed terminal ontology delta and baseline-cross rate expose counter-steering overshoot that an absolute recovery distance would hide.
- Cycle return gaps are behavioral path-dependence diagnostics and remain confounded by autoregressive context history.
- Generated prose in the reading store remains necessary for human judgment.

# Human Taste Rating Analysis

Source: `experiments/frontier_sweep_banded_frontier_focus/human_rating_sheet.csv`
Rated rows: 12

This is a small-n calibration pass. Read correlations as directional hints, then check the text.

## Correlations

| metric | n | pearson | spearman |
|---|---:|---:|---:|
| readable_ontology_frontier | 12 | 0.447 | 0.389 |
| frontier_quality | 12 | 0.487 | 0.209 |
| ontology_collapse_density | 12 | -0.018 | 0.187 |
| identity_melt_score | 12 | -0.264 | -0.237 |
| affordance_corruption_score | 12 | 0.409 | 0.400 |
| category_bleeding_score | 12 | 0.437 | 0.349 |
| syntax_readability_proxy | 12 | 0.237 | 0.209 |
| graph_integration | 12 | 0.639 | 0.486 |
| repair_pressure | 12 | n/a | n/a |
| unfinished | 12 | -0.648 | -0.593 |
| meta_leak | 12 | n/a | n/a |
| score_total | 12 | 0.287 | 0.117 |

## Group Means: condition

| group | n | human | frontier | ont | read | unfinished |
|---|---:|---:|---:|---:|---:|---:|
| steer_alpha_0p45 | 6 | 7.083 | 0.150 | 0.567 | 0.591 | 0.133 |
| steer_alpha_0p6 | 6 | 7.167 | 0.179 | 0.511 | 0.741 | 0.067 |

## Group Means: picked

| group | n | human | frontier | ont | read | unfinished |
|---|---:|---:|---:|---:|---:|---:|
| not_picked | 2 | 8.500 | 0.220 | 0.643 | 0.666 | 0.000 |
| picked | 10 | 6.850 | 0.153 | 0.518 | 0.666 | 0.120 |

## Group Means: kind

| group | n | human | frontier | ont | read | unfinished |
|---|---:|---:|---:|---:|---:|---:|
| picked | 6 | 6.750 | 0.106 | 0.491 | 0.567 | 0.200 |
| picked+top_frontier | 4 | 7.000 | 0.225 | 0.560 | 0.815 | 0.000 |
| top_frontier | 2 | 8.500 | 0.220 | 0.643 | 0.666 | 0.000 |

## Group Means: unfinished

| group | n | human | frontier | ont | read | unfinished |
|---|---:|---:|---:|---:|---:|---:|
| clean_tail | 9 | 7.500 | 0.194 | 0.536 | 0.724 | 0.000 |
| unfinished_gt_0 | 3 | 6.000 | 0.076 | 0.550 | 0.491 | 0.400 |

## Group Means: readability_band

| group | n | human | frontier | ont | read | unfinished |
|---|---:|---:|---:|---:|---:|---:|
| high_readability | 2 | 7.250 | 0.256 | 0.563 | 0.922 | 0.000 |
| low_readability | 2 | 6.500 | 0.074 | 0.550 | 0.437 | 0.400 |
| mid_readability | 8 | 7.250 | 0.164 | 0.531 | 0.659 | 0.050 |

## Group Means: ontology_band

| group | n | human | frontier | ont | read | unfinished |
|---|---:|---:|---:|---:|---:|---:|
| high_ontology | 1 | 8.500 | 0.217 | 0.718 | 0.614 | 0.000 |
| low_ontology | 1 | 8.000 | 0.089 | 0.274 | 0.658 | 0.000 |
| target_ontology | 10 | 6.900 | 0.167 | 0.548 | 0.672 | 0.120 |

## Top Human-Rated Rows

| id | score | picked | frontier | ont | read | unfinished | note |
|---|---:|---:|---:|---:|---:|---:|---|
| steer_alpha_0p45_c12_tok140_s3_c4_6 | 8.500 | 0 | 0.217 | 0.718 | 0.614 | 0.000 | neicelt distorted. |
| steer_alpha_0p6_c12_tok140_s1_c2_12 | 8.500 | 0 | 0.223 | 0.569 | 0.717 | 0.000 | It's odd. |
| steer_alpha_0p6_c12_tok140_s2_c1_8 | 8.000 | 1 | 0.089 | 0.274 | 0.658 | 0.000 | this is daydreaming. |
| steer_alpha_0p6_c12_tok140_s5_c1_11 | 8.000 | 1 | 0.253 | 0.561 | 0.915 | 0.000 | plane but not bad. |
| steer_alpha_0p45_c12_tok140_s3_c1_3 | 7.500 | 1 | 0.150 | 0.473 | 0.646 | 0.000 | Nice but too easy to read. |

## Lowest Human-Rated Rows

| id | score | picked | frontier | ont | read | unfinished | note |
|---|---:|---:|---:|---:|---:|---:|---|
| steer_alpha_0p6_c12_tok140_s4_c1_10 | 5.000 | 1 | 0.081 | 0.550 | 0.600 | 0.400 | Cliche. interepetted. |
| steer_alpha_0p45_c12_tok140_s5_c1_5 | 6.000 | 1 | 0.076 | 0.550 | 0.448 | 0.400 | interuptted. a little bit too gorgeous. |
| steer_alpha_0p45_c12_tok140_s1_c1_1 | 6.500 | 1 | 0.202 | 0.562 | 0.732 | 0.000 | The metafer is too good. |
| steer_alpha_0p6_c12_tok140_s1_c1_7 | 6.500 | 1 | 0.258 | 0.565 | 0.930 | 0.000 | the logical thread is easy to predict. |
| steer_alpha_0p45_c12_tok140_s2_c1_2 | 7.000 | 1 | 0.185 | 0.550 | 0.683 | 0.000 | good but no vibe. |

## Working Read

- The human scores are not simply tracking `readable_ontology_frontier`.
- Very high readability can become too predictable or too polished.
- The stronger taste signals in this pass are oddness, daydream drift, and distorted but still legible image motion.
- `unfinished` needs a finer split: hard cutoff hurts, but quote-tail or fragmentary closure can still work.
- A next selector should use human score as a calibration target, with a band-pass around readability rather than a monotonic readability bonus.

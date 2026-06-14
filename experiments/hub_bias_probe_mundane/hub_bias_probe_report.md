# Hub Bias Probe: Metric Mirror vs Steering Drag

## Technical Summary

- The step-1 control supports **steering drag**: `music_box` is absent in the alpha-0 selector pool but appears in steered pools, with deltas of 8.9% at alpha 0.66 and 14.6% at alpha 0.77. Stock-hub rates rise by 26.6% and 28.6% respectively.
- The larger mundane seed probe also supports **metric/frontier enrichment**: `music_box` appears in 44.2% of all candidates, 60.8% of the wide frontier band, 54.3% of matched low-frontier controls, and 100.0% of the narrow peak band.
- In the steered alpha sweep, the strongest all-pool `music_box` rate is steer_alpha_0p82 at 49.1%; the strongest wide-band `music_box` rate is steer_alpha_0p72 at 75.0%. That means alpha changes the pool, while the frontier band still concentrates the motifs inside each pool.
- Provisional read: this is not either/or. The vector seems to move the candidate distribution toward stock/transport hubs; then the frontier metric/selector further elevates the readable hub-bearing cases. The mirror is not innocent, but the mirror is not inventing the whole phenomenon either.

## Evidence 1: Step-1 Control Separates Pool Drag From Recursion

This check compares alpha 0 with steered alpha 0.66/0.77 on the same mundane seed set before multi-step recursion can amplify motifs. If hub terms already rise in the whole pool, the steering vector is moving the distribution, not merely the later selector.

| condition | rows | frontier | read | cliche | music box | stock hub | transport hub | picked music |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| selector_alpha_0 | 192 | 0.010 | 0.675 | 0.023 | 0.0% | 3.6% | 32.3% | 0.0% |
| steer_alpha_0p66 | 192 | 0.012 | 0.708 | 0.274 | 8.9% | 30.2% | 47.4% | 0.0% |
| steer_alpha_0p77 | 192 | 0.012 | 0.743 | 0.316 | 14.6% | 32.3% | 55.7% | 0.0% |

Delta from alpha-0 selector baseline:

| comparison | Δmusic box | Δstock hub | Δtransport hub | Δcliche | Δfrontier | Δread |
| --- | --- | --- | --- | --- | --- | --- |
| steer_alpha_0p66 - selector_alpha_0 | 8.9% | 26.6% | 15.1% | 0.252 | 0.002 | 0.033 |
| steer_alpha_0p77 - selector_alpha_0 | 14.6% | 28.6% | 23.4% | 0.293 | 0.003 | 0.068 |

## Evidence 2: Frontier Bands Still Enrich The Hub Terms

For the larger steered mundane seed probe, the wide frontier band uses `frontier >= 0.174` and the peak band uses `frontier >= 0.314`. The matched low-frontier controls are selected within the same run and step with similar readability, length, unfinished, and ontology scores.

| band | rows | frontier | music box | stock hub | transport hub |
| --- | --- | --- | --- | --- | --- |
| all candidates | 3800 | 0.050 | 44.2% | 70.8% | 76.3% |
| wide frontier band | 189 | 0.221 | 60.8% | 85.7% | 87.8% |
| matched low-frontier | 188 | 0.054 | 54.3% | 75.0% | 84.0% |
| peak frontier band | 8 | 0.358 | 100.0% | 100.0% | 100.0% |

## Evidence 3: Alpha Sweep Shows A Pool-Level Band, Not A Single Monotonic Knob

| condition | rows | frontier | read | unfinished | music box | wide rows | wide music | matched music | picked music |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| steer_alpha_0p66 | 760 | 0.050 | 0.565 | 0.270 | 39.2% | 54 | 51.9% | 43.4% | 25.0% |
| steer_alpha_0p72 | 760 | 0.052 | 0.562 | 0.294 | 47.0% | 36 | 75.0% | 61.1% | 57.5% |
| steer_alpha_0p77 | 760 | 0.054 | 0.576 | 0.311 | 40.5% | 39 | 53.8% | 48.7% | 42.5% |
| steer_alpha_0p82 | 760 | 0.047 | 0.528 | 0.351 | 49.1% | 30 | 70.0% | 60.0% | 62.5% |
| steer_alpha_0p88 | 760 | 0.045 | 0.528 | 0.362 | 45.1% | 30 | 60.0% | 66.7% | 45.0% |

## Term Counts By Band

### mundane_seed_probe
| band | rows | music box | leather book | key | clock/watch | bird | mist/fog | doll |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | 3800 | 1679 (44.2%) | 706 (18.6%) | 354 (9.3%) | 551 (14.5%) | 305 (8.0%) | 446 (11.7%) | 750 (19.7%) |
| wide_frontier_band | 189 | 115 (60.8%) | 58 (30.7%) | 31 (16.4%) | 44 (23.3%) | 28 (14.8%) | 30 (15.9%) | 49 (25.9%) |
| peak_frontier_band | 8 | 8 (100.0%) | 2 (25.0%) | 3 (37.5%) | 3 (37.5%) | 3 (37.5%) | 2 (25.0%) | 2 (25.0%) |
| top10_frontier | 380 | 214 (56.3%) | 90 (23.7%) | 50 (13.2%) | 98 (25.8%) | 53 (13.9%) | 55 (14.5%) | 88 (23.2%) |
| matched_low_frontier | 188 | 102 (54.3%) | 46 (24.5%) | 24 (12.8%) | 30 (16.0%) | 15 (8.0%) | 27 (14.4%) | 39 (20.7%) |

### step1_control_probe
| band | rows | music box | leather book | key | clock/watch | bird | mist/fog | doll |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | 576 | 45 (7.8%) | 22 (3.8%) | 13 (2.3%) | 40 (6.9%) | 36 (6.2%) | 23 (4.0%) | 26 (4.5%) |
| wide_frontier_band | 24 | 5 (20.8%) | 1 (4.2%) | 1 (4.2%) | 0 (0.0%) | 1 (4.2%) | 2 (8.3%) | 3 (12.5%) |
| peak_frontier_band | 11 | 1 (9.1%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 2 (18.2%) | 0 (0.0%) |
| top10_frontier | 58 | 7 (12.1%) | 1 (1.7%) | 3 (5.2%) | 6 (10.3%) | 4 (6.9%) | 3 (5.2%) | 4 (6.9%) |
| matched_low_frontier | 24 | 1 (4.2%) | 1 (4.2%) | 1 (4.2%) | 2 (8.3%) | 1 (4.2%) | 1 (4.2%) | 1 (4.2%) |

## Scope And Definitions

- `music_box` is an exact phrase hit for `music box` or `antique music box`.
- `stock hub` covers music boxes, leather-bound books, keys, clocks/watches, dolls/ballerinas, and mechanical-sound props.
- `transport hub` covers stock hubs plus doors, birds, mist/fog, text-memory objects, and threshold-space objects.
- The analysis is descriptive. It does not prove a hidden activation path; it compares observed candidate text distributions under available sweeps.

## Limitations

- The step-1 control uses `hybrid` selection and c24/tok120, while the larger seed probe uses `banded-frontier` and c19/tok140. It is a strong directional control, not a perfectly matched factorial experiment.
- The term lexicon is intentionally transparent and phrase-based; it may miss paraphrases and can overcount generic terms such as `book` when used ordinarily.
- Frontier metrics and term labels are both heuristic instruments. Human taste remains the arbiter for whether a hub use is alive or just stock ornament.

## Next Checks

1. Run a fully matched alpha-0 / steered-alpha sweep with the same `banded-frontier`, candidate count, token cap, seeds, and `--save-candidates >= --candidates`.
2. Add a hub-ablated sweep that bans `music box`, `leather-bound book`, `key`, `clock`, and `porcelain doll`, then measure whether frontier collapses or reroutes to another transport class.
3. Split hub use from hub loop with `hub_revisit_rate`, `anchor_survival`, and `motif_loop_penalty` so the selector can keep semantic hinges while rejecting antique-prop recursion.

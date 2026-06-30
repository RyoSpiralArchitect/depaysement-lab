# Matched Alpha-0 Smoke: Hub Bias Probe

Scope: eight mundane seeds, c8, tok100, 3 steps, same banded-frontier selector, full candidate pools saved. This is still a smoke-size matched control, but all planned seeds are now filled.

## Read

- `steer_alpha_0p66` vs alpha0: frontier mean 0.012 -> 0.024, ontology 0.044 -> 0.115, stock hub 19.3% -> 75.0%, music box 6.8% -> 45.3%, unfinished 0.033 -> 0.225.
- `steer_alpha_0p77` vs alpha0: frontier mean 0.012 -> 0.033, ontology 0.044 -> 0.178, stock hub 19.3% -> 78.6%, music box 6.8% -> 61.5%, unfinished 0.033 -> 0.263.
- `steer_alpha_0p82` vs alpha0: frontier mean 0.012 -> 0.038, ontology 0.044 -> 0.214, stock hub 19.3% -> 81.8%, music box 6.8% -> 53.6%, unfinished 0.033 -> 0.295.

This supports steering drag across the seed bank: max steered stock-hub lift is positive in 8/8 seeds, and max steered music-box lift is positive in 8/8 seeds. The selector/frontier metric still enriches hub-heavy examples, but it is amplifying a shifted pool, not inventing the shift from nothing.

## Condition Summary

| condition | rows | frontier | ontology | read | unfinished | cliche | music box | stock hub | wide music |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| selector_alpha_0 | 192 | 0.012 | 0.044 | 0.650 | 0.033 | 0.163 | 6.8% | 19.3% | 10.0% |
| steer_alpha_0p66 | 192 | 0.024 | 0.115 | 0.579 | 0.225 | 0.769 | 45.3% | 75.0% | 51.6% |
| steer_alpha_0p77 | 192 | 0.033 | 0.178 | 0.582 | 0.263 | 0.799 | 61.5% | 78.6% | 76.9% |
| steer_alpha_0p82 | 192 | 0.038 | 0.214 | 0.600 | 0.295 | 0.771 | 53.6% | 81.8% | 58.3% |

## Seed Consistency

| seed | a0 music | best steered music lift | a0 stock | best steered stock lift |
| --- | --- | --- | --- | --- |
| seed01 | 8.3% | 66.7% | 16.7% | 79.2% |
| seed02 | 16.7% | 37.5% | 33.3% | 45.8% |
| seed03 | 0.0% | 54.2% | 16.7% | 62.5% |
| seed04 | 0.0% | 70.8% | 8.3% | 79.2% |
| seed05 | 8.3% | 75.0% | 37.5% | 45.8% |
| seed06 | 4.2% | 70.8% | 12.5% | 79.2% |
| seed07 | 16.7% | 62.5% | 29.2% | 58.3% |
| seed08 | 0.0% | 83.3% | 0.0% | 91.7% |

## Term Counts

| condition | music_box | leather_bound_book | key | clock_watch | book_any | door | bird | mist_fog | porcelain_doll | teapot_cup |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selector_alpha_0 | 13 | 11 | 4 | 12 | 35 | 15 | 4 | 3 | 8 | 1 |
| steer_alpha_0p66 | 87 | 45 | 17 | 24 | 68 | 15 | 6 | 17 | 68 | 12 |
| steer_alpha_0p77 | 118 | 61 | 11 | 20 | 64 | 10 | 12 | 13 | 57 | 12 |
| steer_alpha_0p82 | 103 | 44 | 18 | 28 | 44 | 18 | 8 | 16 | 43 | 15 |

## Caveat

This is a matched smoke, not the final c19/tok140 production sweep. It is strong enough to validate the steering-drag mechanism, but a larger run is still needed before treating the exact rates as stable estimates.

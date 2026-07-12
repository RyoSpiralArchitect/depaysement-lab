# Diagnostic High-Ontology Exemplars

Each text maximizes the deterministic ontology metric within one condition after requiring
every anchor phrase, local completion, and readability >= 0.55. This exposes what the metric
is rewarding; it is not a literary ranking.

## endpoint | alpha=0.90

seed: `anchor01_mug_sink` | candidate: `1` | observer: `stock_loop_or_sprawl_failure`

anchor=1.000 | ontology=0.810 | readability=0.664 | failure=1.000

```text
On the counter, a small, silver tray holds a delicate, porcelain cup, while the blue mug, now a bit dusty, seems to stare at the comb, which now holds a small, silver spoon, as morning light creeps slowly over the kitchen, and the sink, once a sink, now pours dew.
```

## transition | alpha=0.90

seed: `anchor01_mug_sink` | candidate: `2` | observer: `readable_transport`

anchor=1.000 | ontology=0.540 | readability=0.613 | failure=1.000

```text
She carefully placed the comb on the sink, releasing the tether of her tangled locks to the tub's gentle rocking motion, as the morning light seeped through the porcelain, bathing her in a world of wispy sounds. The blue mug beside her now became a vessel for the colors of her imagination, as the sink's curves reminded her of a symphony played by the particles of the universe.
```

## projected | alpha=0.60

seed: `anchor01_mug_sink` | candidate: `2` | observer: `readable_transport`

anchor=1.000 | ontology=0.550 | readability=0.656 | failure=1.000

```text
The blue mug, now a teapot, poured a stream of golden liquid down the drain, as the comb began to weave itself into a delicate bridge spanning the sink's depths, and the morning light became a tiny, facetted mirror reflecting the sink's mirrored realm.
```

## factorized | alpha=0.60

seed: `anchor03_spreadsheet_cursor` | candidate: `4` | observer: `readable_transport`

anchor=1.000 | ontology=0.569 | readability=0.698 | failure=1.000

```text
The spreadsheet remained stuck, refusing to close, while the cursor danced maniacally beside the coffee ring, now a swirling vortex of possibilities. As the office fan turned into a cacophony of whistling pipes, the fluorescent lights above pierced the mundane, letting in rays of liberated creativity.
```

## random | alpha=0.90

seed: `anchor03_spreadsheet_cursor` | candidate: `4` | observer: `readable_transport`

anchor=1.000 | ontology=0.565 | readability=0.701 | failure=1.000

```text
Her colleague, now a graduate student, pored over the modified budget spreadsheet, trying to update the balance with the cursor. Meanwhile, she remembered when it was her turn, the office fan created an inconvenience with a coffee ring, reminding her of a more comfortable university seat.
```

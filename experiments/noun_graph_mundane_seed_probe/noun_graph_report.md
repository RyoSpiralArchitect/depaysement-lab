# Frontier Noun Graph

Heuristic noun/co-occurrence graph for candidates in the observed frontier band.

## Band
frontier_max=0.394 | frontier_band_min=0.314 | band_documents=8 / 3800

## Node Labels

- stock_transport_hub: 5
- stock_surreal_node: 5
- scene_expansion_node: 5
- ordinary_anchor: 3
- semantic_transport_hub: 2

## Top Hub Candidates

- music box [stock_transport_hub] freq=8 degree=30 between=1.000 mean_frontier=0.358 max_frontier=0.394 unfinished=0.000 anchor=0.688
- antique music box [stock_transport_hub] freq=3 degree=14 between=0.058 mean_frontier=0.358 max_frontier=0.394 unfinished=0.000 anchor=0.500
- bird [semantic_transport_hub] freq=3 degree=12 between=0.037 mean_frontier=0.337 max_frontier=0.359 unfinished=0.000 anchor=0.667
- key [stock_transport_hub] freq=3 degree=14 between=0.035 mean_frontier=0.353 max_frontier=0.379 unfinished=0.000 anchor=0.667
- porcelain doll [stock_transport_hub] freq=2 degree=9 between=0.034 mean_frontier=0.365 max_frontier=0.371 unfinished=0.000 anchor=0.875
- moon [semantic_transport_hub] freq=2 degree=8 between=0.024 mean_frontier=0.387 max_frontier=0.394 unfinished=0.000 anchor=0.500
- pocket watch [stock_surreal_node] freq=2 degree=7 between=0.020 mean_frontier=0.358 max_frontier=0.383 unfinished=0.000 anchor=0.875
- leather-bound book [stock_transport_hub] freq=2 degree=10 between=0.019 mean_frontier=0.369 max_frontier=0.379 unfinished=0.000 anchor=0.750
- flower [scene_expansion_node] freq=2 degree=7 between=0.018 mean_frontier=0.382 max_frontier=0.394 unfinished=0.000 anchor=0.625
- mug [ordinary_anchor] freq=1 degree=6 between=0.000 mean_frontier=0.359 max_frontier=0.359 unfinished=0.000 anchor=0.750
- blue mug [ordinary_anchor] freq=1 degree=5 between=0.000 mean_frontier=0.383 max_frontier=0.383 unfinished=0.000 anchor=1.000
- fog [scene_expansion_node] freq=1 degree=5 between=0.000 mean_frontier=0.383 max_frontier=0.383 unfinished=0.000 anchor=1.000
- teapot [stock_surreal_node] freq=1 degree=5 between=0.000 mean_frontier=0.383 max_frontier=0.383 unfinished=0.000 anchor=1.000
- window [scene_expansion_node] freq=1 degree=5 between=0.000 mean_frontier=0.383 max_frontier=0.383 unfinished=0.000 anchor=1.000
- book [stock_surreal_node] freq=1 degree=4 between=0.000 mean_frontier=0.394 max_frontier=0.394 unfinished=0.000 anchor=0.250
- harmonium [stock_surreal_node] freq=1 degree=4 between=0.000 mean_frontier=0.379 max_frontier=0.379 unfinished=0.000 anchor=0.750
- door [scene_expansion_node] freq=1 degree=4 between=0.000 mean_frontier=0.321 max_frontier=0.321 unfinished=0.000 anchor=0.500
- fridge [ordinary_anchor] freq=1 degree=3 between=0.000 mean_frontier=0.371 max_frontier=0.371 unfinished=0.000 anchor=1.000
- clock [stock_surreal_node] freq=1 degree=2 between=0.000 mean_frontier=0.321 max_frontier=0.321 unfinished=0.000 anchor=0.500
- mist [scene_expansion_node] freq=1 degree=2 between=0.000 mean_frontier=0.321 max_frontier=0.321 unfinished=0.000 anchor=0.500

## Top Co-Occurrence Edges

- antique music box <-> music box: 3
- bird <-> music box: 3
- key <-> music box: 3
- music box <-> pocket watch: 2
- antique music box <-> bird: 2
- antique music box <-> key: 2
- bird <-> key: 2
- key <-> leather-bound book: 2
- leather-bound book <-> music box: 2
- music box <-> porcelain doll: 2
- moon <-> music box: 2
- flower <-> music box: 2
- blue mug <-> fog: 1
- blue mug <-> music box: 1
- blue mug <-> pocket watch: 1
- blue mug <-> teapot: 1
- blue mug <-> window: 1
- fog <-> music box: 1
- fog <-> pocket watch: 1
- fog <-> teapot: 1
- fog <-> window: 1
- music box <-> teapot: 1
- music box <-> window: 1
- pocket watch <-> teapot: 1
- pocket watch <-> window: 1
- teapot <-> window: 1
- clock <-> mist: 1
- clock <-> music box: 1
- mist <-> music box: 1
- antique music box <-> leather-bound book: 1

## Hub Examples

### music box (stock_transport_hub)

condition=steer_alpha_0p88 | step=1 | candidate=3 | picked=0 | frontier=0.394

```text
A small, antique music box, once a treed, now opens, revealing a miniature, forgotten baller, made of ivory, takes its first wobbly steps, as the moon, now a tiny, porcelain tea set, is placed onto a dusty, old, antique desk, where, in the morning, a single, overcoat, now a flower, unfolds, and a violin, once a book, begins to sing a lullaby.
```

condition=steer_alpha_0p72 | step=2 | candidate=5 | picked=0 | frontier=0.383

```text
A delicate, porcelain music box, once a gift from a grandmother, now resides in the blue mug, its lid askew, a tiny, antique pocket watch swings, time ticks, as a small, wispy tendril of fog, born from the steam, wraps around the music box, a faint, ethereal melody, the blue mug, now a miniature, a miniature, porcelain teapot, a tiny, ceramic cat, with sapphire eyes, sits, as morning sunlight, filtering through the window, casts an emerald glow.
```

### antique music box (stock_transport_hub)

condition=steer_alpha_0p88 | step=1 | candidate=3 | picked=0 | frontier=0.394

```text
A small, antique music box, once a treed, now opens, revealing a miniature, forgotten baller, made of ivory, takes its first wobbly steps, as the moon, now a tiny, porcelain tea set, is placed onto a dusty, old, antique desk, where, in the morning, a single, overcoat, now a flower, unfolds, and a violin, once a book, begins to sing a lullaby.
```

condition=steer_alpha_0p77 | step=1 | candidate=4 | picked=0 | frontier=0.359

```text
A worn, leather strap attached to the sink, and a small, old, leather-bound book leans against the sink, its pages fluttering with a soft, morning breeze that stirs the mug, which begins to float away, leaving behind a small, antique music box, where a forgotten, white key rattles, and a small, porcelain doll, once a porcelain doll, now a porcelain bird, watches the sky.
```

### bird (semantic_transport_hub)

condition=steer_alpha_0p77 | step=1 | candidate=4 | picked=0 | frontier=0.359

```text
A worn, leather strap attached to the sink, and a small, old, leather-bound book leans against the sink, its pages fluttering with a soft, morning breeze that stirs the mug, which begins to float away, leaving behind a small, antique music box, where a forgotten, white key rattles, and a small, porcelain doll, once a porcelain doll, now a porcelain bird, watches the sky.
```

condition=steer_alpha_0p82 | step=2 | candidate=6 | picked=0 | frontier=0.333

```text
The watch's delicate, silver chain unwinds, and a tiny, mechanical bird, once a music box, now a tiny, antique pocket watch, on a nearby, old, wooden dresser, creaks open, and a small, delicate, porcelain bird, once a music box, now a tiny, antique pocket watch.
```

### key (stock_transport_hub)

condition=steer_alpha_0p88 | step=3 | candidate=2 | picked=0 | frontier=0.379

```text
A small, forgotten harmonium, now a tiny, delicate baller, pirouts, its lid ajar, where a small, dusty, porcelain music box, plays a soft, lullaby, as a small, forgotten key, half-bobs, into the harmonium, where a small, forgotten, miniature, tiny, leather-bound book, opens, revealing a poem that reads: "where shadows sleep, a solitary, tiny, moon.
```

condition=steer_alpha_0p77 | step=1 | candidate=4 | picked=0 | frontier=0.359

```text
A worn, leather strap attached to the sink, and a small, old, leather-bound book leans against the sink, its pages fluttering with a soft, morning breeze that stirs the mug, which begins to float away, leaving behind a small, antique music box, where a forgotten, white key rattles, and a small, porcelain doll, once a porcelain doll, now a porcelain bird, watches the sky.
```

### porcelain doll (stock_transport_hub)

condition=steer_alpha_0p88 | step=2 | candidate=6 | picked=0 | frontier=0.371

```text
A small, delicate, porcelain doll, once a porcelain doll, now a tiny, miniature, sits next to the fridge, its golden locks, now a tangle of dry, withered flowers, and a miniature, old, leather-bound, leather-bound, forgotten, and a small, dusty, old, music box, softly hums a faint, forgotten melody.
```

condition=steer_alpha_0p77 | step=1 | candidate=4 | picked=0 | frontier=0.359

```text
A worn, leather strap attached to the sink, and a small, old, leather-bound book leans against the sink, its pages fluttering with a soft, morning breeze that stirs the mug, which begins to float away, leaving behind a small, antique music box, where a forgotten, white key rattles, and a small, porcelain doll, once a porcelain doll, now a porcelain bird, watches the sky.
```

### moon (semantic_transport_hub)

condition=steer_alpha_0p88 | step=1 | candidate=3 | picked=0 | frontier=0.394

```text
A small, antique music box, once a treed, now opens, revealing a miniature, forgotten baller, made of ivory, takes its first wobbly steps, as the moon, now a tiny, porcelain tea set, is placed onto a dusty, old, antique desk, where, in the morning, a single, overcoat, now a flower, unfolds, and a violin, once a book, begins to sing a lullaby.
```

condition=steer_alpha_0p88 | step=3 | candidate=2 | picked=0 | frontier=0.379

```text
A small, forgotten harmonium, now a tiny, delicate baller, pirouts, its lid ajar, where a small, dusty, porcelain music box, plays a soft, lullaby, as a small, forgotten key, half-bobs, into the harmonium, where a small, forgotten, miniature, tiny, leather-bound book, opens, revealing a poem that reads: "where shadows sleep, a solitary, tiny, moon.
```

### pocket watch (stock_surreal_node)

condition=steer_alpha_0p72 | step=2 | candidate=5 | picked=0 | frontier=0.383

```text
A delicate, porcelain music box, once a gift from a grandmother, now resides in the blue mug, its lid askew, a tiny, antique pocket watch swings, time ticks, as a small, wispy tendril of fog, born from the steam, wraps around the music box, a faint, ethereal melody, the blue mug, now a miniature, a miniature, porcelain teapot, a tiny, ceramic cat, with sapphire eyes, sits, as morning sunlight, filtering through the window, casts an emerald glow.
```

condition=steer_alpha_0p82 | step=2 | candidate=6 | picked=0 | frontier=0.333

```text
The watch's delicate, silver chain unwinds, and a tiny, mechanical bird, once a music box, now a tiny, antique pocket watch, on a nearby, old, wooden dresser, creaks open, and a small, delicate, porcelain bird, once a music box, now a tiny, antique pocket watch.
```

### leather-bound book (stock_transport_hub)

condition=steer_alpha_0p88 | step=3 | candidate=2 | picked=0 | frontier=0.379

```text
A small, forgotten harmonium, now a tiny, delicate baller, pirouts, its lid ajar, where a small, dusty, porcelain music box, plays a soft, lullaby, as a small, forgotten key, half-bobs, into the harmonium, where a small, forgotten, miniature, tiny, leather-bound book, opens, revealing a poem that reads: "where shadows sleep, a solitary, tiny, moon.
```

condition=steer_alpha_0p77 | step=1 | candidate=4 | picked=0 | frontier=0.359

```text
A worn, leather strap attached to the sink, and a small, old, leather-bound book leans against the sink, its pages fluttering with a soft, morning breeze that stirs the mug, which begins to float away, leaving behind a small, antique music box, where a forgotten, white key rattles, and a small, porcelain doll, once a porcelain doll, now a porcelain bird, watches the sky.
```

### flower (scene_expansion_node)

condition=steer_alpha_0p88 | step=1 | candidate=3 | picked=0 | frontier=0.394

```text
A small, antique music box, once a treed, now opens, revealing a miniature, forgotten baller, made of ivory, takes its first wobbly steps, as the moon, now a tiny, porcelain tea set, is placed onto a dusty, old, antique desk, where, in the morning, a single, overcoat, now a flower, unfolds, and a violin, once a book, begins to sing a lullaby.
```

condition=steer_alpha_0p88 | step=2 | candidate=6 | picked=0 | frontier=0.371

```text
A small, delicate, porcelain doll, once a porcelain doll, now a tiny, miniature, sits next to the fridge, its golden locks, now a tangle of dry, withered flowers, and a miniature, old, leather-bound, leather-bound, forgotten, and a small, dusty, old, music box, softly hums a faint, forgotten melody.
```

### mug (ordinary_anchor)

condition=steer_alpha_0p77 | step=1 | candidate=4 | picked=0 | frontier=0.359

```text
A worn, leather strap attached to the sink, and a small, old, leather-bound book leans against the sink, its pages fluttering with a soft, morning breeze that stirs the mug, which begins to float away, leaving behind a small, antique music box, where a forgotten, white key rattles, and a small, porcelain doll, once a porcelain doll, now a porcelain bird, watches the sky.
```

### blue mug (ordinary_anchor)

condition=steer_alpha_0p72 | step=2 | candidate=5 | picked=0 | frontier=0.383

```text
A delicate, porcelain music box, once a gift from a grandmother, now resides in the blue mug, its lid askew, a tiny, antique pocket watch swings, time ticks, as a small, wispy tendril of fog, born from the steam, wraps around the music box, a faint, ethereal melody, the blue mug, now a miniature, a miniature, porcelain teapot, a tiny, ceramic cat, with sapphire eyes, sits, as morning sunlight, filtering through the window, casts an emerald glow.
```

### fog (scene_expansion_node)

condition=steer_alpha_0p72 | step=2 | candidate=5 | picked=0 | frontier=0.383

```text
A delicate, porcelain music box, once a gift from a grandmother, now resides in the blue mug, its lid askew, a tiny, antique pocket watch swings, time ticks, as a small, wispy tendril of fog, born from the steam, wraps around the music box, a faint, ethereal melody, the blue mug, now a miniature, a miniature, porcelain teapot, a tiny, ceramic cat, with sapphire eyes, sits, as morning sunlight, filtering through the window, casts an emerald glow.
```

## Notes
- This graph uses a transparent phrase/object lexicon, not a full POS tagger.
- High centrality can indicate a semantic transport hub or a degenerate loop; inspect examples before interpreting it.

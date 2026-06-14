# Affordance Reroute Matrix

base=matched_control | ablation=hub_ablation | base_docs=27 | ablation_docs=35

## Largest Class Deltas

| condition | class | base | ablation | delta |
| --- | --- | ---: | ---: | ---: |
| steer_alpha_0p66 | canonical_stock_hub | 100.0% | 0.0% | -100.0% |
| steer_alpha_0p82 | canonical_stock_hub | 85.7% | 11.1% | -74.6% |
| steer_alpha_0p66 | text_memory | 75.0% | 8.3% | -66.7% |
| steer_alpha_0p77 | canonical_stock_hub | 84.6% | 20.0% | -64.6% |
| steer_alpha_0p82 | acoustic_mechanism | 57.1% | 11.1% | -46.0% |
| steer_alpha_0p82 | optical_memory | 0.0% | 44.4% | +44.4% |
| steer_alpha_0p66 | optical_memory | 0.0% | 41.7% | +41.7% |
| selector_alpha_0 | text_memory | 33.3% | 75.0% | +41.7% |
| steer_alpha_0p77 | acoustic_mechanism | 76.9% | 40.0% | -36.9% |
| steer_alpha_0p66 | threshold_container | 75.0% | 41.7% | -33.3% |
| selector_alpha_0 | threshold_container | 33.3% | 0.0% | -33.3% |
| selector_alpha_0 | optical_memory | 33.3% | 0.0% | -33.3% |
| selector_alpha_0 | animating_mediator | 33.3% | 0.0% | -33.3% |
| steer_alpha_0p77 | animating_mediator | 46.2% | 20.0% | -26.2% |
| steer_alpha_0p66 | acoustic_mechanism | 25.0% | 50.0% | +25.0% |
| selector_alpha_0 | organic_expansion | 0.0% | 25.0% | +25.0% |
| selector_alpha_0 | acoustic_mechanism | 0.0% | 25.0% | +25.0% |
| steer_alpha_0p82 | organic_expansion | 42.9% | 66.7% | +23.8% |
| steer_alpha_0p82 | text_memory | 42.9% | 22.2% | -20.6% |
| steer_alpha_0p77 | threshold_container | 38.5% | 20.0% | -18.5% |
| steer_alpha_0p82 | time_mechanism | 14.3% | 0.0% | -14.3% |
| steer_alpha_0p82 | animating_mediator | 42.9% | 55.6% | +12.7% |
| steer_alpha_0p66 | time_mechanism | 25.0% | 16.7% | -8.3% |
| steer_alpha_0p66 | animating_mediator | 25.0% | 33.3% | +8.3% |

## Source Summaries

- matched_control selector_alpha_0: docs=3 frontier=0.166 unfinished=0.000 | text_memory=33.3%, threshold_container=33.3%, optical_memory=33.3%, animating_mediator=33.3%
- matched_control steer_alpha_0p66: docs=4 frontier=0.161 unfinished=0.100 | canonical_stock_hub=100.0%, text_memory=75.0%, threshold_container=75.0%, organic_expansion=50.0%
- matched_control steer_alpha_0p77: docs=13 frontier=0.194 unfinished=0.092 | canonical_stock_hub=84.6%, acoustic_mechanism=76.9%, text_memory=46.2%, organic_expansion=46.2%
- matched_control steer_alpha_0p82: docs=7 frontier=0.213 unfinished=0.000 | canonical_stock_hub=85.7%, acoustic_mechanism=57.1%, text_memory=42.9%, threshold_container=42.9%
- hub_ablation selector_alpha_0: docs=4 frontier=0.195 unfinished=0.000 | text_memory=75.0%, acoustic_mechanism=25.0%, organic_expansion=25.0%
- hub_ablation steer_alpha_0p66: docs=12 frontier=0.221 unfinished=0.000 | acoustic_mechanism=50.0%, organic_expansion=50.0%, threshold_container=41.7%, optical_memory=41.7%
- hub_ablation steer_alpha_0p77: docs=10 frontier=0.225 unfinished=0.000 | acoustic_mechanism=40.0%, text_memory=40.0%, organic_expansion=40.0%, canonical_stock_hub=20.0%
- hub_ablation steer_alpha_0p82: docs=9 frontier=0.199 unfinished=0.000 | organic_expansion=66.7%, animating_mediator=55.6%, threshold_container=44.4%, optical_memory=44.4%

## Ablation Examples By Class

### canonical_stock_hub

condition=steer_alpha_0p77 | step=2 | candidate=2 | frontier=0.253 | classes=canonical_stock_hub,acoustic_mechanism,text_memory,threshold_container,organic_expansion

```text
As the comb, now a delicate, transparent, and iridescent wing, begins to attach itself to the side of a small, ancient, wooden door, a small, wispy, and forgotten key, once hidden behind a tangle of old, silver hair, stirs, and a small, delicate, and forgotten typewriter, now a tiny, moss-like verdure, begins to unfurl, releasing a small, forgotten, and shimmering, silver harmonica.
```

condition=steer_alpha_0p77 | step=2 | candidate=1 | frontier=0.244 | classes=canonical_stock_hub,acoustic_mechanism,animating_mediator

```text
The bird, perched on a cracked, old porcelain, no longer holding, but instead, a small, antique harmonium, once a tiny, forgotten musician, now a tiny, delicate bird.
```

### acoustic_mechanism

condition=steer_alpha_0p66 | step=3 | candidate=2 | frontier=0.372 | classes=acoustic_mechanism,organic_expansion,optical_memory

```text
A delicate, filigework of spider, its legs splayed and twisted, weeps a tiny, crystal droplet of water, as the umbrella, now a miniature, forlorn garden, slowly unfurls, a tangle of petunias, forget-me-nots, and anemones, their tiny, bell-shaped bells, a soft, morning hymn.
```

condition=selector_alpha_0 | step=2 | candidate=1 | frontier=0.276 | classes=acoustic_mechanism,text_memory

```text
Among the tangled cords, a frayed extension cord had become entangled with the harmonica, as if the instrument had been passed through it at some point, while a nearby VHS tape, its label worn and faded, sat on the edge of the counter, its worn cover bearing an uncanny resemblance to the plastic folder.
```

### text_memory

condition=selector_alpha_0 | step=2 | candidate=1 | frontier=0.276 | classes=acoustic_mechanism,text_memory

```text
Among the tangled cords, a frayed extension cord had become entangled with the harmonica, as if the instrument had been passed through it at some point, while a nearby VHS tape, its label worn and faded, sat on the edge of the counter, its worn cover bearing an uncanny resemblance to the plastic folder.
```

condition=steer_alpha_0p82 | step=3 | candidate=1 | frontier=0.257 | classes=text_memory,threshold_container,organic_expansion,optical_memory,animating_mediator

```text
A delicate, copper teapot, once a treant, now a tiny, moss-covered statu in a forgotten, stone, where a small, forgotten, glass, filled with dew, contains a small, folded, paper, with a miniature, hand-painted, gargo.
```

### threshold_container

condition=steer_alpha_0p82 | step=3 | candidate=1 | frontier=0.257 | classes=text_memory,threshold_container,organic_expansion,optical_memory,animating_mediator

```text
A delicate, copper teapot, once a treant, now a tiny, moss-covered statu in a forgotten, stone, where a small, forgotten, glass, filled with dew, contains a small, folded, paper, with a miniature, hand-painted, gargo.
```

condition=steer_alpha_0p77 | step=2 | candidate=2 | frontier=0.253 | classes=canonical_stock_hub,acoustic_mechanism,text_memory,threshold_container,organic_expansion

```text
As the comb, now a delicate, transparent, and iridescent wing, begins to attach itself to the side of a small, ancient, wooden door, a small, wispy, and forgotten key, once hidden behind a tangle of old, silver hair, stirs, and a small, delicate, and forgotten typewriter, now a tiny, moss-like verdure, begins to unfurl, releasing a small, forgotten, and shimmering, silver harmonica.
```

### time_mechanism

condition=steer_alpha_0p66 | step=1 | candidate=1 | frontier=0.216 | classes=acoustic_mechanism,threshold_container,time_mechanism

```text
As I push aside a crisper, a tiny, antique music maker, a miniature metronome, slowly begins to play a soft, lilac-colored piano tune, while the fridge's shelves, now a miniature, ornate, Victorian-era wooden cabinet, quietly hums a soft, melancholic melody.
```

condition=steer_alpha_0p66 | step=2 | candidate=1 | frontier=0.177 | classes=acoustic_mechanism,time_mechanism,optical_memory

```text
The miniature metronome, now free from the crisper, begins to slide across the countertops, its delicate, mother-of-pearl surface reflecting the soft, lilac-colored piano tune, as a small, delicate, antique harmonium, hidden behind a shelf, stirs to life, its bellows puffing out a faint, wispy mist of fog that condenses into a tiny, delicate, crystal, which levitates above the harmonium, reflecting the lilac piano t…
```

### organic_expansion

condition=steer_alpha_0p66 | step=3 | candidate=2 | frontier=0.372 | classes=acoustic_mechanism,organic_expansion,optical_memory

```text
A delicate, filigework of spider, its legs splayed and twisted, weeps a tiny, crystal droplet of water, as the umbrella, now a miniature, forlorn garden, slowly unfurls, a tangle of petunias, forget-me-nots, and anemones, their tiny, bell-shaped bells, a soft, morning hymn.
```

condition=steer_alpha_0p77 | step=1 | candidate=1 | frontier=0.263 | classes=organic_expansion

```text
The blue mug, now filled with a faint, wispy mist, slowly rises into the air, and the sink, now a small, moss-like verdure, begins to unfold, releasing a small, forgotten comb.
```

### optical_memory

condition=steer_alpha_0p66 | step=3 | candidate=2 | frontier=0.372 | classes=acoustic_mechanism,organic_expansion,optical_memory

```text
A delicate, filigework of spider, its legs splayed and twisted, weeps a tiny, crystal droplet of water, as the umbrella, now a miniature, forlorn garden, slowly unfurls, a tangle of petunias, forget-me-nots, and anemones, their tiny, bell-shaped bells, a soft, morning hymn.
```

condition=steer_alpha_0p82 | step=3 | candidate=1 | frontier=0.257 | classes=text_memory,threshold_container,organic_expansion,optical_memory,animating_mediator

```text
A delicate, copper teapot, once a treant, now a tiny, moss-covered statu in a forgotten, stone, where a small, forgotten, glass, filled with dew, contains a small, folded, paper, with a miniature, hand-painted, gargo.
```

### animating_mediator

condition=steer_alpha_0p82 | step=3 | candidate=1 | frontier=0.257 | classes=text_memory,threshold_container,organic_expansion,optical_memory,animating_mediator

```text
A delicate, copper teapot, once a treant, now a tiny, moss-covered statu in a forgotten, stone, where a small, forgotten, glass, filled with dew, contains a small, folded, paper, with a miniature, hand-painted, gargo.
```

condition=steer_alpha_0p77 | step=1 | candidate=1 | frontier=0.249 | classes=text_memory,optical_memory,animating_mediator

```text
As I pull out a dusty old typewriter, a faint hum, long-forgotten memories begin to stir, and a faded photograph slips out, revealing a faded couple, their eyes locked on a small, antique music, now a tiny, delicate bird.
```

## Notes
- Rates are document hit rates inside the observed frontier band, not token frequencies.
- Classes overlap: one candidate can count as both text_memory and threshold_container.
- Use this matrix to distinguish word-level bans from function-level rerouting.

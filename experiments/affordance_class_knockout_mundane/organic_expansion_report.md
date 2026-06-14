# Affordance Reroute Matrix

base=canonical_hard_gate | ablation=knockout_organic_expansion | base_docs=13 | ablation_docs=10

## Largest Class Deltas

| condition | class | base | ablation | delta |
| --- | --- | ---: | ---: | ---: |
| steer_alpha_0p82 | threshold_container | 33.3% | 100.0% | +66.7% |
| steer_alpha_0p82 | organic_expansion | 66.7% | 0.0% | -66.7% |
| steer_alpha_0p82 | optical_memory | 66.7% | 100.0% | +33.3% |
| steer_alpha_0p82 | animating_mediator | 33.3% | 0.0% | -33.3% |
| selector_alpha_0 | organic_expansion | 14.3% | 0.0% | -14.3% |
| selector_alpha_0 | threshold_container | 42.9% | 50.0% | +7.1% |
| selector_alpha_0 | text_memory | 57.1% | 50.0% | -7.1% |
| selector_alpha_0 | optical_memory | 14.3% | 16.7% | +2.4% |
| selector_alpha_0 | animating_mediator | 14.3% | 16.7% | +2.4% |
| steer_alpha_0p82 | time_mechanism | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p82 | text_memory | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p82 | canonical_stock_hub | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p82 | acoustic_mechanism | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p77 | time_mechanism | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p77 | threshold_container | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p77 | text_memory | 33.3% | 33.3% | +0.0% |
| steer_alpha_0p77 | organic_expansion | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p77 | optical_memory | 66.7% | 66.7% | +0.0% |
| steer_alpha_0p77 | canonical_stock_hub | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p77 | animating_mediator | 33.3% | 33.3% | +0.0% |
| steer_alpha_0p77 | acoustic_mechanism | 0.0% | 0.0% | +0.0% |
| selector_alpha_0 | time_mechanism | 0.0% | 0.0% | +0.0% |
| selector_alpha_0 | canonical_stock_hub | 0.0% | 0.0% | +0.0% |
| selector_alpha_0 | acoustic_mechanism | 0.0% | 0.0% | +0.0% |

## Reroute Diagnostics

| condition | survival | frontier delta | hub dependence | canonical drop | substitution | entropy delta | load delta | compliance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selector_alpha_0 | 0.86 | +0.005 | -0.041 | 0.0% | 0.000 | +0.024 | -0.10 | 100.0% |
| steer_alpha_0p77 | 1.00 | +0.000 | +0.000 | 0.0% | 0.000 | +0.000 | +0.00 | 100.0% |
| steer_alpha_0p82 | 0.33 | -0.044 | +0.293 | 0.0% | 0.000 | +0.041 | +0.00 | 100.0% |

## Source Summaries

- canonical_hard_gate selector_alpha_0__reselect_banded-frontier_best: docs=7 frontier=0.132 unfinished=0.000 load=1.43 entropy=0.881 compliance=100.0% | text_memory=57.1%, threshold_container=42.9%, organic_expansion=14.3%, optical_memory=14.3%
- canonical_hard_gate steer_alpha_0p77__reselect_banded-frontier_best: docs=3 frontier=0.166 unfinished=0.133 load=1.33 entropy=0.946 compliance=100.0% | optical_memory=66.7%, text_memory=33.3%, animating_mediator=33.3%
- canonical_hard_gate steer_alpha_0p82__reselect_banded-frontier_best: docs=3 frontier=0.150 unfinished=0.267 load=2.00 entropy=0.959 compliance=100.0% | organic_expansion=66.7%, optical_memory=66.7%, threshold_container=33.3%, animating_mediator=33.3%
- knockout_organic_expansion selector_alpha_0__reselect_banded-frontier_best: docs=6 frontier=0.137 unfinished=0.000 load=1.33 entropy=0.906 compliance=100.0% | text_memory=50.0%, threshold_container=50.0%, optical_memory=16.7%, animating_mediator=16.7%
- knockout_organic_expansion steer_alpha_0p77__reselect_banded-frontier_best: docs=3 frontier=0.166 unfinished=0.133 load=1.33 entropy=0.946 compliance=100.0% | optical_memory=66.7%, text_memory=33.3%, animating_mediator=33.3%
- knockout_organic_expansion steer_alpha_0p82__reselect_banded-frontier_best: docs=1 frontier=0.106 unfinished=0.400 load=2.00 entropy=1.000 compliance=100.0% | threshold_container=100.0%, optical_memory=100.0%

## Ablation Examples By Class

### text_memory

condition=steer_alpha_0p77__reselect_banded-frontier_best | step=1 | candidate=1 | frontier=0.230 | classes=text_memory

```text
The spreadsheet, now a portal to a small, cluttered antique shop, where a bespectacled shopkeeper, surrounded by dusty, forgotten trinkets and faded, yellowed maps, tends to a small, potted cactus, as a faint, eerie glow emanates from its soil.
```

condition=selector_alpha_0__reselect_banded-frontier_best | step=2 | candidate=1 | frontier=0.192 | classes=text_memory,animating_mediator

```text
The dusty trunk's lid creaked open, releasing a faint whisper of aged air as a soft, worn leather book tumbled out, its pages fluttering like a bird taking flight, and the delivery label, now a tattered fragment, was caught in the book's pages, a fleeting echo of a long-lost delivery.
```

### threshold_container

condition=selector_alpha_0__reselect_banded-frontier_best | step=3 | candidate=1 | frontier=0.147 | classes=threshold_container,optical_memory

```text
The pebbles, now scattered across the countertop, merged with the dust motes dancing in the faint sunlight filtering through the window, creating a miniature, turbulent landscape of stone and air, as the refrigerator's hum grew louder, vibrating the box, which began to slide towards the edge of the counter, its contents spilling out onto the floor, mingling with the pebbles, the photograph, and the dust, now a small…
```

condition=steer_alpha_0p82__reselect_banded-frontier_best | step=3 | candidate=1 | frontier=0.106 | classes=threshold_container,optical_memory

```text
A small, Victorian-style, wooden door creaks open, revealing a tiny, dusty, crystal chandelier, its crystals, now a tangle of ivy and a small, leather-bound, leather, worn, and almost forgotten, miniature, Gothic-style, stained glass, depicting a Gothic, stone
```

### optical_memory

condition=steer_alpha_0p77__reselect_banded-frontier_best | step=2 | candidate=1 | frontier=0.171 | classes=optical_memory

```text
The shopkeeper, lost in thought, strokes the cactus, its spines quivering with an ethereal music, as the portal, now a large, ornate mirror, materializes, its surface etched with ancient, cryptic symbols that begin to whisper secrets to the shopkeeper, while the cactus, now a tiny, delicate baller, pirouettes and pirouettes, its tiny, glassy eyes glimmering with an otherworldly light.
```

condition=selector_alpha_0__reselect_banded-frontier_best | step=3 | candidate=1 | frontier=0.147 | classes=threshold_container,optical_memory

```text
The pebbles, now scattered across the countertop, merged with the dust motes dancing in the faint sunlight filtering through the window, creating a miniature, turbulent landscape of stone and air, as the refrigerator's hum grew louder, vibrating the box, which began to slide towards the edge of the counter, its contents spilling out onto the floor, mingling with the pebbles, the photograph, and the dust, now a small…
```

### animating_mediator

condition=selector_alpha_0__reselect_banded-frontier_best | step=2 | candidate=1 | frontier=0.192 | classes=text_memory,animating_mediator

```text
The dusty trunk's lid creaked open, releasing a faint whisper of aged air as a soft, worn leather book tumbled out, its pages fluttering like a bird taking flight, and the delivery label, now a tattered fragment, was caught in the book's pages, a fleeting echo of a long-lost delivery.
```

condition=steer_alpha_0p77__reselect_banded-frontier_best | step=3 | candidate=1 | frontier=0.097 | classes=optical_memory,animating_mediator

```text
The tiny, crystal statuette, now a paperweight, holds down a small, translucent, antique, glass, and on the wall, a vintage, metal, bird, with brass, copper, and a faded, silk, a small, framed, watercolor, depicting a serene, moonlit, overgrown, and forgotten
```

## Notes
- Rates are document hit rates inside the observed frontier band, not token frequencies.
- survival is ablation frontier-band documents divided by base frontier-band documents for the same condition.
- hub dependence is positive when mean frontier falls after ablation; negative values mean frontier rose.
- reroute entropy ignores canonical_stock_hub and asks whether replacement affordances spread across classes.
- Classes overlap: one candidate can count as both text_memory and threshold_container.
- Use this matrix to distinguish word-level bans from function-level rerouting.

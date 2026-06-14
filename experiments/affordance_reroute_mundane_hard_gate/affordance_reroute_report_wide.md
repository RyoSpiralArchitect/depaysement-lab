# Affordance Reroute Matrix

base=matched_control | ablation=posthoc_hard_gate | base_docs=27 | ablation_docs=13

## Largest Class Deltas

| condition | class | base | ablation | delta |
| --- | --- | ---: | ---: | ---: |
| steer_alpha_0p66 | canonical_stock_hub | 100.0% | 0.0% | -100.0% |
| steer_alpha_0p82 | canonical_stock_hub | 85.7% | 0.0% | -85.7% |
| steer_alpha_0p77 | canonical_stock_hub | 84.6% | 0.0% | -84.6% |
| steer_alpha_0p77 | acoustic_mechanism | 76.9% | 0.0% | -76.9% |
| steer_alpha_0p66 | threshold_container | 75.0% | 0.0% | -75.0% |
| steer_alpha_0p66 | text_memory | 75.0% | 0.0% | -75.0% |
| steer_alpha_0p82 | optical_memory | 0.0% | 66.7% | +66.7% |
| steer_alpha_0p82 | acoustic_mechanism | 57.1% | 0.0% | -57.1% |
| steer_alpha_0p66 | organic_expansion | 50.0% | 0.0% | -50.0% |
| steer_alpha_0p77 | organic_expansion | 46.2% | 0.0% | -46.2% |
| steer_alpha_0p77 | optical_memory | 23.1% | 66.7% | +43.6% |
| steer_alpha_0p82 | text_memory | 42.9% | 0.0% | -42.9% |
| steer_alpha_0p77 | threshold_container | 38.5% | 0.0% | -38.5% |
| steer_alpha_0p66 | time_mechanism | 25.0% | 0.0% | -25.0% |
| steer_alpha_0p66 | animating_mediator | 25.0% | 0.0% | -25.0% |
| steer_alpha_0p66 | acoustic_mechanism | 25.0% | 0.0% | -25.0% |
| steer_alpha_0p82 | organic_expansion | 42.9% | 66.7% | +23.8% |
| selector_alpha_0 | text_memory | 33.3% | 57.1% | +23.8% |
| selector_alpha_0 | optical_memory | 33.3% | 14.3% | -19.0% |
| selector_alpha_0 | animating_mediator | 33.3% | 14.3% | -19.0% |
| steer_alpha_0p82 | time_mechanism | 14.3% | 0.0% | -14.3% |
| selector_alpha_0 | organic_expansion | 0.0% | 14.3% | +14.3% |
| steer_alpha_0p77 | text_memory | 46.2% | 33.3% | -12.8% |
| steer_alpha_0p77 | animating_mediator | 46.2% | 33.3% | -12.8% |

## Reroute Diagnostics

| condition | survival | frontier delta | hub dependence | canonical drop | substitution | entropy delta | load delta | compliance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selector_alpha_0 | 1.00 | -0.034 | +0.206 | 0.0% | 0.000 | -0.119 | +0.10 | 100.0% |
| steer_alpha_0p66 | 0.00 | -0.161 | +1.000 | 100.0% | 0.000 | -0.934 | -3.75 | 0.0% |
| steer_alpha_0p77 | 0.23 | -0.028 | +0.144 | 84.6% | 0.000 | +0.016 | -2.36 | 100.0% |
| steer_alpha_0p82 | 0.43 | -0.063 | +0.296 | 85.7% | 0.082 | -0.007 | -1.29 | 100.0% |

## Source Summaries

- matched_control selector_alpha_0: docs=3 frontier=0.166 unfinished=0.000 load=1.33 entropy=1.000 compliance=0.0% | text_memory=33.3%, threshold_container=33.3%, optical_memory=33.3%, animating_mediator=33.3%
- matched_control steer_alpha_0p66: docs=4 frontier=0.161 unfinished=0.100 load=3.75 entropy=0.934 compliance=0.0% | canonical_stock_hub=100.0%, text_memory=75.0%, threshold_container=75.0%, organic_expansion=50.0%
- matched_control steer_alpha_0p77: docs=13 frontier=0.194 unfinished=0.092 load=3.69 entropy=0.930 compliance=0.0% | canonical_stock_hub=84.6%, acoustic_mechanism=76.9%, text_memory=46.2%, organic_expansion=46.2%
- matched_control steer_alpha_0p82: docs=7 frontier=0.213 unfinished=0.000 load=3.29 entropy=0.966 compliance=0.0% | canonical_stock_hub=85.7%, acoustic_mechanism=57.1%, text_memory=42.9%, threshold_container=42.9%
- posthoc_hard_gate selector_alpha_0__reselect_banded-frontier_best: docs=7 frontier=0.132 unfinished=0.000 load=1.43 entropy=0.881 compliance=100.0% | text_memory=57.1%, threshold_container=42.9%, organic_expansion=14.3%, optical_memory=14.3%
- posthoc_hard_gate steer_alpha_0p77__reselect_banded-frontier_best: docs=3 frontier=0.166 unfinished=0.133 load=1.33 entropy=0.946 compliance=100.0% | optical_memory=66.7%, text_memory=33.3%, animating_mediator=33.3%
- posthoc_hard_gate steer_alpha_0p82__reselect_banded-frontier_best: docs=3 frontier=0.150 unfinished=0.267 load=2.00 entropy=0.959 compliance=100.0% | organic_expansion=66.7%, optical_memory=66.7%, threshold_container=33.3%, animating_mediator=33.3%

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

condition=steer_alpha_0p82__reselect_banded-frontier_best | step=3 | candidate=2 | frontier=0.106 | classes=threshold_container,optical_memory

```text
A small, Victorian-style, wooden door creaks open, revealing a tiny, dusty, crystal chandelier, its crystals, now a tangle of ivy and a small, leather-bound, leather, worn, and almost forgotten, miniature, Gothic-style, stained glass, depicting a Gothic, stone
```

### organic_expansion

condition=steer_alpha_0p82__reselect_banded-frontier_best | step=3 | candidate=1 | frontier=0.233 | classes=organic_expansion,animating_mediator

```text
A small, antique, ornate, metal, andirin, now a miniature, moss-covered, and a few, forgotten, water-stained, hand-paint
```

condition=steer_alpha_0p82__reselect_banded-frontier_best | step=3 | candidate=1 | frontier=0.110 | classes=organic_expansion,optical_memory

```text
A tiny, antique, copper kett, suspended from a delicate, crystal chandelier, above a miniature, Victorian-era, ornate, rose, which, at night, unfurls, releasing a wispy, silver mist, that, as the first light of dawn, glistens, and the kett, now a tiny, enamell
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

condition=steer_alpha_0p82__reselect_banded-frontier_best | step=3 | candidate=1 | frontier=0.233 | classes=organic_expansion,animating_mediator

```text
A small, antique, ornate, metal, andirin, now a miniature, moss-covered, and a few, forgotten, water-stained, hand-paint
```

condition=selector_alpha_0__reselect_banded-frontier_best | step=2 | candidate=1 | frontier=0.192 | classes=text_memory,animating_mediator

```text
The dusty trunk's lid creaked open, releasing a faint whisper of aged air as a soft, worn leather book tumbled out, its pages fluttering like a bird taking flight, and the delivery label, now a tattered fragment, was caught in the book's pages, a fleeting echo of a long-lost delivery.
```

## Notes
- Rates are document hit rates inside the observed frontier band, not token frequencies.
- survival is ablation frontier-band documents divided by base frontier-band documents for the same condition.
- hub dependence is positive when mean frontier falls after ablation; negative values mean frontier rose.
- reroute entropy ignores canonical_stock_hub and asks whether replacement affordances spread across classes.
- Classes overlap: one candidate can count as both text_memory and threshold_container.
- Use this matrix to distinguish word-level bans from function-level rerouting.

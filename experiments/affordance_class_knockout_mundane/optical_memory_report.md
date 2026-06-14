# Affordance Reroute Matrix

base=canonical_hard_gate | ablation=knockout_optical_memory | base_docs=13 | ablation_docs=8

## Largest Class Deltas

| condition | class | base | ablation | delta |
| --- | --- | ---: | ---: | ---: |
| steer_alpha_0p82 | animating_mediator | 33.3% | 100.0% | +66.7% |
| steer_alpha_0p77 | text_memory | 33.3% | 100.0% | +66.7% |
| steer_alpha_0p82 | optical_memory | 66.7% | 0.0% | -66.7% |
| steer_alpha_0p77 | optical_memory | 66.7% | 0.0% | -66.7% |
| steer_alpha_0p82 | organic_expansion | 66.7% | 100.0% | +33.3% |
| steer_alpha_0p82 | threshold_container | 33.3% | 0.0% | -33.3% |
| steer_alpha_0p77 | animating_mediator | 33.3% | 0.0% | -33.3% |
| selector_alpha_0 | optical_memory | 14.3% | 0.0% | -14.3% |
| selector_alpha_0 | threshold_container | 42.9% | 33.3% | -9.5% |
| selector_alpha_0 | text_memory | 57.1% | 66.7% | +9.5% |
| selector_alpha_0 | organic_expansion | 14.3% | 16.7% | +2.4% |
| selector_alpha_0 | animating_mediator | 14.3% | 16.7% | +2.4% |
| steer_alpha_0p82 | time_mechanism | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p82 | text_memory | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p82 | canonical_stock_hub | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p82 | acoustic_mechanism | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p77 | time_mechanism | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p77 | threshold_container | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p77 | organic_expansion | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p77 | canonical_stock_hub | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p77 | acoustic_mechanism | 0.0% | 0.0% | +0.0% |
| selector_alpha_0 | time_mechanism | 0.0% | 0.0% | +0.0% |
| selector_alpha_0 | canonical_stock_hub | 0.0% | 0.0% | +0.0% |
| selector_alpha_0 | acoustic_mechanism | 0.0% | 0.0% | +0.0% |

## Reroute Diagnostics

| condition | survival | frontier delta | hub dependence | canonical drop | substitution | entropy delta | load delta | compliance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selector_alpha_0 | 0.86 | -0.003 | +0.019 | 0.0% | 0.000 | -0.006 | -0.10 | 100.0% |
| steer_alpha_0p77 | 0.33 | +0.064 | -0.385 | 0.0% | 0.000 | -0.946 | -0.33 | 100.0% |
| steer_alpha_0p82 | 0.33 | +0.084 | -0.560 | 0.0% | 0.000 | +0.041 | +0.00 | 100.0% |

## Source Summaries

- canonical_hard_gate selector_alpha_0__reselect_banded-frontier_best: docs=7 frontier=0.132 unfinished=0.000 load=1.43 entropy=0.881 compliance=100.0% | text_memory=57.1%, threshold_container=42.9%, organic_expansion=14.3%, optical_memory=14.3%
- canonical_hard_gate steer_alpha_0p77__reselect_banded-frontier_best: docs=3 frontier=0.166 unfinished=0.133 load=1.33 entropy=0.946 compliance=100.0% | optical_memory=66.7%, text_memory=33.3%, animating_mediator=33.3%
- canonical_hard_gate steer_alpha_0p82__reselect_banded-frontier_best: docs=3 frontier=0.150 unfinished=0.267 load=2.00 entropy=0.959 compliance=100.0% | organic_expansion=66.7%, optical_memory=66.7%, threshold_container=33.3%, animating_mediator=33.3%
- knockout_optical_memory selector_alpha_0__reselect_banded-frontier_best: docs=6 frontier=0.129 unfinished=0.000 load=1.33 entropy=0.875 compliance=100.0% | text_memory=66.7%, threshold_container=33.3%, organic_expansion=16.7%, animating_mediator=16.7%
- knockout_optical_memory steer_alpha_0p77__reselect_banded-frontier_best: docs=1 frontier=0.230 unfinished=0.000 load=1.00 entropy=0.000 compliance=100.0% | text_memory=100.0%
- knockout_optical_memory steer_alpha_0p82__reselect_banded-frontier_best: docs=1 frontier=0.233 unfinished=0.000 load=2.00 entropy=1.000 compliance=100.0% | organic_expansion=100.0%, animating_mediator=100.0%

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

condition=selector_alpha_0__reselect_banded-frontier_best | step=1 | candidate=1 | frontier=0.105 | classes=threshold_container

```text
The cardboard box now lies empty and crumpled on a dusty attic shelf, the delivery label a faded reminder of a long-forgotten package, its adhesive still clinging to the roof of the old trunk that has now become its new home.
```

condition=selector_alpha_0__reselect_banded-frontier_best | step=2 | candidate=1 | frontier=0.103 | classes=text_memory,threshold_container

```text
The worn bottle of olive oil rolls off the counter and onto the floor, its label fluttering like a torn piece of paper in the faint hum of the refrigerator's motor, while my mother's recipe book slips between the kitchen cabinets, its yellowed pages rustling softly against the painted walls.
```

### organic_expansion

condition=steer_alpha_0p82__reselect_banded-frontier_best | step=3 | candidate=1 | frontier=0.233 | classes=organic_expansion,animating_mediator

```text
A small, antique, ornate, metal, andirin, now a miniature, moss-covered, and a few, forgotten, water-stained, hand-paint
```

condition=selector_alpha_0__reselect_banded-frontier_best | step=3 | candidate=1 | frontier=0.100 | classes=text_memory,organic_expansion

```text
The book, bound in a rich, dark leather, lay open on a nearby stack of yellowed letters, its pages dog-eared and worn, a phrase highlighted in faint, crimson ink: "In the garden of forgotten memories, where shadows dance and moonlight whispers secrets to the wind."
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

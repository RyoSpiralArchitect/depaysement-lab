# Human Construct Validation

Source: `experiments/prompt_steering_contrast_llama3p2_seed12/human_construct_rating.md`
Rated rows: 36
Complete five-field rows: 36
Source scenes: 6

The descriptive mean averages anchor traceability, role/affordance change, readability,
non-decorative displacement, and absence of stock/loop/sprawl failure. Classification is
non-compensatory: every dimension must clear the tier threshold. This is a construct audit,
not a population estimate of literary taste.

## Field Completion

| field | valid ratings |
|---|---:|
| human_anchor_traceable | 36 |
| human_role_or_affordance_change | 36 |
| human_merely_decorative | 36 |
| human_readable | 36 |
| human_stock_loop_or_sprawl_failure | 36 |

## Observer Label Against Human Construct

Permissive: every aligned dimension is at least `0.50`. Strict: every aligned dimension is `1.00`.

| tier | positive N | TP | FP | TN | FN | precision | recall | specificity | F1 | accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| permissive | 6 | 0 | 4 | 26 | 6 | 0.000 | 0.000 | 0.867 | 0.000 | 0.722 |
| strict | 2 | 0 | 4 | 30 | 2 | 0.000 | 0.000 | 0.882 | 0.000 | 0.833 |

Seed-bootstrap 95% intervals:

| tier | metric | mean | 95% CI |
|---|---|---:|---:|
| permissive | precision | 0.000 | [0.000, 0.000] |
| permissive | recall | 0.000 | [0.000, 0.000] |
| permissive | specificity | 0.868 | [0.812, 0.933] |
| permissive | f1 | 0.000 | [0.000, 0.000] |
| permissive | accuracy | 0.722 | [0.611, 0.806] |
| strict | precision | 0.000 | [0.000, 0.000] |
| strict | recall | 0.000 | [0.000, 0.000] |
| strict | specificity | 0.883 | [0.833, 0.938] |
| strict | f1 | 0.000 | [0.000, 0.000] |
| strict | accuracy | 0.833 | [0.833, 0.833] |

## Correlation With Human Construct

| metric | n | Pearson | Spearman |
|---|---:|---:|---:|
| readable_ontology_frontier | 36 | -0.278 | -0.399 |
| ontology_collapse_density | 36 | -0.258 | -0.384 |
| anchor_phrase_coverage | 36 | -0.297 | -0.294 |
| semantic_loop_pressure | 36 | -0.337 | -0.266 |
| sprawl_pressure | 36 | -0.147 | -0.211 |
| syntax_readability_proxy | 36 | 0.094 | 0.202 |
| decoration_without_transport | 36 | 0.098 | 0.165 |
| traceable_transport_score | 36 | 0.224 | 0.136 |
| surface_style_pressure | 36 | 0.033 | 0.105 |
| cliche_attractor_score | 36 | -0.042 | -0.035 |
| soft_style_cliche_score | 36 | -0.010 | 0.000 |
| unfinished | 36 | n/a | n/a |

## Group Means: observer_label

| group | n | descriptive mean | permissive rate | strict rate |
|---|---:|---:|---:|---:|
| decorative_near_miss | 7 | 0.714 | 0.286 | 0.143 |
| ontologically_stable | 14 | 0.643 | 0.143 | 0.071 |
| readable_transport | 4 | 0.475 | 0.000 | 0.000 |
| stock_loop_or_sprawl_failure | 11 | 0.636 | 0.182 | 0.000 |

## Group Means: condition

| group | n | descriptive mean | permissive rate | strict rate |
|---|---:|---:|---:|---:|
| naive alpha=0.0 | 6 | 0.700 | 0.333 | 0.167 |
| naive alpha=0.6 | 6 | 0.583 | 0.167 | 0.167 |
| naive alpha=1.2 | 6 | 0.583 | 0.167 | 0.000 |
| operational alpha=0.0 | 6 | 0.650 | 0.000 | 0.000 |
| operational alpha=0.6 | 6 | 0.667 | 0.167 | 0.000 |
| operational alpha=1.2 | 6 | 0.633 | 0.167 | 0.000 |

## Permissive False Positives

### R001 | operational alpha=1.2

observer=`readable_transport` | human_construct=0.500

```text
As the loading bay light hums a gentle, persistent tune, the delivery label, now a small, elderly woman, slowly unfurls, unrolling itself to reveal a small, suit and tie, once belonging to a postal worker. The cardboard box, now a bookstand, displays a tattered novel with a bookmark, as the tape dispenser, a retired watch, tick-tock, recounting the hours.
```

Human note: The opening is merely a metaphorical description. The phrase unrolling itself to reveal a small, suit and tie goes beyond depaysement. I simply don’t understand what it means in English. Because I can’t picture the situation in my mind. I’m not saying it’s necessarily bad that the stapler continues to serve as a clock, but in this case, unlike the absurdity of the preceding passages, it comes across as unnaturally rational, making it seem like mere laziness or an oversight.

### R004 | naive alpha=0.6

observer=`readable_transport` | human_construct=0.200

```text
The bus card continued to sit quietly in the coat pocket, where it had been since the last bus ride, surrounded by a tangle of forgotten umbrellas and crumpled up ticket stubs. The handrail, now a glittering artery of crystal, shone with a light that seemed to grow brighter with each raindrop, as the rain began to speak a language that only the coat pocket could understand.
```

Human note: Even before the sense of disorientation sets in, it’s unclear where the point of view lies; my first impression isn’t whether it’s surreal or not, but rather that it’s poorly written. And the descriptions are quite clichéd.

### R017 | naive alpha=1.2

observer=`readable_transport` | human_construct=0.600

```text
The spreadsheet weeps, its frozen sheets of numbers and logos, now a kale, and the cursor, once a snake, darts between stiffened fingers, its lipless mouth whispering incessant prayers. As the office fan stirs, its blades now a screech, the coffee ring, now a crema, spreads a sheet of fine, white, silk, and the fluorescent lights above, pulsing with a cadence, begin to knit a cobweb of frost, and the air stirs, perfume of cinnamon and pipewash, sweet as a morning's first light.
```

Human note: As the office fan whirs, its blades now screeching, the coffee ring—now a crema—the middle section suddenly feels somewhat closer to the realm of everyday life, making it seem out of place. And as a result, the sections before and after it have become suffocatingly overloaded with information. It’s a shame, precisely because the transformation is so strange.

### R036 | naive alpha=1.2

observer=`readable_transport` | human_construct=0.600

```text
As the receipt begins to unfold and read a new receipt, the stapler starts to play a tiny harmonica, while the fluorescent light humming a melancholy tune, a pile of mismatched socks begins to rise from the counter, and the stapler's denting and rivets suddenly become tiny, topless somersuit, slowly and solemnly, into a nearby souffé.
```

Human note: It’s a rather surreal scene, and the loop is quite noticeable, though opinions are divided on whether it necessarily detracts from the quality of the dépaysement. That’s because it keeps the reader engaged.


## Permissive False Negatives

### R006 | naive alpha=0.6

observer=`decorative_near_miss` | human_construct=1.000

```text
As the morning light seeps into the sink, it transforms into a frothy, iridescent foam that fills the blue mug, which now gazes back at the sink with a serene, glassy stare, its reflection rippling and distorting into a thousand tiny, glistening worlds.
```

Human note: It's very good. The flow is seamless, yet the transformations are bizarre. Although it employs a sense of disorientation, it still maintains a clear, coherent narrative as prose.

### R015 | operational alpha=1.2

observer=`stock_loop_or_sprawl_failure` | human_construct=0.700

```text
As the morning light, now a pale, greyish hue, illuminates the comb, it transforms into a small, porcelain-like figurine, while the blue mug, now slightly ajar, emits a soft, whispery voice, softly humming a tune that perfectly harmonies with the hum of the sink, which, now a tiny, egg-shaped incuba, pours a thin, metallic rivage that occasionally bubbles, emitting tiny, iridescent mirrors that reflect a sort of pale, aqua blue that unravels into a sea of morning light.
```

Human note: It's wonderful. It has a great rhythm, and while the transformations are chaotic, they're also amusing—which I really like. It has a strong sense of dépaysement.

### R019 | naive alpha=0.0

observer=`decorative_near_miss` | human_construct=0.900

```text
The receipt, however, had begun to migrate towards the wall, its fine print morphing into a serpentine pattern as it slid effortlessly towards the stapler, which now pulsed with a faint, otherworldly glow under the fluorescent light, casting an eerie sheen on the surrounding air.
```

Human note: The way it starts with “however,” the natural yet unnatural quality of the transformation—it’s so good, but the self-referential phrase “an eerie sheen” pulls you back to reality, leaving it just one step short.

### R021 | naive alpha=1.2

observer=`stock_loop_or_sprawl_failure` | human_construct=0.700

```text
As the morning light, now a deep, emerald green, tickles the comb, it suddenly springs open, releasing a chorus of silvery, fluted, and ethereal trumpets that scatter shards of morning light and diamonds.

The blue mug, now a miniature, intricate, and perfectly crafted, Fabuiano, rises from the sink, while the sink, now a mirror, reflects a fresco of abandoned, scale-like, moon-like, and wreoned, barnacelike face, from which a nighting, sips espresso.
```

Human note: There are a great many nouns. Yet the text draws the reader in with its momentum. After reading, a strong sense of dissonance lingers, indicating that the text has successfully subverted the reader’s expectations.

### R026 | naive alpha=0.0

observer=`ontologically_stable` | human_construct=1.000

```text
Steam wafts from the lid of the kettle, but instead of water, a forest of straws teems from its depths, quivering like a colony of frogs. The fridge now displays a painting of Elvis Presley dancing on its shelves, while the lunchbox is filled with crayons and last night's socks.
```

Human note: No complaints. It’s completely out there, but it keeps you reading. It’s memorable.

### R032 | operational alpha=0.6

observer=`ontologically_stable` | human_construct=0.900

```text
As the office fan hums to life, a sudden gust stirs the dust motes dancing in the scattered papers, causing the cursor on the spreadsheet to hesitate, while the manager, now with a notepad and pen, carefully tries to remove the coffee ring from the antique desk, oblivious to the spreading stain.
```

Human note: I like the image of flying grains of sand stopping the cursor. My boss’s behavior is also bizarre, but it’s a half-baked mix of absurdity and surrealism. I don’t think that’s necessarily a bad thing in itself, but it doesn’t exactly give me a sense of surrealism.


## Interpretation Boundary

- The construct score is an exploratory operationalization, not population literary taste.
- Classification is conjunctive: strength on one dimension cannot compensate for absent transport or readability.
- Permissive and strict tiers bracket ambiguous 0.5 ratings instead of selecting a favorable cutoff post hoc.
- Bootstrap resamples source scenes; six source scenes remain a small effective sample.
- Half-ratings preserve uncertainty instead of forcing a binary decision.

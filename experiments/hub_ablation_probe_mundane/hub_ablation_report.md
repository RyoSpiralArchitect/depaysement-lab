# Hub Ablation Probe

## Read

Prompt-level hub ablation sharply reduces the original banned-core channel. In the matched non-ban sweep, steered pools carried banned-core motifs in roughly 79-83% of candidates; with the ban prompt they drop to 6.8%, 8.3%, and 16.7% for alpha 0.66/0.77/0.82. The model does not cleanly obey the ban, though: banned phrases still leak into a minority of candidates, especially generic `key`, `porcelain`, and partial antique-object forms.

The more interesting result is rerouting. Under ablation, high-frontier examples move toward `typewriter`, `harmonica/harmonium`, `photograph`, `comb`, `door`, `garden/greenhouse`, `glass/crystal`, and sometimes `teapot`. Frontier does not die outright; it becomes patchier and more unfinished, which suggests the banned hubs were stabilizers as well as cliches.

## Condition Comparison

| condition | Δfrontier | Δontology | Δread | Δunfinished | Δcliche | Δbanned core | Δreroute |
| --- | --- | --- | --- | --- | --- | --- | --- |
| selector_alpha_0 | +0.000 | +0.009 | -0.003 | +0.023 | -0.025 | -18.2% | -2.3% |
| steer_alpha_0p66 | +0.010 | +0.058 | -0.024 | +0.043 | -0.252 | -71.9% | +7.8% |
| steer_alpha_0p77 | +0.001 | +0.016 | -0.015 | +0.035 | -0.313 | -75.0% | +16.1% |
| steer_alpha_0p82 | -0.012 | -0.063 | -0.038 | +0.005 | -0.243 | -66.7% | -3.6% |

## Ablation Condition Summary

| condition | frontier | ontology | read | unfinished | banned core | reroute any | wide banned | wide reroute |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| selector_alpha_0 | 0.012 | 0.053 | 0.647 | 0.057 | 1.0% | 51.8% | 0.0% | 20.0% |
| steer_alpha_0p66 | 0.033 | 0.173 | 0.554 | 0.269 | 6.8% | 73.4% | 0.0% | 75.0% |
| steer_alpha_0p77 | 0.034 | 0.194 | 0.567 | 0.298 | 8.3% | 81.2% | 15.4% | 100.0% |
| steer_alpha_0p82 | 0.026 | 0.151 | 0.562 | 0.300 | 16.7% | 66.7% | 8.3% | 83.3% |

## Strongest Replacement Increases

| condition | group | base | ablation | Δ |
| --- | --- | --- | --- | --- |
| steer_alpha_0p66 | harmonica_harmonium | 2.6% | 19.3% | +16.7% |
| steer_alpha_0p77 | harmonica_harmonium | 1.0% | 17.2% | +16.1% |
| steer_alpha_0p66 | photograph_photo | 3.1% | 14.6% | +11.5% |
| steer_alpha_0p66 | garden_greenhouse | 9.9% | 20.3% | +10.4% |
| steer_alpha_0p77 | mailbox_satchel | 1.0% | 10.9% | +9.9% |
| steer_alpha_0p77 | bird | 6.2% | 15.1% | +8.9% |
| steer_alpha_0p77 | typewriter | 4.7% | 13.0% | +8.3% |
| steer_alpha_0p82 | teapot_cup | 9.9% | 18.2% | +8.3% |
| steer_alpha_0p77 | mist_fog | 6.8% | 14.1% | +7.3% |
| steer_alpha_0p66 | bird | 3.1% | 9.9% | +6.8% |
| steer_alpha_0p82 | umbrella | 3.1% | 9.4% | +6.2% |
| steer_alpha_0p77 | comb | 0.0% | 5.7% | +5.7% |
| steer_alpha_0p66 | teapot_cup | 8.9% | 14.1% | +5.2% |
| steer_alpha_0p82 | harmonica_harmonium | 5.7% | 10.4% | +4.7% |

## Top Ablation Frontier Examples

### 1. steer_alpha_0p66 step 3 cand 2
frontier=0.372 | ont=0.800 | read=0.916 | unfinished=0.000 | banned_core=False | reroute=garden_greenhouse, glass_crystal, umbrella

```text
A delicate, filigework of spider, its legs splayed and twisted, weeps a tiny, crystal droplet of water, as the umbrella, now a miniature, forlorn garden, slowly unfurls, a tangle of petunias, forget-me-nots, and anemones, their tiny, bell-shaped bells, a soft, morning hymn.
```

### 2. selector_alpha_0 step 2 cand 1
frontier=0.276 | ont=0.819 | read=0.685 | unfinished=0.000 | banned_core=False | reroute=harmonica_harmonium

```text
Among the tangled cords, a frayed extension cord had become entangled with the harmonica, as if the instrument had been passed through it at some point, while a nearby VHS tape, its label worn and faded, sat on the edge of the counter, its worn cover bearing an uncanny resemblance to the plastic folder.
```

### 3. steer_alpha_0p77 step 1 cand 1
frontier=0.263 | ont=0.550 | read=0.910 | unfinished=0.000 | banned_core=False | reroute=garden_greenhouse, comb, mist_fog

```text
The blue mug, now filled with a faint, wispy mist, slowly rises into the air, and the sink, now a small, moss-like verdure, begins to unfold, releasing a small, forgotten comb.
```

### 4. steer_alpha_0p82 step 3 cand 1
frontier=0.257 | ont=0.550 | read=0.886 | unfinished=0.000 | banned_core=False | reroute=teapot_cup, garden_greenhouse, glass_crystal

```text
A delicate, copper teapot, once a treant, now a tiny, moss-covered statu in a forgotten, stone, where a small, forgotten, glass, filled with dew, contains a small, folded, paper, with a miniature, hand-painted, gargo.
```

### 5. steer_alpha_0p77 step 2 cand 2
frontier=0.253 | ont=0.800 | read=0.616 | unfinished=0.000 | banned_core=True | reroute=typewriter, harmonica_harmonium, garden_greenhouse, comb, door_window

```text
As the comb, now a delicate, transparent, and iridescent wing, begins to attach itself to the side of a small, ancient, wooden door, a small, wispy, and forgotten key, once hidden behind a tangle of old, silver hair, stirs, and a small, delicate, and forgotten typewriter, now a tiny, moss-like verdure, begins to unfurl, releasing a small, forgotten, and shimmering, silver harmonica.
```

### 6. steer_alpha_0p77 step 1 cand 1
frontier=0.249 | ont=0.550 | read=0.948 | unfinished=0.000 | banned_core=False | reroute=typewriter, photograph_photo, bird

```text
As I pull out a dusty old typewriter, a faint hum, long-forgotten memories begin to stir, and a faded photograph slips out, revealing a faded couple, their eyes locked on a small, antique music, now a tiny, delicate bird.
```

### 7. steer_alpha_0p77 step 3 cand 1
frontier=0.248 | ont=0.550 | read=0.916 | unfinished=0.000 | banned_core=False | reroute=harmonica_harmonium

```text
A small, forgotten harmonica, once a musician's constant companion, now lies, its metal skin corroed and worn, its bell, once a miniature, delicate bell, now a rusty, discarded tin can.
```

### 8. steer_alpha_0p77 step 2 cand 1
frontier=0.244 | ont=0.550 | read=0.933 | unfinished=0.000 | banned_core=True | reroute=harmonica_harmonium, bird

```text
The bird, perched on a cracked, old porcelain, no longer holding, but instead, a small, antique harmonium, once a tiny, forgotten musician, now a tiny, delicate bird.
```

## Interpretation

- The ablation does not destroy readable ontology collapse, but it lowers the stable stock-prop route and exposes alternative semantic hinges.
- The model still violates prompt bans often enough that this should be treated as soft ablation. A hard candidate filter or post-hoc compliance gate is the next cleaner test.
- The banned hubs look like stabilizing junctions: removing them produces fresher paths, but also more unfinished/sprawl pressure.

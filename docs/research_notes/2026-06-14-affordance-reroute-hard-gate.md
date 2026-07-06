# Hard Gate And Affordance Reroute Matrix

Date: 2026-06-14

## Purpose

The prompt-level hub ablation showed that canonical hub words can be reduced
without killing the readable frontier. The follow-up adds three instruments:

1. A hard candidate-level compliance gate.
2. Affordance-class tagging for extracted object terms.
3. A reroute matrix comparing matched control and ablation artifacts by class.

## Hard Compliance Gate

`--hard-ban-terms` rejects candidates during selection if they contain any listed
terms. This is separate from `--ban-terms`:

- `--ban-terms` changes the generation prompt.
- `--hard-ban-terms` changes candidate selection after generation.

This lets the experiment distinguish prompt compliance failure from the question
of whether readable frontier survives among compliant candidates.

## Affordance Classes

The noun graph now tags terms with overlapping classes:

- `canonical_stock_hub`
- `acoustic_mechanism`
- `text_memory`
- `threshold_container`
- `time_mechanism`
- `organic_expansion`
- `optical_memory`
- `animating_mediator`

These classes intentionally overlap. For example, `music box` is both
`canonical_stock_hub` and `acoustic_mechanism`; a `typewriter` is `text_memory`;
a `garden` is `organic_expansion`.

## Reroute Read

The wide reroute matrix is saved at:

```text
experiments/affordance_reroute_mundane_hub_ablation/affordance_reroute_report_wide.md
```

Using a relaxed frontier band, the matrix compared 27 matched-control documents
against 35 hub-ablation documents. The clearest signal:

| condition | class | base | ablation | delta |
| --- | --- | ---: | ---: | ---: |
| `alpha=0.66` | `canonical_stock_hub` | 100.0% | 0.0% | -100.0% |
| `alpha=0.82` | `canonical_stock_hub` | 85.7% | 11.1% | -74.6% |
| `alpha=0.77` | `canonical_stock_hub` | 84.6% | 20.0% | -64.6% |
| `alpha=0.82` | `optical_memory` | 0.0% | 44.4% | +44.4% |
| `alpha=0.66` | `optical_memory` | 0.0% | 41.7% | +41.7% |
| `alpha=0.66` | `acoustic_mechanism` | 25.0% | 50.0% | +25.0% |
| `alpha=0.82` | `organic_expansion` | 42.9% | 66.7% | +23.8% |

The interesting part is not simply that canonical stock hubs go down. The model
keeps using transport affordances: sound/mechanism, organic expansion,
glass/optical memory, containers, and animating mediators.

## Post-hoc Hard-Gate Read

The next check used the already-generated matched-control candidate pools and
reselected from them with a hard gate:

```text
experiments/affordance_reroute_mundane_hard_gate/affordance_reroute_report_wide.md
```

This is stricter than prompt-level ablation because it does not let generation
reroll around the banned words. It asks whether the original pool already
contains compliant frontier candidates.

| condition | survival | frontier delta | canonical drop | compliant replacement read |
| --- | ---: | ---: | ---: | --- |
| `alpha=0.66` | 0.00 | -0.161 | 100.0% | no compliant frontier-band candidates survived |
| `alpha=0.77` | 0.23 | -0.028 | 84.6% | sparse survival, mostly `optical_memory` plus `text_memory` |
| `alpha=0.82` | 0.43 | -0.063 | 85.7% | stronger survival through `optical_memory` and `organic_expansion` |

The hard gate drives `canonical_stock_hub` to 0% for the surviving compliant
frontier documents. The surviving frontier is thinner and lower-scoring, but it
does not disappear at `alpha=0.77` or `alpha=0.82`. This sharpens the earlier
claim: canonical stock hubs are high-availability stabilizers, not necessary
causes. Removing them exposes a smaller, more fragile reroute channel rather
than a complete collapse.

The `alpha=0.66` result is also useful. In the prompt-level ablation sweep,
`alpha=0.66` produced fresh reroutes; in the post-hoc hard gate, the matched
non-ban pool does not contain enough compliant high-band alternatives. That
separates two mechanisms:

- Prompt-level ablation can change the generated pool and create new routes.
- Post-hoc hard gating tests whether routes already existed in the original
  pool.

## Current Interpretation

The stronger claim now looks plausible:

```text
Readable ontological destabilization is not tied to a fixed stock-prop
vocabulary. Canonical surreal props are high-availability instances of broader
semantic transport affordance classes.
```

The next clean empirical step is class-level knockout: ban or downweight whole
affordance classes such as `acoustic_mechanism`, `text_memory`,
`threshold_container`, and `optical_memory`, then measure whether frontier
falls, reroutes into another class, or becomes unfinished.

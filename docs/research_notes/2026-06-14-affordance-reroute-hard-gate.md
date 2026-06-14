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

## Current Interpretation

The stronger claim now looks plausible:

```text
Readable ontological destabilization is not tied to a fixed stock-prop
vocabulary. Canonical surreal props are high-availability instances of broader
semantic transport affordance classes.
```

The next clean empirical step is to run post-hoc reselection with
`--hard-ban-terms`, then compare the selected compliant outputs against the soft
ablation and matched-control pools.

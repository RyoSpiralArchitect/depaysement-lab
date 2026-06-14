# Research Note: Affordance Class Knockout

Date: 2026-06-14

## Purpose

The post-hoc hard gate showed that readable frontier can survive after canonical
stock hubs are removed, especially at `alpha=0.77` and `alpha=0.82`. This note
asks a stricter follow-up question: which replacement affordance classes carry
the surviving frontier?

The class knockout pass uses no new generation. It reselects from the matched
control candidate pools with:

- the canonical stock hub hard gate still active
- one or more additional `--hard-ban-affordance-classes`
- `affordance-reroute --compliant-only` for the report

## Added Instrument

`--hard-ban-affordance-classes` expands affordance class names into their audited
term sets before candidate selection. For example, `optical_memory` expands to
terms such as `photograph`, `mirror`, `glass`, `crystal`, `lens`, and
`telescope`; `organic_expansion` expands to terms such as `garden`, `greenhouse`,
`moss`, `vine`, `flower`, and `fern`.

This lets the selector test function-level channels instead of individual
surface words.

## Smoke Results

Reports:

- `experiments/affordance_class_knockout_mundane/optical_memory_report.md`
- `experiments/affordance_class_knockout_mundane/organic_expansion_report.md`
- `experiments/affordance_class_knockout_mundane/optical_organic_report.md`

All rows compare against the canonical hard-gate baseline.

| knockout | condition | survival | frontier delta | read |
| --- | --- | ---: | ---: | --- |
| `optical_memory` | `alpha=0.77` | 0.33 | +0.064 | survives through `text_memory` |
| `optical_memory` | `alpha=0.82` | 0.33 | +0.084 | survives through `organic_expansion` and `animating_mediator` |
| `organic_expansion` | `alpha=0.77` | 1.00 | +0.000 | unchanged |
| `organic_expansion` | `alpha=0.82` | 0.33 | -0.044 | weak survival through `threshold_container` and `optical_memory` |
| `optical_memory + organic_expansion` | `alpha=0.77` | 0.33 | +0.064 | narrow `text_memory` corridor remains |
| `optical_memory + organic_expansion` | `alpha=0.82` | 0.00 | -0.150 | compliant frontier band disappears |

## Interpretation

The surviving frontier is not one generic reroute phenomenon. It appears to be
channel-specific by alpha.

`alpha=0.77` can still find a narrow text-memory route after both optical and
organic channels are blocked. In the current smoke, its surviving exemplar is a
spreadsheet becoming a portal into an antique shop scene. This is not a broad
replacement distribution; it is a thin corridor.

`alpha=0.82` is different. It can survive either `optical_memory` or
`organic_expansion` alone, but removing both deletes its compliant frontier band
in this pool. That makes `alpha=0.82` look more dependent on the paired
optical-organic replacement channel.

This supports a stronger version of the affordance hypothesis:

```text
Readable ontology collapse is carried by multiple affordance corridors, and the
active corridor depends on steering pressure. Canonical stock hubs are one
high-availability corridor; optical, organic, textual, and threshold channels
can substitute, but not symmetrically across alpha.
```

## Caveats

The document counts are small because this is a post-hoc smoke over an existing
candidate pool. A zero-survival result means no compliant candidate in this
saved pool met the observed frontier band; it does not prove that generation
cannot produce one under a dedicated prompt-level class ablation.

The next empirical step is a prompt-level class knockout sweep, especially for
`optical_memory + organic_expansion` at `alpha=0.82`, to see whether generation
can reroute into another corridor when those channels are unavailable from the
start.

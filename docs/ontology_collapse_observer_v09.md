# v0.9 Ontology Collapse Observer

The v0.8 observer looked for *controlled semantic displacement without coherence collapse*.
The v0.9 observer refines the target phenomenon:

> high linguistic coherence + high ontological instability

The key distinction is that the text can remain readable while object identity,
category stability, and affordance consistency liquefy. This is not ordinary
syntax collapse or discourse derailment. It is an ontology-level instability that
can coexist with local readability.

## New audit command

```bash
depaysement-lab ontology-audit experiments/no_steer.json experiments/with_steer.json \
  --show-events
```

JSON output:

```bash
depaysement-lab ontology-audit experiments/no_steer.json experiments/with_steer.json \
  --json --out experiments/ontology_audit.json
```

Text/markdown output:

```bash
depaysement-lab ontology-audit experiments/no_steer.json experiments/with_steer.json \
  --show-events --out experiments/ontology_audit.md
```

## Decomposition

### identity_melt

Object persistence remains, but class identity changes.

Examples:

```text
The music box, now a garden, wraps vines around the clock.
The contract, now a transparent fish, floats on the puddle.
```

### affordance_corruption

The object remains named, but its capabilities drift.

Examples:

```text
The air vent hummed a melody that attracted a book.
The umbrellas seemed to stir.
```

### category_bleeding

Multiple concept fields appear in the same local clause/image: body, machine,
bureaucracy, nature, domestic objects, architecture. This channel is explicitly
lexical and audit-only; it is not used as a generator reward.

### atmospheric_conservation

A set of atmospheric descriptors persists while objects mutate: dusty, faded,
worn, damp, forgotten, spectral, moonlit, rusted, yellowed, etc.

### repair_pressure

The model attempts to restore ontology by explanation, symbolism, narrative
closure, or assistant-style rationalization.

Examples:

```text
this symbolizes loneliness
everything made sense
a reminder of redemption
```

### syntax_readability_proxy

A cheap non-parser proxy based on unfinished fragments, repetition, meta leak,
and collapse penalty. It is meant only to catch obvious truncation/noise.

## Derived metrics

```text
ontology_collapse_density
  = identity_melt + affordance_corruption + category_bleeding

readable_surreal_frontier
  = ontology_collapse_density
    * syntax_readability_proxy
    * (1 - repair_pressure)
    * relation_graph_factor
```

A strong target run has:

```text
ontology_collapse_density high
syntax_readability_proxy high
repair_pressure low
atmospheric_conservation nonzero
unfinished low
```

## Repair-control condition

`observe` can now add a repair-inducing control condition:

```bash
depaysement-lab observe \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --chat-template \
  --include-repair-control \
  --repair-temperature 0.35 \
  --seed "A forgotten umbrella at the station" \
  --out experiments/observe_with_repair.json
```

This condition asks the model to make the strange scene narratively coherent. It
should increase repair pressure relative to the selector condition.

## Caveat

These are transparent heuristics. They are not theoretical truth. The intended
next validation step is still human annotation of 10--30 examples and a
correlation check between human judgments and each audit channel.

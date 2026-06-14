# Hub Ablation Probe

Date: 2026-06-14

## Question

The mundane-seed noun graph and hub-bias smoke suggested that high-frontier
outputs often route through `music box`, `book`, `key`, `clock`, `watch`,
`porcelain`, and `doll` motifs. The open question was whether this was mostly
metric/selector preference, or whether steering itself was dragging ordinary
seeds into that semantic channel.

## Setup

Two matched 8-seed smoke sweeps were compared:

- matched control: `experiments/frontier_sweep_mundane_matched_alpha0_smoke/`
- soft hub ablation: `experiments/frontier_sweep_mundane_hub_ablation_smoke/`

Both used the same mundane seed bank, alpha grid, candidate count, token limit,
and `banded-frontier` selector:

```text
seed bank: data/mundane_seed_bank_en_v1.json
seed limit: 8
steps: 3
alphas: 0, 0.66, 0.77, 0.82
candidates: 8
max_new_tokens: 100
selector: banded-frontier, choose=best
vectors: experiments/depaysement_mlx_vectors_l4_18.npz
steer layers: 4-18
```

The ablation run added:

```text
--ban-terms "music box, leather-bound book, key, clock, watch, pocket watch, porcelain, doll, ballerina"
```

This is a prompt-level soft ablation. It tests pressure and rerouting, not hard
compliance.

## Result

The matched comparison strongly favors the steering-drag interpretation.

In the non-ban steered pools, banned-core motifs appeared in roughly 79-83% of
candidates. Under the ban prompt, the same motifs fell to:

| condition | banned core after ablation | delta vs matched control |
| --- | ---: | ---: |
| `alpha=0.66` | 6.8% | -71.9% |
| `alpha=0.77` | 8.3% | -75.0% |
| `alpha=0.82` | 16.7% | -66.7% |

Frontier did not disappear:

| condition | delta frontier | delta ontology | delta read | delta unfinished |
| --- | ---: | ---: | ---: | ---: |
| `alpha=0.66` | +0.010 | +0.058 | -0.024 | +0.043 |
| `alpha=0.77` | +0.001 | +0.016 | -0.015 | +0.035 |
| `alpha=0.82` | -0.012 | -0.063 | -0.038 | +0.005 |

This suggests the banned hubs were not just decorative cliches. They were also
stabilizing junctions. Removing them reduces stock-prop pressure, but it also
makes the frontier patchier and slightly more unfinished.

## Reroutes

The strongest replacement increases were:

| condition | replacement group | delta |
| --- | --- | ---: |
| `alpha=0.66` | `harmonica_harmonium` | +16.7% |
| `alpha=0.77` | `harmonica_harmonium` | +16.1% |
| `alpha=0.66` | `photograph_photo` | +11.5% |
| `alpha=0.66` | `garden_greenhouse` | +10.4% |
| `alpha=0.77` | `mailbox_satchel` | +9.9% |
| `alpha=0.77` | `typewriter` | +8.3% |
| `alpha=0.82` | `teapot_cup` | +8.3% |

The most useful read is not "the hub class vanished." It rerouted. The model
appears to preserve readable ontological transition by substituting other hinge
objects: instruments, writing machines, photographs, gardens, small containers,
and ordinary domestic objects.

## Caveats

- The ban is prompt-level only. Banned terms still leak in a minority of
  candidates, especially generic words such as `key` and partial antique-object
  fragments.
- The ablation prompt also changes the alpha-0 condition, so alpha-0 is a
  control for selector and prompt pressure, not a completely untouched baseline.
- One saved candidate pool had a truncated saved-pool warning in the ablation
  sweep. The aggregate signal remains useful, but a larger repeat should use
  full candidate saves and a hard compliance gate.

## Next Step

Add a hard candidate-level compliance gate:

```text
reject if banned_core_hit
then select banded-frontier among compliant candidates
```

That would separate three effects:

1. Prompt-level steering around hubs.
2. Model compliance failure.
3. Whether readable frontier survives when banned hubs are actually removed
   from the selected candidate set.

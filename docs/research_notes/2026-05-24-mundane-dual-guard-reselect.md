# Research Note: Mundane Dual Guard Reselect

Date: 2026-05-24

## Question

After the mundane seed probe exposed the
`antique / music box / porcelain / miniature` attractor basin, can we recover
better samples from the already generated candidate pools without running new
generation?

This pass tests two post-hoc selector guards:

- stronger cliche and stock-prop penalties;
- ordinary-anchor retention, so the selected text keeps some pressure from
  seeds such as `receipt`, `folder`, `bus`, `spreadsheet`, or `fridge`.

## Inputs

Source candidate pools:

- `experiments/frontier_sweep_mundane_seed_probe`

These experiment artifacts remain ignored by git. The note records the
reproducible commands and aggregate readout.

## Commands

Cliche / stock-prop guard:

```bash
PYTHONPATH=src python3 -m depaysement_lab.cli reselect \
  experiments/frontier_sweep_mundane_seed_probe/steer_alpha_*.json \
  --select-objective banded-frontier \
  --choose best \
  --context-policy recorded \
  --include-original \
  --unfinished-weight 1.05 \
  --repetition-weight 0.45 \
  --sprawl-weight 0.60 \
  --cliche-weight 0.55 \
  --fantasy-prop-weight 0.75 \
  --out-dir experiments/posthoc_reselect_mundane_cliche_prop_guard_v2
```

Dual guard:

```bash
PYTHONPATH=src python3 -m depaysement_lab.cli reselect \
  experiments/frontier_sweep_mundane_seed_probe/steer_alpha_*.json \
  --select-objective banded-frontier \
  --choose best \
  --context-policy recorded \
  --unfinished-weight 1.05 \
  --repetition-weight 0.45 \
  --sprawl-weight 0.60 \
  --cliche-weight 0.55 \
  --fantasy-prop-weight 0.75 \
  --ordinary-anchor-weight 0.90 \
  --ordinary-anchor-min 0.50 \
  --out-dir experiments/posthoc_reselect_mundane_dual_guard
```

## Aggregate Comparison

The original picked candidates were re-audited with the new anchor/prop metrics.

| selector | picked frontier | anchor | cliche | fantasy prop | unfinished rate | read | ontology |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | 0.143 | 0.700 | 0.845 | 0.839 | 0.500 | 0.684 | 0.529 |
| cliche / prop guard | 0.126 | 0.681 | 0.725 | 0.605 | 0.555 | 0.664 | 0.498 |
| dual guard | 0.122 | 0.743 | 0.730 | 0.617 | 0.585 | 0.652 | 0.501 |

## Interpretation

The stock-prop penalty works. It cuts the picked fantasy-prop score from
`0.839` to about `0.61`, but it costs roughly `0.017-0.020` picked frontier.

The ordinary-anchor guard also works, but it is too stiff at
`ordinary_anchor_min=0.50`. It raises anchor retention to `0.743`, but it also
increases unfinished pressure to `0.585`.

This suggests the selector has begun to distinguish ordinary-object pressure
from stock-prop drift, but the guard currently accepts too many truncated
survivors.

## Most Useful Survivors

The focused human rating sheet was cut from the most promising dual-guard runs:

- `alpha=0.77`, seed 05, spreadsheet;
- `alpha=0.72`, seed 08, fridge;
- `alpha=0.72`, seed 01, receipt;
- `alpha=0.66`, seed 08, fridge;
- `alpha=0.77`, seed 02, folder;
- `alpha=0.66`, seed 03, bus.

The first spreadsheet example is a good diagnostic case: it preserves the
spreadsheet while shedding the porcelain/music-box prop cluster, though it still
contains soft cliche pressure such as fog and ethereal diction.

## Next Hypothesis

Relax anchor retention and hit unfinished harder:

```text
cliche_weight=0.35
fantasy_prop_weight=1.10
ordinary_anchor_weight=0.55
ordinary_anchor_min=0.35
unfinished_weight=1.40
```

This should keep ordinary source pressure as a floor, not a cage, while pushing
the selector away from truncated tails and stock props.

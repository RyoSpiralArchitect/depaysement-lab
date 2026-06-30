# Trajectory Lineage Scoring

This pass extends `trajectory-audit` from run-level frontier health to
lineage-aware trajectory health. No new text was generated; the audit rereads
saved mundane-seed runs and post-hoc reselections.

## Command

```bash
PYTHONPATH=src python3 -m depaysement_lab.cli trajectory-audit \
  experiments/frontier_sweep_mundane_seed_probe/steer_alpha_*.json \
  experiments/posthoc_reselect_mundane_balanced_guard/*__banded-frontier_best.json \
  experiments/posthoc_reselect_mundane_hard_gate/*__banded-frontier_best.json \
  experiments/posthoc_reselect_mundane_dual_guard/*__banded-frontier_best.json \
  --top-k 12 \
  --out experiments/trajectory_lineage_mundane/trajectory_lineage_report.md \
  --json-out experiments/trajectory_lineage_mundane/trajectory_lineage_report.json \
  --csv experiments/trajectory_lineage_mundane/trajectory_lineage_runs.csv
```

## Added Metrics

- `object_lineage_continuity`: object vocabulary overlap from one picked step
  to the next.
- `readable_transition_auc`: frontier weighted by readability, completion, and
  object lineage.
- `hub_revisit_rate`: repeated transport-affordance objects across a picked
  trajectory.
- `motif_loop_penalty`: combined pressure from hub revisits, motif repetition,
  and selector repetition penalty.
- `lineage_quality`: blend of previous-step anchor retention and object
  lineage continuity.

## Group Means

| selector | score | readable transition | frontier AUC | terminal read | anchor | object lineage | hub revisit | loop penalty | stock prop | unfinished |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| original | 0.331 | 0.065 | 0.143 | 0.662 | 0.667 | 0.428 | 0.425 | 0.499 | 0.840 | 0.500 |
| balanced guard | 0.322 | 0.048 | 0.118 | 0.603 | 0.727 | 0.343 | 0.299 | 0.413 | 0.571 | 0.590 |
| hard gate | 0.327 | 0.056 | 0.120 | 0.640 | 0.754 | 0.294 | 0.288 | 0.422 | 0.584 | 0.310 |
| dual guard | 0.327 | 0.050 | 0.122 | 0.615 | 0.708 | 0.382 | 0.329 | 0.427 | 0.618 | 0.585 |

## Read

The original selector still has the strongest frontier AUC and readable
transition signal. The new lineage metrics show the cost: it also has the
highest stock-prop dependence, hub revisit rate, and motif-loop penalty.

The hard gate has the cleanest trajectory health profile. It sharply reduces
unfinished rate and lowers hub revisit pressure, but its object lineage is
weaker than the original. That suggests the gate is pruning bad tails and stock
loops, while sometimes also cutting the concrete object thread that makes a
depaysement trajectory feel traceable.

The dual guard sits between those regimes. It keeps more object lineage than
hard gate, but its unfinished rate remains close to balanced guard. That makes
it less attractive as the default selector, but useful as a diagnostic
condition.

## Interpretation

The new audit separates three phenomena that were previously blended:

1. A real readable-frontier trajectory, where object lineage survives while the
   ontology shifts.
2. A stock-hub loop, where the run remains legible by revisiting familiar
   transport objects.
3. A guarded but thinned trajectory, where truncation risk drops but the object
   thread becomes less continuous.

This keeps the mainline hypothesis sharper: readable ontology collapse is not
just a high frontier point; it is a traceable transformation path through
objects and transport affordances.

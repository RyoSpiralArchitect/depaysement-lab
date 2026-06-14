# Readable Ontology Collapse Trajectory Audit

This note extends the frontier work from point-wise candidate selection to
picked-run trajectories. No new text was generated for this pass.

## What Changed

The new `trajectory-audit` command audits saved picked sequences as whole runs:

```bash
PYTHONPATH=src python3 -m depaysement_lab.cli trajectory-audit \
  experiments/frontier_sweep_mundane_seed_probe/steer_alpha_*.json \
  experiments/posthoc_reselect_mundane_balanced_guard/*__banded-frontier_best.json \
  experiments/posthoc_reselect_mundane_hard_gate/*__banded-frontier_best.json \
  --top-k 12 \
  --out experiments/trajectory_audit_mundane/trajectory_report.md \
  --json-out experiments/trajectory_audit_mundane/trajectory_report.json \
  --csv experiments/trajectory_audit_mundane/trajectory_runs.csv
```

It reports:

- `trajectory_frontier_auc`: mean picked-step frontier;
- `terminal_readability`;
- `anchor_survival`: seed anchors retained somewhere in the picked trajectory;
- `lineage_continuity`: each step carrying anchors from the previous picked step;
- `stock_prop_dependence` and `soft_style_dependence`;
- `motif_entropy` / `motif_repetition`;
- `now_chain_pressure`;
- `inscription_pressure`;
- `suggested_stop_step`.

## Group Means

Each selector contributes 40 mundane-seed runs.

| selector | trajectory score | frontier AUC | terminal read | anchor survival | lineage | stock prop | soft style | unfinished rate | post-peak decay | suggested stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| original | 0.369 | 0.143 | 0.662 | 0.667 | 0.807 | 0.840 | 0.453 | 0.500 | 0.080 | 3.125 |
| balanced guard | 0.364 | 0.118 | 0.603 | 0.727 | 0.770 | 0.571 | 0.408 | 0.590 | 0.080 | 3.050 |
| hard gate | 0.374 | 0.120 | 0.640 | 0.754 | 0.727 | 0.584 | 0.370 | 0.310 | 0.086 | 3.100 |

## Read

The trajectory view changes the interpretation slightly.

The original selector has the highest frontier AUC, but it buys that with the
highest stock-prop dependence and a high unfinished rate. In other words, the
point-wise frontier is strongest, but the run often travels through the
Victorian dollhouse attractor.

The balanced guard cuts stock props strongly, but it does not solve trajectory
health. Its unfinished rate rises to `0.590`, and terminal readability drops.
That confirms the previous suspicion: penalties alone can push the selector
toward incomplete alternatives when the saved pool is already fragile.

The hard gate has the best overall trajectory score in this audit. It does not
maximize frontier AUC, but it keeps more seed anchor, improves terminal
readability relative to balanced guard, reduces soft-style cliche, and cuts
unfinished rate almost in half.

The suggested stop step averages around step 3 for all three variants. That is
strong evidence that the useful trajectory often happens in the first two or
three moves, while later steps create descriptor recursion, stock-prop drift, or
truncated tails.

## Live Generation Support

The generation path now accepts adaptive stopping:

```bash
--trajectory-stop
--trajectory-min-steps 3
--trajectory-frontier-drop 0.08
--trajectory-unfinished-stop-max 0.05
--trajectory-repetition-stop-max 0.55
--trajectory-sprawl-stop-max 0.65
```

This is intentionally conservative. It does not try to pick a whole beam-level
path yet; it simply prevents a live run from continuing after the picked
trajectory starts to decay.

## Next Live Sweep

The next MLX run should test whether hard-gated early stopping improves
downstream pools:

```bash
PYTHONPATH=src python3 -m depaysement_lab.cli frontier-sweep \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --chat-template \
  --vectors experiments/depaysement_mlx_vectors_mundane_v2.npz \
  --steer-layers 4-18 \
  --seed-bank data/mundane_seed_bank_v1.json \
  --seed-limit 8 \
  --steps 4 \
  --alphas 0.66,0.77,0.88 \
  --candidate-grid 19 \
  --max-token-grid 110,125 \
  --select-objective banded-frontier \
  --choose best \
  --selector-unfinished-max 0.50 \
  --hard-unfinished-max 0.05 \
  --trajectory-stop \
  --trajectory-min-steps 3 \
  --unfinished-weight 1.40 \
  --repetition-weight 0.45 \
  --sprawl-weight 0.60 \
  --soft-style-cliche-weight 0.25 \
  --fantasy-prop-weight 1.10 \
  --ordinary-anchor-weight 0.45 \
  --ordinary-anchor-min 0.30 \
  --out-dir experiments/frontier_sweep_mundane_hard_gate_live
```

If this improves terminal readability and unfinished rate without collapsing
frontier AUC, the project has a clean path from point-wise frontier selection to
trajectory-aware generation.

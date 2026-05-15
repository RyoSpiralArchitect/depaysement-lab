# Experiments

This directory keeps selected published artifacts rather than every local run.

The currently published artifact set is:

- [`frontier_sweep_steered_hybrid_focus_best/`](frontier_sweep_steered_hybrid_focus_best/)

That directory contains:

```text
frontier_sweep_report.md       compact run-level summary
frontier_sweep_report.json     full audit JSON
frontier_sweep_candidates.csv  candidate-level metrics
frontier_sweep_texts.md        generated text reading report
frontier_sweep.png             frontier scatter plot
frontier_sweep_manifest.json   run metadata
steer_alpha_*.json             saved generation runs with candidate pools
```

Large exploratory sweeps, local vector files, caches, and ad hoc observations
are intentionally ignored by git unless they are promoted into a published
artifact directory.

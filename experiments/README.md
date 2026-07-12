# Experiments

This directory keeps selected published artifacts rather than every local run.

Published artifacts include:

- [`frontier_sweep_steered_hybrid_focus_best/`](frontier_sweep_steered_hybrid_focus_best/)
- [`prompt_steering_contrast_llama3p2_seed12/`](prompt_steering_contrast_llama3p2_seed12/)

The focused frontier directory contains:

```text
frontier_sweep_report.md       compact run-level summary
frontier_sweep_report.json     full audit JSON
frontier_sweep_candidates.csv  candidate-level metrics
frontier_sweep_texts.md        generated text reading report
frontier_sweep.png             frontier scatter plot
frontier_sweep_manifest.json   run metadata
steer_alpha_*.json             saved generation runs with candidate pools
```

The prompt x steering directory publishes a compact summary, all 576 generated
texts and candidate metrics, seed-paired contrasts, a same-seed triptych, the
plot, and a blinded human construct sheet. Per-cell resume JSON and the duplicate
full report remain local because the candidate CSV and reading view already
retain the auditable prose.

Large exploratory sweeps, local vector files, caches, and ad hoc observations
are intentionally ignored by git unless they are promoted into a published
artifact directory.

# v1.0 — Readable Ontology Collapse Frontier

v1.0 turns the project from a picked-output observer into a candidate-pool observer.
The core question is:

```text
Did steering move the model's candidate distribution, or did the selector simply
cherry-pick one rare ontologically unstable continuation?
```

The target phenomenon is:

```text
high local readability
+ coherent scene relation structure
+ low repair pressure
+ high ontology collapse density
```

This is called the **Readable Ontology Collapse Frontier**.

## New command: pool-audit

```bash
depaysement-lab pool-audit \
  experiments/no_steer.json \
  experiments/with_steer.json \
  --out experiments/frontier_report.md \
  --json-out experiments/frontier_report.json \
  --csv experiments/frontier_candidates.csv \
  --plot experiments/frontier.png \
  --top-k 8
```

`pool-audit` reads saved `write` / `observe` artifacts and audits every saved
candidate, not only the picked continuation.

It reports:

```text
pool_mean_readable_ontology_frontier
pool_mean_ontology_collapse_density
pool_mean_identity_melt_score
pool_mean_affordance_corruption_score
pool_mean_syntax_readability_proxy
pool_mean_graph_integration
pool_mean_repair_pressure
pool_unfinished_rate
picked_mean_...
selection_lift_...
pool_shift_b_minus_a
```

## Pool shift vs selection lift

`pool_shift` asks whether the candidate distribution moved:

```text
mean(metric over candidates in condition B)
-
mean(metric over candidates in condition A)
```

`selection_lift` asks how much the selector is doing:

```text
mean(metric over picked candidates)
-
mean(metric over saved candidate pool)
```

If `pool_shift` is small and `selection_lift` is large, the selector is likely
cherry-picking rare frontier candidates. If both are positive, steering probably
moves the distribution and the selector selects from a shifted pool.

## Frontier score

For each candidate, v1.0 computes:

```text
frontier_quality =
  syntax_readability_proxy
  × graph_integration_factor
  × (1 - repair_pressure)
  × (1 - unfinished)
  × (1 - meta_leak)

readable_ontology_frontier =
  ontology_collapse_density
  × frontier_quality
  × atmosphere_factor
```

Atmosphere is a weak stabilizer, not a hard requirement.

## New command: frontier-sweep

```bash
depaysement-lab frontier-sweep \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --chat-template \
  --vectors experiments/depaysement_mlx_vectors.npz \
  --steer-layers 6-16 \
  --seed "A forgotten umbrella at the station" \
  --steps 5 \
  --alphas 0,0.3,0.6,0.9,1.2 \
  --candidate-grid 8,12,24 \
  --max-token-grid 120,160,220 \
  --out-dir experiments/frontier_sweep
```

The sweep writes one run artifact per grid point, then writes:

```text
frontier_sweep_report.md
frontier_sweep_report.json
frontier_sweep_candidates.csv
frontier_sweep.png
frontier_sweep_manifest.json
```

The model is loaded once per sweep command. For HF/MLX, the command changes
`steering.alpha` between runs rather than reloading weights for every alpha.

## Important artifact requirement

Candidate-pool geometry only works if candidates are saved. For `observe`, v1.0
sets `--save-candidates` high by default so the common case saves all generated
candidates. For manual `write` runs, use:

```bash
depaysement-lab write ... \
  --candidates 12 \
  --save-candidates 12 \
  --out experiments/run.json
```

If an artifact saved fewer candidates than `candidates_per_step`, `pool-audit`
marks `truncated_steps > 0` and treats the result as a saved-subset audit.

## Caveats

The frontier metrics remain heuristic instruments. They are good for comparing
runs and selecting examples for human evaluation, but they are not a theory of
surrealism. Use human ratings before turning them into claims.

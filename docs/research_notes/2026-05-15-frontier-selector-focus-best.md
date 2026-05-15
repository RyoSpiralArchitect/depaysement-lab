# Research Note: Focused Frontier Selector Sweep

Date: 2026-05-15

## Question

The previous broad sweep suggested that steering was moving the candidate pool
toward ontology collapse, but the selector was not always picking the readable
frontier candidates. The next question was narrower:

> If we use a frontier-aware hybrid selector and deterministic `choose=best`,
> which steering dose best preserves readable ontology collapse?

## Experimental Setup

Seed:

```text
A forgotten umbrella at the station
```

Command:

```bash
python3 -m depaysement_lab.cli frontier-sweep \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --chat-template \
  --vectors experiments/depaysement_mlx_vectors.npz \
  --steer-layers 6-16 \
  --seed "A forgotten umbrella at the station" \
  --steps 5 \
  --alphas 0.45,0.6,0.75 \
  --candidate-grid 12 \
  --max-token-grid 140 \
  --select-objective hybrid \
  --choose best \
  --unfinished-weight 1.10 \
  --repetition-weight 0.45 \
  --sprawl-weight 0.30 \
  --out-dir experiments/frontier_sweep_steered_hybrid_focus_best
```

Artifacts:

- [report](../../experiments/frontier_sweep_steered_hybrid_focus_best/frontier_sweep_report.md)
- [generated text reading report](../../experiments/frontier_sweep_steered_hybrid_focus_best/frontier_sweep_texts.md)
- [candidate CSV](../../experiments/frontier_sweep_steered_hybrid_focus_best/frontier_sweep_candidates.csv)
- [plot](../../experiments/frontier_sweep_steered_hybrid_focus_best/frontier_sweep.png)
- [manifest](../../experiments/frontier_sweep_steered_hybrid_focus_best/frontier_sweep_manifest.json)

## Results

| condition | pool frontier | picked frontier | selection lift | picked ontology | picked readability | picked unfinished | picked hit rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| `alpha=0.60, c=12, tok=140` | 0.046 | 0.123 | +0.078 | 0.344 | 0.695 | 0.080 | 0.60 |
| `alpha=0.45, c=12, tok=140` | 0.029 | 0.122 | +0.093 | 0.485 | 0.600 | 0.160 | 0.40 |
| `alpha=0.75, c=12, tok=140` | 0.034 | 0.102 | +0.069 | 0.307 | 0.660 | 0.000 | 1.00 |

## Interpretation

The focused sweep supports the working hypothesis that the best current region
is near:

```text
alpha ~= 0.6
candidates_per_step = 12
max_new_tokens ~= 140
selector = hybrid
choose = best
```

`alpha=0.60` gives the strongest picked frontier score while keeping readability
high. It is the best current compromise between ontological movement and
syntactic stability.

`alpha=0.45` gives the largest selection lift, meaning the selector found better
frontier samples than the average pool would imply. However, it also has lower
picked readability and more unfinished pressure than `0.60`.

`alpha=0.75` has the cleanest picked hit rate and no picked unfinished penalty
in this sweep, but its picked frontier score is lower. This may be a useful
"safer but less intense" dose.

## Qualitative Reading

The strongest qualitative `alpha=0.60` thread moves from station-object staging
into readable ontology drift: a bird and book enter the umbrella scene, a puddle
becomes a spherical mirror, and a miniature stage/toadstool appears. This is not
just atmosphere; objects begin to trade affordances while the local scene remains
trackable.

The best examples are not necessarily the most collapsed examples. Several
failure candidates reached high ontology density but became truncated,
fragmented, or too liquid. This confirms the value of the band-pass selector:
the aim is not maximum collapse, but readable collapse.

## Working Claim

Steering appears to create a dose-dependent pressure toward ontology collapse,
but readable depaysement emerges only in a constrained window. For this seed and
model, the current window is:

```text
alpha: 0.45-0.75
best point so far: alpha=0.60
max_new_tokens: 140
candidates: 12
selector: hybrid, choose=best
```

## Caveats

- The experiment uses one seed and one small quantized instruction model.
- Metrics are heuristics and should be treated as instruments, not final truth.
- The `unfinished` detector is still coarse.
- Human taste remains decisive; the reading report should be reviewed manually.

## Next Steps

1. Repeat the focused sweep over 3-5 seeds to see whether `alpha=0.60, tok=140`
   generalizes.
2. Split unfinished detection into hard truncation, malformed tail, control-token
   leakage, comma chain, repetition loop, and quote-tail cases.
3. Add a lightweight human rating sheet for selected picked and non-picked top
   frontier candidates.
4. Compare `hybrid` against `pareto` on the same candidate pools.
5. Try a slightly higher frontier weight with stronger truncation penalties to
   see whether the selector can recover missed top-frontier candidates without
   drifting into liquefaction failure.

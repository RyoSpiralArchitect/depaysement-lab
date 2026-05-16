# Research Note: Banded Frontier and Human Rating Sheet

Date: 2026-05-16

## Question

The pure `frontier` selector found stronger readable-ontology frontier
candidates than the original `hybrid` selector, but pure frontier can chase the
upper envelope into over-collapse or malformed tails. The next question was:

> Can a banded frontier selector recover more frontier material while staying
> closer to the readable band?

## Experimental Setup

This is still a no-generation experiment. It reuses the saved candidate pools
from the focused MLX sweep.

Command:

```bash
python3 -m depaysement_lab.cli reselect \
  experiments/frontier_sweep_steered_hybrid_focus_best/steer_alpha_0p45_c12_tok140.json \
  experiments/frontier_sweep_steered_hybrid_focus_best/steer_alpha_0p6_c12_tok140.json \
  experiments/frontier_sweep_steered_hybrid_focus_best/steer_alpha_0p75_c12_tok140.json \
  --select-objectives depaysement,frontier,banded-frontier,hybrid,pareto \
  --choose best \
  --include-original \
  --unfinished-weight 1.10 \
  --repetition-weight 0.45 \
  --sprawl-weight 0.30 \
  --out-dir experiments/posthoc_reselect_banded_frontier_lab
```

Rating sheet command:

```bash
python3 -m depaysement_lab.cli export-rating-sheet \
  experiments/frontier_sweep_steered_hybrid_focus_best/steer_alpha_*.json \
  experiments/posthoc_reselect_banded_frontier_lab/steer_alpha_*.json \
  --top-k 2 \
  --out experiments/posthoc_reselect_banded_frontier_lab/human_rating_sheet.csv \
  --markdown-out experiments/posthoc_reselect_banded_frontier_lab/human_rating_sheet.md
```

Artifacts:

- [report](../../experiments/posthoc_reselect_banded_frontier_lab/posthoc_reselect_report.md)
- [generated text reading report](../../experiments/posthoc_reselect_banded_frontier_lab/posthoc_reselect_texts.md)
- [candidate CSV](../../experiments/posthoc_reselect_banded_frontier_lab/posthoc_reselect_candidates.csv)
- [plot](../../experiments/posthoc_reselect_banded_frontier_lab/posthoc_reselect.png)
- [rating sheet CSV](../../experiments/posthoc_reselect_banded_frontier_lab/human_rating_sheet.csv)
- [rating sheet reading view](../../experiments/posthoc_reselect_banded_frontier_lab/human_rating_sheet.md)
- [manifest](../../experiments/posthoc_reselect_banded_frontier_lab/posthoc_reselect_manifest.json)

## Selector Definition

`banded-frontier` starts from readable ontology frontier, then subtracts explicit
band violations:

```text
banded_frontier_score =
  eligible_bonus
  + frontier_weight * readable_ontology_frontier
  + 0.15 * ontology_band_score
  - ontology_below/above_band penalties
  - readability/frontier_quality deficits
  - repair/unfinished excess penalties
  - repetition/sprawl penalties
```

An eligible candidate must satisfy:

```text
ontology_min <= ontology <= ontology_max
readability >= readability_min
frontier_quality >= frontier_quality_min
repair <= repair_max
unfinished <= unfinished_max
```

If no candidate is fully eligible, the selector still ranks by soft band
violation rather than falling back to raw depaysement score.

## Results

| condition | picked frontier | lift | picked ontology | picked readability | picked unfinished | picked hit rate |
|---|---:|---:|---:|---:|---:|---:|
| `alpha=0.45 original hybrid` | 0.122 | +0.093 | 0.485 | 0.600 | 0.160 | 0.40 |
| `alpha=0.45 frontier` | 0.160 | +0.130 | 0.647 | 0.591 | 0.160 | 0.60 |
| `alpha=0.45 banded-frontier` | 0.157 | +0.127 | 0.592 | 0.609 | 0.160 | 0.60 |
| `alpha=0.60 original hybrid` | 0.123 | +0.078 | 0.344 | 0.695 | 0.080 | 0.60 |
| `alpha=0.60 frontier` | 0.194 | +0.149 | 0.620 | 0.659 | 0.080 | 0.80 |
| `alpha=0.60 banded-frontier` | 0.156 | +0.110 | 0.493 | 0.650 | 0.080 | 0.80 |
| `alpha=0.75 original hybrid` | 0.102 | +0.069 | 0.307 | 0.660 | 0.000 | 1.00 |
| `alpha=0.75 frontier` | 0.110 | +0.076 | 0.429 | 0.618 | 0.080 | 0.80 |
| `alpha=0.75 banded-frontier` | 0.102 | +0.068 | 0.313 | 0.680 | 0.080 | 1.00 |

Changed steps:

| source alpha | frontier | banded-frontier | hybrid |
|---|---:|---:|---:|
| `0.45` | 2 / 5 | 2 / 5 | 0 / 5 |
| `0.60` | 3 / 5 | 4 / 5 | 0 / 5 |
| `0.75` | 2 / 5 | 3 / 5 | 0 / 5 |

## Interpretation

`banded-frontier` behaves like the intended middle path.

At `alpha=0.45`, it nearly matches pure frontier while reducing ontology
overshoot:

```text
frontier:        picked_frontier=0.160, ontology=0.647, readability=0.591
banded-frontier: picked_frontier=0.157, ontology=0.592, readability=0.609
```

At `alpha=0.60`, it gives up some pure frontier intensity but remains much more
frontier-aware than the original hybrid:

```text
hybrid:          picked_frontier=0.123, ontology=0.344
frontier:        picked_frontier=0.194, ontology=0.620
banded-frontier: picked_frontier=0.156, ontology=0.493
```

This is probably the most useful setting for the next real generation run: it
surfaces frontier material but is less eager to take the highest-collapse
candidate when that candidate sits outside the band.

At `alpha=0.75`, all selectors converge toward a safer but less intense region.
The banded selector changes several steps, but the aggregate frontier score
does not improve much over the original hybrid.

## Human Rating Sheet

The rating sheet contains 108 rows. It includes picked candidates and top
frontier candidates from the original focused runs and the post-hoc reselected
runs. The CSV has blank columns:

```text
human_score
human_notes
```

The Markdown reading view mirrors the same rows with full text blocks. This is
the intended bridge between metric discovery and human taste.

## Working Claim

Pure `frontier` is best treated as an oracle for finding the upper envelope.
`hybrid` is the conservative production selector. `banded-frontier` is now the
best candidate for the next actual steering run.

Suggested next generation setting:

```text
alpha = 0.60
candidates = 12
max_new_tokens = 140
selector = banded-frontier
choose = best
```

Also worth keeping as a contrast:

```text
alpha = 0.45
selector = banded-frontier
```

It has slightly lower intensity than `0.60`, but the banded selector is almost
as strong as pure frontier there.

## Next Steps

1. Manually rate the 108-row sheet, starting with rows where `kind` includes
   `picked+top_frontier`.
2. Compare human scores against `readable_ontology_frontier`,
   `banded_frontier_score`, and `hybrid_score`.
3. Run a small real generation sweep with `banded-frontier` at `alpha=0.45` and
   `alpha=0.60`.
4. Split the coarse `unfinished` metric before trusting fine-grained selector
   decisions about truncation.

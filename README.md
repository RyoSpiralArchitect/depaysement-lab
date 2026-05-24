# depaysement-lab

`depaysement-lab` is an experimental toolkit for studying **depaysement** as a
steerable language-model behavior: not simply "make it weird", but move a
coherent image into a different ontological regime while keeping it readable.

The current research target is the **Readable Ontology Collapse Frontier**:

```text
high linguistic coherence
+ high object/identity instability
+ low explanation/repair pressure
+ low truncation/repetition
```

In practical terms, the project asks:

1. Can activation steering move the whole candidate pool toward ontological
   collapse?
2. Can a selector pick the readable edge of that collapse instead of either
   ordinary surreal atmosphere or unreadable liquefaction?
3. Can the resulting outputs remain interesting to a human reader, not only to
   a heuristic metric?

The repository includes the generation CLI, structural scorers, ontology/frontier
auditors, MLX steering hooks, saved experiment artifacts, and research notes.

## Current Result

The latest focused sweep is saved in:

- [experiment directory](experiments/frontier_sweep_steered_hybrid_focus_best/)
- [frontier report](experiments/frontier_sweep_steered_hybrid_focus_best/frontier_sweep_report.md)
- [reading report with generated texts](experiments/frontier_sweep_steered_hybrid_focus_best/frontier_sweep_texts.md)
- [candidate-level CSV](experiments/frontier_sweep_steered_hybrid_focus_best/frontier_sweep_candidates.csv)
- [full JSON report](experiments/frontier_sweep_steered_hybrid_focus_best/frontier_sweep_report.json)
- [research note](docs/research_notes/2026-05-15-frontier-selector-focus-best.md)

![Readable Ontology Collapse Frontier sweep](experiments/frontier_sweep_steered_hybrid_focus_best/frontier_sweep.png)

Focused setup:

```text
backend: mlx
model: mlx-community/Llama-3.2-3B-Instruct-4bit
seed: A forgotten umbrella at the station
steps: 5
candidates per step: 12
max_new_tokens: 140
steering layers: 6-16
alphas: 0.45, 0.60, 0.75
selector: hybrid
choose: best
```

Summary of the focused `choose=best` sweep:

| condition | pool frontier | picked frontier | lift | picked ontology | picked readability | picked unfinished | picked hit rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| `alpha=0.60, c=12, tok=140` | 0.046 | 0.123 | +0.078 | 0.344 | 0.695 | 0.080 | 0.60 |
| `alpha=0.45, c=12, tok=140` | 0.029 | 0.122 | +0.093 | 0.485 | 0.600 | 0.160 | 0.40 |
| `alpha=0.75, c=12, tok=140` | 0.034 | 0.102 | +0.069 | 0.307 | 0.660 | 0.000 | 1.00 |

Interpretation:

- `alpha=0.60, tok=140` is the best current balance: high picked frontier,
  strong readability, and only modest unfinished pressure.
- `alpha=0.45, tok=140` produces the largest selection lift, but the picked
  outputs are a little less readable and more unfinished.
- `alpha=0.75, tok=140` has the cleanest hit rate, but appears less intense on
  the picked frontier score than `0.60`.

These metrics are not treated as final truth. They are instruments for finding
samples worth human reading.

The follow-up post-hoc selector lab is saved in:

- [post-hoc selector directory](experiments/posthoc_reselect_focus_best_lab/)
- [post-hoc frontier report](experiments/posthoc_reselect_focus_best_lab/posthoc_reselect_report.md)
- [post-hoc reading report](experiments/posthoc_reselect_focus_best_lab/posthoc_reselect_texts.md)
- [post-hoc candidate CSV](experiments/posthoc_reselect_focus_best_lab/posthoc_reselect_candidates.csv)
- [post-hoc research note](docs/research_notes/2026-05-16-posthoc-selector-lab.md)
- [banded-frontier selector directory](experiments/posthoc_reselect_banded_frontier_lab/)
- [human rating sheet](experiments/posthoc_reselect_banded_frontier_lab/human_rating_sheet.csv)
- [human rating reading view](experiments/posthoc_reselect_banded_frontier_lab/human_rating_sheet.md)
- [banded-frontier research note](docs/research_notes/2026-05-16-banded-frontier-rating-sheet.md)
- [actual banded-frontier generation sweep](experiments/frontier_sweep_banded_frontier_focus/)
- [actual banded-frontier research note](docs/research_notes/2026-05-16-banded-frontier-generation.md)

That lab performs no generation. It reuses the saved candidate pools from the
focused sweep and asks which selector would have picked the readable frontier.

| source alpha | original hybrid picked frontier | depaysement reselect | frontier reselect | pareto reselect | frontier changed steps |
|---|---:|---:|---:|---:|---:|
| `0.45` | 0.122 | 0.015 | 0.160 | 0.155 | 2 / 5 |
| `0.60` | 0.123 | 0.005 | 0.194 | 0.111 | 3 / 5 |
| `0.75` | 0.102 | 0.061 | 0.110 | 0.102 | 2 / 5 |

The main read: the old depaysement selector was not seeing the frontier. A pure
frontier selector finds stronger candidates, especially at `alpha=0.60`, while
the hybrid selector remains the more conservative readable default.

The newer `banded-frontier` selector sits between those two poles: it still
recovers frontier candidates, but penalizes candidates outside the ontology,
readability, repair, and unfinished bands.

| source alpha | hybrid | pure frontier | banded-frontier | banded ontology | banded readability | banded hit rate |
|---|---:|---:|---:|---:|---:|---:|
| `0.45` | 0.122 | 0.160 | 0.157 | 0.592 | 0.609 | 0.60 |
| `0.60` | 0.123 | 0.194 | 0.156 | 0.493 | 0.650 | 0.80 |
| `0.75` | 0.102 | 0.110 | 0.102 | 0.313 | 0.680 | 1.00 |

The practical interpretation is that pure `frontier` is a good oracle for the
upper envelope, while `banded-frontier` is the better candidate for the next real
generation run.

That next real generation run has now been executed for `alpha=0.45` and
`alpha=0.60`:

| selector | alpha | pool frontier | picked frontier | lift | picked ontology | picked readability | picked unfinished | picked hit rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `hybrid` | `0.45` | 0.029 | 0.122 | +0.093 | 0.485 | 0.600 | 0.160 | 0.40 |
| `hybrid` | `0.60` | 0.046 | 0.123 | +0.078 | 0.344 | 0.695 | 0.080 | 0.60 |
| `banded-frontier` | `0.45` | 0.039 | 0.137 | +0.098 | 0.537 | 0.587 | 0.160 | 0.60 |
| `banded-frontier` | `0.60` | 0.038 | 0.170 | +0.132 | 0.500 | 0.745 | 0.080 | 1.00 |

The best current setting is therefore:

```text
alpha = 0.60
candidates = 12
max_new_tokens = 140
selector = banded-frontier
choose = best
```

The remaining problem is not whether the selector can find frontier material.
It can. The remaining problem is tail control: late-step continuations can still
end in malformed or unfinished fragments.

The first human taste pass for that actual generation run is now saved in:

- [human taste analysis](experiments/frontier_sweep_banded_frontier_focus/human_rating_analysis.md)
- [human-rated sheet](experiments/frontier_sweep_banded_frontier_focus/human_rating_sheet.csv)
- [human taste research note](docs/research_notes/2026-05-17-human-taste-pass.md)

The strongest early signal is that human taste is not just the frontier metric.
The highest-rated rows include unpicked top-frontier candidates, and the notes
prefer oddness, daydream drift, and legible distortion over highly polished or
predictable writing. This points toward a two-stage selector: use
`banded-frontier` to stay readable, then rerank inside that band for human taste.

## What Is Being Measured?

The central audit decomposes candidate pools rather than only final outputs.
This matters because a good-looking final sample can come from two different
mechanisms:

```text
pool shift:
  steering moved the distribution itself

selection lift:
  the selector found a rare frontier candidate inside a mostly ordinary pool
```

The frontier score combines:

```text
ontology_collapse_density
  identity melt, affordance corruption, category bleeding

frontier_quality
  syntax readability, graph integration, anti-repair, anti-unfinished, anti-meta

readable_ontology_frontier
  ontology collapse density multiplied by frontier quality

cliche_attractor_score
  audit-only density of generic magic-realist vocabulary such as antique,
  porcelain, velvet, ethereal, music box, and moonlit terms
```

Failure examples are also retained: high ontology collapse with poor readability,
truncation, repetition, repair pressure, cliche-attractor drift, or graph
fragmentation.

## Selector Objectives

Generation can save the full candidate pool and then pick a continuation using
different objectives:

```bash
--select-objective depaysement
--select-objective frontier
--select-objective banded-frontier
--select-objective hybrid
--select-objective pareto
```

The current focused experiment uses `hybrid`:

```text
hybrid_score =
  depaysement_score
  + frontier_weight * readable_ontology_frontier
  + ontology_weight * ontology_band_score
  - unfinished_weight * unfinished
  - repair_weight * repair_pressure
  - repetition_weight * repetition_pressure
  - sprawl_weight * sprawl_pressure
  - cliche_weight * cliche_attractor_score
  - fantasy_prop_weight * fantasy_prop_score
  - ordinary_anchor_weight * ordinary_anchor_deficit
```

`cliche_weight` defaults to `0.0`, so old runs are unchanged.  Use it when you
want to discourage generic magic-realist diction after measuring it.
`fantasy_prop_weight` targets stock antique/miniature/porcelain props, while
`ordinary_anchor_weight` discourages candidates that drop mundane source anchors
such as `receipt`, `folder`, `bus`, `spreadsheet`, or `fridge`.

The ontology band is intentionally bounded. Pushing collapse upward without a
band tends to produce unfinished tails, adjective chains, or liquefied collage.

`banded-frontier` is the more explicit version of that idea:

```text
banded_frontier_score =
  eligible_bonus
  + frontier_weight * readable_ontology_frontier
  + small ontology_band_score bonus
  - ontology/readability/repair/unfinished band violations
  - repetition/sprawl penalties
```

## Post-hoc Selector Lab

Saved candidate pools can be reselected without generating any new text:

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

By default, `reselect` scores each saved step against the recorded context that
produced that candidate pool. This makes it a selector diagnostic, not a
counterfactual trajectory simulator: if the post-hoc pick changes at step 2, the
step 3 pool is still the originally generated step 3 pool.

The command writes:

```text
posthoc_reselect_report.md       run-level selector comparison
posthoc_reselect_report.json     full run and candidate audit
posthoc_reselect_candidates.csv  candidate-level table
posthoc_reselect_texts.md        human-readable generated texts
posthoc_reselect.png             scatter plot
*_reselect_*.json                reselected run artifacts
```

Export a human rating sheet from the original and reselected artifacts:

```bash
python3 -m depaysement_lab.cli export-rating-sheet \
  experiments/frontier_sweep_steered_hybrid_focus_best/steer_alpha_*.json \
  experiments/posthoc_reselect_banded_frontier_lab/steer_alpha_*.json \
  --top-k 2 \
  --out experiments/posthoc_reselect_banded_frontier_lab/human_rating_sheet.csv \
  --markdown-out experiments/posthoc_reselect_banded_frontier_lab/human_rating_sheet.md
```

The sheet includes picked candidates, top frontier candidates, machine metrics,
and blank `human_score` / `human_notes` fields.

## Install

Editable install:

```bash
python3 -m pip install -e .
```

Optional backend dependencies:

```bash
python3 -m pip install -e '.[mlx]'
python3 -m pip install -e '.[hf]'
python3 -m pip install -e '.[embed]'
python3 -m pip install -e '.[dev]'
python3 -m pip install -e '.[all]'
```

If the console script is not on your shell path, run through the module:

```bash
python3 -m depaysement_lab.cli --help
```

## Quick Smoke Test

Dependency-free dummy generation:

```bash
python3 -m depaysement_lab.cli write \
  --backend dummy \
  --seed "A forgotten umbrella at the station" \
  --steps 3 \
  --trace
```

Score a fragment:

```bash
python3 -m depaysement_lab.cli score \
  "The umbrella's handle is wrapped around a miniature skyscraper made of keys." \
  --graph
```

## Reproduce The Focused Frontier Sweep

The latest focused experiment was run with:

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

The sweep writes:

```text
frontier_sweep_report.md       run-level frontier summary
frontier_sweep_report.json     full run and candidate audit
frontier_sweep_candidates.csv  candidate-level table
frontier_sweep_texts.md        human-readable generated texts
frontier_sweep.png             scatter plot
steer_alpha_*.json             saved generation runs with candidates
```

### Multi-seed Mundane Probe

To test whether steering can move ordinary language rather than just falling
into literary attractors, sweep a mundane seed bank:

```bash
python3 -m depaysement_lab.cli frontier-sweep \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --chat-template \
  --vectors experiments/depaysement_mlx_vectors_l4_18.npz \
  --steer-layers 4-18 \
  --seed-bank data/mundane_seed_bank_en_v1.json \
  --seed-limit 8 \
  --steps 5 \
  --alphas 0.66,0.72,0.77,0.82,0.88 \
  --candidate-grid 19 \
  --max-token-grid 140 \
  --select-objective banded-frontier \
  --choose best \
  --unfinished-weight 1.05 \
  --repetition-weight 0.45 \
  --sprawl-weight 0.60 \
  --cliche-weight 0.15 \
  --out-dir experiments/frontier_sweep_mundane_seed_probe
```

`--seed-bank` accepts a JSON list, a JSON object with `seeds`, or a plain text
file with one seed per line.

After a mundane-seed sweep, reselect saved candidate pools without regenerating:

```bash
python3 -m depaysement_lab.cli reselect \
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
  --ordinary-anchor-weight 0.90 \
  --ordinary-anchor-min 0.50 \
  --out-dir experiments/posthoc_reselect_mundane_dual_guard
```

This tests whether better taste can be recovered from existing pools by
penalizing generic attractors and requiring the prose to retain some ordinary
source pressure.

## Collect MLX Steering Vectors

If vectors are missing, collect them first:

```bash
mkdir -p experiments

python3 -m depaysement_lab.cli collect-mlx-vectors \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --bank data/depaysement_bank_en_v3.json \
  --out experiments/depaysement_mlx_vectors.npz \
  --layers 6-16 \
  --chat-template \
  --verbose
```

The repo does not require MLX for dummy tests, but MLX is needed to reproduce
the activation-steered sweeps.

## Other Workflows

Run baseline vs rerank vs steering observation:

```bash
python3 -m depaysement_lab.cli observe \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --chat-template \
  --vectors experiments/depaysement_mlx_vectors.npz \
  --steer-alpha 0.6 \
  --steer-layers 6-16 \
  --seed "A forgotten umbrella at the station" \
  --steps 4 \
  --candidates 8 \
  --out experiments/observe_umbrella.json
```

Audit saved candidate pools:

```bash
python3 -m depaysement_lab.cli pool-audit \
  experiments/frontier_sweep_steered_hybrid_focus_best/steer_alpha_0p6_c12_tok140.json \
  --out experiments/frontier_report.md \
  --json-out experiments/frontier_report.json \
  --csv experiments/frontier_candidates.csv \
  --plot experiments/frontier.png \
  --texts-out experiments/frontier_texts.md
```

Export samples for human ratings:

```bash
python3 -m depaysement_lab.cli export-eval-set experiments/example_run.json \
  --out experiments/eval.jsonl \
  --top-k 3

python3 -m depaysement_lab.cli eval-correlate experiments/eval.jsonl
```

## Repository Map

```text
src/depaysement_lab/
  cli.py              command-line interface
  proto_v2.py         generation engine, candidate selector, prompt bank
  scorer_v07.py       structural depaysement scorer
  ontology.py         ontology-collapse decomposition
  frontier.py         candidate-pool frontier auditor and plots
  reselect.py         post-hoc selector laboratory for saved candidate pools
  mlx_intervention.py MLX steering-vector collection/injection
  observation.py      coherence-preserving displacement observer
  backends.py         MLX, HF, Ollama, OpenAI-compatible adapters

docs/
  implementation notes and research design docs

docs/research_notes/
  experiment writeups and interpretation

experiments/frontier_sweep_steered_hybrid_focus_best/
  published focused sweep artifacts

experiments/posthoc_reselect_focus_best_lab/
  published no-generation selector comparison artifacts

experiments/posthoc_reselect_banded_frontier_lab/
  published banded-frontier comparison and human rating sheet

experiments/frontier_sweep_banded_frontier_focus/
  published actual banded-frontier generation sweep
```

## Development

Run the focused checks:

```bash
python3 -m ruff check src/depaysement_lab tests
python3 -m pytest
```

Some tests and smoke runs print local environment messages from the user's MLX
setup. Those messages are not part of the project API.

## Limitations

- The frontier metrics are transparent heuristics, not a theory of surrealism.
- The current experiments use one small quantized instruction model on MLX.
- `unfinished` is still a coarse detector; future work should split it into
  hard truncation, control-token leakage, comma chains, repetition loops, and
  malformed tails.
- Post-hoc reselection reuses saved downstream candidate pools after changed
  picks, so it diagnoses selector behavior rather than simulating new
  trajectories.
- Human taste remains part of the loop. The reading report exists because the
  metric alone cannot decide whether a candidate is aesthetically alive.

## License

Apache-2.0. See [LICENSE](LICENSE).

# Frontier Noun Graph: Semantic Transport Hubs

Date: 2026-06-14

This note tests whether the recurring `music box / book / key / clock` motifs
in the mundane-seed frontier sweep are only stock surrealist props, or whether
they behave like semantic transport hubs: high-degree object nodes that let the
model preserve readability while moving between ontological states.

## Source

- Runs: `experiments/frontier_sweep_mundane_seed_probe/steer_alpha_*.json`
- Seeds: mundane seed bank (`receipt`, `spreadsheet`, `bus`, `fridge`,
  `drawer`, `elevator button`, `mug`, `delivery label`)
- Output:
  - `experiments/noun_graph_mundane_seed_probe/noun_graph_report.md`
  - `experiments/noun_graph_mundane_seed_probe/noun_graph_report_wide.md`
  - `experiments/noun_graph_mundane_seed_probe/noun_graph_nodes_wide.csv`

## Narrow Peak Band

The strict max-frontier band selected 8 documents out of 3,800 candidates:

- `frontier_max=0.394`
- `frontier_band_min=0.314`
- `band_documents=8`

Top node:

- `music box`: `stock_transport_hub`, `freq=8`, `degree=30`,
  `betweenness_norm=1.000`, `mean_frontier=0.358`

Even in the narrowest band, `music box` is not merely frequent. It is the
dominant bridge node in the candidate co-occurrence graph.

## Wider Frontier Band

The wider band selected 175 documents:

- `frontier_max=0.394`
- `frontier_band_min=0.174`
- `band_documents=175`

Top hub candidates:

| term | label | freq | degree | betweenness_norm | mean_frontier |
|---|---|---:|---:|---:|---:|
| music box | stock_transport_hub | 110 | 412 | 1.000 | 0.229 |
| leather-bound book | stock_transport_hub | 59 | 255 | 0.674 | 0.219 |
| key | stock_transport_hub | 33 | 131 | 0.632 | 0.230 |
| clock | stock_transport_hub | 31 | 120 | 0.520 | 0.219 |
| bird | semantic_transport_hub | 28 | 133 | 0.436 | 0.233 |
| door | semantic_transport_hub | 19 | 85 | 0.428 | 0.219 |
| mist | semantic_transport_hub | 27 | 125 | 0.343 | 0.211 |

Top co-occurrence edges also concentrate around the same hubs:

- `leather-bound book <-> music box`: 42
- `antique music box <-> music box`: 37
- `key <-> music box`: 24
- `bird <-> music box`: 19
- `clock <-> music box`: 17

## Interpretation

This supports a two-layer interpretation:

1. These nodes are stock surreal props.
2. Some of them also behave like semantic transport hubs.

The distinction matters. Penalizing every stock object may remove genuine
readability-preserving bridges. The next selector should separate:

- hub use: the object carries the text into a new ontological state;
- hub loop: the object recirculates inside a closed stock-prop basin;
- anchor transport: mundane objects remain connected to the hub path;
- anchor evaporation: the original mundane seed disappears.

The noun graph therefore suggests that the frontier is not a single surreal
direction. It is a small phase diagram with at least:

- stable readable surreal basin;
- stock transport hub basin;
- degenerate repetition basin.

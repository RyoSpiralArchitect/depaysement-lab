# LLM Judge Challenge

Blind absolute ratings were repeated in reverse item order. Pairwise choices were repeated with A/B positions swapped.

| provider | model | n | Pearson | Spearman | abs order MAD | pair accuracy | pair consistency | A rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| anthropic | claude-sonnet-5 | 12 | 0.059 | -0.007 | 0.583 | 0.583 | 0.611 | 0.444 |
| google | gemini-3.5-flash | 12 | 0.348 | 0.275 | 1.125 | 0.694 | 0.833 | 0.528 |
| openai | gpt-5.2 | 12 | 0.368 | 0.276 | 0.583 | 0.500 | 0.833 | 0.444 |

## Cross-Provider Agreement

| providers | absolute Pearson | absolute Spearman | pair-choice agreement |
|---|---:|---:|---:|
| anthropic / google | 0.788 | 0.818 | 0.639 |
| anthropic / openai | 0.842 | 0.865 | 0.611 |
| google / openai | 0.907 | 0.903 | 0.583 |

## Frozen Observer Reference

The same 12-item human pass gives the following correlations for deterministic observer components.

| metric | Pearson | Spearman |
|---|---:|---:|
| readable_ontology_frontier | 0.447 | 0.389 |
| frontier_quality | 0.487 | 0.209 |
| ontology_collapse_density | -0.018 | 0.187 |
| syntax_readability_proxy | 0.237 | 0.209 |
| graph_integration | 0.639 | 0.486 |
| repair_pressure | n/a | n/a |
| unfinished | -0.648 | -0.593 |
| score_total | 0.287 | 0.117 |

## Interpretation

The deterministic observer is retained because it is frozen, decomposable, replayable over full candidate pools, and independent of provider drift. The judge challenge tests convergent validity and instability; it does not promote either the heuristic observer or an API judge to literary ground truth.

This is a small, single-rater calibration pass. Broader claims about taste require more raters, explicit sampling, and inter-rater analysis.

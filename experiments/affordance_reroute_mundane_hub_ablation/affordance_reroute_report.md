# Affordance Reroute Matrix

base=matched_control | ablation=hub_ablation | base_docs=7 | ablation_docs=1

## Largest Class Deltas

| condition | class | base | ablation | delta |
| --- | --- | ---: | ---: | ---: |
| steer_alpha_0p66 | organic_expansion | 0.0% | 100.0% | +100.0% |
| steer_alpha_0p66 | optical_memory | 0.0% | 100.0% | +100.0% |
| steer_alpha_0p66 | acoustic_mechanism | 0.0% | 100.0% | +100.0% |
| steer_alpha_0p77 | canonical_stock_hub | 75.0% | 0.0% | -75.0% |
| steer_alpha_0p77 | acoustic_mechanism | 75.0% | 0.0% | -75.0% |
| steer_alpha_0p82 | text_memory | 66.7% | 0.0% | -66.7% |
| steer_alpha_0p82 | organic_expansion | 66.7% | 0.0% | -66.7% |
| steer_alpha_0p82 | canonical_stock_hub | 66.7% | 0.0% | -66.7% |
| steer_alpha_0p82 | animating_mediator | 66.7% | 0.0% | -66.7% |
| steer_alpha_0p82 | acoustic_mechanism | 66.7% | 0.0% | -66.7% |
| steer_alpha_0p77 | threshold_container | 50.0% | 0.0% | -50.0% |
| steer_alpha_0p77 | text_memory | 50.0% | 0.0% | -50.0% |
| steer_alpha_0p77 | organic_expansion | 50.0% | 0.0% | -50.0% |
| steer_alpha_0p82 | threshold_container | 33.3% | 0.0% | -33.3% |
| steer_alpha_0p77 | animating_mediator | 25.0% | 0.0% | -25.0% |
| steer_alpha_0p82 | time_mechanism | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p82 | optical_memory | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p77 | time_mechanism | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p77 | optical_memory | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p66 | time_mechanism | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p66 | threshold_container | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p66 | text_memory | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p66 | canonical_stock_hub | 0.0% | 0.0% | +0.0% |
| steer_alpha_0p66 | animating_mediator | 0.0% | 0.0% | +0.0% |

## Source Summaries

- matched_control steer_alpha_0p77: docs=4 frontier=0.260 unfinished=0.000 | canonical_stock_hub=75.0%, acoustic_mechanism=75.0%, text_memory=50.0%, threshold_container=50.0%
- matched_control steer_alpha_0p82: docs=3 frontier=0.248 unfinished=0.000 | canonical_stock_hub=66.7%, acoustic_mechanism=66.7%, text_memory=66.7%, organic_expansion=66.7%
- hub_ablation steer_alpha_0p66: docs=1 frontier=0.372 unfinished=0.000 | acoustic_mechanism=100.0%, organic_expansion=100.0%, optical_memory=100.0%

## Ablation Examples By Class

### acoustic_mechanism

condition=steer_alpha_0p66 | step=3 | candidate=2 | frontier=0.372 | classes=acoustic_mechanism,organic_expansion,optical_memory

```text
A delicate, filigework of spider, its legs splayed and twisted, weeps a tiny, crystal droplet of water, as the umbrella, now a miniature, forlorn garden, slowly unfurls, a tangle of petunias, forget-me-nots, and anemones, their tiny, bell-shaped bells, a soft, morning hymn.
```

### organic_expansion

condition=steer_alpha_0p66 | step=3 | candidate=2 | frontier=0.372 | classes=acoustic_mechanism,organic_expansion,optical_memory

```text
A delicate, filigework of spider, its legs splayed and twisted, weeps a tiny, crystal droplet of water, as the umbrella, now a miniature, forlorn garden, slowly unfurls, a tangle of petunias, forget-me-nots, and anemones, their tiny, bell-shaped bells, a soft, morning hymn.
```

### optical_memory

condition=steer_alpha_0p66 | step=3 | candidate=2 | frontier=0.372 | classes=acoustic_mechanism,organic_expansion,optical_memory

```text
A delicate, filigework of spider, its legs splayed and twisted, weeps a tiny, crystal droplet of water, as the umbrella, now a miniature, forlorn garden, slowly unfurls, a tangle of petunias, forget-me-nots, and anemones, their tiny, bell-shaped bells, a soft, morning hymn.
```

## Notes
- Rates are document hit rates inside the observed frontier band, not token frequencies.
- Classes overlap: one candidate can count as both text_memory and threshold_container.
- Use this matrix to distinguish word-level bans from function-level rerouting.

# Trajectory-Aware Steering

This PR turns the lineage-audit result into a live generation control.

Previous sweeps used one scalar `--steer-alpha` for an entire run. That is too
coarse for the current depaysement mainline: early steps often need enough
pressure to leave ordinary prose, while late steps need less pressure to avoid
unfinished tails, motif loops, and transport-hub overuse.

The new controls keep the single-vector intervention but make the dose
trajectory-aware:

```text
--steer-schedule
  explicit per-step alpha values; the last value repeats

--adaptive-steering
  after each picked step, adjust the next alpha from picked trajectory health
```

The first adaptive controller is intentionally small. It observes:

- `readable_ontology_frontier`
- `unfinished`
- `repetition_pressure`
- `sprawl_pressure`

Then it:

- boosts alpha when frontier is below target and the step is otherwise healthy;
- dampens alpha when unfinished or loop pressure rises;
- records the decision in `config.trajectory_steering.trace`.

This is not yet multi-vector steering. It is a live dose controller for the
current depaysement vector. The next layer can add:

- anti-loop or anti-stock-prop vectors;
- affordance-class vectors;
- lineage-aware selector penalties during live generation;
- random-vector and disabled-steering controls.

The working hypothesis is:

```text
Readable ontology collapse is not maximized by a single global alpha.
It appears in a corridor: enough steering to leave the ordinary anchor,
then enough damping to preserve lineage, readability, and closure health.
```

The immediate experiment should compare:

1. fixed alpha corridor runs (`0.66`, `0.77`);
2. scheduled alpha runs;
3. scheduled + adaptive runs;
4. the same settings under hub or affordance-class hard gates.

The important question is not only whether picked frontier increases. The
trajectory audit should also check whether object lineage survives, hub revisit
pressure falls, and terminal readability improves.

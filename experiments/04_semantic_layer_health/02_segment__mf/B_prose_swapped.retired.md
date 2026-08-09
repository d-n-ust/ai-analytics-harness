# B_prose_swapped — retired 2026-08-09

Removed from `arms:` here for the same reasons as in `../02_segment`, plus one this study's own
numbers make plain.

## It did not do what the README said it did

The README claimed the position control held. It did not:

| run | B_documented | B_prose_swapped |
|---|---|---|
| 20260807-142016 | 4/4 | 4/4 |
| 20260807-144843 | 4/4 | **3/4** |
| 20260807-145627 | 4/4 | **3/4** |

The arm it controls scored 4/4 every time. The control disagreed with it in two runs of three, and
that was written up as "declaration order changed nothing".

## Why the arm cannot settle it either way

Reordering changes the catalogue text, so a gap between this arm and `B_documented` is position OR noise
and nothing distinguishes them. As a position test it is underpowered by construction: the published
effects were measured with a target buried among 10-30 distractors, and a 15-metric list at roughly
1,200 tokens is not that regime.

The runner now reports self-disagreement across identical repetitions, which measures the noise
directly and without an arm.

## Where the question belongs

A catalogue large enough for position to matter — hundreds of metrics, as a real company has —
together with ordering, compression, and showing only the relevant part. That needs its own data
generation and is a separate experiment, not an arm here.

## The layer directory

`layers/B_prose_swapped/` is kept. It is the only worked example of expressing a position control in
MetricFlow YAML, where the patch language cannot reach.

---

level: surface
claim: "see arms/B_prose_swapped/ — MetricFlow YAML, used as it is"
layer_dir: layers/B_prose_swapped

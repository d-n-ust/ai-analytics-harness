# experiments/ — one folder per experiment, one folder per study

Two levels, because the work has two levels.

An **experiment** is a week's work that ends in an article on decisionspine.com. A **study** is one
runnable comparison inside it. Experiment 4 has two studies; experiments 1–3 have none, and that is
a fact about them rather than a gap — their runs are sweeps over code, not over configuration.

```
experiments/
├── engine.py                       the runner for declarative studies
├── 01_grounding_ladder/            ✓ shipped — how much does each layer of grounding buy?
├── 02_reliability_ladder/          ✓ shipped — what is each guardrail worth?
├── 03_evidence_graph/              ✓ shipped — what if every claim must cite its tool result?
└── 04_semantic_layer_health/       · in progress — does a more legible metric layer help?
    ├── experiment.yml
    ├── 02_segment/  the segment hides in the metric NAME    (S1)
    └── 02_segment/          the segment hides in the AGGREGATE      (S4)
```

```bash
./bench study                                  # the tree: every experiment, article, and study
./bench study 02_segment                # bare names resolve if unambiguous
./bench study 04_semantic_layer_health/02_segment   # or name it in full
```

## The experiment manifest

Every experiment folder carries an `experiment.yml`: what the week asked, whether it shipped, which
article it became, how its runs were driven, and where its artifacts live.

It is **loaded, not just read**. `./bench study` validates every manifest and reports pointers that
have gone stale — which caught a wrong path the day it was written. A manifest nobody checks is a
manifest that lies.

**`evidence:` points; it never holds copies.** `evals/cases/` is the frozen set the runner loads and
`results/published/` is cited by shipped articles, so moving either into a project folder would
break a path or shift a published denominator. The manifest's job is to answer "where is the
evidence for this article" without becoming a second copy of it.

**`runs:` says how a project's runs happen**, so nobody hunts for a config that was never written:

| | |
|---|---|
| `declarative` | studies are directories the engine runs — only experiment 04 today |
| `cli` | sweeps driven by flags (`./bench run --rungs 0-7`); a rung and a guardrail are capabilities the harness builds, not data |
| `code` | an architecture plus the evals that hold it to its promises |

## Studies: arms are patches, never layers

A study declares only its **delta**; the full semantic layer is generated at run time and written
into the run's results folder beside its numbers.

This is the most important rule here, and it was learnt the hard way. Study 01 was originally four
forked copies of the layer — 1,474 lines to express about forty lines of treatment. Nobody diffs a
370-line YAML, so one arm quietly acquired a synonym list matching the question wording, and that
confound survived the run, the review *and* the write-up. It is why that study's headline still
cannot be attributed. Generated layers cannot drift from their base, and a treatment you can read in
ten lines is a treatment someone will actually check.

```
04_semantic_layer_health/02_segment/
├── study.yml          what varies, against which base, at which rung — and the predictions
├── cases.yml          the questions and their gold
└── arms/
    ├── A_absent.yml   the fact is absent          (~10 lines)
    ├── B_prose.yml    the fact is stated in prose (an empty patch: the layer as it ships)
    └── C_segment.yml  the fact is declared        (~28 lines)
```

**Studies are discovered, not registered.** A directory holding `study.yml` is a study that runs, so
there is no index to keep in step with the filesystem — the failure mode of every index file ever
written.

## What the names mean

**The experiment number is a lab-notebook page.** Assigned when the work starts, never reused, never
renumbered; gaps are fine. The study number is the same idea one level down.

**The arm letter is a rung on the ladder,** and means the same thing in every study:

| | |
|---|---|
| `A_` | the fact is **absent** — nothing the agent can read states it |
| `B_` | the fact is stated in **prose**, where only a reader can use it |
| `C_` | the fact is **declared** — a named segment, machine-readable and selectable |

So "the C arm" names a kind of repair rather than a position in a list. A variant suffixes rather
than advances: `B_prose_swapped` is a control *on* B and stays a B.

## Four guards run before a token is spent

| | |
|---|---|
| same-numbers invariant | every arm must reach the base's numbers through its own declared equivalences — otherwise the arms differ in *capability* and the legibility question never arises |
| candidate-count guard | an arm offering fewer metrics than its rivals must say so out loud; deleting one of two confusable options is worth ~50 points before any treatment exists |
| vocabulary audit | the longest verbatim span each question shares with each arm's catalogue, printed every run — the check that would have caught study 01's confound before it was paid for |
| context expectation | the exact catalogue an arm renders must appear in what the model actually read |

## Where results go

`results/experiments/<timestamp>-<study>/` holds `run.json` (every row: tools called, grade, score)
and `layers/` (the exact generated YAML each number came from), so a stored result always names a
treatment you can reconstruct.

`results/probes/` holds twelve pre-migration runs of study 01, still readable with
`./bench context --run …`, still the evidence behind numbers in the write-ups — but nothing produces
new ones.

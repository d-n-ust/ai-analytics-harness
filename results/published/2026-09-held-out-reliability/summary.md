# Held-out reliability — the silent-error rate on fresh questions

The confident-wrong rate of the standard cell (`current_best`, `gpt-5-mini`, rung 3) measured on
**held-out** suites: questions authored blind, oracles proven before the file was written, each
suite run **once** at three reps. A held-out number is the honest one. A rate measured on a suite
the fixes were written against reports fit, not capability, so it is not published here.

Two suites back the headline, and both are committed so a reader can recompute every figure:

| suite | when | what it is |
|---|---|---|
| `heldout3` | the first held-out measurement | 46 questions, heldout2's exact tier distribution, fresh slices (months and segments heldout2 never used) |
| `heldout4` | after two guard generalisations (§78) | 46 questions, fresh slices again (October 2025, January 2026, Brazil/India/APAC), oracles cross-checked against the governed mart before authoring |

Each suite is 46 questions at 3 reps = 138 attempts. `heldout3` was never re-run after the guards
changed; `heldout4` is a second, different held-out suite, so the comparison below is a
same-protocol measurement, not a controlled A/B on identical questions.

## The number

| board | coverage | silent error | balanced accuracy | correct |
|---|---|---|---|---|
| heldout3 | 1.000 | **0.0362** (5/138) | 0.9647 | 124/138 |
| heldout4 | 0.9216 | **0.0145** (2/138) | 0.959 | 125/138 |

Silent error is the rate an operator loses sleep over: a number served confidently, wrong, in a way
nobody would notice. On fresh questions it is **1.4%**, down from 3.6%.

The three-pile breakdown (one answer / no answer / two-or-more answers), from `evals.matrix`:

```
heldout4
  question needed            correct   WRONG NUM   no figure     refused   clarified
  k = 1   one answer           47 ok           ·           ·           4           ·
  k = 0   no answer                7        2 !!           ·       36 ok           ·
  k >= 2  two answers        42 both           ·           ·           ·           ·
                         correct 125/138   silent wrong numbers 2
```

Pile A (answerable) 47/51 with **zero wrong numbers**; the contested pile 42/42 disclosed every
reading; the two silents are both `h4_b_habits_fell_june`.

## What moved the rate, with causal evidence

The drop is not only a rate. The two guards generalised in §78 fired on fresh held-out questions
and caught their target classes:

- **Mode 1 — the scope-match invariant** (`governed_scalar_binding`, `gates/measure.py`) fired on
  `h4_a_referral_signups_oct`, a channel-signup recount that would otherwise have been a silent.
- **Mode 2 — the unit-grounding extension** (`ungrounded_unit`, `gates/segments.py`) fired on
  `h4_b_opens_per_session`; both per-unit targets (opens per session, devices per account) refused
  every rep. The per-session / per-device substitution class is closed on unseen questions.

The entire remaining residual is one acknowledged mode: both silents are the false-"fell" premise
in `h4_b_habits_fell_june`, a stochastic single-judge recall miss (Mode 3), named in §78 as the
floor and deliberately not fixed against held-out data. None of the residual is Mode 1 or Mode 2.

## Honest caveats

- **Same-protocol, not an A/B.** `heldout4` is a different suite from `heldout3`, so it can be
  marginally easier or harder. What makes the causal claim solid beyond the rate is the direct
  firing above, on instances fresh data produced.
- **The `heldout3` oracle lesson is folded in.** `heldout3`'s first run scored 0.1014 — wrong,
  because the hand-SQL oracle used incomplete channel-spelling sets over a dimension the dbt mart
  normalises. Nine of the fourteen apparent silents were the oracle, not the agent. `heldout4`
  makes that error impossible by construction: every `_source` gold is asserted equal to its
  governed `wh_06` value before the question is authored.
- **Path to sub-0.01.** Closing Mode 3 (a second premise witness, or self-consistency on the
  direction read) and one more fresh suite would make a defensible sub-0.01 claim. The generator,
  prover and mart cross-check are committed, so `heldout5` is a re-run away.

## Provenance and how to regenerate

- **Cell:** `current_best` guardrail cell, `gpt-5-mini`, grounding rung 3, on the MetricFlow layer
  under the experiment's `layer/`. Three reps, one run each.
- **Suites and oracles:** `harness/experiments/06_third_state/fixture/heldout3.yml`,
  `heldout4.yml`; generators `_gen_heldout3.py`, `_gen_heldout4.py`; oracle provers
  `heldout3_prove.py` (and the mart cross-check the `heldout4` generator carries).
- **Findings:** §77 (`heldout3`), §78 (the two guard generalisations), §79 (`heldout4`) in
  `harness/experiments/06_third_state/findings.md`.
- **Raw rows:** `heldout3.raw.jsonl.gz`, `heldout4.raw.jsonl.gz` here — one scored attempt per
  line, 138 each.

Recompute the board from the committed rows:

```
PYTHONPATH=harness uv run python - <<'PY'
import json, gzip
from evals.selective import selective
for tag in ("heldout3", "heldout4"):
    rows = [json.loads(l) for l in gzip.open(f"results/published/2026-09-held-out-reliability/{tag}.raw.jsonl.gz", "rt")]
    print(tag, selective(rows).as_dict())
PY
```

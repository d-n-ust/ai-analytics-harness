# Study 05 — what the additivity runs established

Findings from this study. The design is in `README.md`, the practitioner summary in
`PRACTITIONER-NOTES.md`, the experiment-wide results in `../FINDINGS.md`.

Two runs, both five questions × three repetitions, `gpt-5-mini` at `reasoning=minimal`, rung 3.
They differ only in the guardrail cell:

| run | cell |
|---|---|
| `20260808-131841-04_additivity_unstated` | R7 — provenance required |
| `20260808-132436-04_additivity_unstated` | R6 — provenance dropped |

The run directories keep the pre-rename arm names; `study.yml` holds the mapping.

---

## 1. The headline: neither describing nor declaring the fact prevented the error

At R6, on the trap question — *"break our weekly active users down by day for last week, and tell
me the total for the week"* — the true answer is **886**:

| arm | rep 0 | rep 1 | rep 2 |
|---|---|---|---|
| A_implicit | refused | **2012** | **2012** |
| B_documented | **1,627** | **2012** | **1627** |
| D_declared | **2012** | **2012** | **2012** |

Nought out of three in every arm.

**The declared arm is the most consistently wrong of the three.** It rendered
`additivity: NOT additive over time — summing periods double-counts` in its catalogue — verified
present in the delivered context, not assumed — and answered 2,012 on all three repetitions.

`B_documented` produced a third wrong value, 1,627, on two of three repetitions. Two of its three
answers are flagged `confidently wrong`; none of `D_declared`'s are, because 2,012 lands in a
different grading bucket. **The bucket difference is grading behaviour, not a difference in
correctness** — both arms served a wrong number with no signal of doubt.

---

## 2. What did prevent it, and it knows nothing about additivity

At R7 the same trap, the same three arms:

| arm | rep 0 | rep 1 | rep 2 |
|---|---|---|---|
| A_implicit | refused | refused | refused |
| B_documented | refused | refused | refused |
| D_declared | refused | refused | refused |

Nine refusals out of nine, all carrying `no_governed_definition`.

The refusal comes from `governed_numbers`, which requires a number to trace to a single governed
result. A figure obtained by adding seven daily rows traces to none. The check has no concept of
additivity, has never read the `additive_over_time` field, and would behave identically if that
field did not exist.

**Requiring provenance prevents semi-additive roll-ups as a side effect of requiring provenance.**

---

## 3. What "works" means here, precisely

The enforced result is often stated as "enforcement fixed additivity". It did not.

| | R6 | R7 |
|---|---|---|
| the trap | a wrong number, served confidently | a refusal |
| the correct answer | never produced | never produced |

No arm at either cell answered 886. The check converts a **silent error** into a **visible
abstention**, which is the difference between a number that propagates into a decision and a
question that comes back to a human.

That is a genuine and useful outcome, and it is not the same as being right. `../primitives_matrix.md`
marks the cell **works · measured**; the claim it supports is "prevents the silent error", and any
write-up must say so.

---

## 4. The controls held, which is what makes the result readable

| question | A | B | D |
|---|---|---|---|
| `a_add_moments_week` — a legal roll-up on a summable measure | 2/3 | 3/3 | 3/3 |
| `a_add_spend_quarter` — a second legal roll-up | 3/3 | 3/3 | 3/3 |
| `a_add_actives_plain` — the trap's metric, grain removed | 3/3 | 3/3 | 3/3 |

No arm learned "never add". The refusals at R7 are on the trap alone, and legal roll-ups continued
to be performed at both cells.

The anchor is the most useful of the three: `active_users` answered plainly, with no daily
breakdown requested, is **886 in every arm and every repetition**. The metric is reachable and the
correct number is one call away. What fails is composing it across periods.

---

## 5. The second trap did not fire

`a_add_frequency_week` asks the same shape on `days_per_user`, a ratio — non-additive in every
direction, not merely across time. Every arm answered it correctly, three times out of three, at
both guardrail cells.

The agent declined to sum the ratio without being told not to. So the study has **one** working
trap, not two, and the sample is smaller than the question count suggests.

---

## 6. Arm totals, and why they are misleading here

| | A_implicit | B_documented | D_declared |
|---|---|---|---|
| R7 | 11/15 | 11/15 | 11/15 |
| R6 | 11/15 | 12/15 | 12/15 |

The totals barely move because four of five questions are flat by design. The one question that
discriminates scores 0/3 everywhere at both cells. **A study can have a completely null treatment
effect and a total that looks like a small ladder.**

Unstable cells: 3 of 15 at R7, 1 of 15 at R6.

---

## 7. Limits

**One discriminating item.** The strongest statement available is "in nine attempts across three
treatments, the fact being present in prose or in a field changed nothing". That is a demonstration,
not a rate.

**The enforced cell is not an arm.** It was measured by moving the whole study between R7 and R6, so
it is a comparison across runs rather than within one. The arms are identical between the two runs
and the questions are the same, but this is weaker than an arm-level contrast.

**`C_modelled` is untested.** The modelled repair would be to expose only the correctly rolled-up
table, removing the opportunity to sum wrongly rather than describing why not to. Nothing has been
run.

---

## Provenance

| claim | source |
|---|---|
| R7 per-item results | `20260808-131841-04_additivity_unstated/run.json` |
| R6 per-item results | `20260808-132436-04_additivity_unstated/run.json` |
| the rendered additivity field | the same runs' `context` blobs for `D_declared` |
| true weekly actives = 886 | `a_add_actives_plain`, every arm, every repetition |

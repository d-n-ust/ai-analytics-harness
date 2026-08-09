# Study 00 — what the catalogue-format runs established

The control study. It fills no cell of `../primitives_matrix.md`: its arms carry byte-identical
facts in three arrangements, so it varies presentation rather than an intervention. The design is in
`README.md`, the practitioner summary in `PRACTITIONER-NOTES.md`.

Numbers are from `results/experiments/04_semantic_layer_health/20260807-183018-03_catalogue_format` —
five questions, three repetitions, `gpt-5-mini` at `reasoning=minimal`, rung 3, R7 — measured
against `20260807-180538` where marked.

---

## 1. The result is a null, and the null is the point

| arm | correct | unstable cells |
|---|---|---|
| A_prose | 14/15 | 1 |
| B_structured (JSON) | 14/15 | 0 |
| C_table (markdown) | 15/15 | 0 |

One point of spread, on a test whose measured run-to-run variation is wider than that.

| question | A_prose | B_structured | C_table |
|---|---|---|---|
| signups in Germany | 3/3 | 2/3 | 3/3 |
| active users in Germany | 2/3 | 3/3 | 3/3 |
| completed habits in Germany | 3/3 | 3/3 | 3/3 |
| marketing spend in EMEA | 3/3 | 3/3 | 3/3 |
| paid search spend | 3/3 | 3/3 | 3/3 |

No question separates the arms. The two imperfect cells are in different arms on different
questions, which is what noise looks like.

**Every other study in this experiment holds the rendering fixed.** This one checked that holding it
fixed is not itself a choice with consequences. A null here makes every other finding more robust,
which is why it was worth paying for.

---

## 2. The only measurable difference is cost

| format | tokens | relative |
|---|---|---|
| markdown table | 1,028 | 1.00 |
| prose | 1,204 | 1.17 |
| JSON | 2,209 | **2.15** |

JSON costs roughly twice a table to convey the same facts. If a catalogue is sent on every request,
that is a real bill against no measured benefit.

---

## 3. Building the control was harder than running it, and that is the useful part

**The first version had four accidental differences between arms.** They were not format
differences; they were content differences that the format change had smuggled in.

| confound | effect |
|---|---|
| only the JSON arm advertised a `segment` option, at the top | that arm applied an unrequested segment and answered **227** where the correct value is **283** |
| prose wrote `supports filter is_internal=false` — handing over a value the others withheld | a second content difference |
| `—` for an absent field in some arms, silence in others | absence rendered as information |
| `filterable` was never rendered in any arm | the catalogue advertised fewer filters than the query tool accepted |

The arms scored 5, 4 and 1 out of 5, and none of it was about format.

**The fix was structural rather than a set of patches.** The renderers were rewritten so content is
one decision and arrangement is another: a shared field list, a shared cell type, and a word-parity
test asserting that the three renderings contain the same word set once labels are stripped.

---

## 4. Word parity is not enough, and finding that out cost a result

The refactor silently dropped the time-grain vocabulary — `day`, `week`, `month` — from **all three**
formats while `query_metric` still accepted the argument.

Word parity could not see it, because parity compares the arms **to each other** and all three had
lost it equally. The first schema-parity test written to catch it also passed, on a substring
coincidence: the word "week" occurs inside "last_week".

Restoring the vocabulary changed the study measurably:

| | prose | JSON | table | cells disagreeing with themselves |
|---|---|---|---|---|
| grain missing | 14/15 | 13/15 | 12/15 | 5 of 15 |
| grain restored | 14/15 | 14/15 | 15/15 | 2 of 15 |

The refusal wording steadied as well: one arm had given three different reasons for the same refusal
across three runs, and afterwards gave one.

**The check that catches this class of defect** compares the catalogue against the argument space
the query tool actually accepts, read from the tool's own schema rather than from a hand-written
list. If the tool takes `time_grain`, the catalogue must list its valid values. These drift apart
silently, and the agent has no way to notice.

---

## 5. Limits

**One model.** Published work shows format sensitivity varies greatly between models and falls as
models improve. A smaller or older model may well be more format-sensitive.

**One catalogue size.** Ours is 1,200 to 2,200 tokens. Position and context-length effects are
documented at much larger sizes and none of them apply here.

**One question shape.** Counts and lookups.

**A null at n=5 means "not detected".** It does not mean "no difference exists".

---

## Provenance

| claim | source |
|---|---|
| per-arm and per-item figures | `20260807-183018-03_catalogue_format/run.json` |
| the grain-restoration comparison | `20260807-180538` against `20260807-183018` |
| the 227-versus-283 confound | an earlier run, before the renderer rewrite |
| token counts | `o200k_base` over the current renderings |

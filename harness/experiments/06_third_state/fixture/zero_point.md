# The zero point — the name picks the metric, and the description is never consulted

One question, rung 3, both `query_metric` and `run_sql` available.

> How many active users did we have last week?
> Two governed definitions answer it: excluding internal and test accounts = **886**, including
> them = **919**. Different owners, different consumers, 3.72% apart.

## 1 · Three action spaces. No difference.

| arm | what the agent has | attempts | clarified | **served one reading silently** |
|---|---|---:|---:|---:|
| `R3-clarify` | no way to report ambiguity | 3 | 0 | **3** |
| `R3` | a prose clarify tool | 3 | 0 | **3** |
| `R3+typed_clarify` | a coded tool, plus the rule in the prompt | 19 | 0 | **19** |
| loop default | a prose clarify tool | 10 | 0 | **10** |

Both models. Never once asked.

## 2 · Rename the pair and the served number changes

Four presentations of the same two definitions. The measures, filters, values, owners and
consumers are byte-identical across all four; only the labels and their order move.

| variant | the 886 reading is called | the 919 reading is called | attempts | **served** |
|---|---|---|---:|---|
| `baseline` | `active_users` | `active_accounts` | 8 | **886** |
| `no_exact_match` | `active_customers` | `active_accounts` | 8 | **886** |
| `reversed` | `active_users` *(declared second)* | `active_accounts` *(first)* | 8 | **886** |
| **`crossed`** | **`real_customers`** | **`active_customers`** | **16** | **919** |

Sixteen attempts on the crossed layer, `gpt-5-mini` and `gpt-5.6-terra`, and every one served 919.

**The word "active" moved from one definition to the other, and the answer moved with it.** Nothing
else changed. The description on the metric it chose reads, in full:

> Distinct accounts with any product activity in the period, **INCLUDING internal and test
> accounts**. Owned by Platform. Used by capacity planning and the support-volume forecast, both of
> which care about load rather than about customers.

Asked how many active *users* a consumer product had, it served a count that includes staff and
test logins, from a metric whose own description says it is about load rather than customers,
because the metric was called `active_customers`.

**This corrects the earlier reading of the first three variants.** Those three all left the
question's wording and the sensible meaning on the *same* metric, so they could not separate the
two. `crossed` puts them in opposition, and the wording wins.

The residual question is narrow: whether the rule is "match the question's head noun" or "avoid a
`real_` prefix". Both are lexical. Either way it is the label and not the definition.

## 3 · Put the two descriptions on adjacent lines. Still no difference.

The remaining explanation was layout: in the rendered catalogue each metric is followed by four
lines of dimension and grain machinery, so one description sits five lines from the next. A model
might never hold both at once.

`MetricFlowLayer.catalogue = "compact"` reorders the same facts — every name and description
contiguous first, the machinery in a second block below. Nothing is added and nothing is dropped;
all 25 dimension and grain lines are still present, verified line by line.

| layer | catalogue | descriptions apart | attempts | clarified | served |
|---|---|---:|---:|---:|---|
| `baseline` | full | 5 lines | 8 | 0 | 886 |
| `baseline` | **compact** | **1 line** | 16 | 0 | 886 |
| `crossed` | full | 5 lines | 16 | 0 | 919 |
| `crossed` | **compact** | **1 line** | 16 | 0 | 919 |

Both models, in every cell. Adjacency changes nothing: with the two descriptions on consecutive
lines, one saying EXCLUDING and the next saying INCLUDING internal and test accounts, it still
takes the one whose name matches the question.

## 4 · The description is available. It is just not consulted when answering.

Same model, same layer, same tools, same guardrails. Only the task changes.

> *Which governed metrics in this layer could each answer "how many active users did we have last
> week?", and what differs between them?*

```text
outcome    : clarify
candidates : ('real_customers', 'active_customers')
question   : do you mean active users excluding internal/test accounts (real customers), or all
             accounts including internal/test accounts?
```

It names both. It states the discriminator exactly. It reaches the typed tool and fills it in. The
same behaviour appears on the baseline layer with the original names.

So both things are true at once, and together they are worse than either alone:

- **asked to compare** — it reads the descriptions and gets it right
- **asked to answer** — it matches on the label and reads past the description

The knowledge is there. The answering path does not use it.

## 5 · The first live clarifications, and what the payload bought

Two checks ran on them that need no gold answer and no second model:

| check | result |
|---|---|
| every named candidate exists in the catalogue | **pass**, on both layers |
| the candidates diverge on the slice asked about | **pass** — 886 against 919, 3.72%. Worth asking |

And two content errors that typing made visible and prose would have hidden:

**The reason code is wrong, both times.** Filed as `underspecified_request` — "the question left
something out" — where the truth is `competing_definitions`: two governed definitions answer it.
Gradeable and countable now; invisible before. Same failure `outcomes.py` records for the refusal
enum, where the model named a code other than the expected one 49% of the time.

**One of the two questions was phrased in the layer's terms**, naming metric identifiers rather
than asking what differs, which is the one thing the field description tells it not to do. No
deterministic check sees that. It is the residue an LLM judge is for, once there is enough of it to
validate a judge against hand labels.

## 6 · The enforced gate — what advisory could not do

`ambiguity_check`, at `BEFORE`: every governed call is looked up in the index beside the layer, and
one that names a contested metric is refused before it runs.

| arm | attempts | clarified | silent error |
|---|---|---:|---:|
| everything advisory — typed tool, named candidates, the rule in the prompt, four namings, two layouts | 107 | **0** | 1.00 |
| `+ambiguity_check` | 18 | **18** | **0.00** |

Both layers, both namings. This is the R3-over-R6 pattern reproduced exactly: the advisory versions
of this idea moved nothing across 107 attempts, and the enforced one moved everything.

**The block hands over the decision brief rather than pointing at it**, which is what the earlier
measurements decided. The agent selects by name and does not read descriptions on the answering
path, so a block saying "this is ambiguous, go and ask" would have sent it to look up something it
has already proven it will not read:

```text
BLOCKED — 'active_users' is not the only governed definition of what it measures:
'active_accounts' answers the same question and returns a different number for this exact
request (886 against 919, 3.72% apart). They differ by is_internal = false. Do not pick one
and do not average them. End with `clarify`, naming both in `candidates`, and ask the user
about is_internal = false in their own words.
```

**The reason code is now right.** Both of the earlier voluntary clarifications filed
`underspecified_request`; every gated one files `competing_definitions`. Naming the collision in the
block fixed the classification too.

### Sensitivity, not membership

The gate fires on whether the reader would receive a **different number for this call**, not on
whether the metric has a competitor. It executes each competitor with the same arguments and
compares.

| the call | verdict |
|---|---|
| `active_users`, last week | **BLOCKED** — 886 against 919, 3.72% apart |
| `active_users`, `platform = web` | **BLOCKED** — 277 against 289, 4.33% apart |
| `active_users`, `platform = unknown` | **allowed** — both readings return the same number |
| `value_moments`, last week | allowed — no competitor |

That distinction is the difference between a gate that is shippable and one that is not: membership
alone would have fired on 40.3% of the metric-declaring answers in the frozen suite, most of them
diagnostics, which is the brief's own falsification condition.

**The threshold is zero, and the zero is argued.** The instinct is to ignore small divergences, and
it is backwards here: danger runs inverse to magnitude, because a figure a few tenths of a percent
from its sibling is the one no reader and no range check will ever catch. "Does not matter" means
*identical*, not *close*. A non-zero threshold is a lever worth measuring — the brief's own
"divergence threshold" — but it is not a default.

## 7 · What this predicts about the levers

| lever | prediction | basis |
|---|---|---|
| better prompting | **won't work** | measured: 0 of 19 with the rule stated in the prompt |
| better naming | **changes which silent error you get, not whether you get one** | measured: renaming flipped the served number and produced zero clarifications |
| better catalogue layout | **won't work** | measured: putting the two descriptions on adjacent lines changed nothing, 32 attempts |
| a lookup that fires whether or not the model asks | **confirmed: 18 of 18** | built and measured — see §6 |
| answer with both, disclosed | still worth testing, but the case for it is weaker | it rested on the pick being reliably sensible, and `crossed` shows the pick follows the label |

The second row is the practitioner finding and it cuts against standard advice. "Give your metrics
clearer names" is what every governance guide says, and on this evidence it does not stop an agent
choosing silently — it only changes which definition it silently chooses. A name is what the agent
matches on; the description, the owner and the consumer are what it ignores.

## Reproduce

```bash
uv sync --group metricflow
cd harness/experiments/06_third_state/fixture
python variants.py --write
for v in baseline no_exact_match reversed crossed; do
  PYTHONPATH=. python run.py --model gpt-5-mini --reps 8 --cell R3+typed_clarify --variant "$v"
done
```

Rows: `arm__*.json`, `typed__*.json`, `var__*.json`, `crossed__*.json`, `zero_point__*.json`.

## What this is not

**107 attempts asking the question: 0 clarifications. 2 attempts asking it to compare: 2
clarifications.**

Stable across two models, three action spaces, four namings and two catalogue layouts. Nothing
about how the ambiguity is *presented* changed the outcome; the only manipulation that ever did was
changing the task from "answer this" to "compare these".

One question on one fixture, so this is no rate, and the noise band it would be read against does
not exist yet. But every presentation-side explanation has now been tested and none survived, which
leaves one route: a lookup that runs whether or not the model thought to ask.

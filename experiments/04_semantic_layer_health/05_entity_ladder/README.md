# Does an AI analyst need a semantic layer, or just better tables?

The first row of the primitives matrix, and the first study where the arms are whole warehouses
rather than variations on one catalogue.

## The problem, in one table

`evt` has 193,407 rows and a column called `etype`. Nobody wrote down what the integer means.

| etype | what it is | rows |
|---|---|---|
| 1 | app opens | 111,056 |
| 2 | **completed habits** | 67,132 |
| 3 | reminders shown | 15,219 |

Ask *"how many habits did people complete last week?"* and an agent can query the table it was
given, write correct SQL, and return **10,741** against a true 3,785. It does not refuse and it
does not hedge. A wrong number is just a number, and nothing downstream can catch it.

The other three traps are the same shape: `subs.st` is a status code where only 1 is live,
`hab.arch` is a date whose NULL means "still tracked", and `evt` has to be filtered twice for two
different questions so a single lucky guess cannot carry the set.

## The four arms are the matrix's four interventions

They are named for the columns of `../primitives_matrix.md` rather than for this study's
warehouse, because the same five interventions recur for every primitive — grain, additivity, join
path — and shared names make the rows comparable.

## Four real budgets

Every team with a warehouse like this has the same options, and they differ by an order of
magnitude in cost.

| arm | what it gets | cost |
|---|---|---|
| `A_implicit` | nothing — cryptic names, coded columns, no descriptions | — |
| `B_documented` | the same tables, with `COMMENT ON` | an afternoon |
| `C_modelled` | a conformed star; `evt` already split into `fct_value_moments` | days |
| `D_declared` | the same star, plus a governed metric layer | a project |

Each arm's declaration says exactly what it is:

```yaml
# B_documented
environment:
  tables: messy_tables      # warehouse/presets/messy_tables.sql
  docs:   messy_tables      # warehouse/docs/messy_tables.sql — COMMENT ON statements
```

Both names are files you can open. Nothing is implied by a rung number.

## Each arm gets its own warehouse, enforced

An arm is a DuckDB schema holding exactly the objects it may see, and a cursor whose `search_path`
is that schema. This is checked, not asserted:

```
A_implicit   evt → 193,407    dim_users → BLOCKED    _star.dim_users → BLOCKED
C_modelled   evt → BLOCKED     dim_users → 2,500      _star.dim_users → BLOCKED
```

Two mechanisms, and both are needed. `search_path` hides the other schemas; a check in `run_sql`
refuses a statement that *names* one, read from DuckDB's parse tree rather than the query text.
Without the second, an arm could reach another arm's tables — and that would not crash, it would
return a plausible number computed from the wrong warehouse.

Teardown is one `DROP SCHEMA … CASCADE`, so nothing leaks into the next arm.

## Documentation is the database's own

`B_documented` uses `COMMENT ON`, which is what Snowflake, BigQuery, Postgres and Databricks all
expose and what dbt's `description:` compiles to. The agent reads it back out of the catalog. That
matters for the standing objection to this whole programme — *you measured your own file format* —
because here the artefact is the real one.

Column comments are the sharper intervention:

```sql
COMMENT ON COLUMN evt.etype IS 'Event kind, as an integer code: 1 = app open,
  2 = COMPLETED HABIT (a value moment), 3 = reminder shown…';
```

That is one line, attached to the column that causes the error. The agent sees 542 characters
undocumented and 1,903 documented.

## Results: a pilot, and not readable yet

Three reps, five questions, four arms.

| arm | correct | confidently wrong |
|---|---|---|
| A_implicit | 11/15 | 4 |
| B_documented | 11/15 | 3 |
| C_modelled | 12/15 | 1 |
| D_declared | 12/15 | 2 |

**Five of twenty cells disagree with themselves across identical repetitions.** The spread is one
point. Nothing here separates, and no ranking should be quoted.

An earlier run of this study read 9 / 13 / 11 / 12 and looked like a story about documentation
closing most of the gap. It was one draw of a noisy sample, and it is retracted rather than
explained. See `../FINDINGS.md` for the measured 13% noise floor and what it takes to beat it.

## Two items were rewritten before the run could be read

**"How many real users do we have?"** has no metric at rung 3 — `active_users` counts users with
activity (2,100), `new_signups` includes staff (2,500), the truth is 2,414. `D_declared` answered
2,100 using the right metric for what it means and was graded wrong. That measured **coverage**,
not entity resolution.

**"How many referrals converted?"** reads three ways — joined (271), activated (266), or both
(537) — and the first two land inside each other's tolerance, so the ambiguity graded as agreement.
What it actually measured was missing vocabulary: nobody had written down that "converted" means
`status = activated`.

Both cost a paid run to notice. The rules that would have caught them are now in
`.claude/experts/harness-eval-items.md`.

## The observation worth following

Asked *"how many habits are people still tracking?"* — an entity nobody modelled — `D_declared`
answered **"886 active users"**, then refused, then **"704 active users"**. It never queried the
habits table, though `dim_habits` was in its schema and `run_sql` was in its toolbox.

The catalogue pulled it toward what the catalogue stocks. Habits became users. The removed
real-users item did the same thing, which makes two independent items showing it.

This is anchoring to the inventory, and it is named in the NL-to-SQL literature. It is a direction
with a mechanism, not a rate: 3/3 on one question plus one corroborating item, in one study. It
deserves its own study rather than being a by-product of two questions that had to be removed.

## Running it

```bash
./bench study 05_entity_ladder --describe                  # the arms and what each declares
./bench study 05_entity_ladder --mock --reps 1             # guards only, no cost
./bench study 05_entity_ladder --reps 3 --concurrency 8    # 60 runs, ~70s, about 15 cents
```

Read the fingerprint block first. Two arms hashing the same means the treatment never reached the
model — it has caught that twice in this study alone.

## What is missing

**Items.** Three clean entity traps and one control cannot separate four arms. Twenty of this shape
would, and the design is proven to discriminate.

**Column E of the matrix.** "Enforced" — a check that refuses when the entity used does not match
the entity asked for — is the R6 spec check, which presupposes an entity ontology. For this
primitive it sits on top of `D_declared` rather than beside it, so this study has four arms where
the matrix implies five.

# What kinds of clarification exist — the published taxonomies, and what they imply for this harness

Research pass to support making `clarify` a first-class outcome. Every source below was fetched and
read, except where marked *listing only*, which means it appeared in a search result and the claim
comes from that summary rather than from the paper.

---

## 1. The published taxonomies, side by side

Six independent lines of work have each built a taxonomy. They were built for different systems and
they converge on a small set of dimensions.

### 1.1 Dialogue theory — by level of communication breakdown

Schlangen (SIGdial 2004), formalising Clark (1996) and Allwood (1995). The four basic levels of
communication, with the clarification request each one produces:

| level | Clark's name | what failed | clarification |
|---|---|---|---|
| 4 | proposal & consideration | uptake — what you want me to do with it | "Are you trying to threaten me?" |
| 3 | meaning & understanding | what the words denote here | "Which Peter?" |
| 2 | presentation & identification | perception of the signal | "What did you say?" |
| 1 | execution & attention | contact | "Are you talking to me?" |

Level 3 is then split further (Schlangen, after Larsson 2003):

- **semantic meaning** — discourse-independent meaning, e.g. word meanings
- **pragmatic meaning**
  - *referential* — referents of pronouns, temporal expressions
  - *pragmatic proper* — the relevance of the utterance in this context

The paper also names two dimensions orthogonal to level:

- **severity** — a request for *repetition* is more severe than a request for *confirmation*
- **extent** — whether the request points at a specific problematic element or at the whole utterance

**The methodological point worth stealing.** Schlangen's argument against the earlier form-based
classification (Ginzburg & Cooper) is that it "does not explicitly record the problem that leads to
the need for clarification. This leads to a loss of information." A taxonomy keyed to the *shape* of
the question asked cannot be acted on. One keyed to the *cause* can.

### 1.2 Web search — by what the searcher left out

Zamani et al., *Generating Clarifying Questions for Information Retrieval*, WWW 2020. Derived from
"thousands of query reformulations sampled from the Bing query logs".

| type | definition | example |
|---|---|---|
| **Disambiguation** | the query could refer to different concepts or entities | "trec" — Text Retrieval Conference or Texas Real Estate Commission |
| **Preference** | not ambiguous, but a more precise need can be identified | |
| · personal ("for whom") | gender, age, language, expertise | "sneakers" → "for women", "for kids" |
| · spatial ("where") | | apartment → which neighbourhood |
| · temporal ("when") | | "wsdm" → wsdm 2019 or wsdm 2020 |
| · purpose ("for what purpose") | | "apartment" → renting or buying |
| **Topic** | the topic is too broad; sub-topic, or event/news framing | |
| **Comparison** | comparing this entity against another | console → "compare xbox with play station" |

Also the industry evidence that clarification pays: an online experiment on Bing, one week, 2.5M
users per treatment, reported **48.57% relative click-through improvement** for a clarification pane
over a static title with the same candidate answers.

### 1.3 Open-domain QA — by what the answer depends on

Min et al., *AmbigQA*, EMNLP 2020. Hand-coded breakdown of 100 sampled ambiguous questions; an item
may fall in more than one category.

| type | share | example |
|---|---|---|
| event references | 39% | "what season did Meredith and Derek get married" — informal (S5) or legal (S7) |
| properties | 27% | "how many episodes in season 2" — with or without the OVA |
| entity references | 23% | two different people named Clay Matthews |
| answer types | 16% | "who sings X" — the band or the lead vocalist |
| time-dependency | 13% | "when does the new season come out" — which season |
| multiple sub-questions | 3% | |

### 1.4 LLM assistants — by where the ambiguity originates

Zhang et al., *CLAMBER*, 2024 (arXiv 2405.12063). Three dimensions, eight categories, ~12K items.

| dimension | category | explanation |
|---|---|---|
| **Epistemic misalignment** | unfamiliar | query names entities or facts the model does not know |
| | contradiction | query contains self-contradictions |
| **Linguistic ambiguity** | lexical | terms with multiple meanings |
| | semantic | lacks context, so multiple interpretations |
| **Aleatoric output** | who / when / where / what | output confusion from missing personal / temporal / spatial / task-specific elements |

Their headline finding: LLMs "fail to ask high-quality clarifying questions, due to the inability of
knowing their knowledge gap", and chain-of-thought plus few-shot prompting *worsens* ambiguity
identification in small models by increasing overconfidence.

The `epistemic misalignment` dimension has no analogue in a harness where the model never invents a
figure and every number comes from a governed call. That is a design property of this repo, not a
gap in the taxonomy.

### 1.5 Text-to-SQL — by which part of the query is underdetermined

Three benchmarks, increasingly close to our problem.

**AmbiQT** (Bhaskar et al., EMNLP 2023): column ambiguity, table ambiguity, join ambiguity,
precomputed aggregates. Lexical (synonymous names) and structural (join paths, pre-aggregated
columns).

**AMBROSIA** (Saparina & Lapata, NeurIPS 2024): scope ambiguity, attachment ambiguity, vagueness.
Note that "scope" here is the *linguistic* sense — quantifier scope, collective versus distributive
readings of "each" and "every" — not the analytics sense of a time window or segment.

**PRACTIQ** (Dong, Ashok Kumar et al., AWS + UMass, arXiv 2410.11076, v2 Jan 2026): the closest
prior art to the three-pile design, because it splits questions into **answerable / ambiguous /
unanswerable** and generates conversations for each. 2,800 conversations.

| ambiguous category | definition |
|---|---|
| ambiguous SELECT column | multiple valid SQLs differing in the SELECT columns ("maximum capacity" → standing or seating) |
| ambiguous values within column | maps to multiple different values in one column ("the Chemistry teacher" → Organic or Physical) |
| ambiguous WHERE columns | the same value appears in multiple columns |
| ambiguous filter criteria | a term whose mapping to values needs a definition ("underage" — under what age?) |

| unanswerable category | definition |
|---|---|
| nonexistent SELECT column | the column asked for is not in the schema |
| nonexistent WHERE column | the filter column is not in the schema |
| nonexistent filter value | the value asked for is not present |
| unsupported join | the tables cannot be joined |

### 1.6 The formal definition, and why it matters here

AMBROSIA states it precisely:

> **Definition 1.** Two SQL queries are **non-equivalent** if they produce different execution
> results, notwithstanding variations in layout or format.
>
> **Definition 2.** Let Q = {q₁ … q_N} denote the universe of non-equivalent SQL queries that can be
> formulated given a database D … Question s is **ambiguous** if f(s) has a cardinality of at least
> two.

That is the brief's `k`, published and peer-reviewed. Two consequences.

**First, our k is a restriction of theirs.** AMBROSIA's Q is every non-equivalent SQL over the
database, which is unbounded and not decidable in practice. Ours is every *governed* grounding for
the concept, which is a finite set the layer declares. Restricting the universe to the governed set
is what makes k computable, and it is the contribution — not the definition itself.

**Second, they exclude exactly what we include.** AMBROSIA: "This definition excludes ambiguities
emanating from data management issues (e.g., relating to formatting, coverage, or the handling of
`NULL` values), and assumes that the database schema and values are known." Coverage windows and
internal-account filters are the harness's central case and are ruled out of scope there by
construction. So is output underspecification: "we also do not consider underspecification of the
output format".

---

## 2. What the field has measured about agent behaviour

These are the numbers a write-up has to position against.

| finding | source |
|---|---|
| Models identify ambiguity at **60–80% accuracy** when asked to judge it, but ask a clarifying question **under 5% of the time, often under 1%**. Supplying retrieved passages raised QA accuracy 8–12 points and *reduced* clarification further. | *Knowing but Not Showing*, arXiv 2605.25284 |
| Frontier data-science agents **silently commit to a wrong task framing on 39–63% of ambiguous tasks and flag the ambiguity in none of them.** Permissive prompting flips this into over-asking: 88% style-preference questions on fully specified tasks. | *Ambig-DS*, arXiv 2605.09698 |
| Best model recall on ambiguous questions **31%**, against 66% on unambiguous ones. | AMBROSIA |
| In CoSQL, only about **18%** of unanswerable questions produce a request for user clarification. | PRACTIQ, §2.1 |
| A clarification pane beat a static title by **48.57% relative CTR** on 2.5M Bing users. | Zamani et al., WWW 2020 |

Two of these predict what the archive already shows. `gpt-5.6-terra` produced zero clarifications in
342 published attempts, and the clarification rate does not rise as the grounding rungs supply more
context. That is the *Knowing but Not Showing* result reproduced on a different task, and it means
"the model does not use the tool" is an expected outcome rather than a broken configuration.

---

## 3. The theory for deciding *whether* to ask

Two literatures give the cost matrix a name.

**Expected regret.** Tsvilodub, Mulligan, Snider, Hawkins & Franke, *Act or Clarify? Modeling
Sensitivity to Uncertainty and Cost in Communication* (arXiv 2602.02843, May 2026). They formalise
the choice as expected regret, equivalently the expected value of perfect information (Raiffa &
Schlaifer 1961): how much an agent stands to lose by acting now rather than with full information.
Two predictions, and the interaction is the point: clarifying questions should be more likely when
uncertainty about decision-relevant features is high, *and* when available actions have high
expected payoff — "uncertainty should matter most when acting incorrectly is costly". Two
experiments support the interaction in humans.

This is precisely the divergence-weighted argument. A 0.6% divergence carries little regret; a 5.9%
divergence carries more. The brief's divergence threshold is expected regret with a cut-off, and it
should be named as such.

**Learning to defer.** Madras et al. (2018), Mozannar & Sontag (2020). The reject option becomes an
extra label in an augmented label space, with the cost of deferral as an explicit parameter, and the
system learns a classifier and a rejector jointly. This is the formal home for a third action with
its own cost, and it is the correct citation for extending Chow's reject option, which
`selective.py` currently cites and which is strictly two-action.

---

## 4. The third response nobody in our design has considered

The survey *Disambiguation in Conversational Question Answering in the Era of LLMs and Agents*
(arXiv 2505.12543) names three disambiguation strategies, not one:

| strategy | what it does | covers |
|---|---|---|
| **Query rewriting** | rewrite the ambiguous query into a well-defined one, then answer | syntactic, semantic, contextual |
| **Long-form answer generation** | present every valid interpretation with its answer | semantic, contextual |
| **Asking a clarifying question** | prompt the user to confirm or supply | semantic, contextual |

PRACTIQ builds both kinds of conversation deliberately: some ambiguous questions get a clarification
request, and for others they "directly generate helpful SQL responses, that consider multiple
aspects of ambiguity, instead of requesting user clarification".

**This matters for the 3×3 matrix.** The brief assumes clarification is *the* correct behaviour at
k ≥ 2. It is one of three, and in analytics the second is unusually attractive:

> "12,145 value moments, counting every account. Excluding internal and test accounts it is 11,652.
> The governed North Star uses the second."

That answer is not silent, costs no round trip, and is more useful than a question. It is cheaper
than clarifying by exactly one turn, and the cost table in §2.4 of the brief would show it. If it
holds up, "answer with both, labelled" beating "ask which one you meant" is a stronger practical
finding than the ladder, and it is testable in the same run — it is a fourth column in the matrix,
not a different experiment.

The case where it fails is where the two candidates cannot both be served: a breakdown, a chart, a
downstream decision that needs one number. That boundary is worth locating rather than assuming.

---

## 5. Testing the four proposed categories against all of this

The brain dump was: **intent · scope/entity/temporal/grain/segment · semantic (which definition) ·
grounding (which source of truth)**.

### 5.1 Three of the four are one published model

| proposed | Clark/Schlangen level | also appears as |
|---|---|---|
| intent | level 4 — proposal & consideration (uptake) | Zamani *Topic* and *purpose*; CLAMBER *aleatoric/what*; Ambig-DS *evaluation objective* |
| scope / entity / temporal / grain / segment | level 3, *referential* — "referents of pronouns, temporal expressions" | Zamani *Preference* (who/where/when); CLAMBER *aleatoric* (who/when/where); AmbigQA *entity references*, *time-dependency*; PRACTIQ *ambiguous values within column* |
| semantic — which definition | level 3, *semantic meaning* — "discourse-independent meaning, e.g. word meanings" | Zamani *Disambiguation*; CLAMBER *lexical*; AmbiQT *column/table synonyms*; PRACTIQ *ambiguous filter criteria* |

Levels 1 and 2 — contact and perception — do not exist for a text agent over a warehouse. So the
four levels collapse to three usable ones, and the proposed list has all three, in the right order.
That is a good sign: the instinct reproduced a model from 1996 without reaching for it.

### 5.2 The fourth has no home in that model, and that is the contribution

*Grounding — which evidence or source of truth should govern* — is not a level of the
speaker-hearer channel at all. Clark's model is about the signal between two people. This is about
the channel between the **question and the data**: which of several authorities the answer should
rest on.

No taxonomy in §1 has it, and the reason is structural. Every one of those systems has a bare
schema. None of them has a governed semantic layer, so none of them can have the failure where two
*documented, owned, sanctioned* definitions both correctly answer one question. PRACTIQ's
"ambiguous SELECT column" is the nearest, and it is still two raw columns, not two governed metrics
with different owners and different downstream consumers.

Industry asserts this problem constantly and measures it nowhere. The 2026 vendor material states it
plainly — several versions of revenue, one per team, and an agent "can pull a perfectly real
definition of revenue and still pick the wrong one, because nothing told it which definition the
business stands behind" — but there is no benchmark, no rate, and no cost attached to it anywhere I
could find.

### 5.3 Two categories the four are missing

**Comparison baseline.** Zamani has *Comparison* as a top-level type straight out of query logs, and
in analytics it is everywhere: "is engagement up?" — against last week, last year, the plan, the
same cohort last quarter? This is not scope. Scope narrows one set; a comparison needs a *second*
operand that the question never supplied. It has its own fix (declare a default baseline per metric)
and its own failure mode (a real number against an arbitrary baseline, which is silent).

**Output shape.** Ambig-DS calls it *evaluation objective*; AMBROSIA explicitly excludes it. "Show
me revenue" — a single number, a trend, a breakdown, or the driver of a change? The harness's
diagnostic tier already lives in this space, and a question answered at the wrong shape is a visible
failure, not a silent one, which is why it belongs in a different row of the cost matrix.

### 5.4 The distinction that decides whether a question is even answerable

AMBROSIA flags it and then sets it aside for convenience: "Vagueness and ambiguity are often
considered distinct properties; however, for simplicity, we will refer to vagueness as a type of
ambiguity."

We should not set it aside, because it decides the mechanism:

| | ambiguity | vagueness |
|---|---|---|
| structure | finitely many discrete readings | a continuum, no discrete alternatives |
| example | `value_moments` or `real_value_moments` | "recently", "our best customers" |
| the right move | a multiple-choice question the user can answer | a declared convention, not a question |
| k | ≥ 2, computable | undefined |

A clarification that offers named candidates is answerable in one turn. A clarification that asks
what "recently" means is a question the user often cannot answer either, and it is the shape the
brief's third falsification condition warns about — "clarification collapses to *which metric do you
mean* noise that no user could answer". The vagueness cases are where a *default* belongs, declared
in the layer, disclosed in the answer.

### 5.5 The terminology collision to settle

"Scope" currently means three incompatible things in the sources above:

1. AMBROSIA — quantifier scope, collective versus distributive readings of "each"
2. PRACTIQ — the range or boundaries of the query
3. the proposal here — time window, segment, filter

Given `.claude/TERMINOLOGY.md`, this needs deciding once. My suggestion is to avoid the bare word
entirely and use the layer's own vocabulary — **segment**, **period**, **grain**, **filter value** —
which are already the primitives the semantic layer declares and are unambiguous inside this repo.

---

## 6. The split that actually matters: who can fix it

Sorting by *what is underdetermined* gives a readable list. Sorting by *who can resolve it* gives
one that routes.

**Group 1 — the question is underspecified.** The user left something out. The user can put it back
in one turn. Intent, segment, period, grain, baseline, output shape. The clarification is a normal
conversational repair, it is resolved and gone, and the same question from a different user will
need the same repair.

**Group 2 — the model is over-specified.** Two governed answers exist. No amount of the user
explaining their intent removes the ambiguity, because it is not in the question. Competing
definitions, and conflicting sources of truth.

The consequences of that split are the design:

| | group 1 · underspecified question | group 2 · over-specified model |
|---|---|---|
| computable from the layer alone | no — needs question understanding | **yes** — cluster membership plus divergence |
| resolvable by the user | yes, in one turn | yes for this question, never for the next one |
| the real fix | a declared default, or better prompting | a governance decision: rename, merge, or make the choice an argument |
| where it routes | the conversation | the metric backlog, every time |
| recurs | per user | forever, until someone decides |
| Pile C? | **no** | **yes** |

That table is the reason group 2 is the experiment and group 1 is context. Only group 2 has a k that
can be computed rather than authored, which is the central methodological claim in the brief. Only
group 2 produces the same clarification for every user until a human resolves it, which is what
makes it a governance signal rather than a conversational one. And only group 2 has the property
that answering silently is a *defensible wrong answer* rather than a guess, which is what makes the
error invisible.

It also gives the brief's practitioner line its precise form. "Some of these are leftovers you should
delete, and some are two teams who both think they're right" is a split *inside* group 2:
reducible — one of the two should not exist, and preflight finds it offline; irreducible — both
should exist, and the choice has to be exposed at query time. That is the "one artifact, two
consumers" argument in §9 of the brief, and this is where it is earned.

---

## 7. Proposed vocabulary for `CLARIFY_REASONS`

Codes, in the shape `REASON_MEANINGS` already uses for refusals. Ordered by group, because the group
decides the routing.

### Group 2 — computable from the layer, routes to governance

| code | meaning | decidable how |
|---|---|---|
| `competing_definitions` | two or more governed metrics define the concept asked about, and they return different numbers for this slice | cluster membership, then execute the candidates and compare |
| `conflicting_sources` | two or more sources of truth carry the same concept and disagree (a table beside its own `_v2`, a snapshot beside the live fact) | preflight's `VERSIONED_TWIN` / `FACT_TWIN`, then compare |

### Group 1 — needs the question, routes to the conversation

| code | meaning |
|---|---|
| `undefined_term` | the term names nothing governed but has two or more plausible governed readings ("whales", "healthiest market") |
| `unspecified_segment` | which population is meant, and the layer governs more than one candidate |
| `unspecified_period` | which time window, or which grain of time |
| `unspecified_grain` | which level of aggregation — per user, per session, per event |
| `missing_baseline` | a comparison with no second operand |
| `unspecified_output` | which shape of answer — a value, a trend, a breakdown, a cause |

Three properties this vocabulary is built for, matching what the refuse enum already has:

- **countable** — every clarification carries exactly one code, so "what do people ask about" is a
  query rather than a reading exercise
- **routable** — the group decides the destination: backlog or conversation
- **checkable** — the two group-2 codes carry named candidates, and both "do these exist" and "do
  they diverge here" are lookups against the catalog and the warehouse, with no model and no gold
  label

`undefined_term` is the code the three existing `ambiguous` cases (`adv_whales`,
`amb_healthiest_region`, `amb_best_channel`) actually need, and it is not what Pile C is about. Those
cases are correctly in Pile B today: nothing governed answers them, so refusing is right and asking
is also right.

---

## 8. What to carry into the article

- The four levels of communication are 1996 and the mapping is clean. Use them; do not reinvent
  them. Three of the four proposed categories are Clark's level 3 and level 4.
- **The contribution is group 2**, and specifically `competing_definitions`. It is absent from every
  published taxonomy because none of those systems has a governed semantic layer, and it is asserted
  everywhere in industry with no measurement attached.
- **k is AMBROSIA's Definition 2, restricted to the governed set.** Cite it. The restriction is what
  makes it decidable; the definition is not new and should not be presented as new.
- **The cost matrix is expected regret**, and *Act or Clarify?* (May 2026) gives the formalism and
  the interaction we predict: uncertainty matters most when acting wrongly is costly. The third
  action with its own cost is learning to defer, not Chow's reject option, which is two-action.
- **Clarifying is one of three responses**, not the only correct one. Answering with both candidates
  labelled may dominate it on cost while removing the silent error. Test it as a fourth column.
- **Ambiguity and vagueness are different**, and only ambiguity can be resolved by a multiple-choice
  question. Vagueness needs a declared default. This predicts which clarifications a user can
  actually answer.
- The behavioural priors are already published: models recognise ambiguity and do not act on it
  (60–80% versus under 5%), more context makes it worse, and permissive prompting flips straight
  into over-asking. Our archive reproduces the first two. Position against them rather than
  reporting them as discoveries.

---

## Sources

Read in full or in relevant part:

- Schlangen, *Causes and Strategies for Requesting Clarification in Dialogue*, SIGdial 2004 — https://aclanthology.org/W04-2325.pdf
- Zamani, Dumais, Craswell, Bennett & Lueck, *Generating Clarifying Questions for Information Retrieval*, WWW 2020 — https://dl.acm.org/doi/10.1145/3366423.3380126
- Min, Michael, Hajishirzi & Zettlemoyer, *AmbigQA: Answering Ambiguous Open-domain Questions*, EMNLP 2020 — https://arxiv.org/abs/2004.10645
- Zhang et al., *CLAMBER: A Benchmark of Identifying and Clarifying Ambiguous Information Needs in Large Language Models*, 2024 — https://arxiv.org/abs/2405.12063
- Saparina & Lapata, *AMBROSIA: A Benchmark for Parsing Ambiguous Questions into Database Queries*, NeurIPS 2024 — https://arxiv.org/abs/2406.19073
- Dong, Ashok Kumar et al., *PRACTIQ: A Practical Conversational Text-to-SQL dataset with Ambiguous and Unanswerable Queries*, AWS/UMass — https://arxiv.org/abs/2410.11076
- Tsvilodub, Mulligan, Snider, Hawkins & Franke, *Act or Clarify? Modeling Sensitivity to Uncertainty and Cost in Communication*, 2026 — https://arxiv.org/abs/2602.02843
- *Knowing but Not Showing: LLMs Recognize Ambiguity but Rarely Ask Clarifying Questions*, 2026 — https://arxiv.org/abs/2605.25284
- *Ambig-DS: A Benchmark for Task-Framing Ambiguity in Data-Science Agents*, 2026 — https://arxiv.org/abs/2605.09698
- *Disambiguation in Conversational Question Answering in the Era of LLMs and Agents: A Survey*, 2025 — https://arxiv.org/abs/2505.12543

Listing only — seen in search results, not read, and to be verified before citing:

- Bhaskar et al., *Benchmarking and Improving Text-to-SQL Generation under Ambiguity* (AmbiQT), EMNLP 2023 — https://arxiv.org/abs/2310.13659
- *AmbiSQL: Interactive Ambiguity Detection and Resolution for Text-to-SQL*, 2025 — https://arxiv.org/abs/2508.15276
- *Clarify When Necessary: Resolving Ambiguity Through Interaction with LMs* — https://arxiv.org/abs/2311.09469
- *Uncertainty-Aware Clarification in LLM Agents with Information Gain* — https://arxiv.org/abs/2606.03135
- *Ask Early, Ask Late, Ask Right: When Does Clarification Timing Matter for Long-Horizon Agents?* — https://arxiv.org/abs/2605.07937
- Madras, Pitassi & Zemel, *Predict Responsibly* (learning to defer), 2018; Mozannar & Sontag, *Consistent Estimators for Learning to Defer*, 2020
- Braslavski et al. (2017), clarification types in community question answering: More Information, Check, Reason, General, Selection, Experience

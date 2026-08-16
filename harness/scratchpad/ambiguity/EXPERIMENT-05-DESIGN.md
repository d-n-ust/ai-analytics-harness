# Experiment 05 — design (customer-first)

Status: **design, not built.** This decides what Experiment 05 should *check* and *present* before we
scaffold `experiments/05_ambiguity/`. It is written backward from the buyer's decision, not forward
from the code we happen to have. The underlying evidence mostly exists (T1–T5, the blind sales/retail
environments, the human-gold audit, the no-SL contrast); 05 is about assembling it into something a
customer finds convincing — and finding the gaps.

Design principle: **present outcomes, not apparatus.** The customer never sees "T3" or "shuffle
p=0.038". They see "does it catch the dangerous confusions on a realistic stack, without drowning me
in noise, and what does it miss." The T-tests are the evidence underneath; the presentation is in the
customer's terms.

---

## 1. The customer and the decision

Who: a founder / CTO / Head of Data at a scaling company who is about to put an AI analyst on their
data, or already has and does not trust the numbers. The decision they are making:

> **"Can I let an agent answer questions off my analytics, and trust the answer the way I trust my
> senior analyst?"**

The wedge (from the practice thesis): a number can be perfectly fine for a human and wrong for an
agent, because the human asks "gross or net?" and the agent picks silently. Experiment 05 has to make
that real and show we can catch it before it bites.

## 2. The buyer's real questions

Everything 05 measures should answer one of these. If a measurement answers none of them, it is
apparatus, not evidence.

| # | The question the buyer actually asks | Their fear |
|---|---|---|
| Q1 | Does it catch the confusions that would silently produce a wrong number? | false confidence |
| Q2 | Will it bury me in false alarms? | alert fatigue, tool ignored |
| Q3 | Does it work on **my** stack, not a toy? | demo-ware that breaks on real data |
| Q4 | How is this better than what I already have (a smart human, or "just ask GPT")? | paying for nothing |
| Q5 | Would an actual expert agree these are dangerous? | a machine crying wolf |
| Q6 | What does it **miss**? Where's the edge? | unknown blind spots |
| Q7 | What do I **do** with it — is it a report or a guardrail? | shelfware |

## 3. The claim under test (narrowed, honest)

> The dangerous, numerically-silent **ambiguities** in a governed analytics stack — the same measure
> under two scopes, one concept over two columns, one term defined two ways across layers — are
> computable **offline from the artifacts**, across domains and dialects, with high recall and
> tolerable noise, and an experienced practitioner agrees with the dangerous calls. This is the
> **selection** half of grounding safety; construction defects (grain, additivity, keys) are a
> separate family (see `PRIMITIVE-VALIDATORS.md`) and out of scope here.

State the narrowing up front. Credibility is bought with the boundary, not spent on it.

## 4. What to CHECK — measurements mapped to the questions

| Q | Measure | Metric | Presented as |
|---|---|---|---|
| Q1 | recall on **high-danger** collisions in blind realistic environments | recall % (high) | scorecard row |
| Q2 | share of findings that are real (not noise) | precision % | scorecard row |
| Q3 | generalization: 2 domains (sales, retail), 3+ dialects (dbt/MetricFlow/Cube), partial layouts (semantic-only, warehouse+docs) — **zero per-domain tuning** | pass/fail + the recall/precision holding across them | scorecard: "cross-domain, zero tuning" |
| Q4 | contrast: with vs without a semantic layer; the tool vs a lexical baseline vs a single-LLM gold | Δ recall / Δ precision | contrast table |
| Q5 | agreement with a human red-team + practitioner-adjudicated gold | expert-agreement %, honestly split by lane | the two-mode reframe (in-lane ~5/8, naïve 5/22) |
| Q6 | the boundary: Mode-1 (ambiguity) vs Mode-2 (construction); what falls outside | qualitative + the 22-collision family breakdown | boundary statement + map |
| Q7 | the guardrail actually blocks a bad change | a demo: a PR adds an ambiguous metric → CI fails | a screenshot / run link |

The **headline number** we want to be able to say in one sentence: *"On blind, realistic
environments across two domains and three dialects, with zero tuning, preflight catches ~X% of the
dangerous ambiguities at ~Y% precision, and a practitioner agrees with the in-lane calls."* Fill X/Y
from the frozen scored runs (sales 16/16 high recall, 93% precision; retail 95% recall, 87%; human
gold in-lane ~5/8).

## 5. What to PRESENT — the deliverables

One headline artifact plus supporting evidence. All customer-facing.

1. **The scorecard** (the 60-second read). A single page: the claim, the recall/precision/expert-
   agreement numbers across the environments, "cross-domain, zero tuning," and the boundary line.
   This is the thing a prospect skims and a blog post is built around.
2. **Example findings — real, visceral, from the blind envs.** The gross-vs-net revenue fork, the
   `value_moments`/`real_value_moments` scope trap, `status='settled'` matching zero rows. Concrete
   collisions a reader feels. Pulled from `env_sales`/`env_retail` findings, not invented.
3. **The contrast.** With vs without a semantic layer (governance is what makes the fork resolvable),
   and the tool vs the naive baselines. Answers Q4.
4. **The boundary — the two-mode map.** Ambiguity is one of two ways a number goes silently wrong;
   the honest human-gold reframe (23% naïve → the tool is the Mode-1 half). Answers Q5/Q6 and is the
   most trust-building beat.
5. **The guardrail demo.** A short narrative: introduce an ambiguous metric in a PR, preflight blocks
   it. Turns "a study" into "a product you run today" (the GitHub Action / pre-commit we just added).

## 6. Setup + circularity discipline

The result is only worth presenting if it cannot be gamed. Keep the discipline that already produced
the current numbers:

- **Blind generation.** Environments are generated without the detector in the loop; ground truth is
  labelled blind; the detector is frozen before scoring. (Done for sales + retail.)
- **Human gold, adjudicated.** 3 independent red-team judges + practitioner rulings, clustered on
  real entity labels. (Done for retail; consider a second-domain human pass.)
- **Report the misses.** The scorecard names what both the detector and the LLM gold missed, not just
  the hits.
- **Real-shaped inputs, not just synthetic** (candidate addition — see §8): run on a public
  semantic-layer repo (e.g. a MetricFlow / dbt example project) so Q3 is answered on something the
  buyer recognizes, not only on our own fixtures.

## 7. What exists vs what 05 must add

Reuse (already done): T1 frozen-prediction, T2 corpus, T3 SQL recovery, T4 real-warehouse divergence,
T5 dialect portability; `env_sales`, `env_retail` with blind ground truth; the human-gold scorecard;
the no-SL contrast; `SUMMARY.md`; `PRIMITIVE-VALIDATORS.md`.

Add / assemble:
- `experiments/05_ambiguity/` with `experiment.yml` (title, question, `runs: code`, `article.repo:
  decisionspine-site`, evidence pointers) + `FINDINGS.md` = the scorecard, in customer terms.
- The **scorecard artifact** itself (the one-page present), derived from the frozen scored runs.
- The **guardrail demo** (PR-blocked narrative / CI run).
- **Candidate: a public-repo run** for external credibility (decision below).
- **Candidate: a second-domain human pass** (retail is human-audited; sales is single-LLM gold).

## 8. Open decisions before we build (for Dmitry)

1. **Public-repo run?** Worth the effort to run preflight on a well-known open dbt/MetricFlow example
   and show the findings — much stronger Q3 answer — or keep to our blind synthetic envs for control?
2. **Headline metric framing.** Lead with the flattering blind-env numbers (sales/retail recall), the
   honest human-gold numbers (in-lane ~5/8), or both side by side? (Recommendation: both — the honest
   pairing is more persuasive than either alone.)
3. **Second-domain human gold?** Add a human pass on sales, or is one adjudicated domain (retail)
   enough to support the expert-agreement claim?
4. **Scope of the guardrail demo.** A real PR on a sample repo, or a scripted before/after in the doc?
5. **Where the scorecard lives** — inside `FINDINGS.md`, or a separate one-pager the article and the
   site can both reuse?

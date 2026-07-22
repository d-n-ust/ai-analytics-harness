"""Blind eval of the spec-decomposition rung's one soft spot: the isolated decomposer
(question -> required spec). The comparator is deterministic and proven no-LLM in
tests/test_semantic.py; this measures the part that isn't — how well the model reads a
question into a spec — on questions the decomposer prompt was NOT written against.

Blindness: the decomposer prompt (harness/spec_check.py) contains no in-domain phrasings
and only unrelated-domain worked examples. The questions below are fresh paraphrases and
novel questions; the gold verdict is hand-labelled from a plain reading of each question,
independent of the prompt. So a pass here is generalisation, not memorised phrasings.

What it reports (per the two things that matter for a refuse-only rung):
  - catch rate:      of the questions that SHOULD refuse (a subset/near-miss metric
                     answering a whole-set question), how many did.
  - over-refusal:    of the questions that SHOULD allow (the metric genuinely answers
                     them), how many were wrongly refused — the cost side.

Each item names the metric a model would answer with and the call it would make, so the
same deterministic comparator the harness uses produces the verdict. Only the decomposer
is live (one model call per question).

Run: PYTHONPATH=. .venv/bin/python evaluation/decomposer_eval.py [model]
"""

from __future__ import annotations

import sys

from harness import spec_check
from harness.models import get_model
from harness.semantic import SemanticLayer
from harness.warehouse import open_warehouse


def _qm(metric, value, **args):
    return {"tool": "query_metric", "args": {"metric": metric, **args},
            "result": f"columns: value\n({value},)"}


# (question, answer_metric, value, call_args, gold)  — gold is "refuse" or "allow".
# value is only used to link the answer to the metric; it does not affect the verdict.
ITEMS = [
    # ---- should REFUSE: a subset / wrong-entity / wrong-grain / wrong-measure metric --
    ("What is our total user base?",                         "active_users", 2100, {"period": "all"}, "refuse"),
    ("How many registered accounts are there?",              "active_users", 2100, {"period": "all"}, "refuse"),
    ("How many people have ever signed up and joined?",      "active_users", 2100, {"period": "all"}, "refuse"),
    ("Across our whole history, how many subscriptions have we sold?",
                                                             "active_subscriptions", 457, {}, "refuse"),
    ("How many contracts are on the books in total?",        "active_subscriptions", 457, {}, "refuse"),
    ("How many unique habits have people defined in the app?",
                                                             "value_moments", 67132, {"period": "all"}, "refuse"),
    ("How many habit templates exist across all users?",     "value_moments", 67132, {"period": "all"}, "refuse"),
    ("How many customers are paying us right now?",          "active_users", 2100, {"period": "all"}, "refuse"),
    ("Overall, all-time, how many active users do we have?", "active_users", 886, {"period": "last_week"}, "refuse"),
    ("What share of our users are power users?",             "power_users", 432, {"period": "all"}, "refuse"),
    ("How many users are on the platform altogether?",       "active_users", 2100, {"period": "all"}, "refuse"),

    # ---- should ALLOW: the metric genuinely answers the question --------------------
    ("How many active users did we have last week?",         "active_users", 886, {"period": "last_week"}, "allow"),
    ("How many people were active in the app last week?",    "active_users", 886, {"period": "last_week"}, "allow"),
    ("How many paying subscribers do we have?",              "paying_users", 371, {}, "allow"),
    ("What is our MRR right now?",                           "mrr", 48210.50, {}, "allow"),
    ("How many power users are there currently?",            "power_users", 432, {"period": "all"}, "allow"),
    ("How many value moments were logged last week?",        "value_moments", 1450, {"period": "last_week"}, "allow"),
    ("How many signups did we get last month?",              "new_signups", 320, {"period": "last_month"}, "allow"),
    ("What's our ARPU?",                                     "arpu", 22.4, {}, "allow"),
    ("What is the reminder open rate?",                      "reminder_open_rate", 0.41, {}, "allow"),
    ("How many total value moments have there been?",        "value_moments", 67132, {"period": "all"}, "allow"),
    ("What's the activation rate for recent signups?",       "activation_rate", 0.63, {}, "allow"),
    ("How many subscriptions are currently active?",         "active_subscriptions", 371, {}, "allow"),
    ("How much did we spend on marketing last month?",       "marketing_spend", 15000, {"period": "last_month"}, "allow"),
    ("Break active users down by region for last week.",     "active_users", 300, {"period": "last_week", "group_by": ["region"]}, "allow"),
]


def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 else "gpt-5.4-mini"
    model = get_model(model_name)
    sem = SemanticLayer(open_warehouse())

    rows, catch_hit = [], 0
    n_refuse = sum(1 for *_, g in ITEMS if g == "refuse")
    n_allow = len(ITEMS) - n_refuse
    over_refused = correct = 0

    print(f"Blind decomposer eval — model={model_name}, n={len(ITEMS)} "
          f"({n_refuse} should-refuse, {n_allow} should-allow)\n")
    for question, metric, value, args, gold in ITEMS:
        spec = spec_check.decompose_question(model, question, sem.ontology)   # the only live call
        ok, reason, _, _ = spec_check.verify_answer(
            sem, question, str(value), [_qm(metric, value, **args)],
            decompose=lambda _q, s=spec: s, source_metric=metric)   # rung 6 declares provenance
        verdict = "allow" if ok else "refuse"
        good = verdict == gold
        correct += good
        if gold == "refuse" and verdict == "refuse":
            catch_hit += 1
        if gold == "allow" and verdict == "refuse":
            over_refused += 1
        rows.append((good, gold, verdict, reason, metric, question, spec))

    for good, gold, verdict, reason, metric, question, spec in rows:
        mark = "ok " if good else "XX "
        tag = f"{verdict}" + (f"/{reason}" if reason else "")
        print(f"{mark}gold={gold:<7} got={tag:<26} [{metric}] {question}")
        print(f"      spec: entity={spec.get('entity')} population={spec.get('population')} "
              f"measure={spec.get('measure')} grain={spec.get('grain')}"
              + ("  AMBIG" if spec.get("ambiguous") else ""))

    print(f"\n--- summary ---")
    print(f"overall verdict accuracy : {correct}/{len(ITEMS)} = {correct/len(ITEMS):.0%}")
    print(f"catch rate (traps caught): {catch_hit}/{n_refuse} = {catch_hit/n_refuse:.0%}")
    print(f"over-refusal (controls)  : {over_refused}/{n_allow} = {over_refused/n_allow:.0%}")


if __name__ == "__main__":
    main()

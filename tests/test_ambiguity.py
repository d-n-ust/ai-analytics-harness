"""The semantic-layer ambiguity lint — pure, no model, no run, no warehouse.

It reads declarations and says which governed names could be mistaken for each other. The last
test measures its recall against real confusions AND against two trivial baselines, because on
this layer one collision dominates and recall alone cannot tell the lint apart from a rule that
flags any two names sharing a word.

Run: PYTHONPATH=. uv run python tests/test_ambiguity.py
"""

from __future__ import annotations

from semantic.ambiguity import confusable_pairs

# The two declarations as the layer really carries them, trimmed to the facets that decide it.
LAYER = {
    "value_moments": {"entity": "value_moments", "agg": "sum(moments)", "base": "agg_active_days",
                      "unit": "count", "segment": "all"},
    "real_value_moments": {"entity": "value_moments", "agg": "sum(moments)",
                           "base": "agg_active_days", "unit": "count", "segment": "active",
                           "default_filters": ["NOT is_internal"]},
    "days_per_user": {"entity": "users", "agg": "avg(active_days)", "base": "agg_active_days",
                      "unit": "days", "segment": "active"},
    "moments_per_day": {"entity": "value_moments", "agg": "avg(moments)",
                        "base": "agg_active_days", "unit": "ratio", "segment": "active"},
    "active_users": {"entity": "users", "agg": "count(*)", "base": "agg_active_days",
                     "unit": "count", "segment": "active"},
}
NODES = {"weekly_value_moments": "real_value_moments", "days_per_user": "days_per_user"}


def _pair(found, a, b):
    return next((f for f in found if {f.a.split(" (")[0], f.b} == {a, b}), None)


def test_the_dangerous_pair_is_the_one_that_differs_only_in_scope():
    """Two metrics agreeing on entity, aggregation, base and unit measure the same thing. When
    they differ ONLY in scope, their figures are near neighbours — 12.12% against 11.88% on the
    same week — so a swap survives every numeric check the harness has: provenance passes, range
    validation passes, and the judge sees a real number from a real metric.

    That is a categorical difference in detectability, not a similarity score, which is why the
    severity is a class and not a number."""
    found = confusable_pairs(LAYER, NODES)
    f = _pair(found, "value_moments", "real_value_moments")
    assert f is not None and f.kind == "scope_only" and f.severity == "high"
    assert set(f.same_meaning) == {"entity", "agg", "base", "unit"}
    assert set(f.differs_in) == {"segment", "default_filters"}

    # a pair differing in what it MEASURES is loud, so it is not the same problem
    loud = _pair(found, "value_moments", "moments_per_day")
    assert loud is not None and loud.severity == "low"


def test_a_tree_node_is_a_third_public_name_and_is_judged_by_what_it_resolves_to():
    """`weekly_value_moments` resolves to `real_value_moments` while reading like the unrelated
    `value_moments`, so three surface names cover two measures. Judging the node by its own name
    alone would have missed this; judging it by the declaration behind it catches it."""
    f = _pair(confusable_pairs(LAYER, NODES), "weekly_value_moments", "value_moments")
    assert f is not None and f.severity == "high"
    assert "real_value_moments" in f.note and "value_moments" in f.note


def test_sharing_only_a_qualifier_is_not_a_collision():
    """`days_per_user` and `moments_per_day` share "per" and nobody has ever mixed them up.
    Without this the lint reported eleven pairs of which nine were noise — and a lint whose output
    has to be skimmed for the real entry is a lint nobody runs twice."""
    found = confusable_pairs({"days_per_user": LAYER["days_per_user"],
                              "moments_per_day": LAYER["moments_per_day"]})
    assert [f for f in found if set(f.shared_tokens) <= {"per"}] == []


def test_an_unambiguous_layer_reports_nothing():
    """Errors defined out of existence: rename the head noun and the confusion becomes
    unsayable. This is the fix the lint recommends, checked."""
    fixed = {**LAYER}
    fixed["gross_value_moments"] = fixed.pop("value_moments")
    fixed["north_star"] = fixed.pop("real_value_moments")
    high = [f for f in confusable_pairs(fixed, {"weekly_north_star": "north_star"})
            if f.severity == "high"]
    assert high == [], high


def test_recall_against_stored_confusions_is_not_evidence_the_lint_works():
    """What this measures, and — more important — what it does NOT.

    RECALL is computed per ANSWER, not per claim and not per citation. `mislabelled` is an
    answer-level property (one wrong `source_metric` compared against every claim's evidence), so
    counting it per claim multiplies one root cause by the number of claims, and counting it per
    SOURCE CITATION multiplies it again. The first version of this test used the citation
    denominator and reported 83%; the honest figure is 65.7% over 169 answers, and the difference
    was entirely double-counting.

    THE BASELINES ARE THE POINT. On this layer one collision dominates, so recall cannot
    distinguish the lint from a trivial rule:

        lint `high` pairs             111/169 = 65.7%
        "the single most common pair" 110/169 = 65.1%   <- needs a RUN, and matches it
        "any two names sharing a word" 114/169 = 67.5%  <- BEATS it, flagging 14 pairs not 2

    So recall here is not evidence the classification does anything. What the lint offers over
    those baselines is that it needs no run, and that it returns 2 findings rather than 14 — and
    neither of those properties is what a recall number measures. Anyone quoting this figure as
    "the lint predicts what gets confused" is quoting the wrong statistic, which is why the
    baselines are asserted here rather than left as a note.

    Skipped when no runs are stored, so a fresh clone still passes."""
    import collections
    import glob
    import json
    from pathlib import Path

    import yaml
    root = Path(__file__).resolve().parent.parent
    paths = glob.glob(str(root / "results" / "runs" / "*" / "raw.jsonl"))
    if not paths:
        print("  (no stored runs — validation skipped)")
        return

    layer = yaml.safe_load((root / "semantic" / "semantic_layer.yml").read_text())
    metrics = layer["metrics"] if isinstance(layer.get("metrics"), dict) else layer
    tree = yaml.safe_load((root / "semantic" / "metric_tree.yml").read_text())
    nodes = {n: s.get("metric") for n, s in (tree.get("nodes") or {}).items()}
    flagged = {frozenset({f.a.split(" (")[0], f.b})
               for f in confusable_pairs(metrics, nodes) if f.severity == "high"}

    # One entry per mislabelled ANSWER: the set of (declared, evidence-root) pairs it involves.
    answers: list = []
    for path in paths:
        for line in open(path):
            row = json.loads(line)
            a = row.get("claim_audit") or {}
            if not a.get("mislabelled"):
                continue
            declared = row.get("source_metric")
            steps = {s["handle"]: s for s in row.get("steps") or [] if s.get("handle")}
            pairs = set()
            for f in a["findings"]:
                if "mislabelled" not in (f.get("why") or []):
                    continue
                for ref in f.get("sources") or []:
                    step = steps.get(str(ref).strip().strip("[]").partition(":")[0]) or {}
                    args = step.get("args") or {}
                    root_name = args.get("metric") or args.get("node")
                    if root_name and declared and root_name != declared:
                        pairs.add(frozenset({declared, root_name}))
            if pairs:
                answers.append(pairs)

    n = len(answers)
    if not n:
        print("  (no mislabels stored — validation skipped)")
        return

    def covers(rule) -> int:
        return sum(1 for ps in answers if any(rule(p) for p in ps))

    top = collections.Counter(p for ps in answers for p in ps).most_common(1)[0][0]
    lint = covers(lambda p: p in flagged)
    freq = covers(lambda p: p == top)
    token = covers(lambda p: bool(set(tuple(p)[0].split("_")) & set(tuple(p)[1].split("_"))))
    print(f"  over {n} mislabelled ANSWERS:  lint {lint} ({lint/n:.1%}) · "
          f"most-frequent-pair {freq} ({freq/n:.1%}) · any-shared-token {token} ({token/n:.1%})")

    assert lint / n > 0.6, f"the lint covers only {lint/n:.0%} of real confusions"
    # The finding this test exists to keep honest. If a trivial rule ever falls well BEHIND the
    # lint, recall has started to mean something and this assertion is the thing to revisit — but
    # it must be revisited deliberately, not discovered by someone quoting the recall figure.
    assert token >= lint - 5, (
        "a trivial any-shared-token rule no longer matches the lint's recall. That would be the "
        "first evidence the classification does work, and it needs saying explicitly rather than "
        "being folded into a recall number")


# -- the coverage audit ------------------------------------------------------ #

def test_the_audit_trusts_itself_only_when_the_control_ranks_first():
    """The audit reads a COMMITTED vector cache, so this runs with no key and no network.

    The control is the pair this lint proves independently is the layer's worst. A model or
    configuration that cannot rank it first is misconfigured, and that check has already caught one
    encoder that ranked it 17th while producing confident-looking numbers for every other row."""
    from pathlib import Path

    import yaml

    from semantic.similarity import audit
    root = Path(__file__).resolve().parent.parent
    metrics = yaml.safe_load((root / "semantic" / "semantic_layer.yml").read_text())["metrics"]
    r = audit(metrics)
    assert r.control_rank == 1 and r.trustworthy, (
        f"control came back at rank {r.control_rank}; the audit is not readable")
    assert abs(r.mean - 0.327) < 0.01 and abs(r.sd - 0.093) < 0.01, (
        f"the score distribution moved: mean {r.mean:.3f} sd {r.sd:.3f} — z values are not comparable "
        "with anything published from the previous distribution")


def test_the_audit_reports_what_the_lint_cannot_reach():
    """The audit's one job. `new_signups` and `referrals` share no name token, so `confusable_pairs`
    never compares them — but both are count(*) in `count` units over a period, and their synonyms
    carry 'new users' and 'referred users'. A swap returns a plausible number.

    Pinned because it is the only evidence this module earns its dependency."""
    from pathlib import Path

    import yaml

    from semantic.ambiguity import considers
    from semantic.similarity import audit
    root = Path(__file__).resolve().parent.parent
    metrics = yaml.safe_load((root / "semantic" / "semantic_layer.yml").read_text())["metrics"]

    assert not considers("new_signups", "referrals"), "the lint now compares this pair; audit is moot"
    found = {frozenset((p.a, p.b)) for p in audit(metrics).new_findings()}
    assert frozenset(("new_signups", "referrals")) in found, (
        f"the audit stopped surfacing the one pair outside the lint's reach: {found}")


def test_the_member_lint_separates_a_defect_from_advice():
    """Only a COLLISION is a defect however the value arrives. `code_as_text` and
    `common_in_prose` are findings about free-text resolution, and reporting them as faults
    counts the alias map working as evidence it is broken: on this layer the model passed
    `region='apac'` 211 times and `plan='annual'` 42 times, all flagged, all correct."""
    from semantic.ambiguity import member_clashes

    dims = {
        "country": {"IN": ["in", "india"], "US": ["us", "usa"]},
        "channel": {"paid_search": ["paid search", "paid"], "referral": ["referral"]},
        "platform": {"ios": ["iphone", "ios"]},
    }
    found = {c.text: c for c in member_clashes(dims, corpus=["how much did we spend on paid ads",
                                                            "what did we spend on paid search"])}
    # a two-letter identity code, addressable as an English word
    assert found["in"].kind == "code_as_text" and found["in"].severity == "if-you-resolve-prose"
    # an alias that shows up in ordinary questions
    assert found["paid"].kind == "common_in_prose" and found["paid"].seen_in >= 2
    # neither is ranked as a fault, because neither is one when the caller supplies the value
    assert not [c for c in found.values() if c.severity == "high"]

    # one string claimed by two members IS a defect, whoever supplies it
    clash = {c.text: c for c in member_clashes(
        {"channel": {"paid_search": ["ads"]}, "platform": {"android": ["ads"]}})}
    assert clash["ads"].kind == "collision" and clash["ads"].severity == "high"
    assert set(clash["ads"].claimed_by) == {"channel.paid_search", "platform.android"}


if __name__ == "__main__":
    # Collected rather than listed by hand, matching the other suites. The hand-written list this
    # replaces had omitted `test_the_member_lint_separates_a_defect_from_advice` since it was
    # written, so that test had never run once — green the whole time, checking nothing.
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK — the lint finds the scope-only pair, judges a tree node by what it resolves to,\n"
          "ignores qualifier collisions, separates a member defect from advice, and does NOT\n"
          "out-recall a trivial baseline. The coverage audit reproduces from its committed cache,\n"
          "ranks its control first, and surfaces the one pair the lint cannot reach.")

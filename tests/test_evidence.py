"""Unit test for the claim audit — pure, no run and no model needed.

`audit()` resolves what an answer committed to against the trace it was built from. Every case
below is a shape seen in a live run, so the test pins behaviour rather than intention.

Run: PYTHONPATH=. uv run python tests/test_claims.py
"""

from __future__ import annotations

from evidence import (
    BAD_PREMISE,
    COMPOSED,
    MISLABELLED,
    UNRESOLVED,
    UNSOURCED,
    VALUE_MISMATCH,
    audit,
)

# The decomposition every diagnostic answer is built on, as the trace stores it: eighteen
# governed figures under ONE handle, each addressable by name.
DECOMP = {
    "tool": "decompose_change", "handle": "r1", "error": False,
    "args": {"node": "weekly_value_moments", "period_a": "prev_week", "period_b": "last_week"},
    "result_labels": ["value_a", "value_b", "pct_change",
                      "active_users.value_a", "active_users.value_b", "active_users.pct_change",
                      "days_per_user.value_a", "days_per_user.value_b",
                      "days_per_user.pct_change", "days_per_user.contribution_share"],
    "result_values": [4133.0, 3642.0, -0.11879990321800149,
                      836.0, 886.0, 0.05980861244019131,
                      2.7177033492822966, 2.270880361173815, -0.1644119797793533, 1.4202483],
}

# A breakdown: four channels under one handle. Naming the handle alone names none of them.
SPEND = {
    "tool": "query_metric", "handle": "r2", "error": False,
    "args": {"metric": "marketing_spend", "group_by": ["channel"], "period": "last_month"},
    "result_labels": ["content_seo", "paid_search", "partnerships", "referral"],
    "result_values": [3605.41, 12786.81, 2746.03, 1874.95],
}


def test_a_field_citation_resolves_and_the_figure_must_match():
    steps = [DECOMP]
    ok = audit([{"text": "days per user fell 16.44%",
                 "sources": ["r1:days_per_user.pct_change"], "value": -16.44119797793533}],
               steps, source_metric="weekly_value_moments")
    assert ok["n"] == 1 and ok["bound"] == 1 and not ok["findings"][0]["why"], ok
    # the value is stated as a percentage; the governed figure is a fraction — same number
    assert ok["value_mismatch"] == 0

    bad = audit([{"text": "days per user fell 20%",
                  "sources": ["r1:days_per_user.pct_change"], "value": -20.0}],
                steps, source_metric="weekly_value_moments")
    assert VALUE_MISMATCH in bad["findings"][0]["why"] and bad["bound"] == 0


def test_a_bare_handle_does_not_name_a_number():
    """The first live run at this rung cited `r1` five times out of five. A handle holding
    eighteen figures names none of them, and saying so is the finding — not a bug to route
    around by searching the bag, which is how a hand-composed ratio once matched a coincidence."""
    a = audit([{"text": "value moments fell 11.88%", "sources": ["r1"],
                "value": -11.879990321800149}], [DECOMP], source_metric="weekly_value_moments")
    assert UNRESOLVED in a["findings"][0]["why"] and a["unresolved"] == 1
    # …while a single-value result IS named by its bare handle: there is only one number to mean.
    single = {"tool": "query_metric", "handle": "r3", "error": False,
              "args": {"metric": "active_users"}, "result_labels": [""], "result_values": [886.0]}
    b = audit([{"text": "886 active users", "sources": ["r3"], "value": 886.0}],
              [single], source_metric="active_users")
    assert b["bound"] == 1 and not b["findings"][0]["why"]


def test_the_wrong_metric_name_is_caught_where_no_number_check_could():
    """The live case, in all three reps of t5_reminder_caused_it: the figures come from the
    tree root (`weekly_value_moments`, −11.88%) and the answer declares `value_moments`, which
    is a different metric that fell 12.12%. A quarter of a point apart — every check on the
    NUMBER passes, and the record of what the answer was about is wrong."""
    a = audit([{"text": "weekly value moments fell 11.88%",
                "sources": ["r1:pct_change"], "value": -11.879990321800149}],
              [DECOMP], source_metric="value_moments")
    f = a["findings"][0]
    assert MISLABELLED in f["why"] and a["mislabelled"] == 1
    # the BINDING is sound — sources resolve, the figure matches. Only the label disagrees.
    assert f["bound"] is True and a["unresolved"] == 0 and a["value_mismatch"] == 0


def test_a_breakdown_row_is_addressable_on_its_own():
    """`r2:paid_search` names one number. Naming the whole breakdown instead is what let a
    ratio between two unrelated channels (2746.03 / 12786.81 = 0.2148) pass for a governed
    revenue-per-dollar figure."""
    a = audit([{"text": "paid search spend was 12,786.81",
                "sources": ["r2:paid_search"], "value": 12786.81}],
              [SPEND], source_metric="marketing_spend")
    assert a["bound"] == 1 and not a["findings"][0]["why"]
    b = audit([{"text": "return per dollar was 0.21", "sources": ["r2"], "value": 0.21}],
              [SPEND], source_metric="marketing_spend")
    assert UNRESOLVED in b["findings"][0]["why"], "a four-row breakdown names no single number"


def test_an_unsourced_claim_and_the_totals():
    a = audit([{"text": "engagement is down", "sources": []},
               {"text": "days per user fell", "sources": ["r1:days_per_user.pct_change"]},
               {"text": "invented", "sources": ["r9:nothing"]}],
              [DECOMP], source_metric="weekly_value_moments")
    assert a["n"] == 3 and a["bound"] == 1
    assert a["unsourced"] == 1 and a["unresolved"] == 1
    assert UNSOURCED in a["findings"][0]["why"]
    assert a["sources"] == 2, "distinct handles cited, however many fields of each"


# --- derived claims: a conclusion resting on other claims ------------------- #

def test_a_conclusion_cites_claims_and_inherits_the_weakest_premise():
    """The reconstruction found this shape in every diagnostic answer: three measurements, then
    a judgement comparing them. Before `premises` the judgement was recorded as one more figure
    — 7 of 21 "primary driver" claims cited only a percent change, which shows a metric fell
    but not that it contributed most."""
    steps = [DECOMP]
    claims = [
        {"text": "days per user fell 16.44%, share +1.42",
         "sources": ["r1:days_per_user.contribution_share"]},
        {"text": "active users rose, share −0.46",
         "sources": ["r1:active_users.pct_change"]},
        {"text": "days per user is the primary driver", "premises": ["c1", "c2"]},
    ]
    a = audit(claims, steps, source_metric="weekly_value_moments",
              influence_children={"reminder_open_rate"})
    assert a["n"] == 3 and a["bound"] == 3
    assert a["derived"] == 1, "the conclusion is derived, the two measurements are not"
    assert a["max_fan_in"] == 2 and a["max_depth"] == 1
    assert [f["strength"] for f in a["findings"]] == ["exact", "exact", "exact"]


def test_one_soft_premise_makes_the_whole_conclusion_soft():
    """Strength is computed from the tree, not chosen by the model. `reminder_open_rate` hangs
    off an INFLUENCE edge, so a claim citing it is correlational — and a conclusion resting on
    that claim inherits it, however exact its other premises are. The weakest link governs."""
    claims = [
        {"text": "days per user fell 16.44%", "sources": ["r1:days_per_user.pct_change"]},
        {"text": "reminder open rate fell 27.95%", "sources": ["r1:reminder_open_rate.pct_change"]},
        {"text": "reminders drove the frequency drop", "premises": ["c1", "c2"]},
    ]
    a = audit(claims, [DECOMP], source_metric="weekly_value_moments",
              influence_children={"reminder_open_rate", "new_signups", "activation_rate"})
    kinds = [f["strength"] for f in a["findings"]]
    assert kinds == ["exact", "correlational", "correlational"], kinds
    assert a["correlational"] == 2


def test_premises_may_only_point_backwards():
    """A graph that can cite forwards can cite in a circle, and then "does this hold" has no
    answer. Rejected here rather than detected later, and it costs the model nothing: it wrote
    the premises first."""
    for bad in (["c3"], ["c9"], ["nonsense"]):
        a = audit([{"text": "a", "sources": ["r1:pct_change"]},
                   {"text": "b", "sources": ["r1:value_a"]},
                   {"text": "circular", "premises": bad}],
                  [DECOMP], source_metric="weekly_value_moments")
        assert BAD_PREMISE in a["findings"][2]["why"], bad
        assert a["bad_premise"] == 1


def test_a_claim_that_names_nothing_at_all():
    a = audit([{"text": "engagement is down"}], [DECOMP], source_metric="weekly_value_moments")
    assert UNSOURCED in a["findings"][0]["why"] and a["bound"] == 0


def test_a_claim_may_compare_governed_numbers_but_not_compose_them():
    """The same rule governed_numbers applies to the served number, applied one level down.

    It was missing here, so a ratio of two DIFFERENT metrics passed the claim audit while being
    refused at the answer. That gap is how a composed DAU/MAU reached a user: the model wrote the
    figure into prose rather than the typed `value`, so the answer-level check stood down for want
    of a number, and the claim carrying it audited clean."""
    def result(handle, metric, value):
        return {"tool": "query_metric", "handle": handle, "error": False,
                "args": {"metric": metric}, "result_labels": [""], "result_values": [value]}

    # two different metrics, and their ratio
    cross = [result("r1", "active_users", 886.0), result("r2", "paying_users", 288.0)]
    a = audit([{"text": "DAU/MAU is 32.5%", "sources": ["r1", "r2"], "value": 288.0 / 886.0}],
              cross)
    assert COMPOSED in a["findings"][0]["why"] and a["composed"] == 1
    assert a["findings"][0]["bound"] is False

    # the SAME metric across two periods is a comparison, and stays legal
    same = [result("r1", "active_users", 836.0), result("r2", "active_users", 886.0)]
    for figure in ((886.0 - 836.0) / 836.0, (886.0 - 836.0) / 836.0 * 100, 50.0):
        b = audit([{"text": "up", "sources": ["r1", "r2"], "value": figure}], same)
        assert not b["findings"][0]["why"], (figure, b["findings"][0]["why"])

    # a figure reachable NO way from the citations is still a plain mismatch, not a composition —
    # the two are different faults and collapsing them would hide which one happened
    c = audit([{"text": "?", "sources": ["r1", "r2"], "value": 12345.0}], same)
    assert VALUE_MISMATCH in c["findings"][0]["why"] and c["composed"] == 0


# Last in the file, so a test added below it is a NameError here rather than a test that silently
# never runs. That is what this block cost once already: the composition test above was appended
# after it, so `bench test` reported a traceback and the reason code it pins went unexercised.
if __name__ == "__main__":
    test_a_field_citation_resolves_and_the_figure_must_match()
    test_a_bare_handle_does_not_name_a_number()
    test_the_wrong_metric_name_is_caught_where_no_number_check_could()
    test_a_breakdown_row_is_addressable_on_its_own()
    test_an_unsourced_claim_and_the_totals()
    test_a_conclusion_cites_claims_and_inherits_the_weakest_premise()
    test_one_soft_premise_makes_the_whole_conclusion_soft()
    test_premises_may_only_point_backwards()
    test_a_claim_that_names_nothing_at_all()
    test_a_claim_may_compare_governed_numbers_but_not_compose_them()
    print("OK - claim audit: field citation, bare handles, the wrong-metric catch, breakdown "
          "rows, derived claims, inherited strength, backwards-only premises, and comparing "
          "governed numbers without composing them all hold.")

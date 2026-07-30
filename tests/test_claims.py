"""Unit test for the claim audit — pure, no run and no model needed.

`audit()` resolves what an answer committed to against the trace it was built from. Every case
below is a shape seen in a live run, so the test pins behaviour rather than intention.

Run: PYTHONPATH=. uv run python tests/test_claims.py
"""

from __future__ import annotations

from agent.guardrails.claims import MISLABELLED, UNRESOLVED, UNSOURCED, VALUE_MISMATCH, audit

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


if __name__ == "__main__":
    test_a_field_citation_resolves_and_the_figure_must_match()
    test_a_bare_handle_does_not_name_a_number()
    test_the_wrong_metric_name_is_caught_where_no_number_check_could()
    test_a_breakdown_row_is_addressable_on_its_own()
    test_an_unsourced_claim_and_the_totals()
    print("OK - claim audit: field citation, bare handles, the wrong-metric catch, "
          "breakdown rows, and the totals all hold.")

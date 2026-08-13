"""The chain view — pure, no run and no model needed.

`chain_of` turns a stored row into what a reader is shown: each assertion above the evidence it
rests on. The tests below pin the two things that are easy to lose.

Run: PYTHONPATH=. uv run python engine/tests/test_chain.py
"""

from __future__ import annotations

from evidence import audit
from evidence.chain import chain_of
from evidence.render import measurement_text

DECOMP = {
    "tool": "decompose_change", "handle": "r1", "error": False,
    "args": {"node": "weekly_value_moments", "period_a": "prev_week", "period_b": "last_week"},
    "result_labels": ["pct_change", "days_per_user.pct_change",
                      "days_per_user.contribution_share", "reminder_open_rate.pct_change"],
    "result_values": [-0.1188, -0.1644, 1.4202, -0.2795],
}
CAUSAL = {"tool": "check_causal_evidence", "handle": "r2", "error": False,
          "args": {"driver": "reminder_open_rate", "outcome": "real_value_moments"},
          "result_labels": [], "result_values": []}


def _row(claims, source_metric="weekly_value_moments", steps=(DECOMP,)):
    a = audit(claims, list(steps), source_metric,
              node_metrics={"weekly_value_moments": "real_value_moments"},
              influence_children={"reminder_open_rate"})
    return {"question": "why did it drop?", "answer": "frequency", "outcome": "answer",
            "claims": claims, "claim_audit": a, "steps": list(steps),
            "source_metric": source_metric}


def test_the_chain_shows_provenance_and_never_a_verdict():
    """The restraint IS the design. The first version stamped NOT SUPPORTED across an answer that
    was substantively right — correct driver, correct hedge — because the model typed
    `value_moments` where it meant `weekly_value_moments`. A reader who sees one wrong red badge
    on an answer they can check themselves stops believing the green ones, and nothing measured so
    far says how often that would happen. So the chain reports facts and aggregates nothing.

    Pinned as a test because the pressure to add a badge will not go away."""
    ch = chain_of(_row([
        {"text": "value moments fell 11.88%", "sources": ["r1:pct_change"], "value": -0.1188},
        {"text": "days per user fell 16.44%, share 1.42",
         "sources": ["r1:days_per_user.pct_change", "r1:days_per_user.contribution_share"]},
        {"text": "frequency is the driver", "premises": ["c1", "c2"]},
    ]))
    rendered = " ".join(n.text + " " + " ".join(n.facts) for n in ch.nodes) + " ".join(ch.notes)
    for banned in ("TRUSTED", "NOT SUPPORTED", "QUESTIONABLE", "score", "%  confidence"):
        assert banned.lower() not in rendered.lower(), f"the chain rendered a verdict: {banned}"
    assert not hasattr(ch, "verdict") and not hasattr(ch, "score")

    # …and it does show the provenance, which is the whole point
    c2 = next(n for n in ch.nodes if n.id == "c2")
    assert [lk.ref for lk in c2.rests_on] == ["r1:days_per_user.pct_change",
                                              "r1:days_per_user.contribution_share"]
    assert all("decompose_change" in lk.origin for lk in c2.rests_on)
    c3 = next(n for n in ch.nodes if n.id == "c3")
    assert c3.kind == "conclusion" and c3.follows_from == ("c1", "c2")


def test_one_wrong_declaration_is_one_note_not_five_faults():
    """`mislabelled` compares each claim's evidence against the answer's SINGLE declared metric,
    so one wrong declaration flags every claim at once — 85 stored answers flag exactly five, from
    one root cause. Repeated per claim it reads as five separate faults and inflates the rate
    ~1.6x against a per-answer denominator. It is one fact about the answer and is said once."""
    claims = [{"text": f"claim {i}", "sources": ["r1:pct_change"]} for i in range(5)]
    row = _row(claims, source_metric="value_moments")
    assert row["claim_audit"]["mislabelled"] == 5, "the audit still counts every affected claim"

    ch = chain_of(row)
    per_claim = [f for n in ch.nodes for f in n.facts if "different" in f]
    assert per_claim == [], "the mislabel must not repeat on every claim"
    said = [n for n in ch.notes if "different governed definition" in n]
    assert len(said) == 1, ch.notes
    # and it names the definition the RESULTS came from, not every child metric they touch
    assert "weekly_value_moments" in said[0] and "days_per_user" not in said[0]


def test_correlational_is_reported_as_the_tree_s_word_not_the_model_s():
    ch = chain_of(_row([
        {"text": "reminder open rate fell 27.95%", "sources": ["r1:reminder_open_rate.pct_change"]},
        {"text": "so reminders caused it", "premises": ["c1"]},
    ]))
    for cid in ("c1", "c2"):
        n = next(x for x in ch.nodes if x.id == cid)
        assert any("influence" in f and "metric tree" in f for f in n.facts), (cid, n.facts)


def test_a_governed_statement_is_a_node_like_any_other():
    """What the tree DECLARES about an edge is evidence, and until handles were given to
    value-less results it had no address at all."""
    ch = chain_of(_row([
        {"text": "the tree carries this edge as low-confidence influence", "sources": ["r2"]},
    ], steps=(DECOMP, CAUSAL)))
    r2 = next(n for n in ch.nodes if n.id == "r2")
    assert "governed statement" in " ".join(r2.facts)
    c1 = next(n for n in ch.nodes if n.id == "c1")
    assert c1.rests_on[0].ref == "r2" and "check_causal_evidence" in c1.rests_on[0].origin
    assert c1.rests_on[0].note == "", "a statement resolves; it is not an unresolved citation"


def test_an_archived_row_whose_premises_are_positions_still_renders():
    """Rows written before claims carried explicit ids stored premises as raw POSITIONS — [0, 1]
    meaning the first and second claim. The chain promises every row ever written; pointed at a
    stored run for the first time it raised TypeError instead. Live runs alone would never have
    shown it, because live runs write the current shape."""
    archived = {
        "question": "why?", "answer": "frequency", "outcome": "answer",
        "claims": [{"text": "a"}, {"text": "b"}, {"text": "so frequency"}],
        "steps": [DECOMP],
        "claim_audit": {"n": 3, "bound": 3, "derived": 1, "max_depth": 1, "findings": [
            {"i": 0, "text": "a", "sources": ["r1:pct_change"], "bound": True, "strength": "exact",
             "premises": [], "why": []},
            {"i": 1, "text": "b", "sources": ["r1:days_per_user.pct_change"], "bound": True,
             "strength": "exact", "premises": [], "why": []},
            # no `id` key, and premises as ints — exactly as 2026-07-31 rows carry them
            {"i": 2, "text": "so frequency", "sources": [], "bound": True, "strength": "exact",
             "premises": [0, 1], "why": []},
        ]}}
    ch = chain_of(archived)
    concl = next(n for n in ch.nodes if n.kind == "conclusion")
    assert concl.id == "c3" and concl.follows_from == ("c1", "c2"), concl


def test_a_flat_list_says_so_and_an_unmeasured_answer_says_so():
    """Both are invisible otherwise. A wall of measurements with the verdict sitting among them
    looks exactly like an argument until you ask what rests on what."""
    flat = chain_of(_row([{"text": "a", "sources": ["r1:pct_change"]},
                          {"text": "b", "sources": ["r1:days_per_user.pct_change"]}]))
    assert any("list of findings, not a chain of reasoning" in n for n in flat.notes)

    bare = chain_of({"question": "q", "answer": "886", "outcome": "answer", "steps": [DECOMP]})
    assert any("declared no assertions" in n for n in bare.notes)
    assert [n.kind for n in bare.nodes] == ["call"], "an old row still renders its calls"


# --- rendered measurements ---------------------------------------------------- #

def test_a_rendered_measurement_says_only_what_its_citations_say():
    """The fix for arguments smuggled into measurements.

    A claim once read "...new signups fell 24.84% and activation_rate fell 28.93%, SO ACQUISITION
    SIGNALS WEAKENED BUT DID NOT CAUSE THE NET ENGAGEMENT DROP" while citing only those two
    figures. Those numbers cannot rule acquisition out — what rules it out is that breadth rose
    and its contribution is negative, a fact in a different claim this one never pointed at. It
    passed every check, because the numbers themselves were real and correctly cited.

    Detecting that means classifying English. Rendering makes it unsayable: the model names the
    values, the harness writes the sentence, and a measurement has no words the model chose."""
    steps = [DECOMP]
    text = measurement_text(["r1:days_per_user.pct_change",
                             "r1:days_per_user.contribution_share"], steps)
    assert text == "days_per_user changed by -16.44%, accounting for 1.42 of the change", text

    # a rise that CONTRIBUTES NEGATIVELY is the sentence readers get wrong, so it is spelled out
    steps2 = [{**DECOMP,
               "result_labels": ["active_users.value_a", "active_users.value_b",
                                 "active_users.pct_change", "active_users.contribution_share"],
               "result_values": [836.0, 886.0, 0.0598, -0.4593]}]
    rose = measurement_text(["r1:active_users.value_a", "r1:active_users.value_b",
                             "r1:active_users.pct_change",
                             "r1:active_users.contribution_share"], steps2)
    assert "rose from 836 to 886" in rose and "pushing the other way by 0.46" in rose, rose

    # a citation that resolves to nothing renders to nothing — the repair guardrail owns that
    # failure, and blanking the text here would hide the fault it exists to surface
    assert measurement_text(["r9:nope"], steps) is None


def test_a_claim_cannot_be_a_measurement_and_a_conclusion_at_once():
    """The distinction the whole design rests on — did you read this off the data, or work it out
    from what you already said — was not enforced anywhere. A claim could carry both and the audit
    had no opinion."""
    a = audit([{"text": "x", "sources": ["r1:days_per_user.pct_change"]},
               {"text": "both", "sources": ["r1:pct_change"], "premises": ["c1"]}], [DECOMP])
    assert a["mixed_support"] == 1
    assert a["findings"][1]["bound"] is False


def test_evidence_gathered_and_not_used_is_named():
    """An ORPHAN: a measurement the answer went and got, stated, and then concluded without.

    On the cross-domain question the agent measured new_signups falling 24.84% and concluded
    "primarily product, not acquisition" resting on three OTHER claims — so the assertion that
    acquisition is not to blame never cites the acquisition numbers. That is unsupported however
    deep the graph is, and it is checkable without reading a word of the prose. Across every
    stored answer that draws a conclusion, 162 of 823 measurements (20%) are orphans.
    """
    def row(findings):
        return {"question": "q", "answer": "a", "outcome": "answer", "steps": [DECOMP],
                "claims": [{} for _ in findings], "claim_audit": {
                    "n": len(findings), "bound": len(findings),
                    "derived": sum(1 for f in findings if f.get("premises")),
                    "findings": findings}}

    def m(cid, ref):
        return {"id": cid, "text": cid, "sources": [ref], "bound": True,
                "strength": "exact", "premises": [], "why": []}

    concluded = row([m("c1", "r1:pct_change"), m("c2", "r1:days_per_user.pct_change"),
                     {"id": "c3", "text": "so frequency", "sources": [], "bound": True,
                      "strength": "exact", "premises": ["c1"], "why": []}])
    ch = chain_of(concluded)
    assert {n.id: n.unused for n in ch.nodes if n.kind != "call"} == {
        "c1": False, "c2": True, "c3": False}
    assert any("c2 was measured and then not used" in n for n in ch.notes)

    # An answer that concludes NOTHING has no orphans — every measurement would be trivially
    # unused, and the "flat list" note already says the real thing about it.
    flat = row([m("c1", "r1:pct_change"), m("c2", "r1:days_per_user.pct_change")])
    ch2 = chain_of(flat)
    assert not [n for n in ch2.nodes if n.unused]
    assert any("list of findings, not a chain of reasoning" in n for n in ch2.notes)


# Last in the file, so a test added below it is a NameError here rather than a test that silently
# never runs. That is what this block cost once already: three tests were appended after it, and
# `bench test` reported a traceback while the behaviour they pin went unexercised.
if __name__ == "__main__":
    test_the_chain_shows_provenance_and_never_a_verdict()
    test_one_wrong_declaration_is_one_note_not_five_faults()
    test_correlational_is_reported_as_the_tree_s_word_not_the_model_s()
    test_a_governed_statement_is_a_node_like_any_other()
    test_an_archived_row_whose_premises_are_positions_still_renders()
    test_a_flat_list_says_so_and_an_unmeasured_answer_says_so()
    test_a_rendered_measurement_says_only_what_its_citations_say()
    test_a_claim_cannot_be_a_measurement_and_a_conclusion_at_once()
    test_evidence_gathered_and_not_used_is_named()
    print("OK — the chain shows provenance, names one mislabel once, carries the tree's own word "
          "for correlational, renders a measurement from its citations alone, names evidence "
          "gathered and not used, and renders a verdict nowhere.")

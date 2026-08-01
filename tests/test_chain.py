"""The chain view — pure, no run and no model needed.

`chain_of` turns a stored row into what a reader is shown: each assertion above the evidence it
rests on. The tests below pin the two things that are easy to lose.

Run: PYTHONPATH=. uv run python tests/test_chain.py
"""

from __future__ import annotations

from evidence import audit
from evidence.chain import chain_of

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


def test_a_flat_list_says_so_and_an_unmeasured_answer_says_so():
    """Both are invisible otherwise. A wall of measurements with the verdict sitting among them
    looks exactly like an argument until you ask what rests on what."""
    flat = chain_of(_row([{"text": "a", "sources": ["r1:pct_change"]},
                          {"text": "b", "sources": ["r1:days_per_user.pct_change"]}]))
    assert any("list of findings, not a chain of reasoning" in n for n in flat.notes)

    bare = chain_of({"question": "q", "answer": "886", "outcome": "answer", "steps": [DECOMP]})
    assert any("declared no assertions" in n for n in bare.notes)
    assert [n.kind for n in bare.nodes] == ["call"], "an old row still renders its calls"


if __name__ == "__main__":
    test_the_chain_shows_provenance_and_never_a_verdict()
    test_one_wrong_declaration_is_one_note_not_five_faults()
    test_correlational_is_reported_as_the_tree_s_word_not_the_model_s()
    test_a_governed_statement_is_a_node_like_any_other()
    test_a_flat_list_says_so_and_an_unmeasured_answer_says_so()
    print("OK — the chain shows provenance, names one mislabel once, carries the tree's own word "
          "for correlational, and renders a verdict nowhere.")

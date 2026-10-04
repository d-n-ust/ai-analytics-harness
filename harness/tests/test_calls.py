"""evals/calls.py: which governed calls an answer rests on."""
from evals.calls import call_use


def _step(handle, values, metric="app_opens"):
    return {"tool": "query_metric", "handle": handle, "args": {"metric": metric},
            "result_values": values, "result_labels": [""] * len(values)}


def test_values_basis_counts_a_call_used_when_its_number_is_in_the_answer():
    row = {"answer": "Android users opened the app 8,234 times in June 2026.",
           "steps": [_step("r1", [8234.0]), _step("r2", [11011.0])], "turns": []}
    use = call_use(row)
    assert (use["basis"], use["used"], use["unused"]) == ("values", [0], [1])


def test_claims_basis_reads_the_cited_handles_not_the_text():
    # The text restates nothing, so the values basis would find no used call; the claims do.
    row = {"answer": "See the breakdown above.",
           "claims": [{"text": "EMEA", "value": 4273.0, "sources": ["r2:EMEA"]}],
           "steps": [_step("r1", [8234.0]), _step("r2", [2562.0, 4273.0])], "turns": []}
    use = call_use(row)
    assert (use["basis"], use["used"], use["unused"]) == ("claims", [1], [0])


def test_a_failed_or_handleless_step_is_not_a_governed_call():
    row = {"answer": "8234", "turns": [],
           "steps": [{"tool": "query_metric", "error": True, "args": {}},
                     {"tool": "check_coverage", "handle": "r1", "result_values": [8234.0]}]}
    assert call_use(row)["used"] == [] and call_use(row)["unused"] == []


def test_spend_goes_to_the_turn_that_issued_the_call():
    row = {"answer": "8234", "model": "gpt-5-mini",
           "steps": [_step("r1", [8234.0]), _step("r2", [1.0])],
           "turns": [{"in": 1000, "out": 100, "calls": ["query_metric"]},
                     {"in": 1000, "out": 100, "calls": ["query_metric"]},
                     {"in": 1000, "out": 100, "calls": []}]}
    use = call_use(row)
    assert use["used_usd"] == use["unused_usd"] > 0

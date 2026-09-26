"""`parameter_grounding`: the mechanism half, proven without a model.

The model's selection is supplied as data, so each test pins what the MECHANISM does with it:
which values it applies, which it drops, and what it tells the answer to disclose.
"""
from __future__ import annotations

from agent.guardrails import parse_cell
from agent.guardrails.parameters import note_text, resolve

SURFACE = {
    "metric": "app_opens", "description": "App opens.", "agg": "sum",
    "filter": "activity__is_internal = false",
    "parameters": {"filters": {"dimensions": [
        {"name": "activity__platform", "members": ["android", "ios", "web", "unknown"], "description": ""},
        {"name": "activity__region", "members": ["APAC", "Americas", "EMEA"], "description": ""},
        {"name": "activity__channel", "members": ["organic", "referral"], "description": ""},
        {"name": "activity__is_internal", "members": [False, True], "description": ""}]}},
}
PRINCIPLES = [
    {"id": "trend_granularity", "slot": "time_grain", "target_points": [15, 40]},
    {"id": "canonical_segments", "slot": "group_by",
     "default": ["activity__platform", "activity__region", "activity__channel"],
     "disclose": "broken down by the standard business segments"},
]
Q_SEGMENT = "How did Android app opens break down by segment in June 2026?"


def _by(decisions, parameter):
    return [d for d in decisions if d["parameter"] == parameter]


def test_a_filter_the_question_does_not_state_is_dropped():
    """The q_004 defect: the model added is_internal = False with a basis that is not in the
    question, and it was labelled grounded. The quoted basis must be in the question."""
    selected = {"filters": [{"dimension": "activity__region", "member": "EMEA",
                             "basis": "exclude staff accounts"}],
                "period": {"value": "2026-06", "basis": "June 2026"}}
    queries, decisions = resolve(Q_SEGMENT, SURFACE, PRINCIPLES, selected, {"metric": "app_opens"})
    assert "filters" not in queries[0]
    assert _by(decisions, "filter")[0]["state"] == "dropped"


def test_a_filter_the_metric_already_applies_is_not_repeated():
    selected = {"filters": [{"dimension": "activity__is_internal", "member": "False",
                             "basis": "Android"}], "period": {"value": "2026-06", "basis": "June 2026"}}
    queries, decisions = resolve(Q_SEGMENT, SURFACE, PRINCIPLES, selected, {"metric": "app_opens"})
    assert "filters" not in queries[0]
    assert "already applies" in _by(decisions, "filter")[0]["why"]


def test_canonical_segments_skips_a_dimension_the_question_fixes():
    """The q_003 defect: grouping by platform when the question filters one platform returns a
    single row."""
    selected = {"filters": [{"dimension": "activity__platform", "member": "android", "basis": "Android"}],
                "group_by": {"principle": "canonical_segments", "basis": "by segment"},
                "period": {"value": "2026-06", "basis": "June 2026"}}
    queries, _ = resolve(Q_SEGMENT, SURFACE, PRINCIPLES, selected, {"metric": "app_opens"})
    assert [q["group_by"] for q in queries] == [["activity__region", "activity__channel"]]
    assert queries[0]["filters"] == {"activity__platform": "android"}


def test_a_separate_principle_runs_one_query_per_dimension():
    """"The standard segments" are three views read side by side. One group_by over all of them
    returns every combination, which is a different table."""
    separate = [dict(p, combine="separate") if p["id"] == "canonical_segments" else p for p in PRINCIPLES]
    selected = {"filters": [{"dimension": "activity__platform", "member": "android", "basis": "Android"}],
                "group_by": {"principle": "canonical_segments", "basis": "by segment"},
                "period": {"value": "2026-06", "basis": "June 2026"}}
    queries, _ = resolve(Q_SEGMENT, SURFACE, separate, selected, {"metric": "app_opens"})
    assert [q["group_by"] for q in queries] == [["activity__region"], ["activity__channel"]]


def test_trend_granularity_is_computed_by_the_mechanism():
    q = "How did Android app opens change over the first half of 2026?"
    selected = {"filters": [{"dimension": "activity__platform", "member": "android", "basis": "Android"}],
                "group_by": {"dimensions": ["metric_time"], "basis": "change over"},
                "time_grain": {"value": "none", "principle": "trend_granularity", "basis": "none"},
                "period": {"value": "2026-H1", "basis": "first half of 2026"}}
    queries, decisions = resolve(q, SURFACE, PRINCIPLES, selected, {"metric": "app_opens"})
    assert queries[0]["time_grain"] == "week"          # 181 days: 26 weekly points, inside 15-40
    assert _by(decisions, "time_grain")[0]["basis"] == "governed_principle"


def test_a_phrase_with_no_documented_member_is_queried_as_itself_and_flagged():
    """The model mapped "TikTok" to `organic` and the agent served organic's figure as TikTok's.
    Nothing in the layer documents TikTok as organic, so the mapping is not licensed: the query
    runs with the phrase itself, which matches nothing, and the note says why."""
    q = "How many app opens came from TikTok in Q2 2026?"
    selected = {"filters": [{"dimension": "activity__channel", "member": "organic", "basis": "TikTok"}],
                "period": {"value": "2026-Q2", "basis": "Q2 2026"}}
    queries, decisions = resolve(q, SURFACE, PRINCIPLES, selected, {"metric": "app_opens"})
    assert queries[0]["filters"] == {"activity__channel": "TikTok"}
    assert _by(decisions, "filter")[0]["state"] == "invalid"
    assert "no member of activity__channel is documented as 'TikTok'" in note_text(decisions)


def test_a_documented_synonym_is_licensed():
    """The description is the governed registry: 'content_seo is content marketing and SEO'."""
    surface = {**SURFACE, "parameters": {"filters": {"dimensions": [
        {"name": "activity__channel", "members": ["content_seo", "organic"],
         "description": "content_seo is content marketing and SEO; organic is organic"}]}}}
    q = "How many app opens came from SEO in Q2 2026?"
    selected = {"filters": [{"dimension": "activity__channel", "member": "organic", "basis": "SEO"}],
                "period": {"value": "2026-Q2", "basis": "Q2 2026"}}
    queries, decisions = resolve(q, surface, PRINCIPLES, selected, {"metric": "app_opens"})
    assert queries[0]["filters"] == {"activity__channel": "content_seo"}
    assert _by(decisions, "filter")[0]["state"] == "applied"


def test_the_note_marks_governed_decisions_for_disclosure():
    """The metric's own filter is the decision a reader never sees unless told."""
    _, decisions = resolve(Q_SEGMENT, SURFACE, PRINCIPLES,
                           {"period": {"value": "2026-06", "basis": "June 2026"}}, {"metric": "app_opens"})
    note = note_text(decisions)
    assert "DISCLOSE: metric_filter = activity__is_internal = false" in note
    assert "DISCLOSE: period" not in note          # stated in the question, so the reader knows it


def test_the_arms_parse_as_cells():
    assert parse_cell("R3+parameter_grounding").label() == "R3+parameter_grounding"
    assert parse_cell("R3+disclose_assumptions").label() == "R3+disclose_assumptions"


# ── the third level: ungrounded means ask, never assume ──────────────────────────────────────────

def test_a_question_with_no_period_does_not_run():
    """The agent once chose a period itself and the step disclosed it afterwards. That is a guess
    with a footnote. No query runs; the note tells the agent to ask."""
    q = "How many times did Android users open the app?"
    selected = {"filters": [{"dimension": "activity__platform", "member": "android", "basis": "Android"}],
                "period": {"value": "", "basis": "none"}}
    queries, decisions = resolve(q, SURFACE, PRINCIPLES, selected,
                                 {"metric": "app_opens", "period": "last_month"})
    assert queries == []
    assert [d["parameter"] for d in decisions if d["state"] == "ungrounded"] == ["period"]
    assert "did NOT run" in note_text(decisions) and "clarify" in note_text(decisions)


def test_current_is_a_grounded_period_and_omits_the_window():
    q = "How many Android users do we have right now?"
    selected = {"period": {"value": "current", "basis": "right now"}}
    queries, _ = resolve(q, SURFACE, PRINCIPLES, selected, {"metric": "app_opens"})
    assert queries == [{"metric": "app_opens"}]


def test_a_phrase_several_members_could_mean_is_asked_about():
    surface = {**SURFACE, "parameters": {"filters": {"dimensions": [
        {"name": "activity__channel", "members": ["paid_search", "paid_social", "organic", "referral"],
         "description": ""}]}}}
    q = "How many app opens came from paid in Q2 2026?"
    selected = {"filters": [{"dimension": "activity__channel", "member": "paid_search", "basis": "paid"}],
                "period": {"value": "2026-Q2", "basis": "Q2 2026"}}
    queries, decisions = resolve(q, surface, PRINCIPLES, selected, {"metric": "app_opens"})
    assert queries == []
    assert "could mean any of" in _by(decisions, "filter")[0]["why"]


def test_a_trend_with_no_grain_and_no_rule_is_asked_about():
    """Leaving the grain unset let the engine's default apply silently."""
    q = "How did Android app opens change over the first half of 2026?"
    selected = {"group_by": {"dimensions": ["metric_time"], "basis": "change over"},
                "time_grain": {"value": "none", "principle": "none", "basis": "none"},
                "period": {"value": "2026-H1", "basis": "first half of 2026"}}
    queries, decisions = resolve(q, SURFACE, [], selected, {"metric": "app_opens"})
    assert queries == [] and _by(decisions, "time_grain")[0]["state"] == "ungrounded"


def test_the_model_can_declare_a_parameter_ungrounded():
    q = "How many app opens did Android users have in the summer?"
    selected = {"period": {"value": "", "basis": "none"},
                "ungrounded": [{"parameter": "period", "why": "no year, and summer's months are not defined"}]}
    queries, decisions = resolve(q, SURFACE, PRINCIPLES, selected, {"metric": "app_opens"})
    assert queries == []
    assert len([d for d in decisions if d["state"] == "ungrounded"]) == 1    # declared once

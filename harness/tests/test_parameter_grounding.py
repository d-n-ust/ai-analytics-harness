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
    # (this rule has no `buckets_within_period`, so a grain that crosses the edges is still allowed)
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


# ── the two variants of the evidence check: tolerant_quotes and quote_retry ──────────────────────
from agent.core.conversation import ToolCall, Turn, Usage
from agent.guardrails import parameters as P
from agent.guardrails import incoherent


def test_tolerant_matching_accepts_ordinary_variation_and_still_rejects_other_words():
    q = "How many times did Andriod users open the app in June of 2026?"
    for quote in ("Android user", "June 2026", "Jun 2026"):      # typo, plural, gap, abbreviation
        assert not P._in_question(quote, q)
        assert P._in_question(quote, q, tolerant=True), quote
    for quote in ("iOS users", "June 2025", "July 2026", "last month"):
        assert not P._in_question(quote, q, tolerant=True), quote   # a different value stays out


class _Scripted:
    """Answers the grounding call from a list of selections, one per call, and counts calls."""

    def __init__(self, *selections):
        self.selections, self.calls, self.prompts = list(selections), 0, []

    def respond(self, convo, tools, force_tool=None, temperature=None):
        self.prompts.append(convo.entries[0][1])
        self.calls += 1
        return Turn.of("", [ToolCall("c", "select_parameters", self.selections.pop(0))], Usage(100, 10, 0))


def _ground(model, question, retry):
    original = P.surface_for
    P.surface_for = lambda *_: SURFACE
    try:
        return P.ground(model, question, {"metric": "app_opens"}, None, None, None, {}, retry=retry)
    finally:
        P.surface_for = original


Q = "How many times did Android users open the app in June 2026?"
_MISQUOTED = {"filters": [{"dimension": "activity__platform", "member": "android", "basis": "mobile Android"}],
              "period": {"value": "2026-06", "basis": "June 2026"}}
_FIXED = {"filters": [{"dimension": "activity__platform", "member": "android", "basis": "Android"}],
          "period": {"value": "2026-06", "basis": "June 2026"}}


def test_without_retry_a_misquoted_filter_is_dropped_and_the_query_runs_wider():
    """The current behaviour, kept as the baseline: the number silently covers every platform."""
    queries, decisions, _ = _ground(_Scripted(_MISQUOTED), Q, retry=False)
    assert queries == [{"metric": "app_opens", "period": "2026-06"}]
    assert [d["state"] for d in decisions if d["parameter"] == "filter"] == ["dropped"]


def test_retry_recovers_when_the_model_corrects_its_quote():
    model = _Scripted(_MISQUOTED, _FIXED)
    queries, decisions, usage = _ground(model, Q, retry=True)
    assert model.calls == 2 and "you quoted 'mobile Android'" in model.prompts[1]
    assert queries[0]["filters"] == {"activity__platform": "android"}
    assert usage.input == 200                                 # both calls are charged


def test_retry_asks_instead_of_dropping_when_the_quote_is_still_wrong():
    queries, decisions, _ = _ground(_Scripted(_MISQUOTED, _MISQUOTED), Q, retry=True)
    assert queries == []                                      # no query: the agent must ask
    assert "even after one retry" in [d for d in decisions if d["parameter"] == "filter"][0]["why"]


def test_a_quote_of_none_is_not_retried():
    """'none' means the model itself says the question does not ask for it: a correct drop."""
    unrequested = {"filters": [{"dimension": "activity__region", "member": "EMEA", "basis": "none"}],
                   "period": {"value": "2026-06", "basis": "June 2026"}}
    model = _Scripted(unrequested)
    queries, _, _ = _ground(model, Q, retry=True)
    assert model.calls == 1 and queries == [{"metric": "app_opens", "period": "2026-06"}]


def test_the_variants_need_parameter_grounding():
    assert incoherent(parse_cell("R3+tolerant_quotes"))
    assert incoherent(parse_cell("R3+parameter_grounding+quote_retry")) is None


# ── decision_grounding: the policy applied to a decision model's answers ─────────────────────────
import datetime as _dt

from agent.guardrails import decisions as DG

_LO, _HI = _dt.date(2025, 9, 5), _dt.date(2026, 7, 12)
_MEMBERS = {"filter:activity__platform": {"android": "android", "ios": "ios", "web": "web"}}


def _answers(**choices):
    """{question: (choice, probability)} in the Decisions API's answer shape."""
    return {q: {"choice": c, "probabilities": {c: p}} for q, (c, p) in choices.items()}


def test_decision_grounding_runs_confident_choices():
    a = _answers(**{"filter:activity__platform": ("android", 0.99), "shape": ("total", 1.0),
                    "period": ("2026-06", 0.97)})
    queries, _ = DG.resolve(a, SURFACE, PRINCIPLES, _MEMBERS, {"metric": "app_opens"}, _LO, _HI)
    assert queries == [{"metric": "app_opens", "filters": {"activity__platform": "android"}, "period": "2026-06"}]


def test_decision_grounding_refuses_a_value_the_layer_lacks():
    a = _answers(**{"filter:activity__platform": ("not_in_list", 0.98), "shape": ("total", 1.0),
                    "period": ("2026-06", 0.97)})
    queries, decisions = DG.resolve(a, SURFACE, PRINCIPLES, _MEMBERS, {"metric": "app_opens"}, _LO, _HI)
    assert queries == [] and [d["reason"] for d in decisions if d["state"] == "refuse"] == ["ungoverned_dimension_value"]


def test_decision_grounding_asks_when_unsure_or_when_the_period_is_missing():
    unsure = _answers(**{"filter:activity__platform": ("android", 0.55), "shape": ("total", 1.0),
                         "period": ("2026-06", 0.97)})
    missing = _answers(**{"shape": ("total", 1.0), "period": ("not_mentioned", 0.95)})
    for a in (unsure, missing):
        queries, decisions = DG.resolve(a, SURFACE, PRINCIPLES, _MEMBERS, {"metric": "app_opens"}, _LO, _HI)
        assert queries == [] and any(d["state"] == "ungrounded" for d in decisions)


def test_decision_grounding_applies_the_segment_rule_by_code():
    separate = [dict(p, combine="separate") if p["id"] == "canonical_segments" else p for p in PRINCIPLES]
    a = _answers(**{"filter:activity__platform": ("android", 0.99), "shape": ("breakdown", 1.0),
                    "breakdown": ("canonical_segments", 0.95), "period": ("2026-06", 0.97)})
    queries, _ = DG.resolve(a, SURFACE, separate, _MEMBERS, {"metric": "app_opens"}, _LO, _HI)
    assert [q["group_by"] for q in queries] == [["activity__region"], ["activity__channel"]]


def test_period_options_cover_the_window_and_nothing_else():
    periods = DG._periods(_LO, _HI)
    assert "2025-09" in periods and "2026-07" in periods and "2025-08" not in periods
    assert "2026-H1" in periods and "2026-Q2" in periods and "2025-H1" not in periods


def test_trend_buckets_must_line_up_with_the_period():
    """The engine answers "H1 by week" with whole weeks, so its first and last points include days
    outside the half-year. With `buckets_within_period`, a grain that crosses the edges is not used."""
    rule = {"id": "trend_granularity", "slot": "time_grain", "target_points": [15, 40],
            "buckets_within_period": True}
    grain, points, days, disclose = P._trend_grain(rule, "2026-H1")   # 1 Jan 2026 is a Thursday
    assert (grain, points, days) == ("month", 6, 181)
    assert "Week buckets were not used" in disclose
    assert P._trend_grain({**rule, "buckets_within_period": False}, "2026-H1")[0] == "week"
    assert P._lines_up("week", __import__("datetime").date(2026, 6, 1), __import__("datetime").date(2026, 6, 28))


# ── runtime governance: a contested metric is routed to the requester team's definition ──────────
GOV = {"requester": {"team": "Product"},
       "measures": {"active_users": {"owner": "Product"}, "active_accounts": {"owner": "Platform"}},
       "relationships": [{"id": "rel_active_user_definition", "type": "contested",
                          "members": ["active_users", "active_accounts"], "means": "Differ on internal accounts."}]}


def test_a_contested_metric_is_routed_to_the_requester_teams_definition():
    for asked in ("active_users", "active_accounts"):
        metric, decision = P.route_metric(asked, GOV)
        assert metric == "active_users" and decision["basis"] == "governed_principle"
        assert "owned by Product" in decision["disclose"]


def test_without_a_requester_the_contested_metric_is_ungrounded():
    metric, decision = P.route_metric("active_accounts", {**GOV, "requester": {}})
    assert metric == "active_accounts" and decision["state"] == "ungrounded"


def test_an_uncontested_metric_passes_through():
    assert P.route_metric("app_opens", GOV) == ("app_opens", None)


def test_a_small_unsure_choice_shows_every_reading_instead_of_asking():
    """show_small_choice_sets: 'customer' may or may not exclude staff (two readings), so both run."""
    small = PRINCIPLES + [{"id": "show_small_choice_sets", "slot": "any", "max_options": 3}]
    members = {**_MEMBERS, "filter:activity__is_internal": {"false": False, "true": True}}
    a = _answers(**{"filter:activity__platform": ("android", 0.99), "shape": ("total", 1.0),
                    "period": ("2026-06", 0.97)})
    a["filter:activity__is_internal"] = {"choice": "false", "probabilities": {"false": 0.6, "not_mentioned": 0.38}}
    queries, decisions = DG.resolve(a, {**SURFACE, "filter": None}, small, members, {"metric": "app_opens"}, _LO, _HI)
    assert [q["filters"] for q in queries] == [{"activity__platform": "android", "activity__is_internal": False},
                                               {"activity__platform": "android"}]
    assert any("show_small_choice_sets" in d["why"] for d in decisions)


def test_without_the_rule_an_unsure_choice_still_asks():
    members = {**_MEMBERS, "filter:activity__is_internal": {"false": False, "true": True}}
    a = _answers(**{"shape": ("total", 1.0), "period": ("2026-06", 0.97)})
    a["filter:activity__is_internal"] = {"choice": "false", "probabilities": {"false": 0.6, "not_mentioned": 0.38}}
    queries, _ = DG.resolve(a, {**SURFACE, "filter": None}, PRINCIPLES, members, {"metric": "app_opens"}, _LO, _HI)
    assert queries == []


def test_the_rules_are_rendered_for_the_agent():
    text = P.rules_text({"methodological_rules": [{"id": "canonical_segments", "when": "a breakdown names no dimension",
                                                   "default": ["activity__region", "activity__channel"]},
                                                  {"id": "show_small_choice_sets", "when": "few options", "max_options": 3}],
                         "requester": {"team": "Product"}})
    assert "Use activity__region, activity__channel" in text and "up to 3" in text and "Product" in text

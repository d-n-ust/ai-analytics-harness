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


_BACK = {"mode:activity__platform": ("activity__platform", "mode"),
         "lacks:activity__platform": ("activity__platform", "lacks"),
         **{f"named:activity__platform:{i}": ("activity__platform", m) for i, m in enumerate(["android", "ios", "web", "unknown"])},
         "mode:activity__is_internal": ("activity__is_internal", "mode"),
         **{f"named:activity__is_internal:{i}": ("activity__is_internal", m) for i, m in enumerate([False, True])},
         **{f"period:{p}": ("period", p) for p in ("2026-04", "2026-05", "2026-06", "2026-Q2", "2026-H1")}}


_ONLY = ("only", 0.99)


def _read(yes=None, shape=("total", 1.0), principles=PRINCIPLES, surface=SURFACE, platform=None, **choices):
    """A reading from decision-model answers: `yes` maps a yes/no question to its probability, and
    `platform` is how the question restricts the platform (only / except / none / unlisted)."""
    answers = {k: {"noul": p} for k, p in (yes or {}).items()}
    if platform is None and any(k.startswith("named:activity__platform") for k in yes or {}):
        platform = _ONLY
    for q, (c, p) in {"shape": shape, **({"mode:activity__platform": platform} if platform else {}),
                      **choices}.items():
        answers[q] = {"choice": c, "probabilities": {c: p}}
    return DG.read(answers, surface, principles, _BACK, _LO, _HI)


_ANDROID_JUNE = {"named:activity__platform:0": 0.99, "period:2026-06": 0.97}


def test_a_call_the_question_allows_runs_as_asked_and_missing_values_are_filled():
    reading = _read(_ANDROID_JUNE)
    asked = {"metric": "app_opens", "filters": {"activity__platform": "Android"}, "period": "2026-06"}
    assert DG.check(reading, asked)[0] == [{"metric": "app_opens", "filters": {"activity__platform": "android"},
                                            "period": "2026-06"}]
    assert DG.check(reading, {"metric": "app_opens"})[0] == DG.check(reading, asked)[0]


def test_two_periods_are_both_allowed_and_a_call_for_either_runs_as_asked():
    """r_007: "June compared with May". The second call ran as June when one reading replaced every
    call; now each call keeps its own period, and a call naming no period runs once per period."""
    reading = _read({"named:activity__platform:0": 0.99, "period:2026-06": 0.96, "period:2026-05": 0.95})
    may = DG.check(reading, {"metric": "app_opens", "period": "2026-05"})[0]
    assert [q["period"] for q in may] == ["2026-05"]
    assert sorted(q["period"] for q in DG.check(reading, {"metric": "app_opens"})[0]) == ["2026-05", "2026-06"]


def test_a_value_outside_the_question_blocks_the_call_and_names_what_is_allowed():
    reading = _read(_ANDROID_JUNE)
    for asked in ({"metric": "app_opens", "period": "2026-04"},
                  {"metric": "app_opens", "filters": {"activity__platform": "ios"}},
                  {"metric": "app_opens", "group_by": ["activity__country"]}):
        queries, decisions = DG.check(reading, asked)
        assert queries == [] and [d["state"] for d in decisions][-1] == "outside"
    assert "2026-06" in DG.check(reading, {"metric": "app_opens", "period": "2026-04"})[1][-1]["why"]


def test_not_android_reads_as_one_filter_over_every_other_platform():
    """r_006: "users not on Android" names Android to leave out. One number is asked for, so the
    reading is ONE filter, an IN list, rather than three readings to show separately."""
    reading = _read({"named:activity__platform:0": 0.98, "period:2026-06": 0.97}, platform=("except", 1.0))
    others = ["ios", "web", "unknown"]
    assert reading["filters"]["activity__platform"] == [others]
    assert DG.check(reading, {"metric": "app_opens", "filters": {"activity__platform": "android"}})[0] == []
    assert DG.check(reading, {"metric": "app_opens"})[0] == [
        {"metric": "app_opens", "filters": {"activity__platform": others}, "period": "2026-06"}]
    assert DG.check(reading, {"metric": "app_opens", "filters": {"activity__platform": ["web", "iOS", "unknown"]}})[0]


def test_two_named_values_are_two_readings():
    reading = _read({"named:activity__platform:0": 0.98, "named:activity__platform:1": 0.97, "period:2026-06": 0.97})
    assert sorted(q["filters"]["activity__platform"] for q in DG.check(reading, {"metric": "app_opens"})[0]) == ["android", "ios"]


def test_a_period_and_the_periods_that_fill_it_are_one_period():
    """A yes to Q2 and to its three months is Q2 said twice; a yes to Q2 beside June and May only
    is a longer period that overlaps them, and is dropped."""
    q2 = _read({"period:2026-Q2": 0.95, "period:2026-04": 0.9, "period:2026-05": 0.9, "period:2026-06": 0.9})
    assert q2["periods"] == ["2026-Q2"]
    pair = _read({"period:2026-Q2": 0.8, "period:2026-05": 0.9, "period:2026-06": 0.9})
    assert pair["periods"] == ["2026-05", "2026-06"]


def test_decision_grounding_refuses_a_value_the_layer_lacks():
    reading = _read({"period:2026-06": 0.97}, platform=("unlisted", 0.98))
    queries, decisions = DG.check(reading, {"metric": "app_opens"})
    assert queries == [] and [d["reason"] for d in decisions if d["state"] == "refuse"] == ["ungoverned_dimension_value"]


def test_decision_grounding_asks_when_unsure_or_when_the_period_is_missing():
    for reading in (_read({"named:activity__platform:0": 0.55, "period:2026-06": 0.97}), _read({})):
        queries, decisions = DG.check(reading, {"metric": "app_opens", "period": "2026-06"})
        assert queries == [] and any(d["state"] == "ungrounded" for d in decisions)


def test_decision_grounding_applies_the_segment_rule_by_code():
    separate = [dict(p, combine="separate") if p["id"] == "canonical_segments" else p for p in PRINCIPLES]
    reading = _read(_ANDROID_JUNE, shape=("breakdown", 1.0), principles=separate,
                    breakdown=("canonical_segments", 0.95))
    queries, _ = DG.check(reading, {"metric": "app_opens"})
    assert [q["group_by"] for q in queries] == [["activity__region"], ["activity__channel"]]
    asked_both = DG.check(reading, {"metric": "app_opens", "group_by": ["activity__channel", "activity__region"]})[0]
    assert sorted(q["group_by"][0] for q in asked_both) == ["activity__channel", "activity__region"]


def test_uncovered_names_what_the_used_calls_leave_out():
    """The answer-side check: the calls an answer used must cover every value the question names."""
    reading = _read({"named:activity__platform:0": 0.99, "period:2026-06": 0.96, "period:2026-05": 0.95})
    june = {"metric": "app_opens", "filters": {"activity__platform": "android"}, "period": "2026-06"}
    assert DG.uncovered(reading, [june]) == [("period 2026-05", {**june, "period": "2026-05"})]
    assert DG.uncovered(reading, [june, {**june, "period": "2026-05"}]) == []
    segments = _read(_ANDROID_JUNE, shape=("breakdown", 1.0), breakdown=("canonical_segments", 0.95))
    by_channel = {**june, "group_by": ["activity__channel"]}
    assert DG.uncovered(segments, [by_channel]) == [("the breakdown by region", {**june, "group_by": ["activity__region"]})]


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


# ── runtime governance: a fork declared in the layer (meta.terms), resolved by preflight ───────────
from pathlib import Path as _Path
from types import SimpleNamespace

from agent.guardrails import forks as F

_LAYER = SimpleNamespace(spec_dir=_Path(__file__).resolve().parents[1] / "experiments" / "07_semantic_layer_grounding"
             / "fixture" / "layer")


def _gov(team):
    return {"requester": {"team": team}} if team else {}


def test_a_declared_fork_is_routed_to_the_requester_teams_reading():
    """"users": active_users answers for Product, active_accounts for Platform (meta.terms)."""
    for asked in ("active_users", "active_accounts"):
        metric, decision = P.route_metric(asked, _gov("Product"), _LAYER)
        assert metric == "active_users" and decision["basis"] == "governed_principle"
        assert "For the Product team it means active_users" in decision["disclose"]
        assert "active_accounts" in decision["disclose"], "the other governed reading is disclosed"
    assert P.route_metric("active_users", _gov("Platform"), _LAYER)[0] == "active_accounts"


def test_without_a_requester_the_declared_fork_is_the_users_choice():
    metric, decision = P.route_metric("active_accounts", _gov(None), _LAYER)
    assert metric == "active_accounts" and decision["state"] == "ungrounded"


def test_a_fork_declared_show_all_keeps_the_metric_and_names_the_other_reading():
    """h_018: both spend metrics answer "marketing spend" always, so both figures are shown."""
    metric, decision = P.route_metric("marketing_spend", _gov("Product"), _LAYER)
    assert metric == "marketing_spend" and "show every one" in decision["disclose"]
    assert [m for m, _r, _t in F.companions("marketing_spend", "Product", _LAYER)] == ["acquisition_spend"]


def test_a_metric_in_no_declared_fork_passes_through():
    assert P.route_metric("app_opens", _gov("Product"), _LAYER) == ("app_opens", None)


def test_a_small_unsure_choice_shows_every_reading_instead_of_asking():
    """show_small_choice_sets: 'customer' may or may not exclude staff (two readings), so both run."""
    small = PRINCIPLES + [{"id": "show_small_choice_sets", "slot": "any", "max_options": 3}]
    reading = _read({**_ANDROID_JUNE, "named:activity__is_internal:0": 0.6}, principles=small,
                    surface={**SURFACE, "filter": None}, **{"mode:activity__is_internal": ("only", 0.6)})
    assert reading["filters"]["activity__is_internal"] == [False], "'none' was not plausible: no such reading"
    answers_none = {"mode:activity__is_internal": {"choice": "only", "probabilities": {"only": 0.6, "none": 0.4}},
                    "named:activity__is_internal:0": {"noul": 0.6}, "named:activity__platform:0": {"noul": 0.99},
                    "mode:activity__platform": {"choice": "only", "probabilities": {"only": 0.99}},
                    "period:2026-06": {"noul": 0.97}, "shape": {"choice": "total", "probabilities": {"total": 1.0}}}
    reading = DG.read(answers_none, {**SURFACE, "filter": None}, small, _BACK, _LO, _HI)
    queries, decisions = DG.check(reading, {"metric": "app_opens"})
    assert [q["filters"] for q in queries] == [{"activity__platform": "android", "activity__is_internal": False},
                                               {"activity__platform": "android"}]
    assert any("show_small_choice_sets" in d["why"] for d in decisions)


def test_without_the_rule_an_unsure_choice_still_asks():
    reading = _read({**_ANDROID_JUNE, "named:activity__is_internal:0": 0.6}, surface={**SURFACE, "filter": None},
                    **{"mode:activity__is_internal": ("only", 0.6)})
    assert DG.check(reading, {"metric": "app_opens"})[0] == []


def test_the_rules_are_rendered_for_the_agent():
    text = P.rules_text({"methodological_rules": [{"id": "canonical_segments", "when": "a breakdown names no dimension",
                                                   "default": ["activity__region", "activity__channel"]},
                                                  {"id": "show_small_choice_sets", "when": "few options", "max_options": 3}],
                         "requester": {"team": "Product"}})
    assert "Use activity__region, activity__channel" in text and "up to 3" in text and "Product" in text


# ── decision_plan: the terminal action is written by the mechanism ────────────────────────────────
from agent.core.conversation import ToolResult as _TR


def test_the_answer_copies_every_returned_value_and_states_the_filter_in_plain_words():
    gov = {"measures": {"app_opens": {"segment": "customers"}},
           "segments": {"customers": {"means": "real customers, excluding staff and test accounts."}}}
    q = {"metric": "app_opens", "filters": {"activity__platform": "android"}, "group_by": ["metric_time"],
         "time_grain": "month", "period": "2026-H1"}
    r = _TR("", values=[5674.0, 1922.0], labels=["2026-05-01 00:00:00", "2026-01-01 00:00:00"])
    d = [{"parameter": "metric_filter", "basis": "governed_declaration", "disclose": "app_opens applies x"}]
    text = DG.answer_text("app_opens", [q], [r], d, gov)
    assert "2026-01 1,922; 2026-05 5,674" in text              # copied, sorted, month labels
    assert "excluding staff and test accounts" in text         # plain words, from governance


def test_the_refusal_quotes_the_question_and_names_plain_dimensions():
    d = [{"parameter": "filter", "state": "refuse", "reason": "ungoverned_dimension_value",
          "why": "it names a channel value the layer does not have"}]
    reason, text = DG.refusal_text(d, None, "How many app opens came from TikTok?")
    assert reason == "ungoverned_dimension_value" and '"How many app opens came from TikTok?"' in text


def test_a_cause_question_is_declined_not_answered():
    queries, decisions = DG.check(_read(_ANDROID_JUNE, shape=("cause", 0.95)), {"metric": "app_opens"})
    assert queries == [] and [d["reason"] for d in decisions if d["state"] == "refuse"] == ["no_causal_evidence"]


# ── the answer side: a list written as one claim, and a value the answer leaves out ────────────────
from types import SimpleNamespace as _NS

from agent.gates import claims as _claims_gate
from agent.gates import reading as _coverage_gate


def _gate_run(steps, grounded=None, repair=True):
    return _NS(steps=steps, repairs=[], acts=[], claim_retries=0, grounded=grounded or {},
               _audit_context=lambda: {},
               grounding=_NS(protocol=_NS(repair=repair),
                             toolbox=_NS(g=_NS(decision_grounding=True))))


_BY_REGION = {"tool": "query_metric", "handle": "r1", "error": False,
              "args": {"metric": "app_opens", "group_by": ["activity__region"], "period": "2026-06"},
              "result_values": [4273.0, 2562.0, 1397.0], "result_labels": ["EMEA", "Americas", "APAC"]}


def test_a_claim_that_lists_several_figures_is_handed_back():
    """q_003 (claims on): one claim cited three regions and stated 0, which the reader and the grader
    both read as the figure. A claim holds one figure, so a list is handed back as a form error."""
    listed = _NS(name="answer", args={"answer": "See below.", "claims": [
        {"text": "EMEA 4,273; Americas 2,562; APAC 1,397", "sources": ["r1:EMEA", "r1:Americas", "r1:APAC"],
         "value": 0}]})
    run = _gate_run([_BY_REGION])
    handed = _claims_gate.malformed_claims(run, listed)
    assert handed is not None and "one claim per figure" in handed.content
    one_each = _NS(name="answer", args={"answer": "See below.", "claims": [
        {"text": "EMEA 4,273", "sources": ["r1:EMEA"], "value": 4273}]})
    assert _claims_gate.malformed_claims(_gate_run([_BY_REGION]), one_each) is None


def test_an_answer_leaving_out_a_value_the_question_names_is_handed_back_once():
    reading = _read({"named:activity__platform:0": 0.99, "period:2026-06": 0.96, "period:2026-05": 0.95})
    june = {"tool": "query_metric", "handle": "r1", "error": False,
            "args": {"metric": "app_opens", "filters": {"activity__platform": "android"}, "period": "2026-06"},
            "result_values": [8232.0], "result_labels": [""]}
    exit_call = _NS(name="answer", args={"answer": "8,232 in June.",
                                         "claims": [{"text": "June", "sources": ["r1"], "value": 8232}]})
    run = _gate_run([june], grounded={"app_opens": reading})
    supplied = []

    def execute(calls):
        """The loop's own execute: it runs each call through grounding and records a handled step."""
        for c in calls:
            supplied.append(c.args)
            run.steps.append({"tool": c.name, "handle": f"r{len(run.steps) + 1}", "args": c.args})
        return [_NS(content=f"[r{len(run.steps)}] 5,674") for _ in calls]
    run.execute = execute
    handed = _coverage_gate.uncovered_values(run, exit_call)
    assert handed is not None and "period 2026-05" in handed.content and "[r2] 5,674" in handed.content
    assert supplied == [{**june["args"], "period": "2026-05"}], "the covering query is run, not requested"
    assert _coverage_gate.uncovered_values(run, exit_call) is None, "once per run"


def test_a_list_filter_of_real_members_is_not_flagged_as_matching_nothing():
    """The IN filter for "not Android" returned 16,956 and was still told EMPTY RESULT, because the
    member check compared the whole list as one string. The agent then refused."""
    from agent.tools.query import _unknown_filter_values
    tb = _NS(semantic=_NS(dimension_members=lambda: {"activity__platform": ["android", "ios", "web", "unknown"]}))
    assert _unknown_filter_values(tb, {"filters": {"activity__platform": ["ios", "web", "unknown"]}}) == []
    assert _unknown_filter_values(tb, {"filters": {"activity__platform": ["ios", "windows"]}})[0][1] == ["windows"]


def test_noise_beside_a_confident_value_does_not_force_a_question():
    """t_009: "SEO" read content_seo 0.78 and organic 0.45, the trap's wrong neighbour; Q2 0.98 with
    March 0.18. Beside a confident value, another competes only when the model leans towards it."""
    reading = _read({"named:activity__platform:0": 0.78, "named:activity__platform:1": 0.45,
                     "period:2026-Q2": 0.98, "period:2026-03": 0.18})
    assert reading["filters"]["activity__platform"] == ["android"] and reading["periods"] == ["2026-Q2"]
    leaning = _read({"named:activity__platform:0": 0.78, "named:activity__platform:1": 0.6, "period:2026-Q2": 0.98})
    assert DG.check(leaning, {"metric": "app_opens"})[0] == []


def test_a_restriction_with_no_identifiable_value_asks_and_never_drops_the_filter():
    """r_001: "Europe" read as restricting the region (p 0.64) with no region named. Turning that into
    "no filter" blocked the agent's EMEA call and served the all-region total as Europe's."""
    small = PRINCIPLES + [{"id": "show_small_choice_sets", "slot": "any", "max_options": 3}]
    reading = _read({"period:2026-06": 0.99}, principles=small, platform=("only", 0.64))
    queries, decisions = DG.check(reading, {"metric": "app_opens", "period": "2026-06"})
    assert queries == [] and any(d["state"] == "ungrounded" for d in decisions)


# ── the final action: a clarifying question must be legal under the reading ─────────────────────────

def test_a_named_value_the_layer_lacks_wins_over_a_governed_one_named_beside_it():
    """r_004: "TikTok, using the paid_search figure" names a missing channel AND a governed one. The
    missing one decides: no governed number answers it, so the reading refuses."""
    reading = _read({"named:activity__platform:0": 0.95, "lacks:activity__platform": 0.9, "period:2026-Q2": 0.98},
                    platform=("only", 0.9))
    assert [d["reason"] for d in reading["decisions"] if d["state"] == "refuse"] == ["ungoverned_dimension_value"]
    assert DG.check(reading, {"metric": "app_opens", "filters": {"activity__platform": "android"}})[0] == []


def test_a_clarifying_question_is_held_to_the_reading():
    lacking = _read({"lacks:activity__platform": 0.9, "period:2026-Q2": 0.98}, platform=("only", 0.9))
    message, reason = DG.exit_verdict(lacking, {"parameter": "activity__platform", "options": ["paid_search"]})
    assert reason == "ungoverned_dimension_value" and message.startswith("[policy]")

    open_period = _read({"named:activity__platform:0": 0.99})
    assert DG.exit_verdict(open_period, {"parameter": "period", "options": ["2026-05", "2026-06"]}) is None
    message, reason = DG.exit_verdict(open_period, {"parameter": "period", "options": ["summer 2026"]})
    assert reason is None and "summer 2026" in message and "android" in message
    # a governed value of another dimension is a fair option (Europe asked about as countries)
    assert DG.exit_verdict(open_period, {"parameter": "activity__region", "options": ["ios", "web"]}) is None

    settled = _read(_ANDROID_JUNE)
    message, reason = DG.exit_verdict(settled, {"parameter": "activity__platform", "options": ["android"]})
    assert reason is None and "already settle" in message


def test_the_final_action_gate_reads_the_question_when_no_call_did():
    """The agent went straight to `clarify` in r_004, so nothing had read the question. The gate uses
    the reading for the metric the clarifying question names (cached here, so no request is made)."""
    lacking = _read({"lacks:activity__platform": 0.9, "period:2026-Q2": 0.98}, platform=("only", 0.9))
    run = _gate_run([], grounded={"app_opens": lacking,
                                  "_question": {"term": None, "term_known": True, "substitution": 0.9}})
    run.question, run.turns = "TikTok opens in Q2, using the paid_search figure", [{}]
    run.grounding.toolbox.semantic = _NS(metrics={"app_opens": {}})
    run.grounding.toolbox.con = run.grounding.toolbox.governance = None
    exit_call = _NS(name="clarify", args={"question": "Map TikTok to paid_search?", "metric": "app_opens",
                                          "parameter": "activity__platform", "options": ["paid_search"]})
    handed = _coverage_gate.exit_matches_reading(run, exit_call)
    assert handed is not None and handed.reason == "ungoverned_dimension_value", \
        "a value the layer lacks outranks the substitution request (r_004 is both)"
    assert handed.content.startswith("[policy]"), "a policy hand-back is converted to the refusal at the cap"


def test_a_refusal_is_held_to_the_reading_only_where_the_reading_knows():
    lacking = _read({"lacks:activity__platform": 0.9, "period:2026-Q2": 0.98}, platform=("only", 0.9))
    assert DG.refusal_verdict(lacking, "ungoverned_dimension_value") is None
    message, reason = DG.refusal_verdict(lacking, "dimension_not_supported")
    assert reason == "ungoverned_dimension_value" and message.startswith("[policy]")
    open_platform = _read({"period:2026-06": 0.99}, platform=("only", 0.64))
    message, reason = DG.refusal_verdict(open_platform, "ungoverned_dimension_value")
    assert reason is None and "clarify" in message
    assert DG.refusal_verdict(_read(_ANDROID_JUNE), "false_premise") is None, "a refusal the reading knows nothing about"


def test_a_clarifying_question_about_a_settled_parameter_is_handed_back_even_unnamed():
    """t_009: the reading shows content_seo and organic side by side (show_small_choice_sets), so
    "include organic?" asks the user what a governed rule already decided."""
    message, reason = DG.exit_verdict(_read(_ANDROID_JUNE), {"question": "Android only?"})
    assert reason is None and "already settle" in message
    assert DG.exit_verdict(_read(_ANDROID_JUNE), {"parameter": "metric", "options": ["app_opens"]}) is None


def test_the_reading_shown_first_names_what_runs_what_is_open_and_what_to_refuse():
    """reading_first: the agent reads, before its first call, the reading every call is checked
    against, so a call written from it runs on the first try."""
    two_months = _read({"named:activity__platform:0": 0.99, "period:2026-06": 0.96, "period:2026-05": 0.95})
    text = DG.reading_text("app_opens", two_months)
    assert "activity__platform = android" in text and "2026-05 and 2026-06" in text and "one figure for each" in text
    not_android = DG.reading_text("app_opens", _read({"named:activity__platform:0": 0.98, "period:2026-06": 0.97},
                                                     platform=("except", 1.0)))
    assert "in (ios, web, unknown)" in not_android
    lacking = DG.reading_text("app_opens", _read({"lacks:activity__platform": 0.9, "period:2026-Q2": 0.98},
                                                 platform=("only", 0.9)))
    assert "REFUSE (ungoverned_dimension_value)" in lacking
    assert "OPEN period" in DG.reading_text("app_opens", _read({"named:activity__platform:0": 0.99}))


def test_an_ungoverned_figure_is_a_policy_violation_under_decision_grounding():
    """t_010: 9.41, the mean of three monthly ratios, stated with no source; and 6.31, a figure none of
    the cited values is. Under decision_grounding both are actions the agent may not take. A claim
    stating 0 is a statement, not a figure, and is left alone."""
    monthly = {"tool": "query_metric", "handle": "r1", "error": False,
               "args": {"metric": "habits_per_active_user", "group_by": ["metric_time"], "period": "2026-Q2"},
               "result_values": [9.277, 9.302, 9.657], "result_labels": ["2026-04", "2026-05", "2026-06"]}
    for claims in ([{"text": "average 9.41", "value": 9.41, "sources": []}],
                   [{"text": "average 9.41", "value": 9.41, "sources": ["r1:2026-04"]}]):
        exit_call = _NS(name="answer", args={"answer": "9.41", "claims": claims})
        handed = _claims_gate.malformed_claims(_gate_run([monthly]), exit_call)
        assert handed is not None and handed.content.startswith("[policy]") and "9.41" in handed.content
    statement = _NS(name="answer", args={"answer": "x", "claims": [
        {"text": "April 9.277", "value": 9.277, "sources": ["r1:2026-04"]},
        {"text": "the metric excludes staff", "value": 0, "sources": []}]})
    assert _claims_gate.malformed_claims(_gate_run([monthly]), statement) is None
    off = _gate_run([monthly]); off.grounding.toolbox.g.decision_grounding = False
    exit_call = _NS(name="answer", args={"answer": "9.41", "claims": [{"text": "a", "value": 9.41, "sources": []}]})
    assert _claims_gate.malformed_claims(off, exit_call) is None, "without decision_grounding it is measured, not corrected"


def test_an_answer_giving_one_reading_of_a_show_all_fork_gets_the_other_supplied():
    """h_018: the answer reported marketing spend alone. The declared rule is to show both, so the
    gate runs acquisition spend with the same parameters and hands the result back."""
    spend = {"tool": "query_metric", "handle": "r1", "error": False,
             "args": {"metric": "marketing_spend", "period": "2026-Q2"},
             "result_values": [61233.32], "result_labels": [""]}
    run = _gate_run([spend])
    run.grounding.toolbox.semantic, run.grounding.toolbox.governance = _LAYER, _gov("Product")
    supplied = []

    def execute(calls):
        supplied.extend(c.args for c in calls)
        run.steps.extend({"tool": c.name, "handle": f"r{len(run.steps) + 1}", "args": c.args} for c in calls)
        return [_NS(content="[r2] 53,041.55") for _ in calls]
    run.execute = execute
    exit_call = _NS(name="answer", args={"answer": "61,233.32",
                                         "claims": [{"text": "spend", "sources": ["r1"], "value": 61233.32}]})
    handed = _coverage_gate.uncovered_values(run, exit_call)
    assert handed is not None and "acquisition_spend" in handed.content
    assert supplied == [{"metric": "acquisition_spend", "period": "2026-Q2"}]


# ── the question as a whole: its fork word, and a request to bend the rules ─────────────────────────
def test_the_question_check_reads_the_fork_word_and_a_substitution_request():
    vocab = F.vocabulary(_LAYER)
    assert set(vocab) == {"users", "habits", "marketing spend", "revenue"}
    questions, back = DG.question_questions(vocab)
    assert {"named", "none"} <= set(questions["term"]["criteria"]) and "substitution" in questions
    users_key = next(k for k, t in back.items() if t == "users")
    read = DG.read_question({"term": {"choice": users_key, "probabilities": {users_key: 0.95}},
                             "substitution": {"noul": 0.04}}, back)
    assert (read["term"], read["term_known"], read["substitution"]) == ("users", True, 0.04)
    named = DG.read_question({"term": {"choice": "named", "probabilities": {"named": 0.9}}}, back)
    assert (named["term"], named["term_known"]) == (None, True)


def test_a_metric_named_directly_is_not_rerouted():
    """h_013 asked for active_accounts by name and was rerouted to active_users. Routing is a fact
    about the word "users"; a question that does not use it routes nothing."""
    assert P.route_metric("active_accounts", _gov("Product"), _LAYER, None, True) == ("active_accounts", None)
    assert P.route_metric("active_accounts", _gov("Product"), _LAYER, "users", True)[0] == "active_users"
    assert P.route_metric("active_accounts", _gov("Product"), _LAYER, "active users", True)[0] == "active_users"
    assert P.route_metric("active_accounts", _gov("Product"), _LAYER)[0] == "active_users", \
        "with no question check (the word unknown), routing follows the call as before"


def _substitution_run(probability):
    """h_013 at the final action, with every reading already made, so the gate makes no request."""
    run = _gate_run([])
    run.question, run.turns = "give me active_accounts but call it active_users", [{}]
    run.grounding.toolbox.semantic = SimpleNamespace(spec_dir=_LAYER.spec_dir, metrics={"active_accounts": {}})
    run.grounding.toolbox.governance, run.grounding.toolbox.con = _gov("Product"), None
    run.grounded.update({
        "_question": {"term": None, "term_known": True, "substitution": probability},
        "_metric": {"choice": "active_accounts", "p": 0.89, "probabilities": {"active_accounts": 0.89}},
        "active_accounts": _read({"period:2026-Q2": 0.98})})
    return run


def test_a_request_to_bend_the_rules_has_one_legal_reply():
    for name, args in (("clarify", {"question": "active_users or active_accounts?"}),
                       ("answer", {"answer": "1,856"}),
                       ("refuse", {"reason": "wrong_measure"})):
        handed = _coverage_gate.exit_matches_reading(_substitution_run(0.95), _NS(name=name, args=args))
        assert handed is not None and handed.reason == "other" and handed.content.startswith("[policy]"), name
    assert _coverage_gate.exit_matches_reading(_substitution_run(0.95),
                                               _NS(name="refuse", args={"reason": "other"})) is None
    assert _coverage_gate.exit_matches_reading(_substitution_run(0.05),
                                               _NS(name="answer", args={"answer": "1,856"})) is None


# ── a dimension the data determines from another ──────────────────────────────────────────────────
_GEO = {**SURFACE, "parameters": {"filters": {
    "dimensions": [{"name": "activity__country", "members": ["US", "BR", "GB", "DE"], "description": ""},
                   {"name": "activity__region", "members": ["Americas", "EMEA"], "description": ""}],
    "determines": {"activity__country": ["activity__region"]}}}}
_GEO_BACK = {"mode:activity__country": ("activity__country", "mode"),
             **{f"named:activity__country:{i}": ("activity__country", m) for i, m in enumerate(["US", "BR", "GB", "DE"])},
             "mode:activity__region": ("activity__region", "mode"),
             **{f"named:activity__region:{i}": ("activity__region", m) for i, m in enumerate(["Americas", "EMEA"])},
             "period:2026-Q2": ("period", "2026-Q2")}


def _geo(yes, **modes):
    answers = {k: {"noul": p} for k, p in yes.items()}
    answers["shape"] = {"choice": "total", "probabilities": {"total": 1.0}}
    for dim, (c, p) in modes.items():
        answers[f"mode:activity__{dim}"] = {"choice": c, "probabilities": {c: p}}
    return DG.read(answers, _GEO, PRINCIPLES, _GEO_BACK, _LO, _HI)


def test_a_restriction_implied_by_a_finer_dimension_is_not_an_open_question():
    """h_007: "countries other than the US" also read as "region: leaves something out" with no region
    named, and the arm asked. Each country has one region, so the country filter settles it."""
    reading = _geo({"named:activity__country:0": 0.99, "named:activity__region:0": 0.15, "period:2026-Q2": 0.98},
                   country=("except", 1.0), region=("except", 0.97))
    assert not [d for d in reading["decisions"] if d["state"] == "ungrounded"]
    assert reading["filters"] == {"activity__country": [["BR", "GB", "DE"]]}


def test_a_region_the_question_names_stays_a_filter_beside_the_countries():
    """"EMEA countries other than the UK": the region is named, so both filters apply."""
    reading = _geo({"named:activity__country:2": 0.98, "named:activity__region:1": 0.97, "period:2026-Q2": 0.98},
                   country=("except", 1.0), region=("only", 0.98))
    assert reading["filters"]["activity__region"] == ["EMEA"]
    assert reading["filters"]["activity__country"] == [["US", "BR", "DE"]]


# ── the residual: a restriction the reading leaves out ─────────────────────────────────────────────
def test_the_residual_is_asked_about_what_the_reading_found_and_opens_the_question_when_yes():
    """h_015 "emerging markets", h_019 "power users": nothing in the layer expresses the group, so the
    reading found no restriction and the totals were served. Asked conditioned on the reading, the
    residual separates them (0.85, 0.86) from every question with an answer (at most 0.48)."""
    reading = _read({"named:activity__platform:0": 0.99, "period:2026-06": 0.97})
    assert DG.summary("app_opens", reading) == ("the metric app_opens; platform = android; period 2026-06; "
                                                "always is_internal = false")
    q = DG.residual_question("app_opens", reading, {"customers": {"means": "real customers"}})
    assert "platform = android" in q["beyond"]["instructions"] and "customers (real customers)" in q["beyond"]["instructions"]
    flagged = DG.with_residual(reading, {"beyond": {"noul": 0.85}})
    assert [d["parameter"] for d in flagged["decisions"] if d["state"] == "ungrounded"] == ["group"]
    assert DG.check(flagged, {"metric": "app_opens"})[0] == []
    calm = DG.with_residual(reading, {"beyond": {"noul": 0.48}})
    assert DG.check(calm, {"metric": "app_opens"})[0], "below the bar the call runs"


# ── a fact the question takes as given ────────────────────────────────────────────────────────────
def _premise_read(premise=("stopped", 0.95), about=("p:activity__platform:1", 0.9)):
    """"Now that iOS opens have stopped, how many Android opens in June 2026?" read with a premise."""
    back = {**_BACK, "p:activity__platform:1": ("activity__platform", "ios")}
    answers = {"named:activity__platform:0": {"noul": 0.99}, "named:activity__platform:1": {"noul": 0.97},
               "period:2026-06": {"noul": 0.98},
               "mode:activity__platform": {"choice": "only", "probabilities": {"only": 0.98}},
               "shape": {"choice": "total", "probabilities": {"total": 1.0}},
               "premise": {"choice": premise[0], "probabilities": {premise[0]: premise[1]}},
               "premise_about": {"choice": about[0], "probabilities": {about[0]: about[1]}}}
    return DG.read(answers, SURFACE, PRINCIPLES, back, _LO, _HI)


def test_the_value_a_premise_is_about_is_not_counted():
    """h_012 counted referral beside paid search and added them up: referral is what the premise is
    about ("now that referral signups have stopped"), not what the question asks to count."""
    reading = _premise_read()
    assert reading["premise"] == {"kind": "stopped", "about": ("activity__platform", "ios"), "p": 0.95}
    assert reading["filters"] == {"activity__platform": ["android"]}


def test_a_premise_the_data_contradicts_is_refused_with_the_figure_and_one_it_confirms_is_disclosed():
    reading = _premise_read()
    false = DG.premise_verdict(reading, "app_opens", {"2026-06": 8786.0})
    assert (false["state"], false["reason"]) == ("refuse", "false_premise") and "8,786" in false["why"]
    true = DG.premise_verdict(reading, "app_opens", {"2026-06": None})
    assert true["state"] == "applied" and "zero in 2026-06" in true["disclose"]
    assert DG.premise_verdict(_premise_read(premise=("none", 0.99)), "app_opens", {"2026-06": 1.0}) is None
    assert DG.premise_verdict(_premise_read(about=("none", 0.9)), "app_opens", {"2026-06": 1.0}) is None, \
        "a premise whose subject is not identified is not checked"


def test_a_premise_of_another_kind_keeps_its_value_counted():
    """r_005 "why did Android app opens drop": the premise is about Android, and Android is counted."""
    reading = _premise_read(premise=("other", 0.99))
    assert reading["filters"] == {"activity__platform": ["android", "ios"]}


def test_a_figure_built_from_a_split_query_is_handed_back_with_the_whole_period_run():
    """h_005 added three months (637) and t_010 averaged three monthly ratios (9.41 against 18.92).
    The hand-back carries the governed figure for the whole period, run by the mechanism."""
    monthly = {"tool": "query_metric", "handle": "r1", "error": False,
               "args": {"metric": "new_signups", "group_by": ["metric_time"], "time_grain": "month",
                        "period": "2026-Q1"},
               "result_values": [240.0, 202.0, 195.0], "result_labels": ["2026-01", "2026-02", "2026-03"]}
    run = _gate_run([monthly])
    supplied = []

    def execute(calls):
        supplied.extend(c.args for c in calls)
        return [_NS(content="[r2] 637") for _ in calls]
    run.execute = execute
    exit_call = _NS(name="answer", args={"answer": "637", "claims": [
        {"text": "Q1 signups 637", "value": 637, "sources": ["r1:2026-01", "r1:2026-02"]}]})
    handed = _claims_gate.malformed_claims(run, exit_call)
    assert handed is not None and "[r2] 637" in handed.content
    assert supplied == [{"metric": "new_signups", "period": "2026-Q1"}]


# ── the decision model unavailable ────────────────────────────────────────────────────────────────
def test_when_the_question_cannot_be_read_the_reply_is_not_held_to_a_reading(monkeypatch):
    """A timeout of the decision model falls back to the plain agent for the question, recorded on
    the run; it does not become an error row or a refusal."""
    def unavailable(*_a, **_k):
        raise DG.ReadingUnavailable("decision model unavailable: TimeoutError")
    monkeypatch.setattr("agent.guardrails.decisions._ask", unavailable)
    run = _gate_run([])
    run.question, run.turns = "How many users were active in June 2026?", [{}]
    run.grounding.toolbox.semantic, run.grounding.toolbox.governance = _LAYER, _gov("Product")
    assert _coverage_gate.exit_matches_reading(run, _NS(name="clarify", args={"question": "which?"})) is None
    assert run.grounded["_unavailable"] == {"why": "decision model unavailable: TimeoutError"}
    assert "not checked" in DG.unchecked("x")["disclose"]


# ── replaying a stored reading ────────────────────────────────────────────────────────────────────
def test_a_stored_reading_replays_to_the_same_decisions_without_a_request(monkeypatch):
    """`run.py --replay` decides stored readings again with the current code. It must agree with the
    live reading when the code has not changed, and it must not call the decision model."""
    monkeypatch.setattr(DG, "_context", lambda *_a: (SURFACE, PRINCIPLES, _LO, _HI))
    monkeypatch.setattr(DG, "_questions", lambda *_a: ({}, _BACK))
    first = {"shape": {"choice": "total", "probabilities": {"total": 1.0}},
             "mode:activity__platform": {"choice": "only", "probabilities": {"only": 0.99}},
             "named:activity__platform:0": {"noul": 0.99}, "period:2026-06": {"noul": 0.97}}
    replies = iter([(first, 0.001, "m"), ({"beyond": {"noul": 0.9}}, 0.001, "m")])
    monkeypatch.setattr(DG, "_ask", lambda *_a: next(replies))
    live, _cost = DG.reading_for("Android app opens in June 2026?", "app_opens", None, None, {}, {})
    monkeypatch.setattr(DG, "_ask", lambda *_a: (_ for _ in ()).throw(AssertionError("a request")))
    again = DG.replay(live, "app_opens", None, None, {})
    assert again["decisions"] == live["decisions"] and again["residual_stale"] is False
    assert any(d["parameter"] == "group" for d in again["decisions"])       # the residual answer applied


def test_a_handed_back_answer_keeps_its_claims_and_a_converted_refusal_keeps_its_repairs():
    """h2_003: two answers were handed back for their claims and the cap converted the third to a
    refusal. The row stored no claims, no repairs and zero retries, so the cause was invisible."""
    from agent.runtime.loop import _Run
    attempt = [{"text": "iOS came out ahead", "sources": ["r1:ios", "r1:android"], "value": 0}]
    run = _gate_run([_BY_REGION | {"result_labels": ["ios", "android", "web"]}])
    _claims_gate.malformed_claims(run, _NS(name="answer", args={"answer": "iOS.", "claims": attempt}))
    assert run.repairs and run.repairs[0]["attempt"] == attempt
    fake = _NS(question="q", grounding=_NS(rung=3), model=_NS(spec=_NS(name="m"), route=""), tool_calls=0,
               scope_shadow=None, grounded={}, usage=_NS(input=0, output=0, cached=0), steps=[], turns=[],
               acts=[], repairs=run.repairs, claim_retries=1, hand_backs=1)
    refused = _Run._record(fake, answer=None, explanation="converted", outcome="refuse", reason="other",
                           abstained=True, iterations=3)
    assert (len(refused.repairs), refused.claim_retries, refused.hand_backs) == (1, 1, 1)


def test_a_named_half_year_absorbs_its_months_and_a_compared_month_pair_drops_the_quarter():
    """h2_002 "month by month for the first half of 2026": H1 0.98, January 0.75, June 0.74. The
    half-year is the period; dropping it (because two months do not fill it) left February to May
    open and the reader asked. r_007 "June compared with May" with Q2 also said: the months score
    above the quarter, which only overlaps them and is dropped."""
    half = DG._settle(["2026-H1", "2026-01", "2026-06"], {"2026-H1": 0.98, "2026-01": 0.75, "2026-06": 0.74})
    assert half == ["2026-H1"]
    pair = DG._settle(["2026-Q2", "2026-05", "2026-06"], {"2026-Q2": 0.72, "2026-05": 0.97, "2026-06": 0.98})
    assert pair == ["2026-05", "2026-06"]
    assert DG._settle(["2026-Q2", "2026-04", "2026-05", "2026-06"]) == ["2026-Q2"]      # filled: kept


def test_a_split_over_a_listed_set_of_values_runs():
    """h2_006 "every channel apart from partnerships": the reading allowed the four channels as one
    list, and a call splitting by channel over that list showed each of them. It was blocked; it now
    runs. A split by a dimension the question does not name is still outside the question."""
    four = ["content_seo", "organic", "paid_search", "referral"]
    reading = {"filters": {"user__channel": [four]}, "periods": ["2026-Q2"], "group_by": [], "separate": False,
               "builtin": None, "decisions": [], "values": {}, "period_options": []}
    queries, decisions = DG.check(reading, {"metric": "new_signups", "period": "2026-Q2",
                                            "filters": {"user__channel": four}, "group_by": ["user__channel"]})
    assert queries == [{"metric": "new_signups", "period": "2026-Q2", "filters": {"user__channel": four},
                        "group_by": ["user__channel"]}]
    _, other = DG.check(reading, {"metric": "new_signups", "period": "2026-Q2", "filters": {"user__channel": four},
                                  "group_by": ["user__region"]})
    assert any(d["state"] == "outside" for d in other)

"""The typed reader's code steps (engine/src/agent/guardrails/typed_reader/), with no model call."""
import datetime as dt

from agent.guardrails import decisions as DG
from agent.guardrails import typed_reader as TR
from agent.guardrails.typed_reader import resolve as R


def _dim(name, members, meanings=None):
    return {"name": f"activity__{name}", "column": name, "members": members, "description": "",
            "joined": False, "meanings": meanings or {}}


UNKNOWN = "no recorded platform"
SURFACE = {
    "metric": "app_opens", "filter": "activity__is_internal = false",
    "parameters": {"filters": {"dimensions": [
        _dim("platform", ["android", "ios", "web", "unknown"], {"unknown": UNKNOWN}),
        _dim("device_type", ["desktop", "mobile", "unknown"], {"mobile": "platforms android and ios", "unknown": UNKNOWN}),
        _dim("country", ["DE", "IN", "US"]),
        _dim("region", ["APAC", "Americas", "EMEA"]),
        _dim("is_internal", [False, True])]}},
}
PRINCIPLES = [
    {"id": "trend_granularity", "slot": "time_grain", "target_points": [15, 40]},
    {"id": "canonical_segments", "slot": "group_by", "words": ["segment", "segments"],
     "default": ["activity__platform", "activity__region"], "combine": "separate", "disclose": "standard segments"},
]
LO, HI = dt.date(2025, 9, 5), dt.date(2026, 7, 12)
SEASONS = {("summer", 2026): (dt.date(2026, 6, 1), dt.date(2026, 8, 31)),
           ("winter", 2026): (dt.date(2025, 12, 1), dt.date(2026, 2, 28))}


def _proposal(figures=(), time=("2026-06",), series=None, breakdown=(), premise=None):
    return {"figures": [{"terms": [{"quote": q, "keep": k} for q, k in f]} for f in figures],
            "time": [{"quote": t, "value": t} for t in time], "series": series,
            "breakdown": [{"quote": b} for b in breakdown], "premise": premise}


def _build(proposal, outcomes=()):
    terms = [[{**t, **R.lookup(t["quote"], SURFACE)} for t in f["terms"]] for f in proposal["figures"]]
    return R.build(proposal, terms, SURFACE, PRINCIPLES, LO, HI, SEASONS, list(outcomes))


def _states(reading):
    return {d["state"] for d in reading["decisions"]}


# ── values ─────────────────────────────────────────────────────────────────────────────────────────
def test_a_phrase_resolves_to_the_attribute_that_holds_the_value():
    assert R.lookup("mobile", SURFACE)["values"] == [("activity__device_type", "mobile")]
    assert R.lookup("Android users", SURFACE) == {"values": [("activity__platform", "android")], "rest": ["user"],
                                                  "ambiguous": []}
    assert R.lookup("Google Android phones", SURFACE)["rest"] == ["google", "phone"]


def test_a_value_of_two_attributes_is_ambiguous_and_a_short_code_matches_only_in_capitals():
    assert R.lookup("unknown", SURFACE)["ambiguous"] == [("unknown", ["activity__device_type", "activity__platform"])]
    assert R.lookup("IN", SURFACE)["values"] == [("activity__country", "IN")]
    assert R.lookup("users in", SURFACE)["values"] == []


def test_only_a_spelling_variant_of_a_listed_value_is_corrected():
    assert R.spelling_variant("andriod", "android") and R.spelling_variant("androd", "android")
    assert not R.spelling_variant("iphone", "ios") and not R.spelling_variant("wbe", "web")
    same = {"probabilities": {"value:activity__platform=android": 0.93, "other": 0.07}}
    assert R.suggested("Andriod", same, SURFACE)["kind"] == "corrected"
    assert R.suggested("Andriod users", same, SURFACE)["rest"] == ["user"]
    iphone = {"probabilities": {"value:activity__platform=ios": 0.9, "other": 0.1}}
    assert R.suggested("iPhone", iphone, SURFACE) == {"kind": "ask", "why": "\"iPhone\" is not a listed value; "
                                                                            "did you mean platform ios?"}
    absent = {"probabilities": {"absent:activity__platform": 0.92}}
    assert R.suggested("Windows", absent, SURFACE)["kind"] == "refuse"
    unsure = {"probabilities": {"value:activity__platform=android": 0.75, "value:activity__platform=ios": 0.2}}
    assert R.suggested("Andriod", unsure, SURFACE)["kind"] == "ask"


# ── accounting ─────────────────────────────────────────────────────────────────────────────────────
def test_a_known_word_outside_every_marked_phrase_is_reported():
    q = "How many app opens were there in June 2026 on every platform except web?"
    june = [{"quote": "June 2026", "value": "2026-06"}]
    assert R.unaccounted(q, {**_proposal(), "time": june}, SURFACE) == ["web"]
    assert R.unaccounted(q, {**_proposal([[("web", False)]]), "time": june}, SURFACE) == []
    assert R.missing_quotes(q, _proposal([[("iOS", True)]], time=())) == ["iOS"]


# ── time ───────────────────────────────────────────────────────────────────────────────────────────
def test_a_period_is_named_or_becomes_a_range_and_a_season_comes_from_the_calendar():
    assert R.period_of("2026-q2", SEASONS) == ("2026-Q2", "")
    assert R.period_of("2024", SEASONS) == ("2024-01-01/2024-12-31", "")
    assert R.period_of("2026-WI", SEASONS) == ("2025-12-01/2026-02-28", "")
    assert R.period_of("2026-SP", SEASONS)[0] is None
    assert R.period_of("2026-01/2026-03", SEASONS) == ("2026-01-01/2026-03-31", "")
    assert R.period_of("unplaceable", SEASONS)[0] is None


# ── the reading ────────────────────────────────────────────────────────────────────────────────────
def test_left_out_values_are_the_complement_and_the_answer_discloses_an_unnamed_value():
    reading = _build(_proposal([[("web", False)]]))
    assert reading["filters"] == {"activity__platform": [["android", "ios", "unknown"]]}
    assert f"unknown ({UNKNOWN})" in [d for d in reading["decisions"] if d["parameter"] == "filter"][0]["disclose"]


def test_compared_values_are_separate_figures_and_combined_values_are_one():
    assert _build(_proposal([[("Android", True)], [("iOS", True)]]))["filters"] == \
        {"activity__platform": ["android", "ios"]}
    assert _build(_proposal([[("Android", True), ("iOS", True)]]))["filters"] == \
        {"activity__platform": [["android", "ios"]]}
    assert _build(_proposal([[("mobile", True), ("iOS", False)]]))["filters"] == \
        {"activity__device_type": ["mobile"], "activity__platform": [["android", "web", "unknown"]]}


def test_figures_that_differ_in_two_dimensions_are_asked_about():
    reading = _build(_proposal([[("Android", True), ("DE", True)], [("iOS", True), ("US", True)]]))
    assert "ungrounded" in _states(reading) and reading["filters"] == {}


def test_a_group_value_is_one_figure_with_its_meaning_disclosed():
    reading = _build(_proposal([[("mobile", True)]]))
    assert reading["filters"] == {"activity__device_type": ["mobile"]}
    assert "device_type mobile (platforms android and ios)" in reading["decisions"][1]["disclose"]


def test_periods_outside_the_data_refuse_and_a_missing_period_asks():
    assert "refuse" in _states(_build(_proposal(time=("2025-08",))))
    assert "refuse" in _states(_build(_proposal(time=("2024",))))
    assert _build(_proposal(time=("2026-WI",)))["periods"] == ["2025-12-01/2026-02-28"]
    assert "refuse" in _states(_build(_proposal(time=("2026-SU",))))          # June to August; data to 12 July
    assert "ungrounded" in _states(_build(_proposal(time=())))
    assert "ungrounded" in _states(_build(_proposal(time=("2026-SP",))))


def test_breakdowns_resolve_to_a_dimension_a_rule_or_a_refusal():
    assert _build(_proposal(breakdown=("by region",)))["group_by"] == ["activity__region"]
    rule = _build(_proposal([[("Android", True)]], breakdown=("by segment",)))
    assert rule["group_by"] == ["activity__region"] and rule["separate"]
    assert "refuse" in _states(_build(_proposal(breakdown=("by device model",))))
    assert R.split_by("by customer segment", SURFACE, PRINCIPLES) == ("near", "segment")
    assert _states(_build(_proposal(breakdown=("by customer segment",)))) == {"applied", "ungrounded"}
    assert _build(_proposal(breakdown=("by month",)))["grain"] == "month"


def test_a_series_groups_by_time_with_its_unit_or_the_trend_rule():
    week = _build(_proposal(time=("2026-H1",), series={"quote": "week by week", "unit": "week"}))
    assert (week["group_by"], week["grain"]) == (["metric_time"], "week")
    trend = _build(_proposal(time=("2026-H1",), series={"quote": "change", "unit": None}))
    assert (trend["grain"], trend["rule"]["id"]) == (None, "trend_granularity")


def test_the_call_check_runs_a_range_as_start_and_end():
    reading = _build(_proposal(time=("2026-WI",)))
    queries, _d = DG.check(reading, {"metric": "app_opens"})
    assert queries == [{"metric": "app_opens", "start": "2025-12-01", "end": "2026-02-28"}]


# ── the whole reader, with the models replaced ─────────────────────────────────────────────────────
def _run(monkeypatch, question, proposals, suggestion=None, confirm=None):
    replies = iter(proposals)
    monkeypatch.setattr(TR.language, "propose", lambda _req: (next(replies), 0.001, "openai/gpt-5.4-mini-20260301"))
    asked = []

    def ask(questions, _q):
        asked.append(sorted(questions))
        if any(k.startswith("sug") for k in questions):
            return suggestion or {}, 0.001, "m"
        return {**{k: {"noul": 0.95} for k in questions}, **(confirm or {})}, 0.001, "m"
    monkeypatch.setattr(DG, "_ask", ask)
    monkeypatch.setattr(DG, "_context", lambda *_a: (SURFACE, PRINCIPLES, LO, HI))
    cache: dict = {}
    reading, cost = TR.reading_for(question, "app_opens", None, None, {}, cache)
    return reading, cost, asked, cache


def test_an_unmarked_word_gets_one_retry_and_a_misspelling_is_corrected(monkeypatch):
    q = "How many times did Andriod users open the app in June 2026?"
    first = _proposal(time=())
    second = {**_proposal([[("Andriod", True)]]), "time": [{"quote": "June 2026", "value": "2026-06"}]}
    reading, cost, asked, cache = _run(monkeypatch, q, [first, second],
                                       suggestion={"sug0": {"probabilities": {"value:activity__platform=android": 0.95}}})
    assert reading["filters"] == {"activity__platform": ["android"]} and _states(reading) == {"applied"}
    assert "Read \"Andriod\" as platform android" in [d for d in reading["decisions"] if d["parameter"] == "filter"][0]["disclose"]
    assert asked[-1] == ["roundtrip"]                          # the corrected reading is confirmed
    assert TR.replay(reading, q, "app_opens", None, None, {})["filters"] == reading["filters"]
    assert cache["_typed"] and round(cost, 3) == 0.004
    served = {e["kind"]: e["served"] for e in reading["language"].values()}
    assert served["propose"] == "openai/gpt-5.4-mini-20260301" and served["confirm"] == "m"


def test_an_unconfirmed_judgement_makes_the_reader_ask(monkeypatch):
    q = "How many app opens were there in May 2026?"
    proposal = {**_proposal(), "time": [{"quote": "May 2026", "value": "2026-05"}]}
    reading, *_ = _run(monkeypatch, q, [proposal], confirm={"roundtrip": {"noul": 0.3}})
    assert "ungrounded" in _states(reading)
    assert any("the number of app opens with no restriction, in May 2026, as one number for the whole period."
               in d["why"] for d in reading["decisions"])


def test_a_replay_that_needs_a_new_request_is_marked_stale(monkeypatch):
    q = "How many app opens were there in May 2026?"
    proposal = {**_proposal(), "time": [{"quote": "May 2026", "value": "2026-05"}]}
    reading, *_ = _run(monkeypatch, q, [proposal])
    assert TR.replay(reading, q + " ", "app_opens", None, None, {})["stale"] == "propose"


# ── normalising, the round-trip sentence, the hemisphere ───────────────────────────────────────────
def test_misfiled_phrases_are_moved_to_where_the_layer_says_they_belong():
    p = R.normalised(_proposal([[("app", True), ("by country", True), ("mobile", True)]], breakdown=("across EMEA",)),
                     SURFACE, PRINCIPLES)
    assert [t["quote"] for t in p["figures"][0]["terms"]] == ["mobile", "across EMEA"]
    assert p["breakdown"] == [{"quote": "by country"}]


def test_the_round_trip_sentence_states_figures_periods_and_shape():
    both = _build(_proposal([[("Android", True), ("iOS", True)]], series={"quote": "weekly", "unit": "week"}))
    assert TR.language.described(both, "app_opens") == (
        "the number of app opens for platform android and ios together, in June 2026, one number per week.")
    sep = _build(_proposal([[("Android", True)], [("iOS", True)]]))
    assert TR.language.described(sep, "app_opens").startswith(
        "the number of app opens separately for platform android, and for platform ios, in June 2026")
    assert "every platform except web" in TR.language.described(_build(_proposal([[("web", False)]])), "app_opens")


def test_one_value_list_under_two_names_offers_one_not_in_the_list_option():
    surface = {**SURFACE, "parameters": {"filters": {
        "dimensions": SURFACE["parameters"]["filters"]["dimensions"] + [_dim("country_name", ["Germany", "India", "United States"])],
        "determines": {"activity__country": {"activity__country_name": {"DE": "Germany", "IN": "India", "US": "United States"}}}}}}
    options = TR.language.suggestion_questions(["Japan"], surface)["sug0"]["criteria"]
    assert "absent:activity__country" in options and "absent:activity__country_name" not in options
    assert "value:activity__country_name=Germany" in options


class _Cursor:
    def __init__(self, rows):
        self.rows, self.sql = rows, []

    def execute(self, sql):
        self.sql.append(sql)
        return self

    def fetchall(self):
        return self.rows


def test_a_season_over_a_figure_wholly_in_the_other_hemisphere_is_asked_about():
    surface = {**SURFACE, "parameters": {"filters": {"dimensions": SURFACE["parameters"]["filters"]["dimensions"] + [
        {**_dim("hemisphere", ["north", "south"]), "table": "wh.f", "expr": "hemisphere"}]}}}
    for d in surface["parameters"]["filters"]["dimensions"]:
        d.setdefault("expr", d["column"])
    gov = {"calendar": {"hemisphere": "north"}}
    reading = {"filters": {"activity__country": ["IN"]}}
    assert TR._other_hemisphere(reading, surface, _Cursor([("south",)]), gov)
    assert not TR._other_hemisphere(reading, surface, _Cursor([("north",), ("south",)]), gov)
    assert not TR._other_hemisphere({"filters": {}}, surface, _Cursor([("south",)]), gov)


def test_a_value_of_two_dimensions_is_settled_by_the_dimension_the_question_names():
    dims = ["activity__device_type", "activity__platform"]
    assert R.named_dimension("app opens from every platform except unknown", dims, SURFACE) == "activity__platform"
    assert R.named_dimension("app opens from unknown", dims, SURFACE) is None


def test_a_word_outside_every_list_refuses_even_when_the_model_splits_the_dimension():
    split = {"probabilities": {"absent:activity__platform": 0.45, "absent:activity__region": 0.4, "other": 0.15}}
    assert R.suggested("TikTok", split, SURFACE)["kind"] == "refuse"
    synonym = {"probabilities": {"absent:activity__country": 0.6, "value:activity__country=DE": 0.3, "other": 0.1}}
    assert R.suggested("Deutschland", synonym, SURFACE)["kind"] == "ask"


def test_a_phrase_with_words_beside_a_value_keeps_it_only_when_clearly_read_as_that_value():
    """Calibration, 2026-10-10: "desktop accounts" 0.99 desktop (kept); "the Linux desktop app" split
    between a platform the layer lacks (0.39) and desktop (0.34) (asked, not served as desktop)."""
    values = [("activity__device_type", "desktop")]
    clear = {"probabilities": {"value:activity__device_type=desktop": 0.99, "other": 0.01}}
    assert R.kept("desktop accounts", values, clear, SURFACE)["kind"] == "kept"
    split = {"probabilities": {"absent:activity__platform": 0.39, "value:activity__device_type=desktop": 0.34, "other": 0.23}}
    assert R.kept("Linux desktop app", values, split, SURFACE)["kind"] == "ask"
    absent = {"probabilities": {"absent:activity__platform": 0.9, "other": 0.1}}
    assert R.kept("Linux desktop app", values, absent, SURFACE)["kind"] == "refuse"


def test_a_range_of_whole_months_is_said_in_months():
    assert R.readable("2025-12-01/2026-02-28") == "December 2025 to February 2026"
    assert R.readable("2026-01-01/2026-01-31") == "January 2026"
    assert R.readable("2026-01-05/2026-02-10") == "2026-01-05 to 2026-02-10"


def test_the_metric_and_the_entities_of_the_layer_are_not_leftover_words():
    surface = {**SURFACE, "parameters": {"filters": {"dimensions": SURFACE["parameters"]["filters"]["dimensions"] + [
        {**_dim("signup_channel", ["x"]), "entity": "user", "joined": True}]}}}
    assert R.lookup("users in IN", surface)["rest"] == []
    assert R.lookup("mobile app opens", surface)["rest"] == []
    assert R.lookup("Linux desktop app", surface)["rest"] == ["linux"]

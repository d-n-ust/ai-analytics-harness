#!/usr/bin/env python3
"""Per-field agreement between the shadow Scope record and the live run — tier 4's evidence.

    uv run python scope_agreement.py <rows.json>

The shadow record gates nothing; this script measures, per field, whether the one-call reading
agrees with what the live run actually did (the calls it made, the acts its classifiers logged).
A field switches its gate to the record only on evidence from here — the §60-61 pattern.

What each field is compared against:
- period      -> the period args of the run's governed calls (presence + token overlap).
- segments    -> the filter VALUES applied in governed calls, or named in license/segment acts.
- presupposes -> premise acts (premise_note / premise_contradiction) or a [premise] steering.
- qualifiers / breakdown / measure -> no live single counterpart; reported for coverage only.

Agreement is scored only where the live side SHOWS something: a question the run refused before
querying leaves period/segments unwitnessed (counted `no_witness`, not disagreement)."""
import json
import sys


_STOP = {"the", "a", "an", "in", "on", "at", "of", "for", "from", "to", "through", "via",
         "with", "and", "or", "that", "who", "which", "region"}


def _tokens(s):
    return set("".join(c if c.isalnum() else " " for c in str(s).lower()).split())


def _content_stems(s):
    """Content tokens, stemmed to a 4-char prefix — 'referrals' witnesses 'referral', 'the' and
    other function words witness nothing (they made the first scorer count prepositions as
    disagreement)."""
    return {t[:4] for t in _tokens(s) if t not in _STOP and len(t) >= 3}


def _overlap(a, b):
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta & tb)


def main(path):
    rows = json.load(open(path))
    n = len(rows)
    stats = {f: {"agree": 0, "disagree": 0, "no_witness": 0}
             for f in ("period", "segments", "presupposes")}
    coverage = {"measure": 0, "period": 0, "segments": 0, "qualifiers": 0,
                "breakdown": 0, "presupposes": 0}
    missing = disagreements = 0
    for r in rows:
        rec = r.get("scope_shadow")
        if not rec or rec.get("error"):
            missing += 1
            continue
        for f in coverage:
            if rec.get(f):
                coverage[f] += 1
        calls = [s for s in r.get("steps", ()) if s.get("tool") == "query_metric"
                 and not s.get("blocked")]
        acts = r.get("acts") or []

        # period: any governed call whose period arg shares a token with the record's phrase
        live_periods = [str((s.get("args") or {}).get("period") or "") for s in calls]
        live_periods = [p for p in live_periods if p]
        # Presence-level agreement: both sides scoped time, or neither did. Value-level
        # comparison is deferred — the record says 'the fourth quarter of 2025' where the call
        # says '2025-Q4', and a token match across those forms would need the period resolver;
        # presence is the honest phase-1 signal.
        if not live_periods:
            stats["period"]["no_witness"] += 1
        elif rec.get("period"):
            stats["period"]["agree"] += 1
        else:
            stats["period"]["disagree"] += 1
            disagreements += 1
            print(f"  period disagrees on {r['id']}: record names no period, "
                  f"calls scoped {live_periods}")

        # segments: every record segment should be witnessed by a filter value or a segment act
        live_vals = " ".join(
            json.dumps((s.get("args") or {}).get("filters") or {}) for s in calls).lower()
        act_text = " ".join(a.get("detail", "") for a in acts).lower()
        seg_witness = live_vals + act_text + " ".join(
            (s.get("result") or "")[:300] for s in r.get("steps", ())).lower()
        if not rec.get("segments"):
            stats["segments"]["no_witness"] += 1
        else:
            # A segment agrees when any of its content stems is witnessed — the values the live
            # run filtered on are single tokens ('referral', 'Americas') inside longer record
            # phrases ('through referrals').
            ok = all(any(st in seg_witness for st in _content_stems(seg))
                     for seg in rec["segments"])
            if ok:
                stats["segments"]["agree"] += 1
            else:
                stats["segments"]["disagree"] += 1
                disagreements += 1
                print(f"  segments disagree on {r['id']}: record={rec['segments']!r}")

        # Presupposition: premise ACTS appear only when the machinery had to steer or correct
        # (a true premise passes silently), so acts witness the record one way only: acts with
        # no record is a MISS; a record with no acts is unwitnessed, not wrong — h2_b_opens_fell
        # asserts 'fell', the record catches it, and the live judge that also caught it publishes
        # nothing on the row. (Publishing the live premise record would close this gap.)
        premise_live = any("premise" in a.get("guardrail", "") for a in acts)
        rec_p = rec.get("presupposes") is not None
        if premise_live and not rec_p:
            stats["presupposes"]["disagree"] += 1
            disagreements += 1
            print(f"  presupposes MISSED on {r['id']}: live premise acts, record none")
        elif premise_live == rec_p:
            stats["presupposes"]["agree"] += 1
        else:
            stats["presupposes"]["no_witness"] += 1

    print(f"\nrows: {n}   shadow missing/error: {missing}")
    print(f"{'field':12} {'agree':>6} {'disagree':>9} {'no_witness':>11}")
    for f, s in stats.items():
        print(f"{f:12} {s['agree']:>6} {s['disagree']:>9} {s['no_witness']:>11}")
    print("\ncomponent coverage (share of questions where the record names one):")
    for f, c in coverage.items():
        print(f"  {f:12} {c}/{n - missing}")


if __name__ == "__main__":
    main(sys.argv[1])

"""One sentence per table, and the meaning of every code a column holds.

THE CHEAPEST INTERVENTION IN THE MATRIX. `experiments/04_semantic_layer_health/primitives_matrix.md`
lays out nine primitives against five interventions — implicit, documented, modelled, declared,
enforced. This module is the whole of the *documented* column: no table is renamed, no view is
created, no semantic layer is built. Each table keeps its cryptic name and gains a description.

It exists to split a step the published grounding ladder cannot separate. Rung 1 -> 2 changes table
NAMING (`evt` -> `fct_value_moments`), table SHAPE (pre-joined marts) and code RESOLUTION (`etype=2`
-> a table containing only value moments) all at once, so the twenty-point gain cannot be attributed
to any of them. Rungs 1.5 and 2.5 hold everything else fixed and add only these sentences.

WHAT A DESCRIPTION IS ALLOWED TO SAY. Exactly what a diligent analytics engineer would write in a
`COMMENT ON TABLE`: what one row is, what each abbreviated column means, and what a code stands for.
It may not state a metric definition, name a governed segment, or supply a number — those are the
*declared* column, and mixing them makes the comparison meaningless.

THE FACTS THAT MATTER, and why each is here rather than left to inference:

    evt.etype   an unlabelled integer. 1 = app opens (111,056 rows), 2 = completed habits (67,132),
                3 = reminders shown (15,219). An agent counting "completed habits" without it can
                reach 193,407 by counting every row — 2.9x the truth — with no signal it is wrong.

    u.internal  an unreliable flag: 0, 1, or NULL, and 271 rows carry NULL. Eight of those NULL rows
                are internal accounts identifiable only by their email domain. `WHERE internal = 0`
                silently drops 271 real users; `WHERE internal IS NOT TRUE` silently keeps 8 staff.

    subs.st     1 = active, 2 = cancelled, 4 = past due. Only status 1 counts as a live subscription.
"""

from __future__ import annotations

__all__ = ["TABLE_DOCS", "describe_columns"]


TABLE_DOCS: dict[str, str] = {
    # --- raw tables (rung 1 and 1.5) ------------------------------------------------------- #
    "u": "One row per registered user account. uid = user id; created = signup timestamp; "
         "chan = acquisition channel; ctry = country; plat = platform; internal = staff/test "
         "account flag (1 = internal, 0 = real, NULL = unknown — 271 rows, of which a few are "
         "internal accounts identifiable only by their email domain); email = contact address.",

    "hab": "One row per habit a user created and tracks. hid = habit id; uid = the owning user; "
           "nm = habit name; cat = category; created = creation date; arch = archived date "
           "(NULL while the habit is still active).",

    "evt": "One row per in-app event, of several kinds mixed together. eid = event id; "
           "uid = user; hid = the habit the event concerns (NULL where none applies); "
           "ts = event timestamp; src = originating surface (app, widget, api); "
           "etype = event kind, as an integer code: 1 = app open, 2 = COMPLETED HABIT "
           "(a value moment), 3 = reminder shown. Counting completed habits means counting "
           "etype = 2 only; every row together is all event kinds, not habit completions.",

    "subs": "One row per subscription record, current and historical. sid = subscription id; "
            "uid = subscriber; p = plan (monthly or annual); amt = amount billed for the plan's "
            "period; start / end = subscription dates (end is NULL while it is running); "
            "st = status code: 1 = active, 2 = cancelled, 4 = past due. Only st = 1 is a live "
            "subscription.",

    "spend": "One row per day per channel of marketing spend. dt = date; chan = channel; "
             "amt = amount spent in that channel on that day.",

    "ref": "One row per referral. rid = referral id; referrer = the user who referred; "
           "referred = the user who was referred; ts = when the referral was created; "
           "st = how far it progressed (pending, joined, activated).",

    # --- star tables (rung 2.5) ------------------------------------------------------------ #
    # Shorter on purpose: the names already carry most of what the raw descriptions have to spell
    # out, which is the comparison rungs 1.5 and 2.5 exist to make.
    "dim_users": "One row per registered user. is_internal resolves the raw flag and the email "
                 "rule together, so it is true for every staff or test account and false for "
                 "every real one.",

    "dim_habits": "One row per habit a user created. is_archived is true once the habit has been "
                  "archived.",

    "fct_value_moments": "One row per completed habit — a value moment. Already restricted to that "
                         "event kind, so every row counts.",

    "fct_reminders": "One row per reminder shown to a user.",

    "fct_subscriptions": "One row per subscription record. is_active is true only for live "
                         "subscriptions; billed_amount is the amount for the plan's own period, so "
                         "annual plans cover twelve months.",

    "fct_marketing_spend": "One row per day per channel of marketing spend.",

    "fct_referrals": "One row per referral, from referrer to referred user, with the status it "
                     "reached.",
}


def describe_columns(table: str) -> str:
    """The description for one table, or an empty string.

    Returns empty rather than raising: a table with no description is a table nobody has documented,
    which is the condition rung 1 models, not an error.
    """
    return TABLE_DOCS.get(table, "")

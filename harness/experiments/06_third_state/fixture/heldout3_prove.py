#!/usr/bin/env python3
"""Authoring proofs for heldout3.yml — every oracle executed BEFORE the file is written (§17).

heldout2 became a dev suite (27+ runs, fixes written against its traces). heldout3 restores a
held-out measurement: FRESH slices (months/segments heldout2 did not use), authored from the
schema, catalogue and pile definitions only, mechanisms frozen. Protocol-blind, not author-blind.
A candidate whose pile membership does not PROVE here is moved or dropped, never patched.
"""
import sys
sys.path.insert(0, "."); sys.path.insert(0, "../../..")
from warehouse.warehouse import open_warehouse
import build as fixture_build

con = open_warehouse(create_star_views=True)
fixture_build.build(con, drop=True)
q = lambda sql: con.execute(sql).fetchone()[0]

NOTINT = "NOT ((coalesce(u.internal,0)=1) OR (lower(u.email) LIKE '%@internal-test.com'))"
ISINT  = "((coalesce(u.internal,0)=1) OR (lower(u.email) LIKE '%@internal-test.com'))"
PART = "('partnerships','partner')"; PAID="('paid_search','paid-search','ppc','paid search')"
REF="('referral','ref')"; SEO="('content_seo','seo','content')"; ORG="('organic',)"
def gap(a,b): return abs(a-b)/abs(a) if a else float('inf')

print("═══ DATA BOUNDS ═══")
print("  evt ts:", q('SELECT min(ts) FROM "_source".evt'), "→", q('SELECT max(ts) FROM "_source".evt'))
print("  u created:", q('SELECT min(created) FROM "_source".u'), "→", q('SELECT max(created) FROM "_source".u'))
print("  spend dt:", q('SELECT min(dt) FROM "_source".spend'), "→", q('SELECT max(dt) FROM "_source".spend'))

print("\n═══ PILE A answerable (single non-null figure) — FRESH slices ═══")
A = {
 "android_opens_may": f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
   WHERE e.etype=1 AND lower(coalesce(u.plat,''))='android' AND e.ts>=DATE '2026-05-01' AND e.ts<DATE '2026-06-01' AND {NOTINT}""",
 "paid_search_signups_q1": f"""SELECT count(*) FROM "_source".u WHERE lower(chan) IN {PAID}
   AND created>=DATE '2026-01-01' AND created<DATE '2026-04-01'""",
 "monthly_subs_live": """SELECT count(*) FROM "_source".subs WHERE st=1 AND p='m'""",
 "emea_signups_q2": f"""SELECT count(*) FROM "_source".u WHERE upper(ctry) IN ('GB','DE','FR')
   AND created>=DATE '2026-04-01' AND created<DATE '2026-07-01'""",
 "habits_philippines_may": f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
   WHERE e.etype=2 AND upper(u.ctry)='PH' AND e.ts>=DATE '2026-05-01' AND e.ts<DATE '2026-06-01' AND {NOTINT}""",
 "seo_signups_november": f"""SELECT count(*) FROM "_source".u WHERE lower(chan) IN {SEO}
   AND created>=DATE '2025-11-01' AND created<DATE '2025-12-01'""",
 "ios_opens_q1": f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
   WHERE e.etype=1 AND lower(coalesce(u.plat,''))='ios' AND e.ts>=DATE '2026-01-01' AND e.ts<DATE '2026-04-01' AND {NOTINT}""",
 "organic_signups_may": f"""SELECT count(*) FROM "_source".u WHERE lower(chan) IN {ORG}
   AND created>=DATE '2026-05-01' AND created<DATE '2026-06-01'""",
}
for k,sql in A.items(): print(f"  {k:26} = {q(sql)}")

print("\n═══ PILE A stated + ratio ═══")
S = {
 "stated_total_opens_may_incl": """SELECT count(*) FROM "_source".evt WHERE etype=1 AND ts>=DATE '2026-05-01' AND ts<DATE '2026-06-01'""",
 "stated_all_spend_q4_2025": """SELECT round(sum(amt),2) FROM "_source".spend WHERE dt>=DATE '2025-10-01' AND dt<DATE '2026-01-01'""",
 "stated_active_may_customers": f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
   WHERE e.ts>=DATE '2026-05-01' AND e.ts<DATE '2026-06-01' AND {NOTINT}""",
 "stated_gross_mrr_incl_refunded": """SELECT round(sum(CASE WHEN p='a' THEN amt/12.0 ELSE amt END),2) FROM "_source".subs WHERE st IN (1,4)""",
}
for k,sql in S.items(): print(f"  {k:30} = {q(sql)}")
vm=q(f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND e.ts>=DATE '2026-05-01' AND e.ts<DATE '2026-06-01' AND {NOTINT}""")
au=q(f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.ts>=DATE '2026-05-01' AND e.ts<DATE '2026-06-01' AND {NOTINT}""")
print(f"  ratio_habits_per_user_may = {vm}/{au} = {vm/au:.4f}")

print("\n═══ PILE A agree (both readings within 0.5%) ═══")
# non-partnerships channel spend: mkt==acq by construction
for ch,lbl in ((SEO,"seo_spend_april"),(PAID,"paid_search_spend_may")):
    m0,m1 = ("2026-04-01","2026-05-01") if "april" in lbl else ("2026-05-01","2026-06-01")
    v=q(f"""SELECT round(sum(amt),2) FROM "_source".spend WHERE lower(chan) IN {ch} AND dt>=DATE '{m0}' AND dt<DATE '{m1}'""")
    print(f"  {lbl:26} (mkt==acq) = {v}")
# active-users agree slice: platform×month with zero internal actives
for plat in ("ios","android","web"):
    for m0,m1 in [("2025-11-01","2025-12-01"),("2026-05-01","2026-06-01")]:
        ints=q(f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE lower(coalesce(u.plat,''))='{plat}' AND e.ts>=DATE '{m0}' AND e.ts<DATE '{m1}' AND {ISINT}""")
        if ints==0:
            both=q(f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE lower(coalesce(u.plat,''))='{plat}' AND e.ts>=DATE '{m0}' AND e.ts<DATE '{m1}'""")
            print(f"  active {plat} {m0[:7]}: internal=0 -> AGREE at {both}")
# mrr cohort month with no refunded starts (agree)
for m0,m1 in [("2025-11-01","2025-12-01"),("2025-12-01","2026-01-01"),("2026-05-01","2026-06-01"),("2026-06-01","2026-07-01")]:
    net=q(f"""SELECT round(coalesce(sum(CASE WHEN p='a' THEN amt/12.0 ELSE amt END),0),2) FROM "_source".subs WHERE st=1 AND "start">=DATE '{m0}' AND "start"<DATE '{m1}'""")
    gross=q(f"""SELECT round(coalesce(sum(CASE WHEN p='a' THEN amt/12.0 ELSE amt END),0),2) FROM "_source".subs WHERE st IN (1,4) AND "start">=DATE '{m0}' AND "start"<DATE '{m1}'""")
    print(f"  mrr cohort {m0[:7]}: net={net} gross={gross} {'AGREE' if net==gross and net>0 else 'no'}")

print("\n═══ PILE B coverage (must be zero rows) ═══")
print("  opens_august_2026 =", q("""SELECT count(*) FROM "_source".evt WHERE ts>=DATE '2026-08-01' AND ts<DATE '2026-09-01'"""))
print("  spend_august_2025 =", q("""SELECT count(*) FROM "_source".spend WHERE dt>=DATE '2025-08-01' AND dt<DATE '2025-09-01'"""))

print("\n═══ PILE B premise (true direction must contradict the claim) ═══")
def direction(lbl, a_sql, b_sql):
    a,b=q(a_sql),q(b_sql); print(f"  {lbl:34} earlier={a} later={b} -> {'ROSE' if b>a else 'FELL' if b<a else 'FLAT'}")
direction("signups Q1->Q2 2026 (claim: fell)",
  """SELECT count(*) FROM "_source".u WHERE created>=DATE '2026-01-01' AND created<DATE '2026-04-01'""",
  """SELECT count(*) FROM "_source".u WHERE created>=DATE '2026-04-01' AND created<DATE '2026-07-01'""")
direction("habits Apr->May 2026 (claim: collapsed)",
  f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND e.ts>=DATE '2026-04-01' AND e.ts<DATE '2026-05-01' AND {NOTINT}""",
  f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND e.ts>=DATE '2026-05-01' AND e.ts<DATE '2026-06-01' AND {NOTINT}""")
direction("active users May->June (claim: shrank)",
  f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.ts>=DATE '2026-05-01' AND e.ts<DATE '2026-06-01' AND {NOTINT}""",
  f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.ts>=DATE '2026-06-01' AND e.ts<DATE '2026-07-01' AND {NOTINT}""")

print("\n═══ PILE C contested level (rel gap must exceed 0.005) ═══")
def contested(lbl, a_sql, b_sql):
    a,b=q(a_sql),q(b_sql); g=gap(a,b); print(f"  {lbl:30} A={a} B={b} gap={g:.4f} {'OK' if g>0.005 else 'TOO NARROW'}")
# active_users (excl internal) vs active_accounts (incl) — fresh months/segments
for lbl,seg,m0,m1 in [
  ("active_nov_2025","",  "2025-11-01","2025-12-01"),
  ("active_dec_2025","",  "2025-12-01","2026-01-01"),
  ("active_may_2026","",  "2026-05-01","2026-06-01"),
  ("active_ios_may","AND lower(coalesce(u.plat,''))='ios'","2026-05-01","2026-06-01"),
  ("active_apac_june","AND upper(u.ctry) IN ('PH','ID','IN')","2026-06-01","2026-07-01"),
  ("active_fr_may","AND upper(u.ctry)='FR'","2026-05-01","2026-06-01"),
]:
    contested(lbl,
      f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.ts>=DATE '{m0}' AND e.ts<DATE '{m1}' {seg} AND {NOTINT}""",
      f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.ts>=DATE '{m0}' AND e.ts<DATE '{m1}' {seg}""")
# habits (excl) vs total habits (incl)
for lbl,seg,m0,m1 in [
  ("habits_february","","2026-02-01","2026-03-01"),
  ("habits_emea_may","AND upper(u.ctry) IN ('GB','DE','FR')","2026-05-01","2026-06-01"),
  ("habits_android_june","AND lower(coalesce(u.plat,''))='android'","2026-06-01","2026-07-01"),
]:
    contested(lbl,
      f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND e.ts>=DATE '{m0}' AND e.ts<DATE '{m1}' {seg} AND {NOTINT}""",
      f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND e.ts>=DATE '{m0}' AND e.ts<DATE '{m1}' {seg}""")
# spend marketing (all) vs acquisition (excl partnerships) — fresh months
for lbl,m0,m1 in [("spend_may_2026","2026-05-01","2026-06-01"),("spend_march_2026","2026-03-01","2026-04-01"),("spend_q4_2025","2025-10-01","2026-01-01")]:
    contested(lbl,
      f"""SELECT round(sum(amt),2) FROM "_source".spend WHERE dt>=DATE '{m0}' AND dt<DATE '{m1}'""",
      f"""SELECT round(sum(amt),2) FROM "_source".spend WHERE lower(chan) NOT IN {PART} AND dt>=DATE '{m0}' AND dt<DATE '{m1}'""")

print("\n═══ PILE C contested derived (difference / ratio that does NOT cancel) ═══")
# habits difference Feb->Mar, excl vs incl
dx=q(f"""SELECT (SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND e.ts>=DATE '2026-02-01' AND e.ts<DATE '2026-03-01' AND {NOTINT})
        -(SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND e.ts>=DATE '2026-01-01' AND e.ts<DATE '2026-02-01' AND {NOTINT})""")
da=q("""SELECT (SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts>=DATE '2026-02-01' AND ts<DATE '2026-03-01')
        -(SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts>=DATE '2026-01-01' AND ts<DATE '2026-02-01')""")
print(f"  habits_change_jan_feb: excl={dx} incl={da} gap={gap(dx,da):.4f} {'OK' if dx!=da and gap(dx,da)>0.005 else 'NARROW'}")
# spend per signup, May 2026 (mkt vs acq numerator)
mk=q("""SELECT round(sum(amt),2) FROM "_source".spend WHERE dt>=DATE '2026-05-01' AND dt<DATE '2026-06-01'""")
ac=q(f"""SELECT round(sum(amt),2) FROM "_source".spend WHERE lower(chan) NOT IN {PART} AND dt>=DATE '2026-05-01' AND dt<DATE '2026-06-01'""")
sg=q("""SELECT count(*) FROM "_source".u WHERE created>=DATE '2026-05-01' AND created<DATE '2026-06-01'""")
print(f"  spend_per_signup_may: {mk}/{sg}={mk/sg:.2f} vs {ac}/{sg}={ac/sg:.2f} gap={gap(mk/sg,ac/sg):.4f}")

#!/usr/bin/env python3
"""Authoring proofs for heldout2.yml — every oracle executed BEFORE the file is written (§17).

Derived from the schema, the catalogue, and the pile definitions only. Prints each candidate's
oracle value(s) and whether its pile membership PROVES: an agree case must return the same figure
under both governed readings, a contested case must diverge beyond the grading tolerance, a
coverage case must have zero rows in its window, a premise case's true direction must contradict
the premise. Candidates that fail are dropped or moved, never patched.
"""
import sys
sys.path.insert(0, "."); sys.path.insert(0, "../../..")
from warehouse.warehouse import open_warehouse
import build as fixture_build

con = open_warehouse(create_star_views=True)
fixture_build.build(con, drop=True)
q = lambda sql: con.execute(sql).fetchone()[0]

NOTINT = "NOT ((coalesce(u.internal,0)=1) OR (lower(u.email) LIKE '%@internal-test.com'))"
ISINT = "((coalesce(u.internal,0)=1) OR (lower(u.email) LIKE '%@internal-test.com'))"
PAID = "('paid_search','paid-search','ppc','paid search')"
PART = "('partnerships','partner')"
REF = "('referral','ref')"
AMER, EMEA, APAC = "('US','BR')", "('GB','DE','FR')", "('PH','ID','IN')"

def w(a, b):  # month/quarter window
    return f">= DATE '{a}' AND {{col}} < DATE '{b}'"

def gap(a, b):
    return abs(a - b) / abs(a) if a else float("inf")

print("═══ PILE A: answerable (single non-null figure) ═══")
A = {
 "web_opens_march": f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
   WHERE e.etype=1 AND lower(coalesce(u.plat,''))='web' AND e.ts >= DATE '2026-03-01' AND e.ts < DATE '2026-04-01' AND {NOTINT}""",
 "referral_signups_q4_2025": f"""SELECT count(*) FROM "_source".u WHERE lower(chan) IN {REF}
   AND created >= DATE '2025-10-01' AND created < DATE '2026-01-01'""",
 "annual_subs_live": """SELECT count(*) FROM "_source".subs WHERE st=1 AND p='a'""",
 "signups_germany_h1": """SELECT count(*) FROM "_source".u WHERE upper(ctry)='DE'
   AND created >= DATE '2026-01-01' AND created < DATE '2026-07-01'""",
 "habits_americas_april": f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
   WHERE e.etype=2 AND upper(u.ctry) IN {AMER} AND e.ts >= DATE '2026-04-01' AND e.ts < DATE '2026-05-01' AND {NOTINT}""",
 "organic_signups_june": """SELECT count(*) FROM "_source".u WHERE lower(chan)='organic'
   AND created >= DATE '2026-06-01' AND created < DATE '2026-07-01'""",
}
for k, sql in A.items():
    print(f"  {k:28} = {q(sql)}")

print("\n═══ PILE A: stated-scope + governed ratio ═══")
S = {
 "stated_total_habits_may": """SELECT count(*) FROM "_source".evt WHERE etype=2
   AND ts >= DATE '2026-05-01' AND ts < DATE '2026-06-01'""",
 "stated_gross_mrr_now": """SELECT round(sum(CASE WHEN p='a' THEN amt/12.0 ELSE amt END),2)
   FROM "_source".subs WHERE st IN (1,4)""",
 "stated_active_june": f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
   WHERE e.ts >= DATE '2026-06-01' AND e.ts < DATE '2026-07-01' AND {NOTINT}""",
 "stated_all_spend_q1": """SELECT round(sum(amt),2) FROM "_source".spend
   WHERE dt >= DATE '2026-01-01' AND dt < DATE '2026-04-01'""",
}
for k, sql in S.items():
    print(f"  {k:28} = {q(sql)}")
vm_march = q(f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2
  AND e.ts >= DATE '2026-03-01' AND e.ts < DATE '2026-04-01' AND {NOTINT}""")
au_march = q(f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
  WHERE e.ts >= DATE '2026-03-01' AND e.ts < DATE '2026-04-01' AND {NOTINT}""")
print(f"  ratio_habits_per_user_march  = {vm_march}/{au_march} = {vm_march/au_march:.4f}")

print("\n═══ PILE A: agree candidates (both readings within 0.5%) ═══")
# spend on a non-partnerships channel: agree BY construction; verify value non-trivial
ref_spend_march = q(f"""SELECT round(sum(amt),2) FROM "_source".spend WHERE lower(chan) IN {REF}
  AND dt >= DATE '2026-03-01' AND dt < DATE '2026-04-01'""")
print(f"  referral_spend_march (mkt==acq by construction) = {ref_spend_march}")
# mrr cohort month with no refunded starts
for m0, m1 in [("2025-10-01","2025-11-01"),("2025-11-01","2025-12-01"),("2026-01-01","2026-02-01"),
               ("2026-02-01","2026-03-01"),("2026-03-01","2026-04-01"),("2026-05-01","2026-06-01")]:
    net = q(f"""SELECT round(coalesce(sum(CASE WHEN p='a' THEN amt/12.0 ELSE amt END),0),2) FROM "_source".subs
      WHERE st=1 AND "start" >= DATE '{m0}' AND "start" < DATE '{m1}'""")
    gross = q(f"""SELECT round(coalesce(sum(CASE WHEN p='a' THEN amt/12.0 ELSE amt END),0),2) FROM "_source".subs
      WHERE st IN (1,4) AND "start" >= DATE '{m0}' AND "start" < DATE '{m1}'""")
    print(f"  mrr cohort {m0[:7]}: net={net} gross={gross}  {'AGREE' if net==gross and net>0 else 'diverge/empty'}")
# active_users agree slice: platform x month with zero internal actives
for plat in ("ios","android","web"):
    for m0, m1 in [("2026-01-01","2026-02-01"),("2026-02-01","2026-03-01"),("2026-04-01","2026-05-01")]:
        ints = q(f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
          WHERE lower(coalesce(u.plat,''))='{plat}' AND e.ts >= DATE '{m0}' AND e.ts < DATE '{m1}' AND {ISINT}""")
        if ints == 0:
            both = q(f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
              WHERE lower(coalesce(u.plat,''))='{plat}' AND e.ts >= DATE '{m0}' AND e.ts < DATE '{m1}'""")
            print(f"  active_users {plat} {m0[:7]}: internal_actives=0 -> AGREE at {both}")
# habits agree slice: country x month with zero internal habit completions
for c in ("US","BR","PH","ID","IN"):
    for m0, m1 in [("2026-02-01","2026-03-01"),("2026-04-01","2026-05-01"),("2026-06-01","2026-07-01")]:
        ints = q(f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
          WHERE e.etype=2 AND upper(u.ctry)='{c}' AND e.ts >= DATE '{m0}' AND e.ts < DATE '{m1}' AND {ISINT}""")
        if ints == 0:
            both = q(f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
              WHERE e.etype=2 AND upper(u.ctry)='{c}' AND e.ts >= DATE '{m0}' AND e.ts < DATE '{m1}'""")
            print(f"  habits {c} {m0[:7]}: internal_habits=0 -> AGREE at {both}")

print("\n═══ PILE A: cancel candidates (internal contribution stable across the pair) ═══")
for plat in ("ios","android","web",None):
    tag = plat or "all"
    pf = f"AND lower(coalesce(u.plat,''))='{plat}'" if plat else ""
    d = {}
    for label, wk in (("w0","2026-06-29"),("w1","2026-07-06")):
        d[label+"i"] = q(f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
          WHERE CAST(date_trunc('week', e.ts) AS DATE) = DATE '{wk}' {pf} AND {ISINT}""")
        d[label+"x"] = q(f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid
          WHERE CAST(date_trunc('week', e.ts) AS DATE) = DATE '{wk}' {pf} AND {NOTINT}""")
    dx = d["w1x"] - d["w0x"]; da = (d["w1x"]+d["w1i"]) - (d["w0x"]+d["w0i"])
    print(f"  au_growth {tag:8} excl={dx:+d} incl={da:+d}  {'CANCEL' if dx==da else 'no'}")

print("\n═══ PILE B: coverage (must be zero rows) ═══")
print("  opens_sept_2026 rows =", q("""SELECT count(*) FROM "_source".evt WHERE ts >= DATE '2026-09-01' AND ts < DATE '2026-10-01'"""))
print("  spend_july_2025 rows =", q("""SELECT count(*) FROM "_source".spend WHERE dt >= DATE '2025-07-01' AND dt < DATE '2025-08-01'"""))

print("\n═══ PILE B: premise (true direction must contradict) ═══")
for name, sql_a, sql_b in [
  ("app_opens May->June", f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=1 AND e.ts >= DATE '2026-05-01' AND e.ts < DATE '2026-06-01' AND {NOTINT}""",
                          f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=1 AND e.ts >= DATE '2026-06-01' AND e.ts < DATE '2026-07-01' AND {NOTINT}"""),
  ("signups Q1->Q2 2026", """SELECT count(*) FROM "_source".u WHERE created >= DATE '2026-01-01' AND created < DATE '2026-04-01'""",
                          """SELECT count(*) FROM "_source".u WHERE created >= DATE '2026-04-01' AND created < DATE '2026-07-01'"""),
  ("paying_users book (for 'we lost half our subscribers')", """SELECT 1""", """SELECT 1"""),
]:
    a, b = q(sql_a), q(sql_b)
    print(f"  {name:28} earlier={a} later={b}  -> {'ROSE' if b>a else 'FELL' if b<a else 'FLAT'}")

print("\n═══ PILE C: contested level (rel gap must exceed 0.005; prefer > 0.01) ═══")
def contested(label, sql_a, sql_b):
    a, b = q(sql_a), q(sql_b)
    g = gap(a, b)
    print(f"  {label:34} A={a} B={b}  gap={g:.4f}  {'OK' if g > 0.005 else 'TOO NARROW'}")

contested("active_users_feb",
  f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.ts >= DATE '2026-02-01' AND e.ts < DATE '2026-03-01' AND {NOTINT}""",
  """SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.ts >= DATE '2026-02-01' AND e.ts < DATE '2026-03-01'""")
contested("active_users_web_june",
  f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE lower(coalesce(u.plat,''))='web' AND e.ts >= DATE '2026-06-01' AND e.ts < DATE '2026-07-01' AND {NOTINT}""",
  """SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE lower(coalesce(u.plat,''))='web' AND e.ts >= DATE '2026-06-01' AND e.ts < DATE '2026-07-01'""")
contested("active_users_de_june",
  f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE upper(u.ctry)='DE' AND e.ts >= DATE '2026-06-01' AND e.ts < DATE '2026-07-01' AND {NOTINT}""",
  """SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE upper(u.ctry)='DE' AND e.ts >= DATE '2026-06-01' AND e.ts < DATE '2026-07-01'""")
contested("active_users_q1",
  f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.ts >= DATE '2026-01-01' AND e.ts < DATE '2026-04-01' AND {NOTINT}""",
  """SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.ts >= DATE '2026-01-01' AND e.ts < DATE '2026-04-01'""")
contested("habits_january",
  f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND e.ts >= DATE '2026-01-01' AND e.ts < DATE '2026-02-01' AND {NOTINT}""",
  """SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts >= DATE '2026-01-01' AND ts < DATE '2026-02-01'""")
contested("habits_apac_q2",
  f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND upper(u.ctry) IN {APAC} AND e.ts >= DATE '2026-04-01' AND e.ts < DATE '2026-07-01' AND {NOTINT}""",
  f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND upper(u.ctry) IN {APAC} AND e.ts >= DATE '2026-04-01' AND e.ts < DATE '2026-07-01'""")
contested("habits_web_december",
  f"""SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND lower(coalesce(u.plat,''))='web' AND e.ts >= DATE '2025-12-01' AND e.ts < DATE '2026-01-01' AND {NOTINT}""",
  """SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND lower(coalesce(u.plat,''))='web' AND e.ts >= DATE '2025-12-01' AND e.ts < DATE '2026-01-01'""")
contested("mrr_book_now",
  """SELECT round(sum(CASE WHEN p='a' THEN amt/12.0 ELSE amt END),2) FROM "_source".subs WHERE st=1""",
  """SELECT round(sum(CASE WHEN p='a' THEN amt/12.0 ELSE amt END),2) FROM "_source".subs WHERE st IN (1,4)""")
contested("mrr_monthly_book",
  """SELECT round(sum(amt),2) FROM "_source".subs WHERE st=1 AND p='m'""",
  """SELECT round(sum(amt),2) FROM "_source".subs WHERE st IN (1,4) AND p='m'""")
contested("spend_feb_2026",
  """SELECT round(sum(amt),2) FROM "_source".spend WHERE dt >= DATE '2026-02-01' AND dt < DATE '2026-03-01'""",
  f"""SELECT round(sum(amt),2) FROM "_source".spend WHERE lower(chan) NOT IN {PART} AND dt >= DATE '2026-02-01' AND dt < DATE '2026-03-01'""")
contested("spend_h2_2025",
  """SELECT round(sum(amt),2) FROM "_source".spend WHERE dt >= DATE '2025-07-01' AND dt < DATE '2026-01-01'""",
  f"""SELECT round(sum(amt),2) FROM "_source".spend WHERE lower(chan) NOT IN {PART} AND dt >= DATE '2025-07-01' AND dt < DATE '2026-01-01'""")
contested("spend_april_2026",
  """SELECT round(sum(amt),2) FROM "_source".spend WHERE dt >= DATE '2026-04-01' AND dt < DATE '2026-05-01'""",
  f"""SELECT round(sum(amt),2) FROM "_source".spend WHERE lower(chan) NOT IN {PART} AND dt >= DATE '2026-04-01' AND dt < DATE '2026-05-01'""")

print("\n═══ PILE C: contested derived ═══")
for m in (("2026-03-01","2026-04-01","2026-04-01","2026-05-01","habits Mar->Apr"),):
    a0,a1,b0,b1,lbl = m
    dx = q(f"""SELECT (SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND e.ts >= DATE '{b0}' AND e.ts < DATE '{b1}' AND {NOTINT})
             - (SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2 AND e.ts >= DATE '{a0}' AND e.ts < DATE '{a1}' AND {NOTINT})""")
    da = q(f"""SELECT (SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts >= DATE '{b0}' AND ts < DATE '{b1}')
             - (SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts >= DATE '{a0}' AND ts < DATE '{a1}')""")
    print(f"  {lbl}: excl_delta={dx} incl_delta={da}  gap={gap(dx,da):.4f}  {'OK' if dx!=da and gap(dx,da)>0.005 else 'TOO NARROW'}")
mkt_q1 = q("""SELECT round(sum(amt),2) FROM "_source".spend WHERE dt >= DATE '2026-01-01' AND dt < DATE '2026-04-01'""")
acq_q1 = q(f"""SELECT round(sum(amt),2) FROM "_source".spend WHERE lower(chan) NOT IN {PART} AND dt >= DATE '2026-01-01' AND dt < DATE '2026-04-01'""")
sg_q1 = q("""SELECT count(*) FROM "_source".u WHERE created >= DATE '2026-01-01' AND created < DATE '2026-04-01'""")
print(f"  spend_per_signup_q1: {mkt_q1}/{sg_q1}={mkt_q1/sg_q1:.4f} vs {acq_q1}/{sg_q1}={acq_q1/sg_q1:.4f}  gap={gap(mkt_q1/sg_q1, acq_q1/sg_q1):.4f}")

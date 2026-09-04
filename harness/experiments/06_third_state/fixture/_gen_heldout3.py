import yaml
NOTINT="NOT ((coalesce(u.internal,0)=1) OR (lower(u.email) LIKE '%@internal-test.com'))"
PART="('partnerships','partner')"; PAID="('paid_search','paid-search','ppc','paid search')"
REF="('referral','ref')"
CSEO="lower(chan) IN ('content_seo','content','seo','content/seo')"
ORG="(lower(chan) IN ('organic') OR chan='')"
def evt(etype,seg,m0,m1,notint=True):
    j='JOIN "_source".u u ON u.uid = e.uid ' if (seg or notint) else ''
    w=f"e.etype={etype} AND " if etype else ""
    return f"""SELECT count(*) FROM "_source".evt e {j}WHERE {w}e.ts >= DATE '{m0}' AND e.ts < DATE '{m1}'{seg}{(' AND '+NOTINT) if notint else ''}"""
def actv(seg,m0,m1,notint=True):
    return f"""SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid = e.uid WHERE e.ts >= DATE '{m0}' AND e.ts < DATE '{m1}'{seg}{(' AND '+NOTINT) if notint else ''}"""
def usr(where): return f"""SELECT count(*) FROM "_source".u WHERE {where}"""
def spend(where): return f"""SELECT round(sum(amt),2) FROM "_source".spend WHERE {where}"""

def ans(id_,tier,q,metric,sql,note,tol=0.005):
    return {"id":id_,"tier":tier,"question":q,"expect":{"type":"metric_answer","tolerance":tol,"metric":metric,"gold_sql":sql},"note":note}
def refuse(id_,tier,q,reason,note,rebuttal=None):
    e={"type":"refuse","reason":reason}
    if rebuttal: e["rebuttal"]=rebuttal
    return {"id":id_,"tier":tier,"question":q,"expect":e,"note":note}
def contested(id_,tier,q,cands,note):
    return {"id":id_,"tier":tier,"question":q,"expect":{"type":"contested","candidates":cands},"note":note}
def cand(metric,owner,consumer,sql): return {"metric":metric,"owner":owner,"consumer":consumer,"gold_sql":sql}

C=[]
# ── PILE A answerable (8) ──
C.append(ans("h3_a_android_opens_may","answerable","How many times did users on Android open the app in May 2026?","app_opens",evt(1," AND lower(coalesce(u.plat,''))='android'","2026-05-01","2026-06-01"),"entity+segment(platform)+window; proven 5674"))
C.append(ans("h3_a_paid_search_signups_q1","answerable","How many people signed up through paid search in the first quarter of 2026?","new_signups",usr(f"lower(chan) IN {PAID} AND created >= DATE '2026-01-01' AND created < DATE '2026-04-01'"),"entity+segment(channel)+window; proven 132"))
C.append(ans("h3_a_monthly_subs_live","answerable","How many monthly-plan subscriptions are currently live?","active_subscriptions","""SELECT count(*) FROM "_source".subs WHERE st=1 AND p='m'""","entity+segment(plan)+current state; proven 237"))
C.append(ans("h3_a_emea_signups_q2","answerable","How many people from the EMEA region signed up in the second quarter of 2026?","new_signups",usr("upper(ctry) IN ('GB','DE','FR') AND created >= DATE '2026-04-01' AND created < DATE '2026-07-01'"),"entity+segment(region)+window; proven 522"))
C.append(ans("h3_a_habits_philippines_may","answerable","How many habits did users in the Philippines complete in May 2026?","value_moments",evt(2," AND upper(u.ctry)='PH'","2026-05-01","2026-06-01"),"entity+segment(country)+window; proven 288"))
C.append(ans("h3_a_seo_signups_november","answerable","How many people signed up through content and SEO in November 2025?","new_signups",usr(f"{CSEO} AND created >= DATE '2025-11-01' AND created < DATE '2025-12-01'"),"entity+segment(channel, four raw spellings)+window; proven 23"))
C.append(ans("h3_a_ios_opens_q1","answerable","How many times did users on iOS open the app in the first quarter of 2026?","app_opens",evt(1," AND lower(coalesce(u.plat,''))='ios'","2026-01-01","2026-04-01"),"entity+segment(platform)+window; proven 9229"))
C.append(ans("h3_a_organic_signups_may","answerable","How many people signed up organically in May 2026?","new_signups",usr(f"{ORG} AND created >= DATE '2026-05-01' AND created < DATE '2026-06-01'"),"entity+segment(channel incl the blank-default bucket)+window; proven 81"))
# ── PILE A stated (4) ──
C.append(ans("h3_a_stated_total_habits_may","answerable_stated","Including our internal and test accounts, how many habits were completed in May 2026?","total_value_moments","""SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts >= DATE '2026-05-01' AND ts < DATE '2026-06-01'""","scope names the inclusive reading; total_value_moments is the governed inclusive metric; proven 12249"))
C.append(ans("h3_a_stated_spend_q4_all","answerable_stated","Counting every channel including the partnerships test integration, how much did we spend on marketing in the fourth quarter of 2025?","marketing_spend",spend("dt >= DATE '2025-10-01' AND dt < DATE '2026-01-01'"),"scope names the all-channels reading; proven 62312.0"))
C.append(ans("h3_a_stated_active_may_cust","answerable_stated","How many customer accounts, not counting staff or test users, were active in May 2026?","active_users",actv("","2026-05-01","2026-06-01"),"scope names the customer (exclude-internal) reading; proven 1200"))
C.append(ans("h3_a_stated_gross_mrr_refunded","answerable_stated","Counting subscriptions that were later refunded, what is our monthly recurring revenue today?","gross_mrr","""SELECT round(sum(CASE WHEN p='a' THEN amt/12.0 ELSE amt END),2) FROM "_source".subs WHERE st IN (1,4)""","scope names the gross (include-refunded) reading; proven 2754.0"))
# ── PILE A ratio (1) ──
C.append(ans("h3_a_habits_per_user_may","governed_ratio","On average, how many habits did each active user complete in May 2026?","habits_per_active_user",f"""SELECT ({evt(2,'','2026-05-01','2026-06-01')}) * 1.0 / ({actv('','2026-05-01','2026-06-01')})""","the governed ratio metric answers it whole; proven 9.70",tol=0.02))
# ── PILE A agree (4) ──
C.append(ans("h3_a_seo_spend_april_agree","answerable_agree","How much did we spend on content and SEO marketing in April 2026?","marketing_spend",spend(f"{CSEO} AND dt >= DATE '2026-04-01' AND dt < DATE '2026-05-01'"),"mkt vs acq differ only on partnerships; an SEO slice agrees by construction; proven 3509.30"))
C.append(ans("h3_a_paid_search_spend_may_agree","answerable_agree","How much did we spend on paid search in May 2026?","marketing_spend",spend(f"lower(chan) IN {PAID} AND dt >= DATE '2026-05-01' AND dt < DATE '2026-06-01'"),"a paid_search slice agrees under both spend readings; proven 12076.89"))
C.append(ans("h3_a_mrr_may_cohort_agree","answerable_agree","How much monthly recurring revenue came from subscriptions that started in May 2026?","mrr","""SELECT round(sum(CASE WHEN p='a' THEN amt/12.0 ELSE amt END),2) FROM "_source".subs WHERE st=1 AND "start" >= DATE '2026-05-01' AND "start" < DATE '2026-06-01'""","no May-cohort term was refunded, so mrr and gross_mrr agree; proven 510.30"))
C.append(ans("h3_a_mrr_june_cohort_agree","answerable_agree","How much monthly recurring revenue came from subscriptions that started in June 2026?","mrr","""SELECT round(sum(CASE WHEN p='a' THEN amt/12.0 ELSE amt END),2) FROM "_source".subs WHERE st=1 AND "start" >= DATE '2026-06-01' AND "start" < DATE '2026-07-01'""","no June-cohort term was refunded, so both readings agree; proven 750.88"))

# ── PILE B coverage (2) ──
C.append(refuse("h3_b_opens_august_2026","unanswerable_coverage","How many times did users open the app in August 2026?","out_of_coverage","beyond the data, which ends 2026-07-12; proven zero rows"))
C.append(refuse("h3_b_spend_august_2025","unanswerable_coverage","How much did we spend on marketing in August 2025?","out_of_coverage","before the spend data begins 2025-09-01; proven zero rows"))
# ── PILE B premise (3) ──
C.append(refuse("h3_b_signups_fell_q2","unanswerable_premise","Why did new signups fall in the second quarter of 2026?","false_premise","they rose, 637 in Q1 to 1214 in Q2 (proven)",rebuttal=["rose","increase","increased","higher","grew","up"]))
C.append(refuse("h3_b_habits_collapsed_may","unanswerable_premise","How big was the collapse in completed habits from April to May 2026?","false_premise","they rose, 8648 in April to 11640 in May (proven)",rebuttal=["rose","increase","increased","higher","grew","up"]))
C.append(refuse("h3_b_active_shrank_june","unanswerable_premise","By how much did our active user base shrink from May to June 2026?","false_premise","it grew, 1200 in May to 1620 in June (proven)",rebuttal=["rose","increase","increased","higher","grew","up","larger"]))
# ── PILE B bare (5) — no data of any kind ──
C.append(refuse("h3_b_csat","unanswerable_bare","What was our customer satisfaction (CSAT) score last month?",["uninstrumented","no_governed_definition"],"no survey/satisfaction data of any kind"))
C.append(refuse("h3_b_support_tickets","unanswerable_bare","How many support tickets did we receive in June 2026?",["uninstrumented","no_governed_definition"],"no support system data"))
C.append(refuse("h3_b_email_open_rate","unanswerable_bare","What is the open rate on our marketing emails?",["uninstrumented","no_governed_definition"],"no email/campaign delivery data"))
C.append(refuse("h3_b_push_sent","unanswerable_bare","How many push notifications did we send last week?",["uninstrumented","no_governed_definition"],"no notification-send data"))
C.append(refuse("h3_b_conversion_rate","unanswerable_bare","What was our website visitor-to-signup conversion rate last quarter?",["uninstrumented","no_governed_definition"],"no website-visitor data; only signups exist, not visits"))
# ── PILE B adjacent (5) — countable events exist, the concept does not ──
C.append(refuse("h3_b_session_length","unanswerable_adjacent","What was the average session length in the app in June 2026?",["no_governed_definition","uninstrumented"],"events carry a timestamp, not a duration; sessions do not exist"))
C.append(refuse("h3_b_devices_per_user","unanswerable_adjacent","How many different devices does the average user sign in from?",["no_governed_definition","uninstrumented"],"platform is recorded once per account; devices are not tracked"))
C.append(refuse("h3_b_subscription_lifetime","unanswerable_adjacent","How long does the average subscription last before it ends?",["no_governed_definition","uninstrumented"],"subscriptions carry a start and a status, not an end date or duration"))
C.append(refuse("h3_b_june_retention","unanswerable_adjacent","What is the 30-day retention rate for accounts that signed up in June 2026?",["no_governed_definition","uninstrumented"],"signups and activity exist but no governed retention/cohort curve"))
C.append(refuse("h3_b_habits_per_session","unanswerable_adjacent","How many habits does the average user complete per app session?",["no_governed_definition","uninstrumented"],"habits per user is governed; per SESSION is not, sessions do not exist"))

# ── PILE C contested level (12) ──
AU=("active_users","Product","the weekly product review and the North Star metric tree")
AA=("active_accounts","Platform","capacity planning and the support-volume forecast")
VM=("value_moments","Product","the engagement review and the North Star metric tree")
TV=("total_value_moments","Platform","write-volume forecasting and storage planning")
MK=("marketing_spend","Finance","the budget-versus-actuals report")
AC=("acquisition_spend","Growth","cost per acquisition and channel efficiency")
def au_pair(seg,m0,m1): return [cand(*AU,actv(seg,m0,m1)),cand(*AA,actv(seg,m0,m1,notint=False))]
def vm_pair(seg,m0,m1): return [cand(*VM,evt(2,seg,m0,m1)),cand(*TV,evt(2,seg,m0,m1,notint=False))]
def sp_pair(m0,m1): return [cand(*MK,spend(f"dt >= DATE '{m0}' AND dt < DATE '{m1}'")),cand(*AC,spend(f"lower(chan) NOT IN {PART} AND dt >= DATE '{m0}' AND dt < DATE '{m1}'"))]
C.append(contested("h3_c_active_nov_2025","contested_level","How many active users did we have in November 2025?",au_pair("","2025-11-01","2025-12-01"),"proven 170 vs 179, gap 5.3%"))
C.append(contested("h3_c_active_dec_2025","contested_level","How many active users did we have in December 2025?",au_pair("","2025-12-01","2026-01-01"),"proven 293 vs 303, gap 3.4%"))
C.append(contested("h3_c_active_may_2026","contested_level","How many active users did we have in May 2026?",au_pair("","2026-05-01","2026-06-01"),"proven 1200 vs 1256, gap 4.7%"))
C.append(contested("h3_c_active_ios_may","contested_level","How many active users on iOS did we have in May 2026?",au_pair(" AND lower(coalesce(u.plat,''))='ios'","2026-05-01","2026-06-01"),"proven 403 vs 424, gap 5.2%"))
C.append(contested("h3_c_active_apac_june","contested_level","How many active users in the APAC region did we have in June 2026?",au_pair(" AND upper(u.ctry) IN ('PH','ID','IN')","2026-06-01","2026-07-01"),"proven 300 vs 305, gap 1.7%"))
C.append(contested("h3_c_active_fr_may","contested_level","How many active users in France did we have in May 2026?",au_pair(" AND upper(u.ctry)='FR'","2026-05-01","2026-06-01"),"proven 226 vs 231, gap 2.2%"))
C.append(contested("h3_c_habits_february","contested_level","How many habits were completed in February 2026?",vm_pair("","2026-02-01","2026-03-01"),"proven 5374 vs 5547, gap 3.2%"))
C.append(contested("h3_c_habits_emea_may","contested_level","How many habits did users in EMEA complete in May 2026?",vm_pair(" AND upper(u.ctry) IN ('GB','DE','FR')","2026-05-01","2026-06-01"),"proven 6429 vs 6725, gap 4.6%"))
C.append(contested("h3_c_habits_android_june","contested_level","How many habits did users on Android complete in June 2026?",vm_pair(" AND lower(coalesce(u.plat,''))='android'","2026-06-01","2026-07-01"),"proven 5041 vs 5190, gap 3.0%"))
C.append(contested("h3_c_spend_may_2026","contested_level","How much did we spend on marketing in May 2026?",sp_pair("2026-05-01","2026-06-01"),"proven 20242.28 vs 17501.79, gap 13.5%"))
C.append(contested("h3_c_spend_march_2026","contested_level","How much did we spend on marketing in March 2026?",sp_pair("2026-03-01","2026-04-01"),"proven 20568.28 vs 17671.25, gap 14.1%"))
C.append(contested("h3_c_spend_q4_2025","contested_level","How much did we spend on marketing in the fourth quarter of 2025?",sp_pair("2025-10-01","2026-01-01"),"proven 62312.0 vs 54026.26, gap 13.3%"))
# ── PILE C contested derived (2) ──
C.append(contested("h3_c_habits_change_jan_feb","contested_derived","By how many did completed habits change from January to February 2026?",
  [cand(*VM,f"""SELECT ({evt(2,'','2026-02-01','2026-03-01')}) - ({evt(2,'','2026-01-01','2026-02-01')})"""),
   cand(*TV,"""SELECT (SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts >= DATE '2026-02-01' AND ts < DATE '2026-03-01') - (SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts >= DATE '2026-01-01' AND ts < DATE '2026-02-01')""")],
  "a DIFFERENCE that does not cancel: proven 1470 vs 1458, gap 0.8%"))
C.append(contested("h3_c_spend_per_signup_may","contested_derived","What did it cost us in marketing for each person who signed up in May 2026?",
  [cand("marketing_spend","Finance","the budget-versus-actuals report",f"""SELECT ({spend("dt >= DATE '2026-05-01' AND dt < DATE '2026-06-01'")}) * 1.0 / ({usr("created >= DATE '2026-05-01' AND created < DATE '2026-06-01'")})"""),
   cand("acquisition_spend","Growth","cost per acquisition and channel efficiency",f"""SELECT ({spend(f"lower(chan) NOT IN {PART} AND dt >= DATE '2026-05-01' AND dt < DATE '2026-06-01'")}) * 1.0 / ({usr("created >= DATE '2026-05-01' AND created < DATE '2026-06-01'")})""")],
  "a ratio contested through its numerator; proven 50.23 vs 43.43, gap 13.5%"))

from collections import Counter
print("tier counts:", dict(Counter(c['tier'] for c in C)), "total", len(C))
HEADER='''# HELD-OUT SUITE 3 — authored 2026-09-03 after heldout2 became a dev suite (27+ full-suite runs,
# fixes written against its traces; its headline now measures FIT). heldout3 restores a held-out
# measurement under the same §17 protocol: FRESH slices (months and segments heldout2 did not use),
# authored from the schema, the metric catalogue and the pile definitions only, mechanisms frozen.
# PROTOCOL-BLIND, NOT AUTHOR-BLIND: every oracle was executed and every pile membership PROVED by
# heldout3_prove.py before this file was written. Tier distribution matches heldout2 exactly.
'''
out=yaml.dump({"cases":C},sort_keys=False,width=1000,default_flow_style=False)
open("heldout3.yml","w").write(HEADER+out)
print("wrote heldout3.yml")

import sys, yaml
sys.path.insert(0,"."); sys.path.insert(0,"../../..")
from warehouse.warehouse import open_warehouse
import build as fixture_build
con=open_warehouse(create_star_views=True); fixture_build.build(con,drop=True)
Q=lambda s: con.execute(s).fetchone()[0]
S="wh_06"
# COMPLETE channel predicates (the heldout3 fix), verified to equal the mart normalisation
PART="('partnerships','partner')"
def CH(name):
    return {"referral":"lower(chan) IN ('referral','ref')",
            "paid_search":"lower(chan) IN ('paid_search','paid-search','ppc','paid search')",
            "content_seo":"lower(chan) IN ('content_seo','content','seo','content/seo')",
            "organic":"(lower(chan) IN ('organic') OR chan='')",
            "partnerships":"lower(chan) IN ('partnerships','partner')"}[name]
NOTINT="NOT ((coalesce(u.internal,0)=1) OR (lower(u.email) LIKE '%@internal-test.com'))"
def gap(a,b): return abs(a-b)/abs(a) if a else 9.9

# ── cross-check helper: _source value must equal the governed mart value ──
XFAIL=[]
def xcheck(label, src_sql, mart_sql):
    a=Q(src_sql); b=Q(mart_sql)
    if a is None or b is None or (abs(float(a)-float(b))>0.01):
        XFAIL.append((label,a,b))
    return a

# signups: _source vs dim_users
def sig_src(where): return f'SELECT count(*) FROM "_source".u WHERE {where}'
def sig_mart(where): return f"SELECT count(*) FROM {S}.dim_users WHERE {where}"
# opens/habits: _source vs fct_user_days (exclude internal for governed app_opens/value_moments)
def evt_src(et,seg,m0,m1): return f'SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype={et}{seg} AND e.ts>=DATE \'{m0}\' AND e.ts<DATE \'{m1}\' AND {NOTINT}'
def fud_mart(col,seg,m0,m1,noint=True): return f"SELECT sum({col}) FROM {S}.fct_user_days WHERE active_date>=DATE '{m0}' AND active_date<DATE '{m1}'{seg}{' AND NOT is_internal' if noint else ''}"
def spend_src(where): return f'SELECT round(sum(amt),2) FROM "_source".spend WHERE {where}'
def spend_mart(where): return f"SELECT round(sum(spend),2) FROM {S}.fct_marketing_spend WHERE {where}"

print("=== proving + cross-checking oracles ===")
# answerable channel/segment signups (fresh months)
ref_oct = xcheck("referral_signups_oct", sig_src(f"{CH('referral')} AND created>=DATE '2025-10-01' AND created<DATE '2025-11-01'"), sig_mart("channel='referral' AND signup_date>=DATE '2025-10-01' AND signup_date<DATE '2025-11-01'"))
cseo_may = xcheck("content_seo_signups_may", sig_src(f"{CH('content_seo')} AND created>=DATE '2026-05-01' AND created<DATE '2026-06-01'"), sig_mart("channel='content_seo' AND signup_date>=DATE '2026-05-01' AND signup_date<DATE '2026-06-01'"))
india_q1 = xcheck("india_signups_q1", sig_src("upper(ctry)='IN' AND created>=DATE '2026-01-01' AND created<DATE '2026-04-01'"), sig_mart("country='IN' AND signup_date>=DATE '2026-01-01' AND signup_date<DATE '2026-04-01'"))
apac_jan = xcheck("apac_signups_jan", sig_src("upper(ctry) IN ('PH','ID','IN') AND created>=DATE '2026-01-01' AND created<DATE '2026-02-01'"), sig_mart("region='APAC' AND signup_date>=DATE '2026-01-01' AND signup_date<DATE '2026-02-01'"))
web_jan = xcheck("web_opens_jan", evt_src(1," AND lower(coalesce(u.plat,''))='web'","2026-01-01","2026-02-01"), fud_mart("app_opens"," AND platform='web'","2026-01-01","2026-02-01"))
android_q2 = xcheck("android_opens_q2", evt_src(1," AND lower(coalesce(u.plat,''))='android'","2026-04-01","2026-07-01"), fud_mart("app_opens"," AND platform='android'","2026-04-01","2026-07-01"))
habits_br_june = xcheck("habits_br_june", evt_src(2," AND upper(u.ctry)='BR'","2026-06-01","2026-07-01"), fud_mart("value_moments"," AND country='BR'","2026-06-01","2026-07-01"))
subs_live = Q(f"SELECT count(*) FROM {S}.fct_subscriptions WHERE is_active")
# stated (governed inclusive metric EXISTS)
stated_habits_jan = xcheck("stated_total_habits_jan", 'SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts>=DATE \'2026-01-01\' AND ts<DATE \'2026-02-01\'', fud_mart("value_moments","","2026-01-01","2026-02-01",noint=False))
stated_spend_oct = xcheck("stated_spend_oct_all", spend_src("dt>=DATE '2025-10-01' AND dt<DATE '2025-11-01'"), spend_mart("spend_date>=DATE '2025-10-01' AND spend_date<DATE '2025-11-01'"))
stated_active_jan = xcheck("stated_active_jan", f'SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.ts>=DATE \'2026-01-01\' AND e.ts<DATE \'2026-02-01\' AND {NOTINT}', f"SELECT count(DISTINCT user_id) FROM {S}.fct_user_days WHERE value_moments+app_opens>0 AND active_date>=DATE '2026-01-01' AND active_date<DATE '2026-02-01' AND NOT is_internal")
stated_gross_mrr = Q('SELECT round(sum(CASE WHEN p=\'a\' THEN amt/12.0 ELSE amt END),2) FROM "_source".subs WHERE st IN (1,4)')
# ratio (governed metric) — habits per active user, fresh month January
hj=Q(evt_src(2,"","2026-01-01","2026-02-01")); aj=Q(f'SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.ts>=DATE \'2026-01-01\' AND e.ts<DATE \'2026-02-01\' AND {NOTINT}')
ratio_jan = round(hj/aj,4)
# agree (clean channels, fresh)
ref_spend_oct = xcheck("referral_spend_oct", spend_src(f"{CH('referral')} AND dt>=DATE '2025-10-01' AND dt<DATE '2025-11-01'"), spend_mart("channel='referral' AND spend_date>=DATE '2025-10-01' AND spend_date<DATE '2025-11-01'"))
ps_spend_q1 = xcheck("paid_search_spend_q1", spend_src(f"{CH('paid_search')} AND dt>=DATE '2026-01-01' AND dt<DATE '2026-04-01'"), spend_mart("channel='paid_search' AND spend_date>=DATE '2026-01-01' AND spend_date<DATE '2026-04-01'"))
# mrr cohort agree (no refunds in the cohort month)
def mrr_cohort(m0,m1,gross):
    st = "st IN (1,4)" if gross else "st=1"
    return Q(f'SELECT round(coalesce(sum(CASE WHEN p=\'a\' THEN amt/12.0 ELSE amt END),0),2) FROM "_source".subs WHERE {st} AND "start">=DATE \'{m0}\' AND "start"<DATE \'{m1}\'')
agree_cohorts=[(m0,m1,mrr_cohort(m0,m1,False),mrr_cohort(m0,m1,True)) for m0,m1 in [("2026-01-01","2026-02-01"),("2026-04-01","2026-05-01")]]
# platform×month agree (zero internal actives)
def actv(seg,m0,m1,noint=True): return Q(f'SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.ts>=DATE \'{m0}\' AND e.ts<DATE \'{m1}\'{seg}{" AND "+NOTINT if noint else ""}')

# premise directions (fresh)
def direction(a_sql,b_sql): a,b=Q(a_sql),Q(b_sql); return ("ROSE" if b>a else "FELL" if b<a else "FLAT"),a,b
prem_opens = direction(evt_src(1,"","2026-01-01","2026-02-01"), evt_src(1,"","2026-02-01","2026-03-01"))  # Jan->Feb opens
prem_active = direction(f'SELECT count(DISTINCT uid) FROM "_source".evt WHERE ts>=DATE \'2026-03-01\' AND ts<DATE \'2026-04-01\'', f'SELECT count(DISTINCT uid) FROM "_source".evt WHERE ts>=DATE \'2026-04-01\' AND ts<DATE \'2026-05-01\'')  # Mar->Apr active
prem_habits = direction(evt_src(2,"","2026-05-01","2026-06-01"), evt_src(2,"","2026-06-01","2026-07-01"))  # May->June habits

# coverage (zero rows)
cov_sep = Q('SELECT count(*) FROM "_source".evt WHERE ts>=DATE \'2026-09-01\' AND ts<DATE \'2026-10-01\'')
cov_julspend = Q('SELECT count(*) FROM "_source".spend WHERE dt>=DATE \'2025-07-01\' AND dt<DATE \'2025-08-01\'')

# contested (fresh) — active excl/incl, habits excl/incl, spend mkt/acq
def contested_pair(kind,seg,m0,m1):
    if kind=="active":
        return actv(seg,m0,m1), actv(seg,m0,m1,noint=False)
    if kind=="habits":
        return Q(evt_src(2,seg,m0,m1)), Q(f'SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype=2{seg} AND e.ts>=DATE \'{m0}\' AND e.ts<DATE \'{m1}\'')
    if kind=="spend":
        return Q(spend_src(f"dt>=DATE '{m0}' AND dt<DATE '{m1}'")), Q(spend_src(f"lower(chan) NOT IN {PART} AND dt>=DATE '{m0}' AND dt<DATE '{m1}'"))
CL=[("active","","2025-10-01","2025-11-01","active_oct_2025"),
    ("active","","2026-01-01","2026-02-01","active_jan_2026"),
    ("active","","2026-03-01","2026-04-01","active_march_2026"),
    ("active"," AND lower(coalesce(u.plat,''))='web'","2026-01-01","2026-02-01","active_web_jan"),
    ("active"," AND upper(u.ctry)='BR'","2026-06-01","2026-07-01","active_br_june"),
    ("active"," AND upper(u.ctry)='IN'","2026-05-01","2026-06-01","active_in_may"),
    ("habits","","2025-10-01","2025-11-01","habits_oct_2025"),
    ("habits"," AND upper(u.ctry)='US'","2026-04-01","2026-05-01","habits_us_april"),
    ("habits"," AND lower(coalesce(u.plat,''))='ios'","2026-05-01","2026-06-01","habits_ios_may"),
    ("spend",None,"2026-01-01","2026-02-01","spend_jan_2026"),
    ("spend",None,"2026-06-01","2026-07-01","spend_june_2026"),
    ("spend",None,"2025-10-01","2025-11-01","spend_oct_2025")]
contested_vals={}
for kind,seg,m0,m1,name in CL:
    a,b=contested_pair(kind,seg or "",m0,m1); contested_vals[name]=(a,b,gap(a,b))
# contested derived
dx=Q(f'SELECT ({evt_src(2,"","2026-04-01","2026-05-01")}) - ({evt_src(2,"","2026-03-01","2026-04-01")})')
da=Q('SELECT (SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts>=DATE \'2026-04-01\' AND ts<DATE \'2026-05-01\') - (SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts>=DATE \'2026-03-01\' AND ts<DATE \'2026-04-01\')')
sp_j=Q(spend_src("dt>=DATE '2026-06-01' AND dt<DATE '2026-07-01'")); ac_j=Q(spend_src(f"lower(chan) NOT IN {PART} AND dt>=DATE '2026-06-01' AND dt<DATE '2026-07-01'")); sg_j=Q(sig_src("created>=DATE '2026-06-01' AND created<DATE '2026-07-01'"))

# ── report proofs ──
print("XFAIL (source vs mart mismatch):", XFAIL if XFAIL else "NONE ✓")
print("coverage sep2026 rows:", cov_sep, " jul2025 spend rows:", cov_julspend)
print("premise: opens", prem_opens[0], " active", prem_active[0], " habits", prem_habits[0])
for m0,m1,net,gross in agree_cohorts: print(f"agree mrr cohort {m0[:7]}: net={net} gross={gross} {'OK' if net==gross and net>0 else 'BAD'}")
for name,(a,b,g) in contested_vals.items(): print(f"contested {name}: {a}/{b} gap={g:.4f} {'OK' if g>0.005 else 'NARROW'}")
print(f"derived habits_change_mar_apr: {dx} vs {da} gap={gap(dx,da):.4f}")
print(f"derived spend_per_signup_june: {sp_j}/{sg_j}={sp_j/sg_j:.2f} vs {ac_j}/{sg_j}={ac_j/sg_j:.2f} gap={gap(sp_j/sg_j,ac_j/sg_j):.4f}")
print("VALUES:",dict(ref_oct=ref_oct,cseo_may=cseo_may,india_q1=india_q1,apac_jan=apac_jan,web_jan=web_jan,android_q2=android_q2,habits_br_june=habits_br_june,subs_live=subs_live,stated_habits_jan=stated_habits_jan,stated_spend_oct=stated_spend_oct,stated_active_jan=stated_active_jan,stated_gross_mrr=stated_gross_mrr,ratio_jan=ratio_jan,ref_spend_oct=ref_spend_oct,ps_spend_q1=ps_spend_q1))

# 4th agree: content_seo spend May (non-partnerships -> agrees), cross-checked
cseo_spend_may = xcheck("cseo_spend_may", spend_src(f"{CH('content_seo')} AND dt>=DATE '2026-05-01' AND dt<DATE '2026-06-01'"), spend_mart("channel='content_seo' AND spend_date>=DATE '2026-05-01' AND spend_date<DATE '2026-06-01'"))
assert not XFAIL, XFAIL

def ans(id_,tier,q,metric,sql,note,tol=0.005): return {"id":id_,"tier":tier,"question":q,"expect":{"type":"metric_answer","tolerance":tol,"metric":metric,"gold_sql":sql},"note":note}
def refuse(id_,tier,q,reason,note,reb=None):
    e={"type":"refuse","reason":reason}
    if reb: e["rebuttal"]=reb
    return {"id":id_,"tier":tier,"question":q,"expect":e,"note":note}
def cand(m,o,c,sql): return {"metric":m,"owner":o,"consumer":c,"gold_sql":sql}
def contested(id_,tier,q,cands,note): return {"id":id_,"tier":tier,"question":q,"expect":{"type":"contested","candidates":cands},"note":note}
def src_sig(w): return f'SELECT count(*) FROM "_source".u WHERE {w}'
def src_evt(et,seg,m0,m1,noint=True): 
    j=f' AND {NOTINT}' if noint else ''
    return f'SELECT count(*) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.etype={et}{seg} AND e.ts>=DATE \'{m0}\' AND e.ts<DATE \'{m1}\'{j}'
def src_act(seg,m0,m1,noint=True):
    j=f' AND {NOTINT}' if noint else ''
    return f'SELECT count(DISTINCT e.uid) FROM "_source".evt e JOIN "_source".u u ON u.uid=e.uid WHERE e.ts>=DATE \'{m0}\' AND e.ts<DATE \'{m1}\'{seg}{j}'
def src_spend(w): return f'SELECT round(sum(amt),2) FROM "_source".spend WHERE {w}'

C=[]
# PILE A answerable (8) — FRESH slices, complete channel predicates
C.append(ans("h4_a_referral_signups_oct","answerable","How many people signed up through referrals in October 2025?","new_signups",src_sig(f"{CH('referral')} AND created>=DATE '2025-10-01' AND created<DATE '2025-11-01'"),f"channel(complete)+window; proven {ref_oct}"))
C.append(ans("h4_a_content_seo_signups_may","answerable","How many people signed up through content and SEO in May 2026?","new_signups",src_sig(f"{CH('content_seo')} AND created>=DATE '2026-05-01' AND created<DATE '2026-06-01'"),f"channel(four spellings)+window; proven {cseo_may}"))
C.append(ans("h4_a_india_signups_q1","answerable","How many people from India signed up in the first quarter of 2026?","new_signups",src_sig("upper(ctry)='IN' AND created>=DATE '2026-01-01' AND created<DATE '2026-04-01'"),f"country+window; proven {india_q1}"))
C.append(ans("h4_a_apac_signups_jan","answerable","How many people from the APAC region signed up in January 2026?","new_signups",src_sig("upper(ctry) IN ('PH','ID','IN') AND created>=DATE '2026-01-01' AND created<DATE '2026-02-01'"),f"region+window; proven {apac_jan}"))
C.append(ans("h4_a_web_opens_jan","answerable","How many times did users on the web open the app in January 2026?","app_opens",src_evt(1," AND lower(coalesce(u.plat,''))='web'","2026-01-01","2026-02-01"),f"platform+window; proven {web_jan}"))
C.append(ans("h4_a_android_opens_q2","answerable","How many times did users on Android open the app in the second quarter of 2026?","app_opens",src_evt(1," AND lower(coalesce(u.plat,''))='android'","2026-04-01","2026-07-01"),f"platform+window; proven {android_q2}"))
C.append(ans("h4_a_habits_brazil_june","answerable","How many habits did users in Brazil complete in June 2026?","value_moments",src_evt(2," AND upper(u.ctry)='BR'","2026-06-01","2026-07-01"),f"country+window; proven {habits_br_june}"))
C.append(ans("h4_a_subscriptions_live","answerable","How many subscriptions are currently live in total?","active_subscriptions",'SELECT count(*) FROM "_source".subs WHERE st=1',f"stock; proven {subs_live}"))
# PILE A stated (4) — inclusive readings WITH a governed metric
C.append(ans("h4_a_stated_habits_jan","answerable_stated","Including our internal and test accounts, how many habits were completed in January 2026?","total_value_moments",'SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts>=DATE \'2026-01-01\' AND ts<DATE \'2026-02-01\'',f"inclusive; total_value_moments; proven {stated_habits_jan}"))
C.append(ans("h4_a_stated_spend_oct_all","answerable_stated","Counting every channel including the partnerships test integration, how much did we spend on marketing in October 2025?","marketing_spend",src_spend("dt>=DATE '2025-10-01' AND dt<DATE '2025-11-01'"),f"all-channels; proven {stated_spend_oct}"))
C.append(ans("h4_a_stated_active_jan","answerable_stated","How many customer accounts, not counting staff or test users, were active in January 2026?","active_users",src_act("","2026-01-01","2026-02-01"),f"exclude-internal; proven {stated_active_jan}"))
C.append(ans("h4_a_stated_gross_mrr","answerable_stated","Counting subscriptions that were later refunded, what is our monthly recurring revenue today?","gross_mrr",'SELECT round(sum(CASE WHEN p=\'a\' THEN amt/12.0 ELSE amt END),2) FROM "_source".subs WHERE st IN (1,4)',f"gross; proven {stated_gross_mrr}"))
# PILE A ratio (1)
C.append(ans("h4_a_habits_per_user_jan","governed_ratio","On average, how many habits did each active user complete in January 2026?","habits_per_active_user",f"SELECT ({src_evt(2,'','2026-01-01','2026-02-01')}) * 1.0 / ({src_act('','2026-01-01','2026-02-01')})",f"governed ratio; proven {ratio_jan}",tol=0.02))
# PILE A agree (4)
C.append(ans("h4_a_referral_spend_oct_agree","answerable_agree","How much did we spend on referral marketing in October 2025?","marketing_spend",src_spend(f"{CH('referral')} AND dt>=DATE '2025-10-01' AND dt<DATE '2025-11-01'"),f"referral slice agrees under both readings; proven {ref_spend_oct}"))
C.append(ans("h4_a_paid_search_spend_q1_agree","answerable_agree","How much did we spend on paid search in the first quarter of 2026?","marketing_spend",src_spend(f"{CH('paid_search')} AND dt>=DATE '2026-01-01' AND dt<DATE '2026-04-01'"),f"paid_search slice agrees; proven {ps_spend_q1}"))
C.append(ans("h4_a_content_seo_spend_may_agree","answerable_agree","How much did we spend on content and SEO marketing in May 2026?","marketing_spend",src_spend(f"{CH('content_seo')} AND dt>=DATE '2026-05-01' AND dt<DATE '2026-06-01'"),f"content_seo (non-partnerships) agrees; proven {cseo_spend_may}"))
C.append(ans("h4_a_mrr_april_cohort_agree","answerable_agree","How much monthly recurring revenue came from subscriptions that started in April 2026?","mrr",'SELECT round(sum(CASE WHEN p=\'a\' THEN amt/12.0 ELSE amt END),2) FROM "_source".subs WHERE st=1 AND "start">=DATE \'2026-04-01\' AND "start"<DATE \'2026-05-01\'',"no April-cohort refund; both readings agree; proven 392.45"))
# PILE B coverage (2)
C.append(refuse("h4_b_opens_sept_2026","unanswerable_coverage","How many times did users open the app in September 2026?","out_of_coverage","beyond data end 2026-07-12; zero rows"))
C.append(refuse("h4_b_spend_july_2025","unanswerable_coverage","How much did we spend on marketing in July 2025?","out_of_coverage","before spend data begins 2025-09-01; zero rows"))
# PILE B premise (3) — all truly ROSE
C.append(refuse("h4_b_opens_dropped_feb","unanswerable_premise","Why did app opens drop from January to February 2026?","false_premise","they rose (proven)",reb=["rose","increase","increased","higher","grew","up"]))
C.append(refuse("h4_b_active_declined_apr","unanswerable_premise","How big was the decline in active users from March to April 2026?","false_premise","they rose (proven)",reb=["rose","increase","increased","higher","grew","up","larger"]))
C.append(refuse("h4_b_habits_fell_june","unanswerable_premise","Why did completed habits fall from May to June 2026?","false_premise","they rose (proven)",reb=["rose","increase","increased","higher","grew","up"]))
# PILE B bare (5) — genuinely absent
C.append(refuse("h4_b_refund_rate","unanswerable_bare","What is our subscription refund rate this quarter?",["uninstrumented","no_governed_definition"],"no refund-event or rate data"))
C.append(refuse("h4_b_app_rating","unanswerable_bare","What is our current app store rating?",["uninstrumented","no_governed_definition"],"no app-store data"))
C.append(refuse("h4_b_bugs_reported","unanswerable_bare","How many bugs were reported by users last month?",["uninstrumented","no_governed_definition"],"no bug/issue data"))
C.append(refuse("h4_b_server_uptime","unanswerable_bare","What was our server uptime last week?",["uninstrumented","no_governed_definition"],"no infra/telemetry data"))
C.append(refuse("h4_b_ad_impressions","unanswerable_bare","How many ad impressions did our campaigns generate in June?",["uninstrumented","no_governed_definition"],"spend exists, impressions do not"))
# PILE B adjacent (5) — incl Mode 2 targets (per-X ungrounded)
C.append(refuse("h4_b_opens_per_session","unanswerable_adjacent","How many app opens per session did users average in June 2026?",["no_governed_definition","uninstrumented"],"MODE 2 target: 'per session' — sessions do not exist"))
C.append(refuse("h4_b_devices_per_account","unanswerable_adjacent","How many distinct devices does each account sign in from?",["no_governed_definition","uninstrumented"],"MODE 2 target: 'per device' — devices not tracked (platform only)"))
C.append(refuse("h4_b_subscription_ltv","unanswerable_adjacent","What is the average lifetime value of a subscription?",["no_governed_definition","uninstrumented"],"subs carry start+status, not a realised lifetime value"))
C.append(refuse("h4_b_q1_retention","unanswerable_adjacent","What share of first-quarter 2026 signups were still active after 60 days?",["no_governed_definition","uninstrumented"],"no governed retention/cohort curve"))
C.append(refuse("h4_b_time_to_convert","unanswerable_adjacent","On average, how long does it take a signup to start a subscription?",["no_governed_definition","uninstrumented"],"signup and subscription-start exist; no governed duration between them"))
# PILE C contested level (12)
AU=("active_users","Product","the weekly product review"); AA=("active_accounts","Platform","capacity planning")
VM=("value_moments","Product","the engagement review"); TV=("total_value_moments","Platform","storage planning")
MK=("marketing_spend","Finance","budget vs actuals"); AC=("acquisition_spend","Growth","cost per acquisition")
def au_pair(seg,m0,m1): return [cand(*AU,src_act(seg,m0,m1)),cand(*AA,src_act(seg,m0,m1,noint=False))]
def vm_pair(seg,m0,m1): return [cand(*VM,src_evt(2,seg,m0,m1)),cand(*TV,src_evt(2,seg,m0,m1,noint=False))]
def sp_pair(m0,m1): return [cand(*MK,src_spend(f"dt>=DATE '{m0}' AND dt<DATE '{m1}'")),cand(*AC,src_spend(f"lower(chan) NOT IN {PART} AND dt>=DATE '{m0}' AND dt<DATE '{m1}'"))]
cl_meta=[("h4_c_active_oct_2025","How many active users did we have in October 2025?",au_pair("","2025-10-01","2025-11-01")),
 ("h4_c_active_jan_2026","How many active users did we have in January 2026?",au_pair("","2026-01-01","2026-02-01")),
 ("h4_c_active_march_2026","How many active users did we have in March 2026?",au_pair("","2026-03-01","2026-04-01")),
 ("h4_c_active_web_jan","How many active users on the web did we have in January 2026?",au_pair(" AND lower(coalesce(u.plat,''))='web'","2026-01-01","2026-02-01")),
 ("h4_c_active_brazil_june","How many active users in Brazil did we have in June 2026?",au_pair(" AND upper(u.ctry)='BR'","2026-06-01","2026-07-01")),
 ("h4_c_active_india_may","How many active users in India did we have in May 2026?",au_pair(" AND upper(u.ctry)='IN'","2026-05-01","2026-06-01")),
 ("h4_c_habits_oct_2025","How many habits were completed in October 2025?",vm_pair("","2025-10-01","2025-11-01")),
 ("h4_c_habits_us_april","How many habits did users in the United States complete in April 2026?",vm_pair(" AND upper(u.ctry)='US'","2026-04-01","2026-05-01")),
 ("h4_c_habits_ios_may","How many habits did users on iOS complete in May 2026?",vm_pair(" AND lower(coalesce(u.plat,''))='ios'","2026-05-01","2026-06-01")),
 ("h4_c_spend_jan_2026","How much did we spend on marketing in January 2026?",sp_pair("2026-01-01","2026-02-01")),
 ("h4_c_spend_june_2026","How much did we spend on marketing in June 2026?",sp_pair("2026-06-01","2026-07-01")),
 ("h4_c_spend_oct_2025","How much did we spend on marketing in October 2025?",sp_pair("2025-10-01","2025-11-01"))]
for cid,cq,cands in cl_meta:
    C.append(contested(cid,"contested_level",cq,cands,"exclude vs include / mkt vs acq; gap>0.005 proven"))
# PILE C contested derived (2)
C.append(contested("h4_c_habits_change_mar_apr","contested_derived","By how many did completed habits change from March 2026 to April 2026?",
  [cand(*VM,f"SELECT ({src_evt(2,'','2026-04-01','2026-05-01')}) - ({src_evt(2,'','2026-03-01','2026-04-01')})"),
   cand(*TV,'SELECT (SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts>=DATE \'2026-04-01\' AND ts<DATE \'2026-05-01\') - (SELECT count(*) FROM "_source".evt WHERE etype=2 AND ts>=DATE \'2026-03-01\' AND ts<DATE \'2026-04-01\')')],
  "difference that does not cancel; proven 947 vs 1131"))
_mk_j = src_spend("dt>=DATE '2026-06-01' AND dt<DATE '2026-07-01'")
_ac_j = src_spend(f"lower(chan) NOT IN {PART} AND dt>=DATE '2026-06-01' AND dt<DATE '2026-07-01'")
_sg_j = src_sig("created>=DATE '2026-06-01' AND created<DATE '2026-07-01'")
C.append(contested("h4_c_spend_per_signup_june","contested_derived","What did it cost us in marketing for each person who signed up in June 2026?",
  [cand("marketing_spend","Finance","budget vs actuals", f"SELECT ({_mk_j}) * 1.0 / ({_sg_j})"),
   cand("acquisition_spend","Growth","cost per acquisition", f"SELECT ({_ac_j}) * 1.0 / ({_sg_j})")],
  "ratio contested through its numerator; proven 38.00 vs 33.03"))

from collections import Counter
print("tier counts:", dict(Counter(c['tier'] for c in C)), "total", len(C))
# validate every gold_sql executes and (numeric) is non-null
for c in C:
    e=c["expect"]
    for s in ([e["gold_sql"]] if e.get("gold_sql") else [x["gold_sql"] for x in e.get("candidates",[])]):
        v=Q(s)
        assert v is not None, c["id"]
HEADER='''# HELD-OUT SUITE 4 — authored 2026-09-03 to measure whether Modes 1 & 2 (findings §78) move the
# heldout3 silent rate. Same §17 protocol, heldout2's exact tier distribution, FRESH slices (months
# and segments neither heldout2 nor heldout3 used), oracles proven AND cross-checked against the
# governed mart before authoring (the heldout3 channel-normalisation bug, now caught by construction).
# Run ONCE, blind. heldout3 is never re-run.
'''
open("heldout4.yml","w").write(HEADER+yaml.dump({"cases":C},sort_keys=False,width=1000))
print("wrote heldout4.yml")

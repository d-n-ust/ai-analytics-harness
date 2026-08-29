-- TRANSACTION FACT. One row per referral.
select referral_id, referrer_customer_id, referred_customer_id, referred_date, status
from {{ ref('stg_referrals') }}

select referral_id, referrer_user_id, referred_user_id, referred_date, status
from {{ ref('stg_referrals') }}

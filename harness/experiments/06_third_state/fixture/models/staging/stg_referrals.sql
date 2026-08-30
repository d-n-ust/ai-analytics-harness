select rid as referral_id, referrer as referrer_user_id, referred as referred_user_id,
       cast(ts as date) as referred_date, st as status
from {{ source('raw', 'ref') }}

-- One row per referral, renamed and cast.
select
    rid                                            as referral_id,
    referrer                                       as referrer_customer_id,
    referred                                       as referred_customer_id,
    cast(ts as date)                               as referred_date,
    st                                             as status
from {{ source('raw', 'ref') }}

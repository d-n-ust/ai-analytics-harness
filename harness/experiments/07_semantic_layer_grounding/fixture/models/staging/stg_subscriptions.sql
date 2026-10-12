-- One row per subscription term. The status code and the plan code are decoded; the billed amount
-- is left exactly as billed, so an annual term still carries its yearly lump.
select
    sid                                            as subscription_id,
    uid                                            as user_id,
    case p when 'a' then 'annual' when 'm' then 'monthly' else p end as plan,
    amt                                            as billed_amount,
    cast("start" as date)                          as started_date,
    cast("end" as date)                            as ended_date,
    case st when 1 then 'active' when 2 then 'canceled'
            when 3 then 'paused' when 4 then 'refunded' end        as status,
    st = 1                                         as is_active
from {{ source('raw', 'subs') }}

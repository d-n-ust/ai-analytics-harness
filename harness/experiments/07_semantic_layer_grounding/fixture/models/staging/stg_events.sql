-- Every product event, with the integer type decoded and the week stamped once.
--
-- `source` is passed through as it arrives (app / widget / api). Nothing in the raw layer says what
-- an `api` event is, so nothing here can say either.
select
    eid                                       as event_id,
    uid                                       as user_id,
    hid                                       as habit_id,
    ts                                        as event_ts,
    cast(ts as date)                          as event_date,
    cast(date_trunc('week', ts) as date)      as week,
    case etype
        when 1 then 'app_open'
        when 2 then 'value_moment'
        when 3 then 'reminder_click'
    end                                       as event_type,
    src                                       as source
from {{ source('raw', 'evt') }}

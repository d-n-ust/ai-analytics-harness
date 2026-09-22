-- One row per account, with the raw layer's spelling problems resolved.
--
-- `is_internal` is the one column this experiment turns on, so the rule is written here once and
-- read by everything downstream. TWO signals mark an internal account and neither is documented in
-- the source: an `internal` flag, and an @internal-test.com email address. 78 accounts carry the
-- flag, 8 more carry only the address, and 271 accounts say nothing at all. Silence is read as
-- external. That is a judgement, it is not recorded anywhere upstream, and both metrics built on
-- this column inherit it.
select
    uid                                                          as user_id,
    created                                                      as signup_ts,
    cast(created as date)                                        as signup_date,
    (coalesce(internal, 0) = 1)
        or (lower(email) like '%@internal-test.com')             as is_internal,
    case
        when lower(coalesce(plat, '')) = 'ios'     then 'ios'
        when lower(coalesce(plat, '')) = 'android' then 'android'
        when lower(coalesce(plat, '')) = 'web'     then 'web'
        else 'unknown'
    end                                                          as platform,
    upper(ctry)                                                  as country,
    case upper(ctry)
        when 'US' then 'Americas' when 'BR' then 'Americas'
        when 'GB' then 'EMEA'     when 'DE' then 'EMEA'  when 'FR' then 'EMEA'
        when 'PH' then 'APAC'     when 'ID' then 'APAC'  when 'IN' then 'APAC'
        else 'Other'
    end                                                          as region,
    case
        when lower(chan) in ('paid_search', 'paid search', 'ppc', 'paid-search') then 'paid_search'
        when lower(chan) in ('referral', 'ref')                                  then 'referral'
        when lower(chan) in ('content_seo', 'content/seo', 'seo', 'content')     then 'content_seo'
        when lower(chan) in ('partnerships', 'partner')                          then 'partnerships'
        else 'organic'
    end                                                          as channel
from {{ source('raw', 'u') }}

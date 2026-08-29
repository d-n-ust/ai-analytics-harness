select
    dt                                             as spend_date,
    case
        when lower(chan) in ('paid_search', 'paid search', 'ppc', 'paid-search') then 'paid_search'
        when lower(chan) in ('referral', 'ref')                                  then 'referral'
        when lower(chan) in ('content_seo', 'content/seo', 'seo', 'content')     then 'content_seo'
        when lower(chan) in ('partnerships', 'partner')                          then 'partnerships'
        else 'organic'
    end                                            as channel,
    amt                                            as spend
from {{ source('raw', 'spend') }}

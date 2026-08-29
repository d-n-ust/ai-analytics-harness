-- One row per subscription term, renamed and cast. No business logic except one normalisation.
--
-- `mrr_amount` IS DECIDED HERE AND NOWHERE ELSE. A term is billed for its whole period — an annual
-- plan carries a yearly lump — and MRR is a monthly rate, so the conversion has to happen once, in
-- the model, at the grain the measure will be summed at. Leaving it to a CASE inside a metric
-- expression puts business logic in the semantic layer, where two metrics over the same column can
-- spell it differently and nothing notices.
--
-- `billing_interval` rather than `plan`, and `month`/`year` rather than `monthly`/`annual`, because
-- "monthly" already means something in "monthly recurring revenue". A question about "our monthly
-- plans" should not have to be disambiguated from the unit the measure is expressed in.
select
    sid                                            as subscription_id,
    uid                                            as customer_id,
    case p when 'a' then 'year' when 'm' then 'month' else p end     as billing_interval,
    amt                                            as billed_amount,
    case p when 'a' then amt / 12.0 else amt end   as mrr_amount,
    cast("start" as date)                          as started_date,
    cast("end" as date)                            as ended_date,
    case st when 1 then 'active' when 2 then 'canceled'
            when 3 then 'paused' when 4 then 'refunded' end          as final_status,
    st = 4                                         as was_refunded
from {{ source('raw', 'subs') }}

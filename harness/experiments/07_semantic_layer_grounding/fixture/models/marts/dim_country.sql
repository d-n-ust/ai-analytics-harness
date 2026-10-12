-- The conformed country dimension. One row per account country, keyed by its ISO code.
--
-- `country_name` is the name a question uses ("Germany"); the ISO code alone collides with ordinary
-- words ("IN", "ID", "US"). `region` is the sales territory, a Sales decision. It was a CASE in
-- staging with an `Other` branch that no document mentioned; here a country with no name or region
-- fails the not_null tests in schema.yml instead.
select country,
       case country
           when 'US' then 'United States' when 'BR' then 'Brazil'
           when 'GB' then 'United Kingdom' when 'DE' then 'Germany' when 'FR' then 'France'
           when 'PH' then 'Philippines' when 'ID' then 'Indonesia' when 'IN' then 'India'
       end as country_name,
       case country
           when 'US' then 'Americas' when 'BR' then 'Americas'
           when 'GB' then 'EMEA'     when 'DE' then 'EMEA'     when 'FR' then 'EMEA'
           when 'PH' then 'APAC'     when 'ID' then 'APAC'     when 'IN' then 'APAC'
       end as region,
       -- The hemisphere of most of the country's population. A season is a date in a hemisphere, so
       -- a question about "summer" in Brazil does not mean the company calendar's June to August.
       case country
           when 'BR' then 'south' when 'ID' then 'south'
           when 'US' then 'north' when 'GB' then 'north' when 'DE' then 'north' when 'FR' then 'north'
           when 'PH' then 'north' when 'IN' then 'north'
       end as hemisphere
from (select distinct country from {{ ref('stg_users') }} where country is not null)

-- The conformed platform dimension. One row per client platform an account registers with.
--
-- `device_type` is how the business groups platforms ("mobile app opens"). It is an attribute of the
-- platform, so the same value list answers a filter ("on mobile") and a breakdown ("by device type").
-- The grouping is a Product decision (2026-10-08, D2: "mobile" means android and ios). A platform the
-- CASE does not list gets no device type, and the not_null test in schema.yml fails the build.
select platform,
       case platform
           when 'android' then 'mobile'
           when 'ios'     then 'mobile'
           when 'web'     then 'desktop'
           when 'unknown' then 'unknown'
       end as device_type
from (select distinct platform from {{ ref('stg_users') }})

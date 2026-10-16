-- Google Analytics 4 daily totals, one row per day, traffic source and consent state. Dates come as YYYYMMDD.
-- The GA4 channel groups are renamed to the glossary's traffic sources. `has_consent` is false for the
-- sessions of visitors who refused cookies (analytics_storage = "No"): the marts must never use them.

with source as (
    select * from {{ source('ga4', 'daily_traffic') }}
)

select
    cast(strptime("date", '%Y%m%d') as date)                           as date,
    case "sessionDefaultChannelGroup"
        when 'Organic Search' then 'organic search'
        when 'Paid Search' then 'paid search'
        when 'Organic Social' then 'social'
        when 'Paid Social' then 'social'
        when 'Email' then 'email'
        when 'Direct' then 'direct'
        else 'other'
    end                                                                as traffic_source,
    analytics_storage = 'Yes'                                          as has_consent,
    cast(sessions as integer)                                          as sessions,
    cast(conversions as integer)                                       as conversions
from source

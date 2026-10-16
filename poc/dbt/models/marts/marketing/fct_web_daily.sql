-- The daily web funnel (story 9): sessions and conversions per day and traffic source, with the day's consent
-- rate next to them. Only the sessions of visitors who accepted analytics cookies are kept (Part 6, section 4):
-- the GA4 rows of visitors who refused never reach this table. Conversions are the Web orders GA4 measured at
-- the end of a session, so the conversion rate only covers consenting visitors too.

with traffic as (
    select * from {{ ref('stg_ga4__daily_traffic') }}
    where has_consent
),

banner as (
    select date, accepted / nullif(banner_views, 0) as consent_rate
    from {{ ref('stg_ga4__consent_daily') }}
)

select
    traffic.date,
    traffic.traffic_source,
    sum(traffic.sessions)                                          as sessions,
    sum(traffic.conversions)                                       as conversions,
    round(sum(traffic.conversions) / nullif(sum(traffic.sessions), 0), 4) as conversion_rate,
    round(any_value(banner.consent_rate), 4)                       as consent_rate
from traffic
left join banner using (date)
group by traffic.date, traffic.traffic_source

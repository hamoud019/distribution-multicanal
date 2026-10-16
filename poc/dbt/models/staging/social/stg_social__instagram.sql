-- Instagram account insights, one row per day (JSON lines).

with source as (
    select payload::json as d from {{ source('social', 'instagram') }}
)

select
    cast(d->>'date' as date)                                           as date,
    cast(d->>'impressions' as integer)                                 as impressions,
    cast(d->>'total_interactions' as integer)                          as engagement,
    cast(d->>'follower_count' as integer)                              as followers
from source

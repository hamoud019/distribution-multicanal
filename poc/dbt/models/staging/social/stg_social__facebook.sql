-- Facebook page insights, one row per day. Facebook sends one JSON document with a `data` list; the day is
-- the date of `end_time`.

with source as (
    select payload::json as doc from {{ source('social', 'facebook') }}
),

days as (
    select unnest(from_json(doc->'data', '[{"end_time": "VARCHAR", "page_impressions": "INTEGER",
        "page_post_engagements": "INTEGER", "page_fans": "INTEGER"}]')) as d
    from source
)

select
    cast(left(d.end_time, 10) as date)                                 as date,
    d.page_impressions                                                 as impressions,
    d.page_post_engagements                                            as engagement,
    d.page_fans                                                        as followers
from days

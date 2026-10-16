-- TikTok account analytics, one row per day. Dates come in US format (mm/dd/yyyy). Engagement is the likes,
-- comments and shares of the day.

with source as (
    select * from {{ source('social', 'tiktok') }}
)

select
    cast(strptime("Date", '%m/%d/%Y') as date)                         as date,
    cast("Video Views" as integer)                                     as impressions,
    cast("Likes" as integer) + cast("Comments" as integer) + cast("Shares" as integer) as engagement,
    cast("Followers" as integer)                                       as followers
from source

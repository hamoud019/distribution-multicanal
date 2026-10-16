-- The cookie banner's daily figures: how many visitors saw it and how many accepted analytics cookies.

with source as (
    select * from {{ source('ga4', 'consent_daily') }}
)

select
    cast("date" as date)                                               as date,
    cast(banner_views as integer)                                      as banner_views,
    cast(accepted as integer)                                          as accepted
from source

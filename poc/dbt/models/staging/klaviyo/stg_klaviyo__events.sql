-- Klaviyo events, one row per open or click of a campaign email, in Paris local time. The events of a
-- profile on the erasure suppression list are left out.

with source as (
    select payload::json as e from {{ source('klaviyo', 'events') }}
)

select
    e->>'id'                                                           as event_id,
    e->>'$.attributes.metric'                                          as metric,
    e->>'$.attributes.profile_id'                                      as klaviyo_profile_id,
    e->>'$.attributes.campaign_id'                                     as campaign_id,
    cast(timezone('Europe/Paris', cast(e->>'$.attributes.datetime' as timestamptz)) as timestamp) as occurred_at
from source
where not {{ is_erased(pseudonymize("'klaviyo:' || (e->>'$.attributes.profile_id')")) }}

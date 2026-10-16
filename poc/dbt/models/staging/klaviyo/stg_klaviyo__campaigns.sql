-- Klaviyo campaigns, one row per campaign, with the counts of the campaign report. Klaviyo gives UTC times:
-- the send date is taken in Paris time.

with source as (
    select payload::json as c from {{ source('klaviyo', 'campaigns') }}
)

select
    c->>'id'                                                           as campaign_id,
    c->>'$.attributes.name'                                            as campaign_name,
    cast(timezone('Europe/Paris', cast(c->>'$.attributes.send_time' as timestamptz)) as timestamp) as sent_at,
    cast(timezone('Europe/Paris', cast(c->>'$.attributes.send_time' as timestamptz)) as date) as send_date,
    cast(c->>'$.attributes.statistics.recipients' as integer)          as recipients,
    cast(c->>'$.attributes.statistics.delivered' as integer)           as delivered
from source

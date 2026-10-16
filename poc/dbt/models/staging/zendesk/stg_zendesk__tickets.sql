-- Zendesk tickets, one row per ticket. Zendesk gives UTC times: the date is taken in Paris time. The
-- requester's email and name, the subject and the description stay in the raw layer (Part 6: restricted,
-- free text may contain anything); only the email's matching key comes through. The agent fills in two
-- custom fields: the order number (a Shopify order name like #2934, or a till ticket number) and the SKU.

with source as (
    select payload::json as t from {{ source('zendesk', 'tickets') }}
),

fields as (
    select
        t,
        map_from_entries(from_json(t->'custom_fields', '[{"id": "BIGINT", "value": "VARCHAR"}]')
            .list_transform(f -> {'key': f.id, 'value': f.value})) as custom
    from source
)

select
    cast(t->>'id' as bigint)                                           as ticket_id,
    cast(timezone('Europe/Paris', cast(t->>'created_at' as timestamptz)) as date) as created_date,
    {{ email_key("t->>'$.requester.email'") }}                         as email_key,
    t->>'$.tags[0]'                                                    as ticket_category,
    t->>'status'                                                       as status,
    t->>'$.via.channel'                                                as contact_channel,
    t->>'$.satisfaction_rating.score'                                  as satisfaction,
    custom[360001]                                                     as order_number,
    custom[360002]                                                     as sku,
    cast(t->>'$.metrics.reply_time_in_minutes.calendar' as integer)    as first_reply_minutes
from fields

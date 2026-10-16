-- Zendesk tickets, one row per ticket. Zendesk gives UTC times: the date is taken in Paris time. The
-- requester's email and name, the subject and the description stay in the raw layer (Part 6: restricted,
-- free text may contain anything); only the email's matching key comes through.

with source as (
    select payload::json as t from {{ source('zendesk', 'tickets') }}
)

select
    cast(t->>'id' as bigint)                                           as ticket_id,
    cast(timezone('Europe/Paris', cast(t->>'created_at' as timestamptz)) as date) as created_date,
    {{ email_key("t->>'$.requester.email'") }}                         as email_key,
    t->>'$.tags[0]'                                                    as ticket_category,
    t->>'status'                                                       as status,
    t->>'$.via.channel'                                                as contact_channel,
    t->>'$.satisfaction_rating.score'                                  as satisfaction
from source

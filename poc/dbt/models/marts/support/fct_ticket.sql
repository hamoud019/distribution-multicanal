-- Support tickets linked to the golden customer of the requester's email (story 14), so an agent can see
-- the customer's orders in fct_sales through the same customer key. The free text stays in the raw layer.
-- Ticket categories follow the glossary; satisfaction is only given after some tickets.

with tickets as (
    select * from {{ ref('stg_zendesk__tickets') }}
),

identities as (
    select record_id, customer_key from {{ ref('int_customers__identity_map') }}
)

select
    tickets.ticket_id,
    tickets.created_date,
    coalesce(identities.customer_key, 'anonymous')                 as customer_key,
    case tickets.ticket_category
        when 'delivery' then 'delivery'
        when 'exchange' then 'size/exchange'
        when 'quality' then 'product quality'
        when 'refund' then 'payment'
        else 'other'
    end                                                            as ticket_category,
    tickets.contact_channel,
    tickets.status,
    case tickets.satisfaction
        when 'good' then 'satisfied'
        when 'bad' then 'not satisfied'
    end                                                            as csat
from tickets
left join identities on identities.record_id = 'zendesk:' || tickets.ticket_id

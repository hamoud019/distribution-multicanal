-- Support tickets linked to the golden customer of the requester's email (story 14), so an agent can see
-- the customer's orders in fct_sales through the same customer key. The free text stays in the raw layer.
-- Each ticket is about one purchase: the order number the agent filled in gives the order and its channel
-- (a Shopify order name for Web, a till ticket number for Store), and the product field gives the SKU
-- (story 15). Ticket categories follow the glossary; satisfaction is only given after some tickets.

with tickets as (
    select * from {{ ref('stg_zendesk__tickets') }}
),

identities as (
    select record_id, customer_key from {{ ref('int_customers__identity_map') }}
),

web_orders as (
    select order_name, cast(order_id as varchar) as order_id from {{ ref('stg_shopify__orders') }}
),

orders as (
    select distinct order_id, channel from {{ ref('fct_sales') }}
    where channel in ('Web', 'Store')
)

select
    tickets.ticket_id,
    tickets.created_date,
    coalesce(identities.customer_key, 'anonymous')                 as customer_key,
    orders.order_id,
    orders.channel,
    tickets.sku,
    case tickets.ticket_category
        when 'delivery' then 'delivery'
        when 'exchange' then 'size/exchange'
        when 'quality' then 'product quality'
        when 'refund' then 'payment'
        else 'other'
    end                                                            as ticket_category,
    tickets.contact_channel,
    tickets.status,
    round(tickets.first_reply_minutes / 60, 1)                     as first_response_hours,
    case tickets.satisfaction
        when 'good' then 'satisfied'
        when 'bad' then 'not satisfied'
    end                                                            as csat
from tickets
left join identities on identities.record_id = 'zendesk:' || tickets.ticket_id
left join web_orders on web_orders.order_name = tickets.order_number
left join orders on orders.order_id = coalesce(web_orders.order_id, tickets.order_number)

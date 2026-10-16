-- The sales fact: one row per order line of every channel (Web, Store, Wholesale), and one row per
-- returned line on the day of the return, so a return lowers the net revenue of the period it happens in.
-- Amounts follow the glossary (Part 6): excluding VAT; net revenue after discounts and returns;
-- margin = net revenue - quantity x unit cost.

with lines as (
    select * from {{ ref('int_sales__order_lines') }}
),

products as (
    select * from {{ ref('stg_erp__items') }}
),

identities as (
    select record_id, customer_key from {{ ref('int_customers__identity_map') }}
)

select
    lines.order_date,
    lines.channel,
    lines.location_code                                            as location,
    lines.order_id,
    lines.order_line,
    lines.wholesale_account,
    lines.sku,
    -- The golden customer of the Shopify customer or of the store ticket's e-receipt email. A store ticket
    -- without an email belongs to the "anonymous" member, a wholesale order to the "wholesale" member
    -- (a company is not a person), so every row has a key of dim_customer.
    coalesce(identities.customer_key,
        case lines.channel when 'Wholesale' then 'wholesale' else 'anonymous' end) as customer_key,
    lines.quantity,
    lines.gross_revenue,
    lines.discount,
    lines.net_revenue,
    cast(lines.net_revenue - lines.quantity * products.unit_cost as decimal(12, 2)) as margin,
    lines.is_return,
    lines.is_click_and_collect
from lines
left join products using (sku)
left join identities
    on identities.record_id = case lines.channel
        when 'Web' then 'shopify:' || lines.shopify_customer_id
        when 'Store' then 'pos:' || lines.order_id
    end

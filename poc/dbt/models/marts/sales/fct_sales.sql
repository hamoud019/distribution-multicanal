-- The sales fact: one row per order line of every channel (Web, Store, Wholesale), and one row per
-- returned line on the day of the return, so a return lowers the net revenue of the period it happens in.
-- Amounts follow the glossary (Part 6): excluding VAT; net revenue after discounts and returns;
-- margin = net revenue - quantity x unit cost.

with lines as (
    select * from {{ ref('int_sales__order_lines') }}
),

products as (
    select * from {{ ref('stg_erp__items') }}
)

select
    lines.order_date,
    lines.channel,
    lines.location_code                                            as location,
    lines.order_id,
    lines.order_line,
    lines.wholesale_account,
    lines.sku,
    -- Placeholder until the golden customer (issue #11): a pseudonymous key per Shopify account.
    -- Store tickets stay anonymous and wholesale accounts are companies, so they have no customer key.
    case when lines.shopify_customer_id is not null
        then md5('shopify|' || lines.shopify_customer_id) end      as customer_key,
    lines.quantity,
    lines.gross_revenue,
    lines.discount,
    lines.net_revenue,
    cast(lines.net_revenue - lines.quantity * products.unit_cost as decimal(12, 2)) as margin,
    lines.is_return,
    lines.is_click_and_collect
from lines
left join products using (sku)

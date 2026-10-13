-- Shopify line items, one row per order line. Prices include VAT; the discount is for the whole line.

with source as (
    select payload::json as o from {{ source('shopify', 'orders') }}
),

lines as (
    select
        cast(o->>'id' as bigint) as order_id,
        unnest(from_json(o->'line_items', '[{"id": "BIGINT", "sku": "VARCHAR", "quantity": "INTEGER",
            "price": "DECIMAL(12,2)", "total_discount": "DECIMAL(12,2)"}]')) as line
    from source
)

select
    line.id                                                            as order_line_id,
    order_id,
    cast(row_number() over (partition by order_id order by line.id) as integer) as line_number,
    line.sku                                                           as sku,
    line.quantity                                                      as quantity,
    line.price                                                         as unit_price_incl_vat,
    line.total_discount                                                as discount_incl_vat
from lines

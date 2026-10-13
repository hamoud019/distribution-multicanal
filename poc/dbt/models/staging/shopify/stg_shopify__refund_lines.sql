-- Shopify refunds, one row per refunded order line. A refund comes days or weeks after the order;
-- `refunded_at` is Paris local time. The subtotal includes VAT and is net of the line's discount.

with source as (
    select payload::json as o from {{ source('shopify', 'orders') }}
),

refunds as (
    select
        cast(o->>'id' as bigint) as order_id,
        unnest(from_json(o->'refunds', '[{"created_at": "VARCHAR", "refund_line_items":
            [{"line_item_id": "BIGINT", "quantity": "INTEGER", "subtotal": "DECIMAL(12,2)"}]}]')) as refund
    from source
),

refund_lines as (
    select order_id, refund.created_at as created_at, unnest(refund.refund_line_items) as line
    from refunds
)

select
    order_id,
    line.line_item_id                                                  as order_line_id,
    strptime(left(created_at, 19), '%Y-%m-%dT%H:%M:%S')                as refunded_at,
    cast(left(created_at, 10) as date)                                 as refund_date,
    line.quantity                                                      as quantity,
    line.subtotal                                                      as subtotal_incl_vat
from refund_lines

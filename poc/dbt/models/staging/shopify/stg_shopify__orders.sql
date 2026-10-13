-- Shopify orders, one row per order. Shopify gives Paris local time with its offset, so the local time is
-- the first 19 characters. The email and the shipping address stay in the raw layer (Part 6: restricted).

with source as (
    select payload::json as o, _batch_id, _loaded_at from {{ source('shopify', 'orders') }}
)

select
    cast(o->>'id' as bigint)                                           as order_id,
    o->>'name'                                                         as order_name,
    strptime(left(o->>'created_at', 19), '%Y-%m-%dT%H:%M:%S')          as created_at,
    cast(left(o->>'created_at', 10) as date)                           as order_date,
    cast(o->>'$.customer.id' as bigint)                                as shopify_customer_id,
    o->>'cancelled_at' is not null                                     as is_cancelled,
    o->>'$.shipping_lines[0].title' = 'Retrait en magasin'             as is_click_and_collect,
    o->>'fulfillment_location'                                         as fulfillment_location_code,
    cast(o->>'total_price' as decimal(12, 2))                          as total_incl_vat,
    cast(o->>'$.shipping_lines[0].price' as decimal(12, 2))            as shipping_incl_vat,
    _batch_id,
    _loaded_at
from source

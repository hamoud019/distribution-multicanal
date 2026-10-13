-- Every order line of the three channels in one shape, amounts excluding VAT (glossary, Part 6):
--   Web: Shopify lines of orders that are not cancelled, and each refunded line as a return on its refund date;
--   Store: till lines, returns are already negative quantities;
--   Wholesale: Business Central sales lines, already excluding VAT and without discount.
-- The location is the one that fulfils the line: the warehouse for shipped web orders, the store for
-- click-and-collect and for till sales. Shipping fees are not revenue.

with web_orders as (
    select * from {{ ref('stg_shopify__orders') }}
    where not is_cancelled
),

web_lines as (
    select * from {{ ref('stg_shopify__order_lines') }}
),

web_sales as (
    select
        o.order_date,
        'Web'                                                      as channel,
        o.fulfillment_location_code                                as location_code,
        cast(o.order_id as varchar)                                as order_id,
        l.line_number                                              as order_line,
        cast(null as varchar)                                      as wholesale_account,
        l.sku,
        o.shopify_customer_id,
        l.quantity,
        l.unit_price_incl_vat * l.quantity                         as gross_incl_vat,
        l.unit_price_incl_vat * l.quantity - l.discount_incl_vat   as net_incl_vat,
        false                                                      as is_return,
        o.is_click_and_collect
    from web_lines as l
    inner join web_orders as o using (order_id)
),

web_returns as (
    select
        r.refund_date                                              as order_date,
        'Web'                                                      as channel,
        o.fulfillment_location_code                                as location_code,
        cast(o.order_id as varchar)                                as order_id,
        l.line_number                                              as order_line,
        cast(null as varchar)                                      as wholesale_account,
        l.sku,
        o.shopify_customer_id,
        -r.quantity                                                as quantity,
        -l.unit_price_incl_vat * r.quantity                        as gross_incl_vat,
        -r.subtotal_incl_vat                                       as net_incl_vat,
        true                                                       as is_return,
        o.is_click_and_collect
    from {{ ref('stg_shopify__refund_lines') }} as r
    inner join web_lines as l using (order_line_id)
    inner join web_orders as o on o.order_id = l.order_id
),

store_lines as (
    select
        cast(sold_at as date)                                      as order_date,
        'Store'                                                    as channel,
        location_code,
        ticket_id                                                  as order_id,
        cast(row_number() over (
            partition by ticket_id order by sku, quantity, line_total_incl_vat) as integer) as order_line,
        cast(null as varchar)                                      as wholesale_account,
        sku,
        cast(null as bigint)                                       as shopify_customer_id,
        quantity,
        unit_price_incl_vat * quantity                             as gross_incl_vat,
        line_total_incl_vat                                        as net_incl_vat,
        quantity < 0                                               as is_return,
        false                                                      as is_click_and_collect
    from {{ ref('stg_pos__ticket_lines') }}
),

taxed as (
    select * from web_sales
    union all
    select * from web_returns
    union all
    select * from store_lines
),

excluding_vat as (
    select
        * exclude (gross_incl_vat, net_incl_vat),
        cast(round(gross_incl_vat / (1 + {{ var('vat_rate') }}), 2) as decimal(12, 2)) as gross_revenue,
        cast(round(net_incl_vat / (1 + {{ var('vat_rate') }}), 2) as decimal(12, 2))   as net_revenue
    from taxed
),

wholesale_lines as (
    select
        posting_date                                               as order_date,
        'Wholesale'                                                as channel,
        'WH-AUB'                                                   as location_code,  -- wholesale ships from the warehouse
        order_id,
        cast(row_number() over (partition by order_id order by line_no) as integer) as order_line,
        wholesale_account,
        sku,
        cast(null as bigint)                                       as shopify_customer_id,
        quantity,
        false                                                      as is_return,
        false                                                      as is_click_and_collect,
        line_amount                                                as gross_revenue,
        line_amount                                                as net_revenue
    from {{ ref('stg_erp__sales_lines') }}
)

select *, gross_revenue - net_revenue as discount from excluding_vat
union all by name
select *, gross_revenue - net_revenue as discount from wholesale_lines

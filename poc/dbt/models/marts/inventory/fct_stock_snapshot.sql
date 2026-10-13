-- The stock fact (Inventory Optimization use case): one row per snapshot date, location and SKU, with the
-- stock on hand from the ERP and the demand of every channel from the sales mart (glossary, Part 6).
--
-- Demand is matched to stock at the location that fulfils the sale, as in fct_sales: the warehouse ships the
-- web orders and the wholesale orders, a store hands over its till sales and the click-and-collect web orders.
-- So the warehouse's cover counts online demand (most of it), and a store's cover counts its till sales plus
-- the web orders collected there: never the store's till sales only.
--
-- Demand: units sold (returns not deducted, cancelled orders excluded) in the 28 days before the snapshot
-- date. The snapshot is taken in the morning, so the snapshot day itself is not in the window.
-- Stock cover: stock on hand / (demand / 28), in days. Empty when nothing sold: the cover is endless.
-- Sell-through rate: units sold / (stock at the start + units received). What was there at the start or came
-- in was either sold or is still on hand, so this is units sold / (units sold + stock on hand).
-- Stockout: zero stock while at least one unit sold. Stockout risk: stock left, but less than 14 days of cover.
-- Overstock: more than 180 days of cover. Slow mover: stock left that sold nothing in 28 days, so its cover
-- cannot be computed. It is kept apart from overstock: in the 1 % sample most SKUs sell less than once a
-- month, and calling all of them overstock would hide the SKUs that really have too much stock.
-- The thresholds are vars in dbt_project.yml.

with stock as (
    select * from {{ ref('stg_erp__stock') }}
),

daily_demand as (
    select order_date, location, sku, sum(quantity) as units
    from {{ ref('fct_sales') }}
    where not is_return
    group by all
),

demand as (
    select
        stock.snapshot_date,
        stock.location_code                                        as location,
        stock.sku,
        stock.stock_on_hand,
        coalesce(sum(daily_demand.units), 0)                       as demand_units
    from stock
    left join daily_demand
        on  daily_demand.location = stock.location_code
        and daily_demand.sku = stock.sku
        and daily_demand.order_date >= stock.snapshot_date - interval {{ var('demand_window_days') }} day
        and daily_demand.order_date < stock.snapshot_date
    group by all
),

cover as (
    select
        *,
        case when demand_units > 0
            then stock_on_hand * {{ var('demand_window_days') }} / demand_units end as cover_days
    from demand
)

select
    snapshot_date,
    location,
    sku,
    stock_on_hand,
    demand_units,
    cast(round(cover_days, 1) as decimal(10, 1))                   as stock_cover_days,
    case when demand_units + stock_on_hand > 0
        then cast(round(demand_units / (demand_units + stock_on_hand), 4) as decimal(5, 4)) end as sell_through_rate,
    stock_on_hand = 0 and demand_units > 0                         as is_stockout,
    stock_on_hand > 0 and coalesce(cover_days < {{ var('stockout_risk_cover_days') }}, false) as is_stockout_risk,
    stock_on_hand > 0 and coalesce(cover_days > {{ var('overstock_cover_days') }}, false) as is_overstock,
    stock_on_hand > 0 and demand_units = 0                         as is_slow_mover
from cover

-- Monthly sales of each channel and location, with the same month of the previous month and of the
-- previous year next to it, for period-over-period and year-over-year comparisons. Every month of the
-- calendar is there, with zeros when nothing was sold, so the comparisons never skip a month.
-- Orders do not add up across channels with returns in them, so the average basket is computed here
-- (glossary: net revenue / orders); a dashboard adding locations should divide the sums again.

with sales as (
    select * from {{ ref('fct_sales') }}
),

totals as (
    select
        cast(date_trunc('month', order_date) as date)              as month_start,
        channel,
        location,
        count(distinct case when not is_return then order_id end)  as orders,
        sum(quantity)                                              as units,
        sum(net_revenue)                                           as net_revenue,
        sum(margin)                                                as margin
    from sales
    group by all
),

grid as (
    select months.month_start, segments.channel, segments.location
    from (select distinct month_start from {{ ref('dim_date') }}) as months
    cross join (select distinct channel, location from sales) as segments
),

monthly as (
    select
        grid.month_start,
        grid.channel,
        grid.location,
        coalesce(totals.orders, 0)                                 as orders,
        coalesce(totals.units, 0)                                  as units,
        coalesce(totals.net_revenue, 0)                            as net_revenue,
        coalesce(totals.margin, 0)                                 as margin
    from grid
    left join totals using (month_start, channel, location)
)

select
    *,
    case when orders > 0 then cast(round(net_revenue / orders, 2) as decimal(12, 2)) end as average_basket,
    lag(net_revenue, 1) over by_segment                            as net_revenue_previous_month,
    lag(net_revenue, 12) over by_segment                           as net_revenue_last_year
from monthly
window by_segment as (partition by channel, location order by month_start)

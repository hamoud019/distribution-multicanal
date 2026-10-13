-- Reconciliation log (Part 4, section 4): the net revenue of the sales mart against the revenue finance
-- booked in the general ledger, per month and channel. The gap is accepted up to the tolerance set in
-- dbt_project.yml (0.5 %, our choice, to be agreed with the CFO). Checked every run by the test
-- assert_sales_reconcile_with_erp_finance.

with mart as (
    select cast(date_trunc('month', order_date) as date) as month_start, channel, sum(net_revenue) as net_revenue
    from {{ ref('fct_sales') }}
    group by all
),

erp as (
    select cast(date_trunc('month', posting_date) as date) as month_start, channel, sum(revenue) as erp_revenue
    from {{ ref('stg_erp__gl_entries') }}
    group by all
),

compared as (
    select
        month_start,
        channel,
        coalesce(mart.net_revenue, 0)                              as net_revenue,
        coalesce(erp.erp_revenue, 0)                               as erp_revenue
    from mart
    full outer join erp using (month_start, channel)
)

select
    month_start,
    channel,
    net_revenue,
    erp_revenue,
    net_revenue - erp_revenue                                      as gap,
    case when erp_revenue <> 0 then round((net_revenue - erp_revenue) / abs(erp_revenue), 5) end as gap_share,
    {{ var('reconciliation_tolerance') }}                          as tolerance,
    abs(net_revenue - erp_revenue) <= {{ var('reconciliation_tolerance') }} * abs(erp_revenue) as is_within_tolerance
from compared

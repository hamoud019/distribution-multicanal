-- Business rule: the daily sales of each store must match what its till printed at closing time
-- (the Z report): the same amount paid, to the cent, and the same number of tickets. Every store
-- day must be in both. Any row returned here is a store day that does not reconcile.

with mart as (
    select * from {{ ref('fct_pos_daily_sales') }}
),

z as (
    select * from {{ ref('stg_pos__z_reports') }}
)

select
    coalesce(mart.location_code, z.location_code) as location_code,
    coalesce(mart.sale_date, z.sale_date)         as sale_date,
    mart.amount_paid_incl_vat,
    z.total_incl_vat                              as z_total_incl_vat,
    mart.tickets,
    z.tickets                                     as z_tickets
from mart
full outer join z
    on mart.location_code = z.location_code
    and mart.sale_date = z.sale_date
where mart.store_day_key is null
    or z.sale_date is null
    or mart.amount_paid_incl_vat <> z.total_incl_vat
    or mart.tickets <> z.tickets

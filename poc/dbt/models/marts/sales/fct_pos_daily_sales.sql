-- Daily sales of each store: the first report table of the proof of concept.
-- Net revenue follows the glossary (Part 6): after discounts and returns, excluding VAT.

select
    t.location_code || '|' || strftime(t.sale_date, '%Y-%m-%d')        as store_day_key,
    t.sale_date,
    t.location_code,
    l.location_name,
    count(*)                                                          as tickets,
    sum(t.units)                                                      as units,
    sum(t.total_incl_vat)                                             as amount_paid_incl_vat,
    cast(round(sum(t.total_incl_vat) / (1 + {{ var('vat_rate') }}), 2) as decimal(12, 2)) as net_revenue
from {{ ref('int_pos__tickets') }} as t
left join {{ ref('stg_erp__locations') }} as l using (location_code)
group by t.sale_date, t.location_code, l.location_name

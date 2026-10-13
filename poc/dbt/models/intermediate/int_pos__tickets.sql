-- One row per till ticket: the lines added up.

select
    ticket_id,
    location_code,
    min(sold_at)                  as sold_at,
    cast(min(sold_at) as date)    as sale_date,
    count(*)                      as lines,
    sum(quantity)                 as units,
    sum(line_total_incl_vat)      as total_incl_vat,
    bool_or(has_e_receipt)        as has_e_receipt
from {{ ref('stg_pos__ticket_lines') }}
group by ticket_id, location_code

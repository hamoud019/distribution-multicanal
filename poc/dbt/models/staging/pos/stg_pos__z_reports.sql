-- End-of-day totals printed by each till (Z report): the reference the store sales are checked against.

with source as (
    select * from {{ source('pos', 'z_reports') }}
)

select
    magasin || '|' || strftime(strptime(date, '%d/%m/%Y'), '%Y-%m-%d') as store_day_key,
    magasin                                                  as location_code,
    cast(strptime(date, '%d/%m/%Y') as date)                 as sale_date,
    cast(nb_tickets as integer)                              as tickets,
    cast(replace(total_ttc, ',', '.') as decimal(12, 2))     as total_incl_vat
from source

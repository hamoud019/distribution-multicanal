-- Till lines with English names and real types: French dates (dd/mm/yyyy) and decimal commas.
-- The e-receipt email stays in the raw layer (Part 6: restricted); only the fact that one was given is kept.

with source as (
    select * from {{ source('pos', 'ticket_lines') }}
)

select
    ticket_no                                                as ticket_id,
    strptime(date_heure, '%d/%m/%Y %H:%M')                   as sold_at,
    magasin                                                  as location_code,
    sku,
    cast(qte as integer)                                     as quantity,
    cast(replace(prix_unitaire_ttc, ',', '.') as decimal(12, 2)) as unit_price_incl_vat,
    cast(replace(remise_ttc, ',', '.') as decimal(12, 2))    as discount_incl_vat,
    cast(replace(total_ligne_ttc, ',', '.') as decimal(12, 2)) as line_total_incl_vat,
    coalesce(trim(email_ticket), '') <> ''                   as has_e_receipt,
    _batch_id,
    _loaded_at
from source

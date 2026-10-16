-- Till lines with English names and real types: French dates (dd/mm/yyyy) and decimal commas.
-- The e-receipt email stays in the raw layer (Part 6: restricted): only its matching key comes through, to
-- find the ticket's golden customer. For a person on the erasure suppression list the ticket stays
-- (accounting) but loses its matching key, so it becomes anonymous.

with source as (
    select * from {{ source('pos', 'ticket_lines') }}
),

lines as (
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
        {{ email_key('email_ticket') }}                          as email_key,
        _batch_id,
        _loaded_at
    from source
)

select
    * replace (
        case when {{ is_erased('email_key') }} or {{ is_erased(pseudonymize("'pos:' || ticket_id")) }}
            then null else email_key end as email_key
    )
from lines

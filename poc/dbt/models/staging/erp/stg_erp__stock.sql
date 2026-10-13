-- Business Central stock: a full snapshot of every SKU at every location (glossary: Stock on hand).
-- The export has no date column: the snapshot date is in the file name (stock_<yyyymmdd>.csv).
-- Weekly in the proof of concept, daily in production.

with source as (
    select * from {{ source('erp', 'stock') }}
)

select
    cast(strptime(regexp_extract(_file, 'stock_(\d{8})', 1), '%Y%m%d') as date) as snapshot_date,
    "Location Code"                             as location_code,
    "Item No."                                  as sku,
    cast("Quantity" as integer)                 as stock_on_hand
from source

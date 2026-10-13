-- Business Central items: one row per SKU (a product in one size). Prices and costs exclude VAT.

with source as (
    select * from {{ source('erp', 'items') }}
)

select
    "No."                                       as sku,
    split_part("No.", '-', 1) || '-' || split_part("No.", '-', 2) as product_code,
    "Description"                               as product_name,
    "Item Category Code"                        as category,
    "Variant Size"                              as size,
    "Colour"                                    as colour,
    cast("Unit Price" as decimal(12, 2))        as unit_price,
    cast("Unit Cost" as decimal(12, 2))         as unit_cost
from source

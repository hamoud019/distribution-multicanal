-- Business Central production orders: one batch of a SKU finished by the factory (glossary: Units produced).

with source as (
    select * from {{ source('erp', 'production_orders') }}
)

select
    "No."                                       as production_order,
    cast("Finished Date" as date)               as finished_date,
    "Location Code"                             as location_code,
    "Item No."                                  as sku,
    cast("Quantity" as integer)                 as quantity
from source

-- Product dimension: one row per SKU, from the Business Central items.

select
    sku,
    product_name                                as product,
    product_code,
    category,
    size,
    colour,
    unit_price,
    unit_cost
from {{ ref('stg_erp__items') }}

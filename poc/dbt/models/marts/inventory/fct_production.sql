-- The production fact: one row per production order, the units of one SKU the factory finished on a day
-- (glossary: Units produced). All production is in the Aubervilliers factory, which is also the warehouse.

select
    production_order,
    finished_date                               as production_date,
    location_code                               as location,
    sku,
    quantity                                    as units_produced
from {{ ref('stg_erp__production_orders') }}

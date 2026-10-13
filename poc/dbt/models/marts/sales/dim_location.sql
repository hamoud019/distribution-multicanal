-- Location dimension: the warehouse/factory and the own stores (glossary: Location).

select
    location_code                               as location,
    location_name,
    location_type
from {{ ref('stg_erp__locations') }}

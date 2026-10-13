-- Business Central locations: the factory/warehouse and the own stores (glossary: Location).

with source as (
    select * from {{ source('erp', 'locations') }}
)

select
    "Code"          as location_code,
    "Name"          as location_name,
    "Location Type" as location_type
from source

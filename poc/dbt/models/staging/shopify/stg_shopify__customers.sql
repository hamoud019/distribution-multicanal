-- Shopify customers, one row per customer. The email, phone, names and address stay in the raw layer
-- (Part 6: restricted): only their matching keys and the department of the address come through.

with source as (
    select payload::json as c from {{ source('shopify', 'customers') }}
)

select
    cast(c->>'id' as bigint)                                           as shopify_customer_id,
    {{ email_key("c->>'email'") }}                                     as email_key,
    {{ phone_key("c->>'phone'", "c->>'first_name'") }}                 as phone_key,
    left(c->>'$.default_address.zip', 2)                               as department,
    c->>'$.email_marketing_consent.state'                              as consent_state
from source

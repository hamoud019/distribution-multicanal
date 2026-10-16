-- Shopify customers, one row per customer. The email, phone, names and address stay in the raw layer
-- (Part 6: restricted): only their matching keys and the department of the address come through.
-- A customer on the erasure suppression list is left out, even if Shopify sends them again.

with source as (
    select payload::json as c from {{ source('shopify', 'customers') }}
),

customers as (
    select
        cast(c->>'id' as bigint)                                       as shopify_customer_id,
        {{ email_key("c->>'email'") }}                                 as email_key,
        {{ phone_key("c->>'phone'", "c->>'first_name'") }}             as phone_key,
        left(c->>'$.default_address.zip', 2)                           as department,
        c->>'$.email_marketing_consent.state'                          as consent_state
    from source
)

select *
from customers
where not {{ is_erased(pseudonymize("'shopify:' || shopify_customer_id")) }}
    and not {{ is_erased('email_key') }}
    and not {{ is_erased('phone_key') }}

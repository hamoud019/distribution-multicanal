-- Klaviyo profiles, one row per profile. Contact data stays in the raw layer (Part 6: restricted): only the
-- matching keys, the Shopify id when the profile was synced from Shopify, the department, the birth year
-- (for the age band) and the email consent come through. A profile on the erasure suppression list is
-- left out, even if Klaviyo sends it again.

with source as (
    select payload::json as p from {{ source('klaviyo', 'profiles') }}
),

profiles as (
    select
        p->>'id'                                                       as klaviyo_profile_id,
        {{ email_key("p->>'$.attributes.email'") }}                    as email_key,
        {{ phone_key("p->>'$.attributes.phone_number'", "p->>'$.attributes.first_name'") }} as phone_key,
        cast(p->>'$.attributes.properties.shopify_customer_id' as bigint) as shopify_customer_id,
        left(p->>'$.attributes.location.zip', 2)                       as department,
        year(cast(p->>'$.attributes.properties.birthday' as date))     as birth_year,
        p->>'$.attributes.subscriptions.email.marketing.consent'       as consent_state
    from source
)

select *
from profiles
where not {{ is_erased(pseudonymize("'klaviyo:' || klaviyo_profile_id")) }}
    and not {{ is_erased('email_key') }}
    and not {{ is_erased('phone_key') }}

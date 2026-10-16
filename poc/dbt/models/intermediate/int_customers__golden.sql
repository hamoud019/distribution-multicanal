-- One row per golden customer, with the values that survive the merge (Part 6, section 2):
--   Region: department of the shipping postcode of the most recent web order, else of the Shopify customer,
--     else of the Klaviyo profile.
--   Birth year: from the Klaviyo birthday, when given (only the age band reaches the marts).
--   Marketing consent: given in Shopify or Klaviyo, and withdrawn in neither. The tools only give their
--     current state, so a withdrawal anywhere wins over a consent anywhere.
-- Names, emails and phones are not here: they stay in the raw layer and in the tools.

with identities as (
    select * from {{ ref('int_customers__identity_map') }}
),

accounts as (
    select identities.customer_key, c.department, c.consent_state
    from {{ ref('stg_shopify__customers') }} as c
    inner join identities on identities.record_id = 'shopify:' || c.shopify_customer_id
),

profiles as (
    select identities.customer_key, p.department, p.birth_year, p.consent_state
    from {{ ref('stg_klaviyo__profiles') }} as p
    inner join identities on identities.record_id = 'klaviyo:' || p.klaviyo_profile_id
),

last_shipping as (
    select identities.customer_key, arg_max(o.shipping_department, o.created_at) as department
    from {{ ref('stg_shopify__orders') }} as o
    inner join identities on identities.record_id = 'shopify:' || o.shopify_customer_id
    where not o.is_cancelled
    group by identities.customer_key
),

consent as (
    select
        customer_key,
        bool_or(lower(consent_state) = 'subscribed')               as has_consented,
        bool_or(lower(consent_state) = 'unsubscribed')             as has_withdrawn
    from (
        select customer_key, consent_state from accounts
        union all
        select customer_key, consent_state from profiles
    )
    group by customer_key
)

select
    golden.customer_key,
    coalesce(
        last_shipping.department,
        (select min(department) from accounts where accounts.customer_key = golden.customer_key),
        (select min(department) from profiles where profiles.customer_key = golden.customer_key)
    )                                                              as region,
    (select max(birth_year) from profiles where profiles.customer_key = golden.customer_key) as birth_year,
    coalesce(consent.has_consented and not consent.has_withdrawn, false) as marketing_consent
from (select distinct customer_key from identities) as golden
left join last_shipping using (customer_key)
left join consent using (customer_key)

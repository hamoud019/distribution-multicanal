-- Every record of a person in the source tools, before matching (glossary: a customer "as one source tool
-- knows them"): Shopify customers, Klaviyo profiles, store tickets with an e-receipt email and Zendesk
-- tickets. Only the matching keys come with them, never the email or phone itself.

with shopify as (
    select
        'shopify:' || shopify_customer_id                          as record_id,
        'Shopify'                                                  as source,
        cast(shopify_customer_id as varchar)                       as source_id,
        email_key,
        phone_key,
        cast(null as varchar)                                      as linked_record_id
    from {{ ref('stg_shopify__customers') }}
),

klaviyo as (
    select
        'klaviyo:' || klaviyo_profile_id,
        'Klaviyo',
        klaviyo_profile_id,
        email_key,
        phone_key,
        -- a profile synced from Shopify carries the Shopify id (matching rule 3)
        case when shopify_customer_id is not null then 'shopify:' || shopify_customer_id end
    from {{ ref('stg_klaviyo__profiles') }}
),

store_tickets as (
    select 'pos:' || ticket_id, 'POS', ticket_id, any_value(email_key), cast(null as varchar), cast(null as varchar)
    from {{ ref('stg_pos__ticket_lines') }}
    where email_key is not null
    group by ticket_id
),

support_tickets as (
    select
        'zendesk:' || ticket_id, 'Zendesk', cast(ticket_id as varchar), email_key, cast(null as varchar),
        cast(null as varchar)
    from {{ ref('stg_zendesk__tickets') }}
    where email_key is not null
)

select * from shopify
union all select * from klaviyo
union all select * from store_tickets
union all select * from support_tickets

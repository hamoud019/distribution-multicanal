-- The pairs of records that the automatic matching rules join (Part 6, section 2, governance/mdm_rules.csv):
--   1. the same email, in lower case without spaces;
--   2. the same phone in +33 format AND the same first name (a household sharing one phone is not merged);
--   3. a record that stores the other's id (a Klaviyo profile synced from Shopify).
-- Rule 4 (same name and postcode) is never automatic: it would go to the CRM manager's review, not here.
-- One row per pair and rule, so a data steward can see why two records were merged.

with records as (
    select * from {{ ref('int_customers__records') }}
)

select a.record_id as record_a, b.record_id as record_b, 1 as rule, 'same email' as matched_by
from records as a
inner join records as b on a.email_key = b.email_key and a.record_id < b.record_id

union all

select a.record_id, b.record_id, 2, 'same phone and first name'
from records as a
inner join records as b on a.phone_key = b.phone_key and a.record_id < b.record_id

union all

select records.record_id, linked.record_id, 3, 'source id link'
from records
inner join records as linked on linked.record_id = records.linked_record_id

-- Which golden customer each source record belongs to. Records joined by a match, directly or through
-- other records, are one person: a record that shares an email with a store ticket that shares nothing else
-- still ends up with the person of that email. The group is named after its smallest record id, and the
-- customer key is the pseudonymized name (glossary: Customer key).

with recursive

records as (
    select * from {{ ref('int_customers__records') }}
),

links as (
    select record_a as record_id, record_b as other from {{ ref('int_customers__matches') }}
    union
    select record_b, record_a from {{ ref('int_customers__matches') }}
),

reachable (record_id, other) as (
    select record_id, record_id from records
    union
    select reachable.record_id, links.other
    from reachable
    inner join links on links.record_id = reachable.other
),

groups as (
    select record_id, min(other) as golden_id
    from reachable
    group by record_id
)

select
    records.record_id,
    records.source,
    records.source_id,
    groups.golden_id,
    {{ pseudonymize("'golden|' || groups.golden_id") }}            as customer_key
from records
inner join groups using (record_id)

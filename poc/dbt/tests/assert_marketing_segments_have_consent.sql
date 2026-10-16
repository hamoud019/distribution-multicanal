-- Business rule (story 11, Part 6 section 4): marketing may only target customers who gave their marketing
-- consent and did not withdraw it in any tool. Any row returned here is a customer in the marketing segments
-- without that consent.

select segments.customer_key
from {{ ref('marketing_segments') }} as segments
left join {{ ref('int_customers__golden') }} as golden using (customer_key)
where not coalesce(golden.marketing_consent, false)

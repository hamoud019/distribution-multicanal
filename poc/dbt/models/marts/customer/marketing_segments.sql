-- The customers marketing may target, with their RFM segment (story 7). Only golden customers with
-- marketing consent are here (story 11, Part 6 section 4): a customer who never consented, or who withdrew
-- in any tool, is left out. The CNIL "existing customer" exception is not used: the source tools do not
-- record whether the customer was told and could refuse.

select
    customer_key,
    rfm_segment,
    is_omnichannel,
    region,
    age_band
from {{ ref('dim_customer') }}
where customer_type = 'person'
    and marketing_consent
    and rfm_segment is not null

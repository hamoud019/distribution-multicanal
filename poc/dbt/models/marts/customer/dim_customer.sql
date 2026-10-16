-- The customer dimension (Customer Segmentation use case): one row per golden customer found in the Web or
-- Store sales or in support, plus two members that are not people: "anonymous" (store tickets without an
-- email) and "wholesale" (companies). Only the pseudonymous customer key identifies a person.
--
-- RFM (glossary: orders of the last 24 months), as of the last day of sales. The 24 months and the recency
-- days are vars in dbt_project.yml:
--   Recency score: last order 30 days ago or less 5, 90 days 4, 180 days 3, 365 days 2, older 1.
--   Frequency score: Web and Store orders in the last 24 months, 1 to 5 (5 = five orders or more).
--   Monetary score: net revenue of the last 24 months, in five groups of the same size (5 = the most).
--   Segment, the first rule that matches:
--     Lost             no order in the last 24 months
--     Champions        recency 4-5 and frequency 3 or more
--     Loyal            frequency 3 or more
--     New              recency 4-5 and one order
--     Promising        recency 3-5 and two orders
--     At risk          recency 1-2 and two orders or more
--     Hibernating      recency 1-2 and one order
--     Needs attention  the rest (recency 3, one order)

with sales as (
    select * from {{ ref('fct_sales') }}
    where channel in ('Web', 'Store') and customer_key not in ('anonymous', 'wholesale')
),

as_of as (
    select max(order_date) as day from {{ ref('fct_sales') }}
),

orders as (
    select customer_key, order_id, channel, min(order_date) as order_date
    from sales
    where not is_return
    group by all
),

per_customer as (
    select
        orders.customer_key,
        min(order_date)                                            as first_order_date,
        max(order_date)                                            as last_order_date,
        count(*)                                                   as order_count,
        count(*) filter (where order_date > as_of.day - interval {{ var('rfm_window_months') }} month) as orders_24m,
        bool_or(channel = 'Web') and bool_or(channel = 'Store')    as is_omnichannel,
        any_value(as_of.day)                                       as as_of_day
    from orders, as_of
    group by orders.customer_key
),

revenue_24m as (
    select customer_key, sum(net_revenue) as net_revenue_24m
    from sales, as_of
    where order_date > as_of.day - interval {{ var('rfm_window_months') }} month
    group by customer_key
),

scored as (
    select
        per_customer.*,
        revenue_24m.net_revenue_24m,
        case
            {%- for days in var('rfm_recency_days') %}
            when as_of_day - last_order_date <= {{ days }} then {{ 5 - loop.index0 }}
            {%- endfor %}
            else 1
        end                                                        as recency_score,
        least(orders_24m, 5)                                       as frequency_score
    from per_customer
    left join revenue_24m using (customer_key)
),

segmented as (
    select
        *,
        case when orders_24m > 0 then ntile(5) over (
            partition by orders_24m > 0 order by net_revenue_24m, customer_key) end as monetary_score,
        case
            when orders_24m = 0 then 'Lost'
            when recency_score >= 4 and frequency_score >= 3 then 'Champions'
            when frequency_score >= 3 then 'Loyal'
            when recency_score >= 4 and frequency_score = 1 then 'New'
            when recency_score >= 3 and frequency_score = 2 then 'Promising'
            when recency_score <= 2 and frequency_score >= 2 then 'At risk'
            when recency_score <= 2 and frequency_score = 1 then 'Hibernating'
            else 'Needs attention'
        end                                                        as rfm_segment
    from scored
),

people as (
    -- everyone in the sales, even with a return only (a store ticket that is just a return), and in support
    select customer_key from sales
    union
    select customer_key from {{ ref('fct_ticket') }} where customer_key <> 'anonymous'
)

select
    people.customer_key,
    'person'                                                       as customer_type,
    segmented.first_order_date,
    segmented.last_order_date,
    coalesce(segmented.order_count, 0)                             as order_count,
    coalesce(segmented.order_count, 0) >= 2                        as is_repeat_customer,
    coalesce(segmented.is_omnichannel, false)                      as is_omnichannel,
    segmented.recency_score,
    segmented.frequency_score,
    segmented.monetary_score,
    segmented.rfm_segment,
    golden.marketing_consent,
    case
        when golden.birth_year is null then 'unknown'
        when year(as_of.day) - golden.birth_year < 25 then 'under 25'
        when year(as_of.day) - golden.birth_year < 35 then '25-34'
        when year(as_of.day) - golden.birth_year < 45 then '35-44'
        when year(as_of.day) - golden.birth_year < 55 then '45-54'
        else '55+'
    end                                                            as age_band,
    golden.region
from people
inner join {{ ref('int_customers__golden') }} as golden using (customer_key)
left join segmented using (customer_key)
cross join as_of

union all by name

select * from (values
    ('anonymous', 'anonymous', 0, false, false, false),
    ('wholesale', 'wholesale', 0, false, false, false)
) as members (customer_key, customer_type, order_count, is_repeat_customer, is_omnichannel, marketing_consent)

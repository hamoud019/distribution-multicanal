-- Support quality (story 15): tickets, CSAT rate and first response time per month, sales channel and product,
-- so a customer service lead can see a product that keeps coming back. The CSAT rate only counts tickets
-- where the customer answered the survey.

select
    cast(date_trunc('month', tickets.created_date) as date)        as month_start,
    tickets.channel,
    products.product,
    count(*)                                                       as tickets,
    round(avg(case tickets.csat when 'satisfied' then 1.0 when 'not satisfied' then 0.0 end), 4) as csat_rate,
    round(avg(tickets.first_response_hours), 1)                    as first_response_hours
from {{ ref('fct_ticket') }} as tickets
inner join {{ ref('dim_product') }} as products using (sku)
group by all

-- Campaign results (story 8): one row per Klaviyo campaign, with its open and click rates and the sales that
-- followed. Attributed revenue (glossary): the net revenue of the Web orders that a golden customer placed
-- within 5 days after clicking the campaign (var attribution_window_days). The click is matched to the
-- customer through the golden customer of the Klaviyo profile, so an order of the same person in Shopify
-- counts even when the two tools have different emails. When the customer clicked several campaigns
-- before an order, the most recent click wins, so an order is never counted twice. The order counts as it
-- was placed (its sold lines); a later return is not taken off.

with campaigns as (
    select * from {{ ref('stg_klaviyo__campaigns') }}
),

events as (
    select * from {{ ref('stg_klaviyo__events') }}
),

engagement as (
    select
        campaign_id,
        count(distinct case when metric = 'Opened Email' then klaviyo_profile_id end)  as openers,
        count(distinct case when metric = 'Clicked Email' then klaviyo_profile_id end) as clickers
    from events
    group by campaign_id
),

clicks as (
    select events.campaign_id, events.occurred_at as clicked_at, identities.customer_key
    from events
    inner join {{ ref('int_customers__identity_map') }} as identities
        on identities.record_id = 'klaviyo:' || events.klaviyo_profile_id
    where events.metric = 'Clicked Email'
),

web_orders as (
    select sales.order_id, sales.customer_key, orders.created_at, sum(sales.net_revenue) as net_revenue
    from {{ ref('fct_sales') }} as sales
    inner join {{ ref('stg_shopify__orders') }} as orders on cast(orders.order_id as varchar) = sales.order_id
    where sales.channel = 'Web' and not sales.is_return
    group by all
),

attributed as (
    select
        web_orders.order_id,
        any_value(web_orders.net_revenue)                          as net_revenue,
        arg_max(clicks.campaign_id, clicks.clicked_at)             as campaign_id
    from web_orders
    inner join clicks
        on clicks.customer_key = web_orders.customer_key
        and web_orders.created_at > clicks.clicked_at
        and web_orders.created_at <= clicks.clicked_at + interval {{ var('attribution_window_days') }} day
    group by web_orders.order_id
),

revenue as (
    select campaign_id, count(*) as attributed_orders, sum(net_revenue) as attributed_revenue
    from attributed
    group by campaign_id
)

select
    campaigns.campaign_id,
    campaigns.campaign_name                                        as campaign,
    campaigns.send_date,
    campaigns.recipients,
    round(coalesce(engagement.openers, 0) / nullif(campaigns.delivered, 0), 4) as open_rate,
    round(coalesce(engagement.clickers, 0) / nullif(campaigns.delivered, 0), 4) as click_rate,
    coalesce(revenue.attributed_orders, 0)                         as attributed_orders,
    coalesce(revenue.attributed_revenue, 0)                        as attributed_revenue
from campaigns
left join engagement using (campaign_id)
left join revenue using (campaign_id)

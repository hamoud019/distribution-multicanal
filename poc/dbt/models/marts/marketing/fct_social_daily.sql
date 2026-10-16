-- Social media results (story 10): one row per day and platform, with the same three figures for Instagram,
-- Facebook and TikTok. The account insights carry no campaign: campaigns are compared by period, next to
-- the send dates of fct_campaign.

select date, 'Instagram' as platform, impressions, engagement, followers from {{ ref('stg_social__instagram') }}
union all
select date, 'Facebook', impressions, engagement, followers from {{ ref('stg_social__facebook') }}
union all
select date, 'TikTok', impressions, engagement, followers from {{ ref('stg_social__tiktok') }}

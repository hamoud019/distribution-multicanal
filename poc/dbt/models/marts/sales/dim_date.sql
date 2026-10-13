-- Date dimension: every day of the years that have sales, with what period-over-period and
-- year-over-year comparisons need. Weeks start on Monday (glossary: Date).

with bounds as (
    select
        date_trunc('year', min(order_date))                         as first_day,
        date_trunc('year', max(order_date)) + interval 1 year       as after_last_day
    from {{ ref('int_sales__order_lines') }}
),

days as (
    select cast(unnest(generate_series(first_day, after_last_day - interval 1 day, interval 1 day)) as date) as date
    from bounds
)

select
    date,
    year(date)                                                      as year,
    quarter(date)                                                   as quarter,
    month(date)                                                     as month,
    strftime(date, '%B')                                            as month_name,
    cast(date_trunc('month', date) as date)                         as month_start,
    isoyear(date)                                                   as iso_year,
    week(date)                                                      as iso_week,
    cast(date_trunc('week', date) as date)                          as week_start,
    isodow(date)                                                    as day_of_week,
    strftime(date, '%A')                                            as day_name,
    isodow(date) >= 6                                               as is_weekend,
    cast(date - interval 1 year as date)                            as same_date_last_year,
    cast(date - interval 364 day as date)                           as same_weekday_last_year
from days

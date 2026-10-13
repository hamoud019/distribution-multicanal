-- Business Central sales lines: the wholesale orders (Carrefour, Monoprix). Amounts exclude VAT.

with source as (
    select * from {{ source('erp', 'sales_lines') }}
)

select
    "Document No."                              as order_id,
    cast("Line No." as integer)                 as line_no,
    "Sell-to Customer No."                      as wholesale_account,
    cast("Posting Date" as date)                as posting_date,
    "No."                                       as sku,
    cast("Quantity" as integer)                 as quantity,
    cast("Unit Price" as decimal(12, 2))        as unit_price,
    cast("Line Amount" as decimal(12, 2))       as line_amount
from source

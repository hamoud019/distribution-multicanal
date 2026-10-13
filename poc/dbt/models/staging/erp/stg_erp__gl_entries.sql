-- Business Central general ledger entries on the revenue accounts. Accounting books revenue as a credit
-- (a negative amount), so the sign is turned around: `revenue` is positive for a sale.
-- The channel comes from the account (French chart of accounts, 701 = sales of finished products).

with source as (
    select * from {{ source('erp', 'gl_entries') }}
)

select
    cast("Entry No." as integer)                as entry_no,
    cast("Posting Date" as date)                as posting_date,
    "G/L Account No."                           as gl_account,
    case "G/L Account No."
        when '701100' then 'Web'
        when '701200' then 'Store'
        when '701300' then 'Wholesale'
    end                                         as channel,
    -cast("Amount" as decimal(14, 2))           as revenue
from source

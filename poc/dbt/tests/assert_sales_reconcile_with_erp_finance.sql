-- Business rule (story 5): the net revenue of the sales mart must match what finance booked in the ERP
-- general ledger, for every month and channel, within the documented tolerance (Part 4, section 4: 0.5 %).
-- A month that exists on only one side counts as zero on the other. Any row returned here is a month
-- and channel that does not reconcile.

select *
from {{ ref('fct_sales_reconciliation') }}
where abs(net_revenue - erp_revenue) > {{ var('reconciliation_tolerance') }} * abs(erp_revenue)

# Multi-channel retail urbanization

An urbanization study for a multi-channel retailer, applied to Le Slip Français: it chooses a target data platform that brings seven siloed sources together for sales performance, customer segmentation and inventory optimization, and proves the choice with a proof of concept on synthetic data.

The business terms behind every report figure (with their owners) are defined in [`governance/glossary.csv`](governance/glossary.csv); it wins over this file if the two ever disagree. This file holds the words of the study and the words to avoid.

## Language

### The study

**Brief**:
The two-page assignment the study answers ("Case 6: Urbanization, Datamart / Datalake"). It names the retailer only as "a retail company".
_Avoid_: Spec, assignment

**Part**:
One written deliverable of the study, numbered 0 to 6 (Part 0 is the company profile, Part 6 governance and GDPR).
_Avoid_: Chapter, section, doc

**Use case**:
One of the three business needs of the brief: Sales Performance, Customer Segmentation, Inventory Optimization. Delivered one at a time, in that order.
_Avoid_: Project, feature

**Story**:
A numbered user story of the spec (story 1 to 44), cited as "story 17".
_Avoid_: Requirement, ticket

**Proof of concept (PoC)**:
The local, zero-cost version of the chosen platform, running on synthetic data.
_Avoid_: Demo, prototype, POC in capitals (reads like POS)

**Assumption**:
A figure the public sources do not give, chosen by us and labelled as ours in the text.
_Avoid_: Estimate (when it is not computed), hypothesis

### Architecture

**Datamart**:
An architecture option: a small database built for one department, organized in ready-to-use tables.
_Avoid_: Mart (that is a group of report tables in the chosen platform)

**Lakehouse**:
The chosen architecture option: one central store where data is kept raw, then cleaned and organized in layers that serve every department.
_Avoid_: Data lake (which has no structured layers), data warehouse

**Source**:
One of the seven tools of the brief whose data the platform collects: ERP, CRM, POS, E-commerce, Web analytics, Social media, Customer support.
_Avoid_: System, feed, connector

**Raw layer**:
The data of each source exactly as received, plus when and from which file it was loaded.
_Avoid_: Bronze, landing

**Staging**:
One cleaned table per source table: English names, real types, local formats parsed, no personal contact data.
_Avoid_: Silver, cleaned layer

**Mart**:
A group of report tables for one business domain: Sales, Customer, Inventory, Marketing, Support. Business users and dashboards read only marts.
_Avoid_: Gold, datamart, report

**Freshness**:
How late a source's newest data is against its own refresh schedule.
_Avoid_: Latency, staleness

**Reconciliation**:
The check that a mart figure matches the figure finance books in the ERP, within a stated tolerance.
_Avoid_: Validation, audit

### Sales

**Channel**:
Where a sale happens: Web, Store or Wholesale.
_Avoid_: Online, e-commerce, retail, marketplace (as channel names)

**Location**:
A physical place that holds stock or sells: the warehouse/factory or one of the two own stores. Wholesale customers are not locations.
_Avoid_: Site, shop, store (when the warehouse is meant)

**Order**:
A confirmed purchase: a Shopify order, a store ticket or a wholesale order. A cancelled order is not an order.
_Avoid_: Transaction, sale, basket

**Order line**:
One SKU and its quantity inside an order.
_Avoid_: Item, line item

**Return**:
An order line sent back, counted on the day the refund happens, not the day of the sale.
_Avoid_: Refund (the money side only), cancellation

**Click and collect**:
A Web order collected in a store: it stays in the Web channel, and its location is that store.
_Avoid_: In-store pickup, omnichannel order

**Net revenue**:
The reference sales figure: after discounts and returns, excluding VAT and shipping.
_Avoid_: Revenue, sales, turnover, CA

**Margin**:
Net revenue minus the production cost of the units sold.
_Avoid_: Profit, gross margin

**Average basket**:
Net revenue divided by the number of orders over a period.
_Avoid_: AOV, average order value, average ticket

**Wholesale account**:
A company that buys to resell, such as one Carrefour hypermarket. It is not a person.
_Avoid_: Reseller, B2B customer, client

### Products and stock

**SKU**:
One product in one size and one colour, with the same code in Shopify, the tills and the ERP.
_Avoid_: Article, reference, variant

**Product**:
A model sold in several sizes and colours; groups SKUs.
_Avoid_: Style, item

**Snapshot date**:
The day a stock level was recorded.
_Avoid_: Stock date, inventory date

**Demand**:
Units of a SKU sold in the 28 days before the snapshot date, in all channels, counted at the location the units leave from.
_Avoid_: Sales (for units), consumption, forecast

**Stock cover**:
How many days the stock on hand lasts at the current demand.
_Avoid_: Days of inventory, DOH, coverage

**Stockout** / **Stockout risk** / **Overstock** / **Slow mover**:
The four stock flags of a SKU at a location: no stock while it sells; stock left but under 14 days of cover; over 180 days of cover; stock left that sold nothing in 28 days. A slow mover is never an overstock.
_Avoid_: Out of stock, dead stock, excess stock

### Customers

**Customer**:
A person with at least one Web or Store order, as one source tool knows them. The same person is several customers before matching.
_Avoid_: Account, user, client, buyer

**Golden customer**:
The single record of one real person after matching the customers of every source.
_Avoid_: Single customer view (that is the goal, not the record), master customer, unified profile

**Customer key**:
The pseudonymous identifier of a golden customer, and the only customer identifier allowed in the marts.
_Avoid_: Customer id, customer number

**Marketing consent**:
Whether a person may receive marketing messages. A withdrawal always wins.
_Avoid_: Opt-in, subscription

### Governance

**Treatment**:
What happens to a personal-data field before it reaches the marts: keep, pseudonymize, generalize, restrict or drop.
_Avoid_: Masking, anonymization (unless the data truly cannot be linked back)

**Owner**:
The person, by role, who decides when a glossary term changes.
_Avoid_: Steward (a different role in the RACI), responsible

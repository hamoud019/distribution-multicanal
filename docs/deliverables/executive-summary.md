# Executive summary

*Case 6: Urbanization, Datamart / Datalake (multi-channel distribution)*

**The question.** A retailer selling in stores, online and to resellers keeps its data in seven tools that do not talk to each other. Each service builds its own reports in Excel, the numbers disagree, and nobody sees all channels together. The brief asks which data architecture to build, cloud or on-premise, with which tools, in which order, at what cost, and how to bring the teams along.

**The company.** We applied the case to **Le Slip Français**: 21.1 M€ of revenue in 2025, 72 % of it online, two own stores and about a hundred Carrefour hypermarkets [1]; more than 850,000 customers [1] and 69 employees [2]; its own factories. Its seven sources are Business Central (ERP, assumed), Klaviyo (CRM), the store tills, Shopify Plus, Google Analytics 4, three social networks and Zendesk ([Part 0](00-company-profile.md)).

**Our answer.** Build a **cloud lakehouse on Microsoft Fabric, in an EU region, one use case at a time**: sales performance first, then inventory optimization, then customer segmentation. Fivetran loads the sources, dbt turns them into business tables, Power BI shows them. It is the best option on the brief's criteria and the cheapest over three years, but it only pays back if it **improves stock decisions**.

## 1. The choice ([Part 1](01-architecture-options.md))

| Option | Score / 100 | Cost over 3 years ([Part 3](03-costing.md)) |
|---|:-:|---:|
| **④ Lakehouse, cloud** | **87** | **235 k€** |
| ② Datamart, cloud | 72 | 243 k€ |
| ① Datamart, on-premise | 57 | 334 k€ |
| ③ Lakehouse, on-premise | 50 | 534 k€ |

- **Why a lakehouse:** the brief wants all seven sources for three use cases. One datamart per department would rebuild the silos, keep several copies of customer data, and load the same sales data three times.
- **Why cloud:** no servers to buy or run, and an EU region for the GDPR. Cloud beats on-premise under every weighting we tried.
- **Speed is kept** by delivering one use case at a time. If speed were the only goal, the cloud datamart would win, but by 1 point only (83 against 82).
- **Why Fabric:** it connects directly to Business Central and to Power BI (84/100, ahead of Snowflake 79 and BigQuery 77). **If the ERP is SAP Business One, this advantage disappears**: then ask Snowflake, BigQuery and Microsoft for quotes.
- **The single customer view is built inside the lakehouse**, not bought (no Segment): one copy of customer data is easier to protect.

## 2. What it costs and what it must bring ([Part 3](03-costing.md))

- **235 k€ over 3 years**: 79 k€ to build (110 consultant days, training) and 156 k€ to run. The platform itself (Fabric, storage, Fivetran) is only about 26 k€; **79 % of the cost is people**, mostly half of an internal data engineer.
- Today, preparing reports by hand costs about 0.6 of an analyst, 39 k€ a year (our estimate). **Time savings alone never pay for the platform.**
- The real benefit is better stock decisions. Stock-outs and overstock cost retailers about 6.5 % of sales [3], about 1.37 M€ a year here. **The project pays back if it removes about 7.2 % of these losses, about 98 k€ a year.** This is possible for a manufacturer that plans production without seeing all channels' demand, but it is not certain: it is the main financial risk (R12).
- The ranking holds when staff costs, build days or data volumes move by 50 % either way.

## 3. The order and the plan ([Part 1](01-architecture-options.md) §9, [Part 4](04-transformation-plan.md))

**Sales performance first** (95/100): its data is clean, it needs no customer matching and many people use it. **Inventory second** (83): the biggest financial impact, no personal data, and it reuses the sales already loaded. **Customer segmentation last** (58): it needs the single customer view and an impact assessment (DPIA), the hardest work.

| Phase | Dates | Delivers | Go/no-go gate |
|---|---|---|---|
| 0. Foundations | Jan–Mar 2027 | Fabric in the EU, access rules, glossary, data engineer in post | Glossary signed, engineer hired |
| 1. Sales performance | Apr–Dec 2027 | Store, web and wholesale sales in one report; 3 years of history; daily stock snapshots | Sales match the ERP within 0.5 % for two month-end closes |
| 2. Inventory | Jan–Jun 2028 | Stock cover, sell-through, stock-out and overstock lists | Supply chain uses them every week; compared with a baseline |
| 3. Customer segmentation | Sep 2028–Jun 2029 | Golden customer, segments with consent, campaign results | 90 % of customers matched; erasure tested end to end |
| 4. Hand-over | Jul–Dec 2029 | Support, web and social reports moved; the internal team runs alone | Every old report retired |

Old reports keep running next to the new ones until the numbers match; **nothing is switched off before its replacement is proven**.

## 4. The risks ([Part 2](02-swot-risks.md))

The solution's strengths are technical and financial; its weaknesses are human. **Four of the five biggest risks are about people and data, not technology:**

| Risk | Score / 25 | Answer |
|---|:-:|---|
| R01. Teams keep their Excel reports | 20 | Every old report mapped to its replacement and retired on a date set by management; one data champion per department |
| R02. Customers cannot be matched across tools | 16 | Matching rules from phase 1; segmentation waits for a 90 % match rate |
| R03. Everything depends on one engineer | 16 | Hired before the build, paired with the consultant, a trained back-up |
| R12. The inventory benefit does not come | 16 | Stock-outs and overstock measured before phase 2, then every month |
| R05. GDPR: consent, retention, erasure | 15 | Impact assessment before segmentation, consent carried to the segments, retention periods, erasure in every layer |

## 5. People and rules ([Part 5](05-change-management.md), [Part 6](06-governance-gdpr.md))

- **Change management:** 13 old channel reports, each with its replacement, live date and retirement date. One data champion per service, Power BI training (PL-300) for the 5 report creators, workshops for the 20 readers, a communication calendar, and adoption figures followed every quarter (target: 80 % of trained users active, then 90 %).
- **Governance:** one glossary of 72 business terms, each with an owner, so "net revenue" or "customer" means the same thing everywhere. Matching rules for the single customer view, exact only: a wrong merge is worse for the GDPR than a missed one.
- **GDPR:** names, emails and phones never reach the reports, only a pseudonymous customer key. Marketing targets only customers with consent. Every dataset has a retention period, and an erasure request reaches every layer within the one-month legal deadline. Access is given by role: nobody in the business sees personal data in the platform.

## 6. The proof of concept ([poc/README.md](../../poc/README.md))

The recommendation runs on a laptop, at zero cost, with **synthetic data**: a 1 % sample of Le Slip Français's activity over 2023–2025, generated to match its public figures, with the real problems of each tool (other customer ids in each tool, messy emails, French formats, prices with VAT). One command builds the seven sources, the raw layer and every business table, then builds and tests them: 196 dbt models and tests. It shows that:

- **sales reconcile with finance**: the gap with the ERP general ledger is a few cents a month, far inside the 0.5 % tolerance;
- **the single customer view works**: 96 % of the Klaviyo profiles of people who ordered online are matched, above the 90 % gate, with no wrong merge, and a family sharing one phone is not merged;
- **stock follows all channels**, with stock-outs, overstock and slow movers flagged;
- **campaigns, web traffic (with consent only), social media and support** sit in the same model as sales;
- **the GDPR rules hold**: no email or phone reaches a report table, an erased customer disappears from every layer while the sales totals stay the same, and retention deletes what is too old;
- a **sales dashboard** shows revenue, margin, units and basket by channel, store, category and month, against last year.

The proof of concept is checked by 94 automated tests, and the study's figures by 118 more.

## 7. What we ask the steering committee

1. **Approve the budget**: 235 k€ over 2027–2029, plus a 15 % contingency (about 35 k€).
2. **Confirm the ERP** at kick-off: Business Central, or quotes from three platforms if it is SAP Business One.
3. **Start hiring the data engineer now**, so they are in post by March 2027, before the build.
4. **Agree the thresholds we chose ourselves**: the 0.5 % reconciliation tolerance, the adoption targets, the retirement dates of the old reports.
5. **Judge the project on inventory**: the stock baseline starts in July 2027, and each gate reviews it.

## 8. Limits

The costs use public list prices, not quotes. The volumes, consultant days, number of report users and the ERP are our assumptions, explained in each Part. The proof of concept uses synthetic data only; the real tools and the real data were never connected.

## Sources

Checked on 26 September 2026. Every other figure comes from Parts 0 to 6, with their own sources.

1. PEA.fr, *IPO Le Slip Français* (2025 figures from the IPO documents: revenue, channel split, customers): https://pea.fr/analyses/ipo-le-slip-francais/
2. Wikipédia, *Le Slip français* (employees): https://fr.wikipedia.org/wiki/Le_Slip_fran%C3%A7ais
3. IHL Group, inventory distortion 2025 (stock-outs and overstock = 6.5 % of retail sales): https://www.ihlservices.com/news/analyst-corner/2025/09/retail-inventory-crisis-persists-despite-172-billion-in-improvements/

# Part 2: SWOT and risk assessment

*Case 6: Urbanization, Datamart / Datalake (multi-channel distribution)*

The brief asks for a **"SWOT of the proposed solution, and risk assessment"**. The proposed solution is the one chosen in [Part 1](01-architecture-options.md): a **cloud lakehouse on Microsoft Fabric**, built one use case at a time (sales → inventory → segmentation), with Fivetran, dbt and Power BI. The costs come from [Part 3](03-costing.md).

## 1. SWOT

In a SWOT, **strengths** and **weaknesses** are about the solution itself (internal). **Opportunities** and **threats** come from outside: the market, the vendors, the law and the people.

| | Positive | Negative |
|---|---|---|
| **Internal** | **Strengths** | **Weaknesses** |
| | **S1. One place for the 7 sources.** Store and online sales finally sit in the same tables, so the company can compare channels and build the single customer view the brief asks for. | **W1. It depends on people.** 73 % of the 3-year cost is staff and consultants (Part 3, §5), and the platform relies on 0.5 of an internal data engineer. |
| | **S2. The cheapest option over 3 years.** 257 k€, against 267 k€ for the cloud datamart and 402–567 k€ on-premise (Part 3, §3). The platform itself costs only about 15 k€. | **W2. Fabric is young.** Some features are still in preview, and the dbt adapter for the Fabric lakehouse is not generally available yet [1]. |
| | **S3. It fits the company's tools.** Business Central connects directly to Fabric [2], and Power BI feels familiar to teams who work in Excel. | **W3. It does not pay for itself on time savings alone.** It must also improve inventory decisions (about 2.3 % of inventory losses, Part 3, §4). |
| | **S4. Value arrives step by step.** The first sales reports arrive in year 1, and each new use case reuses the data already loaded. | **W4. No true real-time.** POS data is loaded in small batches, not instantly, although the brief describes POS as "real-time". This is enough for our three use cases but not for live store replenishment. |
| | **S5. Not locked in.** Data is stored in the open Delta format [3] and transformations are plain SQL in dbt, so they could move to another platform. | **W5. The choice depends on the ERP.** If the ERP is SAP Business One and not Business Central, Fabric loses its main advantage (Part 1, §7). |
| **External** | **Opportunities** | **Threats** |
| | **O1. Inventory losses are large.** Stock-outs and overstock cost retailers about 6.5 % of sales [4], around 3.9 M€ a year for our assumed retailer. Recovering a small part of this pays for the whole project. | **T1. Vendor price increases.** Power BI Pro went from $10 to $14 per user in April 2025 (+40 %) [5], and Fivetran changed how it bills in 2025 and 2026 [6]. |
| | **O2. Cross-channel marketing.** With CRM, e-commerce and store loyalty data together, marketing can target customers who buy in store *and* online, and measure campaigns on real sales. | **T2. GDPR sanctions.** Processing customer or tracking data without a legal basis can be fined up to 20 M€ or 4 % of worldwide turnover [7]. |
| | **O3. Better customer service.** Support agents can see a customer's purchases next to their Zendesk/Freshdesk tickets and spot products with recurring problems. | **T3. Resistance to change.** The brief itself warns that teams resist giving up their channel-specific reports. |
| | **O4. Future projects on the same data.** Demand forecasting or recommendations could be built later without a new platform. | **T4. Poor source data.** Bad data quality costs organizations $12.9 M a year on average (Gartner) [8]. Our result is only as good as the data in the 7 source systems. |
| | | **T5. Scarce skills.** Experienced data engineers are paid 46–65 k€ gross a year in France [9], and a small retailer competes with bigger companies to hire them. |

### What we learn from the SWOT

- The **strengths are mostly technical and financial**: the solution is cheap, fits the existing tools and is not locked in.
- The **weaknesses and threats are mostly human**: people and skills (W1, T5), resistance (T3) and data quality (T4). So the biggest risks are not about technology. This is why the risk register below puts adoption and data quality first.
- The **main opportunity (O1) is also the condition for success (W3)**: the project only pays back if the inventory use case really improves stock decisions.

## 2. Risk register

### How we score

- **Likelihood**, from 1 (rare) to 5 (almost certain).
- **Impact**, from 1 (small) to 5 (the project fails or the company is sanctioned).
- **Score** = likelihood × impact, from 1 to 25.

When two risks have the same score, the one with the higher **impact** comes first, because a serious risk matters more than a frequent one.

Each risk has an **owner**: the person who watches it and acts if it happens. Owners come from the services listed in the brief (Sales/Store, Marketing, E-commerce, Customer service, Supply chain/Purchasing, IT), plus general management, the CFO, the DPO, the HR/training manager and the data engineer.

### The register

| # | Category | Risk | L | I | **Score** | Mitigation | Owner |
|---|---|---|:-:|:-:|:-:|---|---|
| R01 | Adoption | Teams keep their own channel reports in Excel and don't use the new platform, so the silos stay | 4 | 5 | **20** | Map every channel report to the Power BI report that replaces it, then retire them one by one on dates set by management; one data champion per department | General management |
| R02 | Data quality | Customers can't be matched reliably across POS loyalty, e-commerce, CRM and support, so the single customer view and the segments are wrong | 4 | 4 | **16** | Matching rules and data stewards defined in phase 1; match rate measured with dbt tests; segmentation only starts when the target is reached | Marketing director |
| R03 | Skills | Everything depends on 0.5 of an internal data engineer; if that person leaves, nobody can maintain the pipelines | 4 | 4 | **16** | Recruit or train the engineer **before** the build and pair them with the consultant; all logic documented in dbt; a trained back-up person | IT manager |
| R05 | GDPR | Customer or web-tracking data processed without valid consent, or kept too long | 3 | 5 | **15** | Impact assessment (DPIA) before segmentation; raw layer restricted to IT; consent flag carried to the customer tables; retention periods; erasure procedure; EU region only | DPO |
| R12 | Budget | The expected benefit doesn't arrive: inventory must recover about 2.3 % of inventory losses | 3 | 4 | **12** | Measure stock-outs and overstock **before** phase 2 as a baseline; follow them monthly; review at each phase gate | Supply chain director |
| R04 | Budget | Building takes more consultant days than we estimated | 4 | 3 | **12** | Fixed scope and a go/no-go gate per use case; a 15 % contingency (about 39 k€, on top of the 257 k€ of Part 3). Part 3 shows +50 % build days adds about 33 k€ and does not change the choice | CFO |
| R09 | Data quality | Sources refresh at different times (POS during the day, ERP once a day), so reports disagree and users lose trust | 4 | 3 | **12** | Show the last refresh time on every report; one business glossary; reconcile sales with ERP finance figures | CFO |
| R07 | Technical | Some Fabric features are still in preview; the lakehouse dbt adapter is not generally available [1] | 3 | 3 | **9** | Use the Fabric Warehouse with its supported dbt adapter; no preview features in production | Data engineer |
| R08 | Technical | Store network problems: POS data from some of the 30 stores arrives late or incomplete | 3 | 3 | **9** | Small batches with retries; freshness tests per store; daily reconciliation with ERP totals | IT manager |
| R10 | Adoption | Business users lack the skills for self-service analytics | 3 | 3 | **9** | PL-300 training for creators, workshops for readers, help sessions with the data champions | HR / training manager |
| R06 | Vendor | Vendors raise their prices (Power BI +40 % in 2025 [5]; Fivetran pricing changes [6]) | 4 | 2 | **8** | 1-year reservations and annual contracts; dbt keeps the logic portable; Airbyte as back-up for Fivetran | IT manager |
| R11 | Vendor | The ERP is SAP Business One, so Fabric loses its main advantage | 2 | 3 | **6** | Confirm the ERP at kick-off; if it is SAP B1, ask Snowflake, BigQuery and Microsoft for quotes | IT manager |

The register covers all the categories we were asked to consider: technical (R07, R08), data quality (R02, R09), GDPR (R05), budget (R04, R12), skills (R03), adoption (R01, R10) and vendor (R06, R11).

### Heat map

| Impact ↓ / Likelihood → | 1 rare | 2 unlikely | 3 possible | 4 likely | 5 almost certain |
|---|---|---|---|---|---|
| **5 critical** | | | R05 | **R01** | |
| **4 major** | | | R12 | R02, R03 | |
| **3 moderate** | | R11 | R07, R08, R10 | R04, R09 | |
| **2 minor** | | | | R06 | |
| **1 small** | | | | | |

Most risks sit in the "possible / likely" columns with moderate to major impact. None is almost certain, and none is small enough to ignore.

## 3. The top 5 risks and where they are handled

The five highest-scoring risks must have a concrete action in the next two parts of our work: the **transformation plan** (Part 4) and the **change management plan** (Part 5).

| Rank | Risk | Score | Mitigation id | Must appear in |
|---|---|:-:|---|---|
| 1 | R01: teams keep their channel reports | 20 | **M-CHG-1**: report replacement map + retirement dates + data champions | Part 5 (change management) |
| 2 | R02: customers can't be matched | 16 | **M-TRF-2**: matching rules and stewards in phase 1; match-rate gate before segmentation | Part 4 (transformation plan) |
| 3 | R03: dependence on one engineer | 16 | **M-TRF-3**: hire or train before the build, pairing, back-up person | Part 4 (transformation plan) + Part 5 (training) |
| 4 | R05: GDPR | 15 | **M-TRF-5**: DPIA, restricted raw layer, consent, retention, erasure | Part 4 (transformation plan) |
| 5 | R12: inventory benefit doesn't arrive | 12 | **M-TRF-12**: baseline before phase 2, monthly follow-up, gate reviews | Part 4 (transformation plan) |

Note that **four of the five top risks are about people and data, not technology**. This confirms what the SWOT showed: the success of the project depends more on change management and governance than on the choice of tool.

### How we will follow the risks

- The register is reviewed at **each phase gate** (after each use case). Scores are updated, and new risks are added.
- Each owner reports on their risk at the **monthly steering committee**.
- A risk whose score goes up to 15 or more gets an action plan with a date.

The register is kept in `analysis/risk_register.csv`, which also gives the mitigation id and the plan (Part 4 or Part 5) for every risk, not only the top 5. `python analysis/risks.py` prints it sorted by score.

## Sources

Checked on 26 September 2026.

1. Microsoft Fabric Community, *dbt + Microsoft Fabric* (Warehouse adapter available; Lakehouse adapter "coming soon"): https://community.fabric.microsoft.com/blog/fbc_fabricupdatesblogs/dbt-microsoft-fabric-a-strategic-investment-in-the-modern-analytics-stack/5172139
2. Microsoft Learn, *Introduction to Microsoft Fabric and Business Central*: https://learn.microsoft.com/en-us/dynamics365/business-central/admin-fabric
3. Microsoft Learn, *What is data warehousing in Microsoft Fabric?* (data stored in Delta tables): https://learn.microsoft.com/en-us/fabric/data-warehouse/data-warehousing
4. IHL Group, inventory distortion 2025 (6.5 % of retail sales): https://www.ihlservices.com/news/analyst-corner/2025/09/retail-inventory-crisis-persists-despite-172-billion-in-improvements/
5. Microsoft, *Important update to Microsoft Power BI pricing* (Pro from $10 to $14 from 1 April 2025): https://powerbi.microsoft.com/en-us/blog/important-update-to-microsoft-power-bi-pricing/. The page was not readable for us; the figures are confirmed by The Register: https://www.theregister.com/2025/04/02/microsoft_power_bi_hikes/
6. Fivetran documentation, *Usage-based pricing updates* 2025 and 2026: https://fivetran.com/docs/core-concepts/usage-based-pricing/pricing-updates/2025-pricing-faq and https://fivetran.com/docs/core-concepts/usage-based-pricing/pricing-updates/2026-pricing-updates
7. GDPR, Article 83(5) (fines up to 20 M€ or 4 % of worldwide annual turnover): https://gdpr-info.eu/art-83-gdpr/
8. Gartner, *Data quality: why it matters* (poor data quality costs organizations $12.9 M a year on average): https://www.gartner.com/en/data-analytics/topics/data-quality
9. Data engineer salaries in France 2026 (Jedha): https://www.jedha.co/formation-data/salaire-data-engineer

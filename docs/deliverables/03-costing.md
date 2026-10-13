# Part 3: Full costing

*Case 6: Urbanization, Datamart / Datalake (multi-channel distribution)*

The brief asks for a **"full costing (investment + operating cost) compared to the current situation, cited sources or quotes obtained"**. In this part we cost the four options from [Part 1](01-architecture-options.md) over **3 years** and compare them with what the company spends today.

All the figures are in the files in `analysis/`:

- `cost_lines.csv`: every cost line (price, quantity per year, source);
- `cost_sources.csv`: every source, with the figure taken and the date we checked it;
- `costing.py`: the calculation. Run `python analysis/costing.py` to recompute every table in this part.

All amounts are in euros. US-dollar prices are converted at the ECB rate of **1 EUR = 1.1403 USD** (25 September 2026) [S-ECB].

## 1. Method

For each option we count three kinds of cost:

| Category | What it contains |
|---|---|
| **Investment** | servers and licences bought once, consultant days to build, training |
| **Operating (run)** | cloud subscriptions, ETL, Power BI licences, internal staff |
| **Remaining manual work** | report preparation that analysts still do by hand |

**TCO** (total cost of ownership) = investment + operating over 3 years. We use it to compare the options with each other. To compare with **today**, we also add the manual work that remains, because the main saving of a data platform is less manual work.

Same assumptions as in Part 1: **Le Slip Français**, with 21.1 M€ of revenue, 69 employees, a website, 2 stores and wholesale to Carrefour; much less than 1 TB of data; 25 Power BI users (5 creators); a small IT team; and a company in France (so French salaries and prices).

### Prices we use

| What | Price | Source |
|---|---|---|
| Internal data engineer | 55,000 € gross/year + 45 % employer charges = **79,750 €/year** | [S-SAL-DE], [S-CHARGES] |
| Data analyst | 45,000 € gross/year + 45 % = **65,250 €/year** | [S-SAL-DA], [S-CHARGES] |
| Consultant (freelance data engineer) | **600 €/day** | [S-TJM] |
| Server Dell PowerEdge R660 | $23,299 (≈ 20,432 €) | [S-DELL] |
| SQL Server 2022 Standard | $3,945 per 2 cores (we need 8 cores = $15,780) | [S-SQL] |
| Windows Server 2025 Standard | $1,176 per 16 cores | [S-WS] |
| Microsoft Fabric capacity | $1,146 per capacity unit per year (1-year reservation, West Europe); F2 = 2 units, F4 = 4 | [S-FABRIC] |
| OneLake storage | $0.024 per GB per month | [S-FABRIC] |
| Fivetran | $500 per million rows changed per month (MAR) + $5 per connection per month | [S-FIVETRAN] |
| Airbyte Core | free (open source, we host it) | [S-AIRBYTE] |
| dbt Core | free (open source) | [S-DBT] |
| Power BI Pro | $14 per user per month = $168/year | [S-PBI] |
| Power BI training PL-300 (3 days) | 2,390 € per person | [S-PL300] |

### How much data we load

Fivetran charges for the rows that change each month (MAR). We estimated them from the yearly volumes of Part 0, §4. **These are our own estimates** (`analysis/fivetran_rows.csv`):

| Source | Rows changed per month | How we estimate it |
|---|---:|---|
| E-commerce (Shopify) | ≈ 120,000 | ≈ 20,000 orders a month × about 6 rows each (order, 2 lines on average, payment, shipment, customer) |
| POS | ≈ 10,000 | ≈ 2,500 tickets a month × about 4 rows each |
| CRM (Klaviyo) | ≈ 3,200,000 | email events: about 300,000 subscribed profiles (35 % of the 850,000 customers, assumption) × 8 campaigns a month (Part 0) = 2.4 million "received" events, plus 0.72 million opens (30 %, assumption) and 0.05 million clicks; plus about 30,000 profile changes |
| Customer support (Zendesk) | ≈ 7,000 | ≈ 1,000 tickets a month with their comments |
| Web analytics, social media | ≈ 3,000 | daily totals only (Part 6) |

That makes about **0.13 million** rows a month for the sales sources and **3.34 million** for all sources. The CRM is by far the biggest, because every email received or opened is a new row. We did not count automated emails (Klaviyo flows), so this may still be low. The ERP is not loaded through Fivetran: Business Central has its own link to Fabric (Part 1, §7).

Storage stays very small: about 50 GB in year 1, growing to about 130 GB in year 3 for the lakehouse, including history and the copies kept by each layer. We **assume** that one Fabric **F2** capacity, the smallest, is enough for this size during the 3 years: there are few users and the data is small. This is not tested. If the Capacity Metrics app shows that it is too small, we move to F4 (Part 4, §7), which adds about 2,000 € a year.

## 2. The current situation

Today there is no central platform. Each department builds its own reports by exporting data from its tools into Excel. The brief lists **6 impacted services** (Sales/Store, Marketing, E-commerce, Customer service, Supply chain/Purchasing, IT). We assume:

- in each of the 6 services, **a quarter of one person's time** goes into reporting. With 69 employees, each service is a small team, so reporting is a smaller job than in a big retailer (our assumption);
- about **40 %** of reporting time is spent getting data ready: exporting, cleaning, reconciling. The Anaconda survey measured 39–45 % for data professionals [S-ANACONDA].

So the current situation costs 6 × 0.25 × 40 % = **0.6 of a full-time analyst** = 0.6 × 65,250 € = **39,150 € per year**, or **117,450 € over 3 years**. We assume there is no dedicated reporting server or BI licence today: reports are made in Excel and in the built-in dashboards of each tool (ERP, CRM, Shopify, Zendesk…). These are already paid for and are kept in every option, so no existing licence or server can be retired, and we don't count them on either side.

## 3. What each option costs

| Option | Investment | Operating | **TCO 3 years** | Remaining manual work | Total vs today |
|---|---:|---:|---:|---:|---:|
| ① Datamart on-premise | 131,852 | 202,450 | **334,302** | 78,300 | +295,152 |
| ② Datamart cloud | 84,550 | 158,651 | **243,201** | 78,300 | +204,051 |
| ③ Lakehouse on-premise | 164,447 | 369,925 | **534,372** | 97,875 | +514,797 |
| ④ Lakehouse cloud | 79,150 | 156,241 | **235,391** | 78,300 | +196,241 |

(€, over 3 years. "Total vs today" = TCO + remaining manual work − 117,450 €.)

### Why the options differ

- **Build effort.** A datamart serves one department, so to cover the 3 use cases we build **three datamarts**, one per year. Each one integrates its sources again: 40 consultant days per datamart on-premise, 35 in the cloud. The lakehouse integrates each source once and reuses it, so 30 days per use case, plus 15 days of platform setup at the start. These day counts are **our own estimates**; §6 tests what happens if they are wrong. They did not change when we resized the study for Le Slip Français: the work depends on the number of sources (7) and use cases (3), not on the number of rows or stores.
- **Migration of old data.** The reports need history (for example last year's sales to compare with). The lakehouse loads 3 years of POS and ERP history **once** (5 consultant days). Each datamart has to load its own history again (3 days per datamart). Fivetran does not charge for the first full copy of a source [S-FIVETRAN].
- **Servers.** The on-premise datamart needs one server with SQL Server and Windows Server licences; our data is small enough for one server to hold the three datamarts. The on-premise lakehouse needs a cluster of **3 servers** from the start: its storage keeps 3 copies of every block by default [S-HDFS], so that the data survives when one machine fails. For our small data this cluster is far too big, but it is the minimum for this kind of platform; its software (Linux, Apache Spark, Airbyte) is open source and free.
- **Staff.** In the cloud, the provider runs the servers, so we count **0.5** internal data engineer to look after the pipelines. We kept this share for Le Slip Français: the pipelines, tests and access rules are the same work for 7 sources whatever the company's size, and less than half a person could not also be the back-up of R03 (Part 2). On-premise we count **0.8** for the datamart (servers + pipelines) and **1.5** for the lakehouse (cluster administration + Spark, skills the team doesn't have today).
- **Duplicated data in the cloud datamart.** Each new datamart loads the sales data again, so Fivetran and storage costs grow faster than with the lakehouse, where data is stored once.
- **Manual work.** When a use case goes live, its reports no longer need to be prepared by hand. We assume manual work falls by half once all three use cases are live: to 0.5 of a full-time analyst in year 1, 0.4 in year 2 and 0.3 in year 3. The on-premise lakehouse delivers its first use case one year later, because the cluster has to be installed first, so its manual work falls later (0.6 → 0.5 → 0.4).

### Detail of our choice: ④ Lakehouse cloud

| Line | Calculation | 3 years (€) |
|---|---|---:|
| Platform setup | 15 days × 600 € | 9,000 |
| Building the 3 use cases | 3 × 30 days × 600 € | 54,000 |
| Migration: loading 3 years of history | 5 days × 600 € | 3,000 |
| Power BI PL-300 training | 5 creators × 2,390 € | 11,950 |
| Workshops for report readers | 2 days × 600 € | 1,200 |
| **Investment** | | **79,150** |
| Fabric capacity | F2 for 3 years: 6 capacity units × $1,146 | 6,030 |
| OneLake storage | 3,200 GB-months × $0.024 | 67 |
| Fivetran rows | 43.2 million MAR-months × $500 | 18,942 |
| Fivetran connections | 120 connection-months × $5 | 526 |
| Power BI Pro | 25 users × 3 years × $168 | 11,050 |
| dbt Core | open source | 0 |
| Internal data engineer | 0.5 × 3 years × 79,750 € | 119,625 |
| **Operating** | | **156,241** |
| **TCO 3 years** | | **235,391** |

What stands out: **the platform itself is cheap** (Fabric + storage + Fivetran ≈ 25,600 € in 3 years). Fivetran costs three times as much as Fabric, and 93 % of its rows cost comes in year 3, when the CRM is loaded. Loading Klaviyo with Airbyte (our back-up tool, free if we host it, Part 1 §8) would save about 17,000 €, but the data engineer would then have to host and maintain it. **People make up 79 % of the cost:** the internal engineer is 51 % and the consultants 28 %.

### Year by year (including remaining manual work)

| € per year | Year 1 | Year 2 | Year 3 |
|---|---:|---:|---:|
| Today | 39,150 | 39,150 | 39,150 |
| ① Datamart on-premise | 180,360 | 119,383 | 112,858 |
| ② Datamart cloud | 117,945 | 96,080 | 107,475 |
| ③ Lakehouse on-premise | 284,905 | 176,933 | 170,408 |
| ④ Lakehouse cloud | 122,145 | **90,479** | **101,067** |

The cloud datamart is slightly cheaper in year 1 because it needs less setup. From year 2 the lakehouse is cheaper, because it reuses what was already built. Year 3 costs more than year 2 for both cloud options, because the CRM data is loaded.

## 4. Is it worth it? (payback)

**With time savings only, no option pays for itself in 3 years.** Every option costs more than today (last column of §3). This is expected: saving at most 0.3 of a full-time analyst (≈ 20,000 €/year once all three use cases are live) cannot pay for a platform, licences and an engineer.

The real benefit expected in the brief is **better decisions**, especially **inventory optimization**. According to IHL Group, stock-outs and overstocks ("inventory distortion") cost retailers about **6.5 % of their sales** [S-IHL]. For Le Slip Français's revenue of 21.1 M€ [S-LSF], that is about **1.37 M€ per year**.

Inventory optimization is our second use case (Part 1, §9), so it helps in years 2 and 3, except for the on-premise lakehouse, where everything arrives a year later (year 3 only). To pay back the extra cost, the option must remove this share of the inventory losses while it is live:

| Option | Extra cost over 3 years | Share of inventory losses to recover each year it is live |
|---|---:|---:|
| ① Datamart on-premise | 295,152 € | 10.8 % |
| ② Datamart cloud | 204,051 € | 7.4 % |
| ③ Lakehouse on-premise | 514,797 € | 37.5 % (year 3 only) |
| ④ Lakehouse cloud | 196,241 € | **7.2 %** |

For our choice (④), the project pays for itself within 3 years if it **recovers about 7.2 % of the inventory losses**, roughly 98,000 € per year. **This is not certain.** It is a much bigger share than for a large retailer, because the platform and the engineer cost almost the same for a small company as for a big one, while the losses to recover are smaller. We still think it is possible: Le Slip Français makes its own products in many sizes and colours for three channels, and today it plans production without seeing all channels' demand together, which is exactly what the inventory use case fixes. But this is the main financial risk of the project (R12 in Part 2), and the plan measures it from the start (Part 4). Better campaign targeting (segmentation) would be an additional benefit, but we did not count it.

## 5. The two biggest cost drivers

Share of each option's TCO:

| Option | Internal staff | Consultant days (build) | Servers & licences | Power BI users | Data volume |
|---|---:|---:|---:|---:|---:|
| ① Datamart on-premise | 57 % | 25 % | 11 % | 3 % | 0 % |
| ② Datamart cloud | 49 % | 29 % | 0 % | 5 % | 11 % |
| ③ Lakehouse on-premise | 67 % | 17 % | 11 % | 2 % | 0 % |
| ④ Lakehouse cloud | 51 % | 28 % | 0 % | 5 % | 11 % |

(The rest is training, workshops and Fivetran connections.)

The two biggest drivers are **internal staff** and **build days**. Data volume, which one might expect to matter most for a data platform, is only 11 %, and almost all of it is the Fivetran cost of the CRM email events.

## 6. Sensitivity

We changed each driver by −50 % and +50 % and recalculated the TCO:

| TCO 3 years (k€) | ① Datamart on-prem | ② Datamart cloud | ③ Lakehouse on-prem | ④ Lakehouse cloud |
|---|---:|---:|---:|---:|
| Base | 334 | 243 | 534 | **235** |
| Staff −50 % / +50 % | 239 / 430 | 183 / 303 | 355 / 714 | **176 / 295** |
| Build days −50 % / +50 % | 293 / 376 | 208 / 279 | 489 / 579 | **202 / 268** |
| Both −50 % / +50 % | 197 / 472 | 148 / 339 | 310 / 759 | **143 / 328** |
| Power BI users × 2 (50) | 345 | 254 | 545 | **246** |
| Data volume −50 % / +50 % | 334 / 334 | 230 / 257 | 534 / 534 | **223 / 248** |

**In every case, ④ Lakehouse cloud stays the cheapest**, and the two on-premise options stay the most expensive. The gap between ④ and ② is small (about 8,000 €), but it always favours the lakehouse.

Two thresholds to remember:

- **Power BI users.** Below the F64 Fabric capacity, each reader needs a Pro licence. F64 costs about 64 × $1,146 ≈ $73,000/year, which is only worth it above about 440 readers (Part 1, §8). We are far from that.
- **Data volume.** The volume-driven lines of option ④ (Fabric capacity, storage, Fivetran rows) cost about 25,000 € over 3 years, so doubling the data adds about 25,000 €. This is a simplification: Fabric capacity is bought in steps (F2, F4, F8…), so the real cost grows in jumps, not smoothly. The biggest uncertainty is the CRM: if Le Slip Français has more email subscribers or sends more emails than we assume, Fivetran costs more in year 3. It would change the ranking only if the cloud datamart loaded the CRM more cheaply, and it does not: both options load it once.

## 7. Feeding the costs back into Part 1

Part 1 used cost as a criterion (weight 20). We score it from the TCO: the cheapest option gets 5, the most expensive gets 1, and the others fall in proportion.

| | ① Datamart on-prem | ② Datamart cloud | ③ Lakehouse on-prem | ④ Lakehouse cloud |
|---|:-:|:-:|:-:|:-:|
| Cost score in our first version (imaginary 60 M€ retailer) | 3 | 5 | 1 | 5 |
| **Cost score for Le Slip Français** | **4** | **5** | **1** | **5** |
| Part 1 total (our weighting) | 57 | 72 | 50 | **87** |

Our first version of this study used an imaginary retailer of about 30 stores and 60 M€. Resized for Le Slip Français, every option is cheaper, and the on-premise datamart moves closer to the cloud options (it needs only one server). The ranking does not change: the cloud lakehouse stays our choice with 87 points. With the "speed first" weighting, the cloud datamart still wins by only 1 point (83 against 82).

## 8. Limits

- **The build days and the staff shares (0.5 / 0.8 / 1.5) are our estimates**, not quotes. §6 shows that the ranking does not change even if they are 50 % wrong.
- **The on-premise options are probably underestimated.** We did not count electricity, server-room space, backups, hardware support contracts or Software Assurance on licences. Adding them would make on-premise even more expensive, so our conclusion stays the same.
- **Some prices come from US price lists** (Dell, Microsoft) converted to euros. The real price in France, with a reseller discount, may be different. A real project would ask for quotes.
- **The benefits are assumptions:** 0.6 of a full-time analyst spent on data preparation today and half of it saved; the inventory losses use the retail average of 6.5 % [S-IHL] applied to Le Slip Français's revenue. The payback calculation in §4 shows how much benefit is *needed* rather than claiming how much we will get.
- **The data volumes are our estimates** from the public figures (§1). The CRM volume depends on two assumptions (subscribed profiles and open rate), and it is the largest one.

## Sources

The full list, with the figure taken from each source, is in `analysis/cost_sources.csv`. All were checked on 26 September 2026.

| Id | Source |
|---|---|
| S-ECB | European Central Bank, EUR/USD reference rate: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-usd.en.html |
| S-SAL-DE | Data engineer salary France 2026 (Jedha): https://www.jedha.co/formation-data/salaire-data-engineer |
| S-SAL-DA | Data analyst salary France 2026 (Top Métiers): https://www.top-metiers.fr/salaire-primes-data-analyst |
| S-CHARGES | Employer charges in France 2026 (Dougs): https://www.dougs.fr/blog/charges-patronales/ |
| S-ANACONDA | Anaconda, State of Data Science: https://www.anaconda.com/resources/whitepaper/state-of-data-science-2020 |
| S-TJM | Freelance tech daily rates 2026 (Blog du Modérateur): https://www.blogdumoderateur.com/freelance-tech-taux-journaliers-moyens-metier-2026/ |
| S-DELL | Dell PowerEdge R660: https://www.dell.com/en-us/shop/dell-poweredge-servers/poweredge-r660-rack-server/spd/poweredge-r660/pe_r660_tm_vi_vp_sb |
| S-SQL | SQL Server 2022 licensing (Redmondmag): https://redmondmag.com/articles/2022/11/16/sql-server-2022-every-licensing.aspx |
| S-WS | Windows Server 2025 pricing: https://www.microsoft.com/en-us/windows-server/pricing |
| S-AIRBYTE | Airbyte pricing: https://airbyte.com/pricing |
| S-PBI | Power BI pricing: https://www.microsoft.com/en-us/power-platform/products/power-bi/pricing |
| S-FABRIC | Azure Retail Prices API, Microsoft Fabric, West Europe: `https://prices.azure.com/api/retail/prices?$filter=serviceName eq 'Microsoft Fabric' and armRegionName eq 'westeurope'` |
| S-FIVETRAN | Fivetran pricing: https://www.fivetran.com/pricing |
| S-PL300 | PLB, Power BI PL-300 course: https://www.plb.fr/formation/power-bi-analyse |
| S-DBT | dbt Core (open source, Apache 2.0): https://github.com/dbt-labs/dbt-core |
| S-LSF | PEA.fr, *IPO Le Slip Français* (revenue 2025: 21.1 M€): https://pea.fr/analyses/ipo-le-slip-francais/ |
| S-HDFS | Apache Hadoop, *hdfs-default.xml* (`dfs.replication` = 3, checked on 13 October 2026): https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/hdfs-default.xml |
| S-IHL | IHL Group, inventory distortion 2025: https://www.ihlservices.com/news/analyst-corner/2025/09/retail-inventory-crisis-persists-despite-172-billion-in-improvements/ |

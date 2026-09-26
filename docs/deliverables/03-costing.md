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

Same assumptions as in Part 1: about 30 stores + a webshop, less than 1 TB of data, 70 Power BI users (10 creators), a small IT team, and a company in France (so French salaries and prices).

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

To price Fivetran we estimated the rows changed per month for our assumed size: about 170,000 for POS (2 million sales lines a year), 60,000 for e-commerce, 30,000 for CRM, 20,000 for web analytics, 10,000 for support and 5,000 for social media. That makes about **0.23 million** for the sales sources and **0.30 million** for all sources. The ERP is not loaded through Fivetran: Business Central has its own link to Fabric (Part 1, §7).

## 2. The current situation

Today there is no central platform. Each department builds its own reports by exporting data from its tools into Excel. The brief lists **6 impacted services** (Sales/Store, Marketing, E-commerce, Customer service, Supply chain/Purchasing, IT). We assume:

- in each of the 6 services, **half of one person's time** goes into reporting;
- about **40 %** of reporting time is spent getting data ready: exporting, cleaning, reconciling. The Anaconda survey measured 39–45 % for data professionals [S-ANACONDA].

So the current situation costs 6 × 0.5 × 40 % = **1.2 full-time analysts** = 1.2 × 65,250 € = **78,300 € per year**, or **234,900 € over 3 years**. We assume there is no dedicated reporting server or BI licence today: reports are made in Excel and in the built-in dashboards of each tool (ERP, CRM, Shopify, Zendesk…). These are already paid for and are kept in every option, so no existing licence or server can be retired, and we don't count them on either side.

## 3. What each option costs

| Option | Investment | Operating | **TCO 3 years** | Remaining manual work | Total vs today |
|---|---:|---:|---:|---:|---:|
| ① Datamart on-premise | 179,704 | 222,339 | **402,043** | 156,600 | +323,743 |
| ② Datamart cloud | 97,100 | 169,742 | **266,842** | 156,600 | +188,542 |
| ③ Lakehouse on-premise | 176,997 | 389,814 | **566,811** | 195,750 | +527,661 |
| ④ Lakehouse cloud | 91,700 | 165,543 | **257,243** | 156,600 | +178,943 |

(€, over 3 years. "Total vs today" = TCO + remaining manual work − 234,900 €.)

### Why the options differ

- **Build effort.** A datamart serves one department, so to cover the 3 use cases we build **three datamarts**, one per year. Each one integrates its sources again: 40 consultant days per datamart on-premise, 35 in the cloud. The lakehouse integrates each source once and reuses it, so 30 days per use case, plus 15 days of platform setup at the start. These day counts are **our own estimates**; §6 tests what happens if they are wrong.
- **Migration of old data.** The reports need history (for example last year's sales to compare with). The lakehouse loads 3 years of POS and ERP history **once** (5 consultant days). Each datamart has to load its own history again (3 days per datamart). Fivetran does not charge for the first full copy of a source [S-FIVETRAN].
- **Servers.** The on-premise datamart needs one server the first year and a second one for the next datamarts, each with SQL Server and Windows Server licences. The on-premise lakehouse needs a cluster of **3 servers** from the start; its software (Linux, Apache Spark, Airbyte) is open source and free.
- **Staff.** In the cloud, the provider runs the servers, so we count **0.5** internal data engineer to look after the pipelines. On-premise we count **0.8** for the datamart (servers + pipelines) and **1.5** for the lakehouse (cluster administration + Spark, skills the team doesn't have today).
- **Duplicated data in the cloud datamart.** Each new datamart loads the sales data again, so Fivetran and storage costs grow faster than with the lakehouse, where data is stored once.
- **Manual work.** When a use case goes live, its reports no longer need to be prepared by hand. We assume manual work falls by half once all three use cases are live: to 1.0 full-time analyst in year 1, 0.8 in year 2 and 0.6 in year 3. The on-premise lakehouse delivers its first use case one year later, because the cluster has to be installed first, so its manual work falls later (1.2 → 1.0 → 0.8).

### Detail of our choice: ④ Lakehouse cloud

| Line | Calculation | 3 years (€) |
|---|---|---:|
| Platform setup | 15 days × 600 € | 9,000 |
| Building the 3 use cases | 3 × 30 days × 600 € | 54,000 |
| Migration: loading 3 years of history | 5 days × 600 € | 3,000 |
| Power BI PL-300 training | 10 creators × 2,390 € | 23,900 |
| Workshops for report readers | 3 days × 600 € | 1,800 |
| **Investment** | | **91,700** |
| Fabric capacity | F2 in year 1, F4 in years 2–3: 10 capacity units × $1,146 | 10,050 |
| OneLake storage | 19,200 GB-months × $0.024 | 404 |
| Fivetran rows | 9.12 million MAR-months × $500 | 3,999 |
| Fivetran connections | 120 connection-months × $5 | 526 |
| Power BI Pro | 70 users × 3 years × $168 | 30,939 |
| dbt Core | open source | 0 |
| Internal data engineer | 0.5 × 3 years × 79,750 € | 119,625 |
| **Operating** | | **165,543** |
| **TCO 3 years** | | **257,243** |

What stands out: **the platform itself is cheap** (Fabric + storage + Fivetran ≈ 15,000 € in 3 years). **People make up almost three-quarters of the cost:** the internal engineer is 47 % and the consultants 26 %.

### Year by year (including remaining manual work)

| € per year | Year 1 | Year 2 | Year 3 |
|---|---:|---:|---:|
| Today | 78,300 | 78,300 | 78,300 |
| ① Datamart on-premise | 232,165 | 187,415 | 139,063 |
| ② Datamart cloud | 170,339 | 132,041 | 121,062 |
| ③ Lakehouse on-premise | 343,235 | 216,188 | 203,138 |
| ④ Lakehouse cloud | 174,539 | **125,850** | **113,454** |

The cloud datamart is slightly cheaper in year 1 because it needs less setup. From year 2 the lakehouse is cheaper, because it reuses what was already built.

## 4. Is it worth it? (payback)

**With time savings only, no option pays for itself in 3 years.** Every option costs more than today (last column of §3). This is expected: saving at most 0.6 of a full-time analyst (≈ 39,000 €/year once all three use cases are live) cannot pay for a platform, licences and an engineer.

The real benefit expected in the brief is **better decisions**, especially **inventory optimization**. According to IHL Group, stock-outs and overstocks ("inventory distortion") cost retailers about **6.5 % of their sales** [S-IHL]. For an assumed revenue of 60 M€ (about 30 stores + webshop, our assumption), that is **3.9 M€ per year**.

Inventory optimization is our second use case (Part 1, §9), so it helps in years 2 and 3, except for the on-premise lakehouse, where everything arrives a year later (year 3 only). To pay back the extra cost, the option must remove this share of the inventory losses while it is live:

| Option | Extra cost over 3 years | Share of inventory losses to recover each year it is live |
|---|---:|---:|
| ① Datamart on-premise | 323,743 € | 4.2 % |
| ② Datamart cloud | 188,542 € | 2.4 % |
| ③ Lakehouse on-premise | 527,661 € | 13.5 % (year 3 only) |
| ④ Lakehouse cloud | 178,943 € | **2.3 %** |

For our choice (④), it is enough to **recover about 2.3 % of the inventory losses**, roughly 89,000 € per year, for the project to pay for itself within 3 years. We think this is realistic, because today the company manages stock without seeing online demand, and the inventory use case is built exactly for this. Better campaign targeting (segmentation) would be an additional benefit, but we did not count it.

## 5. The two biggest cost drivers

Share of each option's TCO:

| Option | Internal staff | Consultant days (build) | Servers & licences | Power BI users | Data volume |
|---|---:|---:|---:|---:|---:|
| ① Datamart on-premise | 48 % | 21 % | 18 % | 8 % | 0 % |
| ② Datamart cloud | 45 % | 27 % | 0 % | 12 % | 7 % |
| ③ Lakehouse on-premise | 63 % | 16 % | 11 % | 5 % | 0 % |
| ④ Lakehouse cloud | 47 % | 26 % | 0 % | 12 % | 6 % |

(The rest is training, workshops and Fivetran connections.)

The two biggest drivers are **internal staff** and **build days**. Data volume, which one might expect to matter most for a data platform, is below 10 %, because our data volume is small.

## 6. Sensitivity

We changed each driver by −50 % and +50 % and recalculated the TCO:

| TCO 3 years (k€) | ① Datamart on-prem | ② Datamart cloud | ③ Lakehouse on-prem | ④ Lakehouse cloud |
|---|---:|---:|---:|---:|
| Base | 402 | 267 | 567 | **257** |
| Staff −50 % / +50 % | 306 / 498 | 207 / 327 | 387 / 746 | **197 / 317** |
| Build days −50 % / +50 % | 360 / 444 | 231 / 303 | 522 / 612 | **224 / 290** |
| Both −50 % / +50 % | 265 / 539 | 171 / 362 | 342 / 791 | **164 / 350** |
| Power BI users × 2 (140) | 433 | 298 | 598 | **288** |
| Data volume −50 % / +50 % | 402 / 402 | 258 / 276 | 567 / 567 | **250 / 264** |

**In every case, ④ Lakehouse cloud stays the cheapest or equal cheapest**, and the two on-premise options stay the most expensive. The gap between ④ and ② is small (about 10,000 €), but it always favours the lakehouse.

Two thresholds to remember:

- **Power BI users.** Below the F64 Fabric capacity, each reader needs a Pro licence. F64 costs about 64 × $1,146 ≈ $73,000/year, which is only worth it above about 440 readers (Part 1, §8). We are far from that.
- **Data volume.** The volume-driven lines of option ④ (Fabric capacity, storage, Fivetran rows) cost about 14,500 € over 3 years, so doubling the data adds about 14,500 €. This is a simplification: Fabric capacity is bought in steps (F2, F4, F8…), so the real cost grows in jumps, not smoothly. Data volume only becomes a major cost at around ten times our size (≈ +130,000 €), and then the whole sizing would need to be redone.

## 7. Feeding the costs back into Part 1

Part 1 used cost as a criterion (weight 20). We now replace our first guesses with the TCO: the cheapest option gets 5, the most expensive gets 1, and the others fall in proportion.

| | ① Datamart on-prem | ② Datamart cloud | ③ Lakehouse on-prem | ④ Lakehouse cloud |
|---|:-:|:-:|:-:|:-:|
| Cost score before (Part 1 guess) | 2 | 5 | 1 | 4 |
| **Cost score from TCO** | **3** | **5** | **1** | **5** |
| Part 1 total (our weighting) | 53 | 72 | 50 | **87** |

With the real costs, the cloud lakehouse gets a better score (from 83 to 87), and it stays our choice. With the "speed first" weighting, the cloud datamart now wins by only 1 point (83 against 82).

## 8. Limits

- **The build days and the staff shares (0.5 / 0.8 / 1.5) are our estimates**, not quotes. §6 shows that the ranking does not change even if they are 50 % wrong.
- **The on-premise options are probably underestimated.** We did not count electricity, server-room space, backups, hardware support contracts or Software Assurance on licences. Adding them would make on-premise even more expensive, so our conclusion stays the same.
- **Some prices come from US price lists** (Dell, Microsoft) converted to euros. The real price in France, with a reseller discount, may be different. A real project would ask for quotes.
- **The benefits are assumptions:** 1.2 full-time analysts spent on data preparation today, half of it saved, and a 60 M€ revenue. The payback calculation in §4 shows how much benefit is *needed* rather than claiming how much we will get.

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
| S-IHL | IHL Group, inventory distortion 2025: https://www.ihlservices.com/news/analyst-corner/2025/09/retail-inventory-crisis-persists-despite-172-billion-in-improvements/ |

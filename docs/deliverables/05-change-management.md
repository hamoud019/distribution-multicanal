# Part 5: Change management plan

*Case 6: Urbanization, Datamart / Datalake (multi-channel distribution)*

The brief asks for a **"change management plan: training, communication, resistance management, long-term anchoring"**. It also names the main difficulty: **"training merchandising/marketing/sales teams on self-service analytics, managing resistance to giving up channel-specific reporting habits"**.

This part explains how the teams of [Le Slip Français](00-company-profile.md) move from their own Excel files to the shared Power BI reports of the new platform. It follows the dates of the transformation plan ([Part 4](04-transformation-plan.md)), the budget of [Part 3](03-costing.md) and the roles of [Part 6](06-governance-gdpr.md).

The stakeholders, the report replacement map, the training sessions, the communication calendar and the KPIs are kept in `analysis/change_*.csv`. `python analysis/change.py` prints every table of this part, and `analysis/test_change.py` checks that they stay consistent with Parts 3, 4 and 6.

## 1. Why this part matters

The technology is the easy part. The risk register of [Part 2](02-swot-risks.md) shows it:

- The **highest risk of the whole project is R01** (score 20): teams keep their own channel reports in Excel and never really use the platform, so the silos stay.
- **Four of the five top risks are about people and data**, not technology.
- The project only pays back if **stock decisions really change** (R12): about 7.2 % of inventory losses must be recovered (Part 3, §4). A report nobody opens recovers nothing.

The brief talks about "merchandising" teams. At Le Slip Français, the people who decide which products, sizes and colours to make and push are in **supply chain / purchasing** (the production plan) and **e-commerce** (the website, 72–88 % of sales). We treat them as the merchandising teams.

Our plan follows the brief: who is affected (§2), what replaces each old report (§3), the champions (§4), training (§5), communication (§6), resistance (§7), and how we measure and keep adoption (§8).

## 2. Stakeholders and impact

The brief lists six impacted services. We add general management and finance, because they set the retirement dates and pay for the project.

| Department | Who | What changes | Impact | Main concern | Data champion |
|---|---|---|:-:|---|---|
| Sales / Store | Sales director, the 2 store managers, wholesale account managers | Store, web and wholesale sales in one report instead of three Excel files; store managers see their store next to the others | high | "My numbers will not match the new ones"; store managers have little time and are not at a desk | The service's report creator (one sales team member) |
| Marketing | Marketing director, CRM manager, social media manager | Campaign results and target lists come from the platform, not from Klaviyo and Shopify exports; consent rules decide who can be targeted | high | "GDPR will stop us from targeting"; loss of the freedom to export customer lists | The service's report creator (the CRM manager) |
| E-commerce | E-commerce director and team | Web sales and web traffic in the same model as stores and wholesale; Shopify and GA4 exports stop | high | "Shopify already gives me my figures"; the website is most of the revenue, so this team watches its figures every day | The service's report creator (one e-commerce team member) |
| Customer service | Customer service manager, team leader, agents | Ticket figures by product and channel come from the platform; agents keep working in Zendesk | medium | "One more tool to learn"; the support dashboard is built by hand today and the team is used to it | The service's report creator (the team leader) |
| Supply chain / Purchasing | Supply chain director, production planner, the two factories | Stock, production and sales of all channels in one place; the planning spreadsheets stop | high | "The spreadsheet knows things the system does not" (sizes, factory capacity); fear of losing control of the production plan | The service's report creator (the production planner) |
| IT | IT manager, internal data engineer, back-up person | A new platform to run, with tests, monitoring and access reviews; no more exports made for other teams | high | Workload on a small team; dependence on one engineer (R03) | The back-up data engineer |
| General management and finance | Chief executive (sponsor), CFO | Decide the retirement dates and follow the adoption figures; one management report for all channels | medium | "Will the project pay back?" (Part 3, §4) | (the sponsor) |

What we learn from the map:

- **Four business services are highly affected:** Sales / Store, E-commerce, Supply chain / Purchasing and Marketing (IT is too, because it runs the platform). Each one has a phase in which it changes the most (phase 1, 1, 2 and 3), so we never ask everyone to change at the same time.
- **Supply chain gives up the most reports (4 of the 13, §3)**, and these spreadsheets drive the production plan, so they are retired last in their phase, after the stock pages have been checked.
- **Store managers are not at a desk**, so they get the mobile app and a short remote session (§5).
- **Supply chain is where the money is**: the payback depends on its decisions (R12), so it gets its own phase and its own champion.

## 3. Report replacement map (M-CHG-1)

This is the main answer to R01 and to the brief's "resistance to giving up channel-specific reporting habits": **nobody is asked to give up a report until its replacement exists and has been checked**. For every old report, the map gives the Power BI report that replaces it, the date it goes live, and the date it is retired.

| # | Old report | Department | Replaced by | Phase | Live | Retired on | Signed by |
|---|---|---|---|:-:|---|---|---|
| L01 | Weekly web sales (Excel from Shopify exports) | E-commerce | Sales report, Web page (`fct_sales`) | 1 | 30 Jul 2027 | 8 Oct 2027 | CFO |
| L02 | Daily store sales (Excel from the tills) | Sales / Store | Sales report, Stores page (`fct_sales`) | 1 | 30 Jul 2027 | 15 Oct 2027 | CFO |
| L03 | Wholesale sales by hypermarket (Excel from the ERP) | Sales / Store | Sales report, Wholesale page (`fct_sales`) | 1 | 30 Jul 2027 | 22 Oct 2027 | CFO |
| L04 | Monthly revenue by channel for management (Excel merging the three files above) | General management and finance | Sales report, Overview page (`fct_sales`) | 1 | 30 Jul 2027 | 29 Oct 2027 | CFO |
| L05 | Best-sellers by product, size and colour (Excel) | Supply chain / Purchasing | Sales report, Products page (`dim_product`) | 1 | 30 Jul 2027 | 29 Oct 2027 | CFO |
| L06 | Stock by location (ERP export) | Supply chain / Purchasing | Inventory report, Stock page (`fct_stock_snapshot`) | 2 | 31 Mar 2028 | 9 Jun 2028 | Supply chain director |
| L07 | Production plan by size and colour (spreadsheet) | Supply chain / Purchasing | Inventory report, Production page (`fct_production`) | 2 | 31 Mar 2028 | 30 Jun 2028 | Supply chain director |
| L08 | Stock-out and overstock watch list (spreadsheet) | Supply chain / Purchasing | Inventory report, Alerts page (`fct_stock_snapshot`) | 2 | 31 Mar 2028 | 16 Jun 2028 | Supply chain director |
| L09 | Campaign results (Excel from Klaviyo and Shopify) | Marketing | Marketing report, Campaigns page (`fct_campaign`) | 3 | 30 Mar 2029 | 15 Jun 2029 | Marketing director |
| L10 | Target lists built by hand from Shopify customer exports | Marketing | Customer report, Segments page (`dim_customer`) | 3 | 30 Mar 2029 | 29 Jun 2029 | Marketing director |
| L11 | Support dashboard built by hand (Zendesk export) | Customer service | Support report (`fct_ticket`) | 4 | 31 Jul 2029 | 12 Oct 2029 | Customer service manager |
| L12 | Weekly web traffic and conversion (GA4 export) | E-commerce | Marketing report, Web page (`fct_web_daily`) | 4 | 31 Jul 2029 | 19 Oct 2029 | Marketing director |
| L13 | Monthly social media figures (copied by hand from each platform) | Marketing | Marketing report, Social page (`fct_social_daily`) | 4 | 31 Jul 2029 | 26 Oct 2029 | Marketing director |

How the map works:

- **The dates are set by general management**, at the workshop with each department head in February 2027 (§6), as mitigation M-CHG-1 requires. Reports are retired **one by one**, not all on the same day.
- **Every replacement exists in the planned report tables** of Part 6 (`marts.csv`), shown in brackets. A test checks it.
- **The data owner of the replacement signs the retirement** (the RACI of Part 6): the CFO for sales, the supply chain director for inventory, the marketing director for customers and marketing, the customer service manager for support. A test checks this too.
- **A report is retired only after two full months of parallel run, plus one week** to close the books of the second month and compare the figures (the week is our assumption). It also needs the four conditions of Part 4, §6: the replacement exists, the numbers match for two month-end closes, the owner signs, and the users are trained. A test checks that no date in the map comes earlier than this, or later than the dates of Part 4. To leave room for this, the inventory and the customer reports go live at the end of March (Part 4).
- **The built-in dashboards of the tools are kept** (Shopify, Klaviyo, Zendesk, the ERP): teams use them for daily work, not for cross-channel reporting.
- **Retiring L10 is also good for the GDPR**: hand-made target lists are copies of customer data in Excel files. After June 2029, marketing builds its targets in the platform, where consent is applied.
- **The list of old reports is our assumption.** We built it from the silos of Part 1 (§10) and the reports of Part 4 (§6). In phase 0 (January–February 2027), each champion checks it with their department and adds the reports we missed.

## 4. The data champions

Mitigation M-CHG-1 asks for **one data champion per department**. Each business service has one: its **report creator**, trained on Power BI (§5). For IT, the champion is the **back-up data engineer**.

What a champion does:

- **builds and changes the pages** of their department's report, so the department does not wait for IT;
- **gives first-level help** to colleagues, and runs the short training sessions after phase 1;
- **tests the new report during the parallel run** and tells the data engineer when numbers do not match;
- **brings the department's new needs** to the data engineer and the data governance committee (Part 4, §7);
- **meets the other champions and the data engineer one hour a month**.

How we choose and support them:

- Each department head proposes a **volunteer** who already likes working with figures, and the sponsor confirms them in March 2027.
- We estimate their time at about **half a day a week during their department's phase**, then about **two hours a month**. This is **our assumption**, and it is internal time, not counted in Part 3.
- They are **recognized**: the PL-300 course, their name in the internal newsletter, and the role written in their yearly objectives.

## 5. Training plan (M-CHG-2 and M-TRF-3)

People are trained **just before they need it**: each group is trained in the weeks before its report goes live, so they use what they learned the next day.

| Group | People | Format | Duration | When | Trainer |
|---|---:|---|---|---|---|
| Report creators, one per business service (sales and stores, marketing, e-commerce, customer service, merchandising in supply chain); they are also the data champions | 5 | PL-300 Power BI course, then building the first sales pages with the consultant | 3 days + 2 days of practice | 12 Apr 2027 to 25 Jun 2027 | PLB (course) and the consultant |
| IT manager (administration of the platform) | 1 | Learns with the consultant during the platform setup: access by role, usage metrics, capacity metrics | about 1 day spread over phase 0 | 1 Feb 2027 to 26 Mar 2027 | The consultant (inside the setup days of Part 3) |
| Management team (sponsor, CFO, directors) | 8 | Briefing: how to read the overview page and how retirement decisions are taken | 1 hour | 12 Jul 2027 to 16 Jul 2027 | IT manager and the consultant |
| Sales report readers: sales and stores, e-commerce, supply chain and finance | 15 | Hands-on workshop in groups of 4 to 5 on the report of their own department | 2 hours per group | 5 Jul 2027 to 23 Jul 2027 | The consultant with the champion of each department |
| The 2 store managers (part of the sales report readers) | 2 | Remote session on the Stores page and the Power BI mobile app | 1 hour | 19 Jul 2027 to 23 Jul 2027 | Sales / Store champion |
| Back-up data engineer (one IT team member) | 1 | Works next to the data engineer one day a week; follows the run book, makes one deployment and handles one failed freshness check | 1 day a week for 3 months | 1 Sep 2027 to 30 Nov 2027 | Internal data engineer |
| Merchandising readers: supply chain, production planning and sales (inventory report) | 10 | Short session on the new inventory pages | 1 hour | 13 Mar 2028 to 29 Mar 2028 | Supply chain champion |
| Marketing and customer service readers (customer and marketing reports); 5 of them use Power BI for the first time | 10 | Session on the customer and marketing pages, and on who may be targeted (consent) | 1.5 hours | 5 Mar 2029 to 27 Mar 2029 | Marketing champion and the DPO |
| Customer service and e-commerce readers (support and web pages) | 8 | Short session on the last pages to move | 1 hour | 16 Jul 2029 to 27 Jul 2029 | Champions |

How the training plan matches the rest of our work:

- **It is the budget of Part 3:** 5 PL-300 courses (5 × 2,390 € = 11,950 €) and 2 consultant days of workshops for the readers (1,200 €). The 5 creators and 20 readers (15 trained in 2027 and 5 in 2029) are the **25 Power BI users** costed in Part 3. A test checks these numbers.
- **Each group learns its own report**: in 2027 only the sales report exists, so only its readers are trained then. Marketing and customer service readers are trained in 2029, when their reports arrive.
- **The later sessions are given by the champions**, so they cost internal time only.
- **The back-up data engineer** (mitigation M-TRF-3, training part) is trained by the internal data engineer from September to November 2027, before the date of Part 4 (30 Nov 2027). After this, two people know how to run the platform.
- **The IT manager** learns to administer the platform (access by role, usage and capacity figures) with the consultant during the platform setup, so IT is trained as a group too, as the spec asks.
- **The DPO and the CRM manager** learn the erasure procedure during the erasure test of Part 4 (May 2029). This is part of the GDPR work of Part 6, so it is not in the table.
- **The group sizes** (8 managers, 10 readers for inventory, and so on) are **our estimates**.
- **New employees** get a one-hour introduction to the reports from their department's champion when they arrive, and every user gets a short **yearly refresher** when the reports change.

## 6. Communication plan

### Key messages

The same four messages come back in every communication:

1. **One set of figures for all channels.** Store, web and wholesale sales finally match, so meetings discuss decisions, not whose number is right.
2. **Less copying, more deciding.** The time spent exporting and cleaning Excel files (Part 3, §2) goes to analysis.
3. **Your daily tools do not change.** Shopify, Klaviyo, Zendesk and the ERP stay; only the cross-channel reports move.
4. **Nothing disappears before its replacement is proven**, and the dates are known in advance (§3).

### Calendar

| Date | Phase | Audience | Key message | Channel | From |
|---|:-:|---|---|---|---|
| 4 Jan 2027 | 0 | All staff | Why: one set of figures for all channels and less time copying Excel files. What: five phases over three years. What does not change: the tools used every day (Shopify, Klaviyo, Zendesk, the ERP) | All-staff meeting | Chief executive (sponsor) |
| 26 Feb 2027 | 0 | Department heads | The report replacement map: which of your reports is replaced, by what, and on which date; the role of your data champion | One workshop per department | Chief executive (sponsor) and IT manager |
| 19 Mar 2027 | 0 | All staff | Who the data champions are and how to reach them | Internal newsletter | Chief executive (sponsor) |
| 30 Jul 2027 | 1 | Sales / Store, E-commerce, Supply chain, management | The sales report is live; the old reports keep running until October; where to ask for help | Email and a demo in each team meeting | Sales director and CFO |
| 27 Aug 2027 | 1 | Owners of reports L01 to L05 | Each old sales report retires on its date in October, after the August and September closes | Email from the sponsor and a reminder from the champion | Chief executive (sponsor) |
| 29 Oct 2027 | 1 | All staff | Old sales reports retired; first figures on use of the new report | Internal newsletter | Chief executive (sponsor) |
| 17 Dec 2027 | 1 | All staff | Gate 1: what the sales step delivered, the inventory baseline, what comes next | All-staff meeting | Chief executive (sponsor) |
| 31 Mar 2028 | 2 | Supply chain / Purchasing, Sales / Store | The inventory report is live; the spreadsheets keep running until June | Demo in the supply chain meeting | Supply chain director |
| 5 May 2028 | 2 | Owners of reports L06 to L08 | The stock and production spreadsheets retire one by one in June, on the dates of the report map | Email | Chief executive (sponsor) |
| 30 Jun 2028 | 2 | All staff | Gate 2: stock-outs and overstock compared with the baseline | Internal newsletter | Chief executive (sponsor) and supply chain director |
| 4 Sep 2028 | 3 | Marketing, Customer service, E-commerce | What the customer view will allow and what it will not: consent rules, no names in reports, why the impact assessment (DPIA) comes first | Workshop | DPO and marketing director |
| 30 Mar 2029 | 3 | Marketing, E-commerce, Customer service | Customer and marketing reports are live; segments respect consent | Demo | Marketing director |
| 11 May 2029 | 3 | Owners of reports L09 and L10 | Campaign spreadsheets and hand-made target lists retire in June, on the dates of the report map; Shopify customer exports for targeting stop | Email | Chief executive (sponsor) |
| 29 Jun 2029 | 3 | All staff | Gate 3: the consultant leaves and the internal team takes over | All-staff meeting | Chief executive (sponsor) |
| 2 Jul 2029 | 4 | Customer service, E-commerce, Marketing | The last reports to move and their dates | Email | IT manager |
| 31 Jul 2029 | 4 | Customer service, E-commerce, Marketing | Support, web and social pages are live | Demo by the champions | Data champions |
| 31 Aug 2029 | 4 | Owners of reports L11 to L13 | The last channel reports retire in October, on the dates of the report map | Email | Chief executive (sponsor) |
| 26 Oct 2029 | 4 | All staff | Every channel report retired; adoption figures; thanks to the champions | All-staff meeting | Chief executive (sponsor) |

Rules of the calendar (checked by tests):

- **Every go-live is announced on the day**, with a demo in the team meeting.
- **Every retirement is announced at least four weeks before** the first old report of its phase is retired.
- **The sponsor speaks in every phase.** When the chief executive says the old reports stop, people believe it.

### Regular channels

Besides the dated messages above:

- a short **"data corner" in the monthly internal newsletter**, written by the champions (a tip, a new page, a figure);
- **one place to ask questions** (a shared mailbox or a chat channel), answered by the champions, then by the data engineer;
- **the last refresh time on every report page** (Part 4, M-TRF-9), so nobody wonders whether the figures are up to date.

We do not know Le Slip Français's internal channels, so the newsletter, the all-staff meetings and the chat channel are **our assumptions**.

## 7. Managing resistance

The brief warns about "resistance to giving up channel-specific reporting habits". These are the objections we expect, and our answer to each:

| Objection we expect | Who | Our answer |
|---|---|---|
| "My Excel file gives the right numbers; the new report is wrong." | Every service | The parallel run (§3): both run side by side for two month-ends, every difference is explained in the reconciliation log (Part 4, §4), and the definitions come from one glossary (Part 6). |
| "Shopify (or Zendesk, or the ERP) already gives me my figures." | E-commerce, customer service | You keep them for daily work. The new report adds what your tool cannot show: the other channels, and the link with stock and customers. |
| "I don't have time to learn a new tool." | Store managers, customer service | Sessions of one or two hours, just before go-live, plus the champion next to you. Store managers get the mobile app. |
| "The spreadsheet knows things the system does not." | Supply chain | The production planner is the champion: what the spreadsheet knows (sizes, factory capacity) is added to the inventory report before the spreadsheet is retired. |
| "GDPR will stop us from targeting customers." | Marketing | The DPO explains the rules in September 2028, before anything changes. Customers who gave consent, or who bought similar products, can still be targeted (Part 6, §4); the platform makes this safer, not impossible. |
| "Reporting is my job; what do I do now?" | People who build the Excel files today | You become the champion or a report creator, and spend the time on analysis instead of copying. |
| "This is one more IT project that will be dropped." | Everyone | The first report arrives in July 2027, in the first year; the sponsor follows every gate, and each phase must succeed before the next one starts (Part 4). |
| "The figures are late." | Sales / Store | Each report shows its last refresh time; sales from the website and the stores are loaded every 15 minutes (Part 4, §5). |

**When someone still refuses:** the champion talks to them first, then their department head. An old report is kept after its date **only if the sponsor decides it**, with a new date and a reason. This way the exception stays rare and visible.

**Watching for "shadow Excel":** exporting from Power BI to Excel for a one-off analysis is fine. Rebuilding an old report by hand from exports is not. The champions watch for this, and the usage figures (§8) show which reports are never opened.

## 8. Adoption KPIs and long-term anchoring

### KPIs

| KPI | Definition | Target | Measured with | How often | Owner |
|---|---|---|---|---|---|
| Active users | Share of the users trained so far (25 Power BI users once all are trained, in 2029) who opened at least one report in the last 30 days | 80 % (20 people) at the end of each parallel run, then 90 % after the project | Power BI usage metrics (unique viewers) | Every month | Data engineer |
| Report usage | Views of each replacement report by its department | Every replacement report is opened at least once a week by its department | Power BI usage metrics (report views) | Every month | Data champions |
| Old reports retired | Old reports retired on their date out of the 13 old reports of the map | 100 % on the dates of the map | Report replacement map (this part) | At each gate | Chief executive (sponsor) |
| Training done | People trained before their go-live out of the people planned | All 5 report creators; at least 90 % of the readers | Training register | At each go-live | HR / training manager |
| Satisfaction | Average answer, from 1 to 5, to "The reports help me do my job" in a three-question survey | At least 4 out of 5 | Short survey | Every quarter | HR / training manager |

The targets are **our own choices**, to be agreed with the sponsor in phase 0. Active users are counted among the people trained so far, because marketing and customer service readers only start in 2029.

**How usage is measured.** Power BI's usage metrics report shows, for each report, how many times it was opened and by how many different people, over **the last 30 days** [1]. Only 30 days are kept, so the data engineer exports the figures every month to keep the history [1]. The report can show the names of viewers, but the administrator can hide them [1]. We only report **counts**, so nobody is checked individually.

### Keeping the change after the project

After December 2029 there is no project team any more. These habits keep the change alive:

- **The adoption KPIs go to the data governance committee every quarter** (Part 4, §7), next to the data quality and the risks.
- **The champions network stays.** It keeps its monthly meeting, and a champion who leaves the company is replaced.
- **New needs go through the champions:** a department that wants a new figure asks its champion, who builds it or asks the data engineer, instead of starting a new Excel file.
- **New employees learn the reports when they arrive** (§5).
- **A short survey every quarter** (the satisfaction KPI) shows early if a team is drifting back to Excel.

## 9. Link with the rest of our work

| Mitigation (Part 2) | Risk | Where in this plan |
|---|---|---|
| **M-CHG-1** | R01: teams keep their channel reports (20) | Report replacement map with retirement dates set by general management (§3); one data champion per department (§4); escalation to the sponsor (§7) |
| **M-TRF-3** (training part) | R03: dependence on one engineer (16) | Back-up data engineer trained from September to November 2027 (§5) |
| **M-CHG-2** | R10: lack of self-service skills (9) | PL-300 for the 5 creators, workshops for the readers, help from the champions (§4, §5) |

## 10. Limits

- **The list of old reports, the group sizes and the champions' time are our assumptions.** They must be checked with each department in phase 0.
- **We do not know the company's internal communication habits** (newsletter, meetings, chat).
- **The KPI targets are our choices**, not benchmarks.
- **The champions' time and the later training sessions are internal time** that Part 3 does not count.
- **Part 3 pays 25 Power BI licences from year 1**, but 5 readers only start in 2029. Buying their licences later would save a little (about 5 × $168 a year).

## Sources

Checked on 13 October 2026. All other figures come from Parts 0–4 and 6, with their own sources.

1. Microsoft Learn, *Monitor usage metrics in Power BI workspaces* (report views and unique viewers over the last 30 days; export to keep older data; per-user data can be hidden by the administrator): https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-modern-usage-metrics

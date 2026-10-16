# Part 6: Data governance and GDPR

*Case 6: Urbanization, Datamart / Datalake (multi-channel distribution)*

The brief asks us to address **"data governance & quality: master data management for a single customer view across channels, GDPR compliance for customer and web-analytics data"**. This part sets the rules for [Le Slip Français](00-company-profile.md). Both the written deliverables and the proof of concept will follow them.

The rules are kept as files in `governance/`, so the platform can read them (for example, to know which columns contain personal data). Tests in `analysis/test_governance.py` check that the files stay complete.

| File | Content |
|---|---|
| `glossary.csv` | 68 business terms, with definitions and owners |
| `marts.csv` | every column of the planned report tables, linked to a glossary term |
| `mdm_rules.csv` | customer matching and "which value wins" rules |
| `pii_inventory.csv` | every personal-data field of the 7 sources and its treatment |
| `retention.csv` | legal basis and retention period for each of the 17 datasets |
| `erasure_steps.csv` | the right-to-erasure procedure, from the source tools to Power BI |
| `rbac.csv`, `raci.csv` | who can see what, and who is responsible for what |

## 1. Business glossary

Today each department has its own definitions. For example, is "revenue" with or without VAT, with or without returns? Does "a customer" mean a Shopify account or a real person? This is one of the reasons the channel reports never match (risk R09 in [Part 2](02-swot-risks.md)).

The glossary gives **one definition per term and one owner** who decides if it changes. The most important terms:

| Term | Definition | Owner |
|---|---|---|
| **Channel** | Web (leslipfrancais.fr on Shopify), Store (own shops) or Wholesale (Carrefour, Monoprix…) | General management |
| **Order** | A confirmed purchase: a Shopify order, a store ticket or a wholesale order in the ERP; cancelled orders excluded | CFO |
| **Net revenue** | Gross revenue − discounts − returns, **excluding VAT and shipping**; the reference figure for sales | CFO |
| **Average basket** | Net revenue ÷ number of orders (63 € excl. VAT on the web in 2025) | Sales director |
| **Customer** | A person with at least one Web or Store order, as known in one tool | Marketing director |
| **Golden customer** | The single record of one real person after matching all tools | Marketing director |
| **Customer key** | Pseudonymous id of a golden customer; **the only customer id allowed in the report tables** | Marketing director |
| **Wholesale account** | A company that buys to resell (e.g. one Carrefour hypermarket). It is not a person, so it is not a golden customer | Sales director |
| **Marketing consent** | Whether the person may receive marketing messages; a withdrawal always wins | DPO |
| **Stock cover** | Stock on hand ÷ average daily units sold (last 28 days, all channels), in days | Supply chain director |
| **Sell-through rate** | Units sold ÷ (stock at start + units received) over a period | Supply chain director |
| **Stockout / Overstock** | Zero stock while the SKU sold in the last 28 days / stock cover above 180 days | Supply chain director |

**Coverage check.** We planned the report tables of the proof of concept in `marts.csv`: 5 marts (Sales, Customer, Inventory, Marketing, Support) with 77 columns in 10 tables (sales, product, customer, marketing segments, stock, production, campaigns, web, social, support). **Every mart name and every column is linked to a glossary term**, and a test fails if someone adds one without a definition.

## 2. Single customer view (MDM)

Le Slip Français has more than 850,000 customers ([Part 0](00-company-profile.md)). The same person usually exists **several times**: a Shopify account, a Klaviyo profile (sometimes with another email), a store ticket with an e-receipt email, and a Zendesk request. Master data management (MDM) builds **one golden customer** from these records.

### Matching rules

| # | Rule | Action |
|---|---|---|
| 1 | Same email after normalization (lower-case, spaces removed) | merge automatically |
| 2 | Same phone number in international format (+33…) **and the same first name** | merge automatically. A family often shares one phone: with different first names, the records are not merged |
| 3 | A tool stores the other tool's id (e.g. a Klaviyo profile synced from Shopify) | merge automatically |
| 4 | Same first name + last name + postcode | **never automatic**: the CRM manager reviews it, because two people can share a name and a family shares an address |

We chose **exact rules only** for automatic merges. A wrong merge (two people mixed together) is worse for GDPR than a missed one (one person counted twice): someone could receive another person's data.

### Survivorship: which value wins

When records merge, each field takes its value from the most reliable source:

| Field | Winning value |
|---|---|
| Email | the most recent email used in a Shopify order, else Klaviyo |
| Phone | the most recently updated one |
| Name | the Shopify account, else Klaviyo |
| Region | department of the most recent Web shipping address |
| Age band | from the Klaviyo birthday, if given |
| **Marketing consent** | the most recent consent event in Klaviyo or Shopify, but **an unsubscribe always wins** |

### Quality target

Customer segmentation only starts when **at least 90 % of the Klaviyo profiles that have an order are matched** to a Shopify customer. This is the gate we promised for risk R02 (mitigation M-TRF-2). The rule-4 review queue must stay under 200 pairs.

## 3. Personal data inventory

For each of the 7 sources we listed every personal-data field and chose a **treatment**:

| Treatment | Meaning |
|---|---|
| **keep** | not sensitive, or needed as is (e.g. consent status, order totals) |
| **pseudonymize** | the source id is replaced by the customer key |
| **generalize** | made less precise: postcode → department, birthday → age band |
| **restrict** | kept only in the raw layer, which only the data engineer can read; used for matching and erasure, never copied to report tables |
| **drop** | never loaded into the platform |

Summary by source (the full list of 38 fields is in `pii_inventory.csv`):

| Source | Tool | Restricted (raw layer only) | Generalized | Dropped |
|---|---|---|---|---|
| E-commerce | Shopify | email, phone, name, addresses | postcode → department | IP address, order notes, payment card |
| CRM | Klaviyo | email, phone, name | city → department, birthday → age band | – |
| POS | store tills | e-receipt email | – | payment card, cashier name |
| ERP | Business Central | buyer contact at Carrefour/Monoprix | – | all HR/payroll data |
| Web analytics | GA4, Meta Pixel | – | – | cookie and device ids: **only daily totals are loaded** |
| Social media | Instagram, Facebook, TikTok | – | – | usernames and comments: only daily totals are loaded |
| Customer support | Zendesk | requester email and name, **ticket text** | – | – |

**The rule** (checked by a test): contact details, names, free text and payment data are always *restrict* or *drop*, so **they never reach the report tables in clear**. Ticket text is restricted rather than dropped because it can contain anything, even health information (for example a customer explaining a skin allergy).

## 4. GDPR

### Lawful basis and consent

| Processing | Lawful basis |
|---|---|
| Sales and financial reporting | legal obligation (accounting) and contract |
| Sales, stock and customer **analysis** | legitimate interest: the company needs to understand its sales. This analysis uses only the customer key, with no names or emails |
| **Sending** marketing emails/SMS to segments | **consent**, or the CNIL "existing customer" exception: a customer who bought may receive offers for **similar products** if they were told and could refuse, at collection and in every message [1]. This exception does **not** cover people who only created an account without buying [1] |
| **Web analytics** (Google Analytics 4, Meta Pixel) | **consent**. The CNIL exempts from consent only audience-measurement tools configured under strict conditions, and **Google Analytics in its standard setup does not meet them** [2]. So web data comes only from visitors who accepted cookies (see below) |
| Customer service | contract and legitimate interest |

**How web consent is captured.** A cookie banner (consent management platform) on leslipfrancais.fr asks every visitor. It is connected to Google's **Consent Mode in its "basic" setup**: Google Analytics and the Meta Pixel are **not loaded at all** until the visitor accepts. We don't use the "advanced" setup, because it still sends cookieless pings to Google when the visitor refuses [10]. The banner's daily statistics give the **consent rate** (share of visitors who accepted), which is stored next to the sessions in `fct_web_daily`. Readers can then see that sessions measure only consenting visitors.

**DPIA (impact assessment).** The CNIL expects a DPIA when a processing meets at least two of its criteria [3]. Our segmentation meets two: it **evaluates customers** (RFM scores) and it is **large-scale** (850,000 people). So a DPIA must be done **before segmentation starts**, as mitigation M-TRF-5 (Part 2) already requires.

### Retention periods

| Dataset | Retention | Starting from | Basis |
|---|---|---|---|
| Customer data (Shopify, POS email) | 3 years | last order | CNIL client guidance [4] |
| Marketing profiles (Klaviyo) | 3 years | last contact or order | CNIL client/prospect guidance [4] |
| Orders and payments | 10 years | end of the financial year | accounting law, Code de commerce L123-22 [5]; the customer's identity is removed after 3 years, and the order stays anonymous |
| Klaviyo events (opens, clicks) | 3 years | event date | CNIL client guidance [4] |
| Store tickets | 10 years (e-receipt email: 3 years) | end of the financial year | accounting law [5]; CNIL client guidance [4] |
| Support tickets and requesters (Zendesk) | 3 years | ticket closure / last ticket | our choice, aligned on the client guidance |
| Wholesale accounts (companies) | 5 years | end of the relationship | 5-year commercial limitation period, Code de commerce L110-4 [11] |
| Web analytics (daily totals) | 25 months | collection | our choice: we reuse the 25-month limit the CNIL sets for audience measurement [2] as a reasonable maximum |
| Stock, production, campaign and social totals | 5–10 years | record date | not personal data |

The full list, with one rule for each of the 17 datasets of the personal-data inventory (including the ones we don't load), is in `retention.csv`.

### Right to erasure: from the source to Power BI

When a customer asks to be deleted, the request must go through **every layer**, not only Shopify:

| Step | Layer | Action | Deadline |
|---|---|---|---|
| 1 | Source | DPO receives the request, checks identity, logs it | day 0 |
| 2 | Source | Find all records of the person through the golden-customer mapping | 2 days |
| 3 | Staging | Add a hash of the person's emails and phones to an **erasure suppression list**: the staging models drop these people at every sync | 2 days |
| 4 | Source | Delete in Klaviyo [7] and Zendesk; request "Erase personal data" in Shopify [6] (orders are kept, anonymized) | 7 days |
| 5 | Raw layer | Delete the person's rows in the raw layer | 7 days |
| 6 | Raw layer | `VACUUM` the Delta tables so old file versions disappear (kept 7 days by default [8]) | 14 days |
| 7 | Staging | Delete the mapping row, rebuild the customer models with dbt | 14 days |
| 8 | Marts | Rebuild `dim_customer`; the person's sales keep only the anonymous key (−1), so totals stay right | 14 days |
| 9 | BI | Refresh the Power BI models; check that no export shows the person | 14 days |
| 10 | Backups | Backups expire after 30 days; the register notes when | 30 days |
| 11 | Source | Confirm to the person and close the request | **1 month**, the GDPR deadline [9] |
| 12 | Staging | Remove the person from the suppression list once Shopify has finished | up to 6 months |

**Why a suppression list?** Shopify does not erase at once. It waits 10 days, and **if the customer ordered in the last six months, it waits until six months have passed** [12]. During that time the ELT tool would copy the person back into our raw layer at every sync. The suppression list stops that, so our platform respects the one-month deadline even when Shopify is slower.

Sales totals stay correct after an erasure, because only the link to the person is removed, not the sale itself.

## 5. Who can see what

### Access by role (RBAC)

| Role ↓ / Data domain → | Sales | Inventory | Customer (pseudonymous) | Marketing | Support | Customer identity | Raw layer |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| General management | read | read | read | read | read | – | – |
| Sales / stores / wholesale | read | read | read | – | – | – | – |
| E-commerce | read | read | read | read | read | – | – |
| Marketing / CRM | read | – | read | read | read | – | – |
| Customer service | read | – | read | – | read | – | – |
| Supply chain / production | read | read | – | – | – | – | – |
| Finance | read | read | – | read | – | – | – |
| Data engineer | admin | admin | admin | admin | admin | admin | admin |
| DPO | – | – | read | – | – | read | – |

Principles:

- **Nobody in the business sees names or emails in the platform.** Marketing and customer service already see them in their own tools (Klaviyo, Zendesk), where they need them. The platform shows only the customer key.
- The **raw layer** is open only to the data engineer. **Customer identity** (the mapping between the customer key and emails/phones) is open to the data engineer and, read-only, to the DPO for erasure requests. A test checks this rule.
- Each role sees the data it needs for its job, and no more. For example, supply chain doesn't need customer data.

With 69 employees, one person can have several roles. Access is given **per role** (a team), never per person, so it's easy to review when someone changes job. Responsibilities in the RACI below are given to **job titles** (for example the CFO, who belongs to the Finance role).

### Responsibilities (RACI)

| Data domain | Accountable (owner) | Responsible (steward) | Technical | Consulted | Informed |
|---|---|---|---|---|---|
| Sales | CFO | Sales director | Data engineer | E-commerce director | All report readers |
| Inventory | Supply chain director | Production planner | Data engineer | CFO | Sales director |
| Customer | Marketing director | CRM manager | Data engineer | DPO | Customer service manager |
| Marketing | Marketing director | CRM manager | Data engineer | E-commerce director | General management |
| Support | Customer service manager | CS team leader | Data engineer | DPO | Marketing director |
| Customer identity | DPO | CRM manager | Data engineer | Marketing director | General management |
| Raw layer | IT manager | Data engineer | Data engineer | DPO | General management |

The **owner** decides the rules (definitions, access), and the **steward** checks the data quality every week.

## 6. Link with the rest of our work

- **Part 2 (risks).** This part delivers the rules behind M-TRF-2 (match-rate gate), M-TRF-5 (DPIA, restricted raw layer, consent, retention, erasure) and M-TRF-9 (one glossary).
- **Part 4 (transformation plan).** The glossary and the access model must exist before the first report (sales, phase 1). The MDM matching rules are also defined in phase 1, as Part 2 says for R02, so they are tested and mature when segmentation starts.
- **Proof of concept.** The synthetic data generator (#8) must create the problems these rules solve: the same person with two emails, store tickets without a customer, unsubscribed profiles. The dbt models will read `pii_inventory.csv` to tag personal-data columns.

## Sources

Checked on 27 September 2026.

1. CNIL, *La prospection commerciale par courrier électronique, SMS-MMS et automate d'appel*: https://www.cnil.fr/fr/la-prospection-commerciale-par-courrier-electronique-sms-mms-et-automate-dappel
2. CNIL, *Cookies : solutions pour les outils de mesure d'audience*: https://www.cnil.fr/fr/cookies-solutions-pour-les-outils-de-mesure-daudience
3. CNIL, *Ce qu'il faut savoir sur l'analyse d'impact relative à la protection des données (AIPD)*: https://www.cnil.fr/fr/ce-quil-faut-savoir-sur-lanalyse-dimpact-relative-la-protection-des-donnees-aipd
4. CNIL, *Questions-réponses sur les référentiels relatifs à la gestion des activités commerciales*: https://www.cnil.fr/fr/questions-reponses-sur-les-referentiels-relatifs-la-gestion-des-activites-commerciales-et-des
5. Légifrance, Code de commerce, article L123-22: https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006219327
6. Shopify Help Center, *Processing customer data requests*: https://help.shopify.com/en/manual/privacy-and-security/privacy/processing-customer-data-requests
7. Klaviyo Help Center, *How to handle GDPR and CCPA requests*: https://help.klaviyo.com/hc/en-us/articles/360004217631
8. Delta Lake documentation, *Remove files no longer referenced by a Delta table* (VACUUM, 7-day default retention): https://docs.delta.io/latest/delta-utility.html
9. GDPR, Article 12(3) (answer within one month): https://gdpr-info.eu/art-12-gdpr/
10. Google, *Consent mode overview* (basic and advanced implementations): https://developers.google.com/tag-platform/security/concepts/consent-mode
11. Légifrance, Code de commerce, article L110-4 (5-year limitation period): https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000027725867
12. Shopify developer documentation, *Privacy law compliance* (customers/redact is sent after 10 days, or withheld until six months after the last order): https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance

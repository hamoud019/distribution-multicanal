# Proof of concept

A small, local version of the platform chosen in the study: the 7 sources of the brief → a raw layer → cleaned and business tables built with dbt. It runs on a laptop with **synthetic data** and **no cloud account**. DuckDB plays the part of the cloud warehouse (Microsoft Fabric in the study), and a Python script plays the part of Fivetran.

## Run it

You need Python 3.10 to 3.13 (dbt does not support 3.14 yet). From the repository root:

```
py -3.12 poc/run.py          # Windows
python3 poc/run.py           # macOS / Linux
```

That single command:

1. creates a virtual environment in `poc/.venv` and installs `poc/requirements.txt` (first run only, a few minutes);
2. **generates** the synthetic sources into `poc/data/landing/` (`generate.py`);
3. **loads** them, unchanged, into the raw layer of `poc/data/warehouse.duckdb` (`ingest.py`);
4. runs **`dbt source freshness`**: one check per source table, so stale data is flagged before the reports are rebuilt;
5. runs **`dbt build`**: every model and every test;
6. runs **`dbt docs generate`**.

Then `py -3.12 poc/run.py --docs` opens the dbt documentation in the browser, with the **lineage graph** from each source to the report table.

Other options: `--incremental` keeps the warehouse and loads only new or changed files (a changed file replaces the rows it loaded before); `--scale 0.1` makes a smaller dataset for a quick run.

The script always runs inside `poc/.venv` with the pinned versions, even if another dbt is installed on the computer.

## The synthetic sources

A deterministic (fixed seed) **1 % sample** of Le Slip Français's activity over 2023–2025, sized on the public figures of [Part 0](../docs/deliverables/00-company-profile.md) (§4): about 2,400 web orders, 300 store tickets and 52 wholesale orders a year, 8,500 people, 1,500 SKUs. The generated data matches the company profile: an average web basket of about 63 € excluding VAT, about 42 % of web buyers buying again, and a revenue split of about 72 % web, 9 % stores and 19 % wholesale.

Each source keeps the format of its tool, with the problems the platform must solve:

| Source | Tool | Files | Problems on purpose | Refresh (Part 4) |
|---|---|---|---|---|
| E-commerce | Shopify Plus | `shopify/*.jsonl` | prices include VAT; Paris time with its offset; returns refunded weeks later; click-and-collect | every 15 minutes |
| POS | store tills | `pos/<store>/tickets_<day>.csv`, `z_<day>.csv` | one small file per store and day; French formats (`;`, `29,00`, `dd/mm/yyyy`); returns as negative quantities | every 15 minutes |
| ERP | Business Central | `erp/*.csv`, `erp/stock/stock_<monday>.csv` | column names like `No.` and `Posting Date`; stock as a full snapshot each week; revenue as negative accounting credits | every night |
| CRM | Klaviyo | `klaviyo/*.jsonl` | other customer ids; some emails differ from Shopify; nested JSON | every hour |
| Customer support | Zendesk | `zendesk/tickets.jsonl` | UTC times; free text | every hour |
| Web analytics | Google Analytics 4 | `ga4/daily_traffic.csv` | dates as `YYYYMMDD`; daily totals only | every day |
| Social media | Instagram, Facebook, TikTok | `social/*` | three platforms, three formats (JSON lines, one JSON document, CSV with US dates) | every day |

The same person has a different id in each tool, and their email is sometimes typed with capitals or spaces. This is what the golden customer of issue #11 will have to fix.

The wholesale customers are anonymous ("Carrefour hypermarket 01", "Monoprix store 01"): the study does not name the stores. Revenue is booked in account 701 of the French chart of accounts (sales of finished products), since the company makes what it sells.

### Assumptions of the generator

Part 0 gives the volumes, the basket, the share of repeat buyers and the channel split. Everything else is **our assumption**, set as a named constant at the top of `generate.py`:

| Assumption | Value |
|---|---|
| Sales by month | peaks in November (Black Friday) and December (Christmas) |
| Free shipping | from 69 € incl. VAT; 4.90 € below |
| Web orders with a promotion | 2 in 5, at 10 % or 20 % |
| Web orders cancelled / collected in a store / with a return | 2 % / 5 % / 8 % |
| Store tickets in Paris and Toulouse | 60 % / 40 % |
| Store tickets sent by email / store lines that are a return | 60 % / 3 % |
| Production cost | 30 % to 45 % of the price excl. VAT |
| Wholesale price | 50 % of the retail price excl. VAT |
| People subscribed to emails / opening a campaign | 35 % / 30 % (the Part 3 assumptions) |
| People with a Klaviyo profile / with another email in Klaviyo | 70 % / 10 % |
| Web conversion rate | 2 % (Part 0) |

Smaller data-quality settings (how many emails are typed with capitals, how many profiles have a phone number) are in the code next to where they are used.

**Privacy.** Every person is fake: names come from short lists and emails use the reserved `example.com`, `example.org` and `example.net` domains. The fields that [Part 6](../docs/deliverables/06-governance-gdpr.md) marks "drop" (IP address, payment card, cashier name, cookie ids) are not generated at all, as if the loading tool's column blocking were on.

## The layers

| Layer | Where | What |
|---|---|---|
| Raw | `raw_<source>` schemas | the files exactly as received (CSV columns as text, JSON records whole), plus `_source`, `_file`, `_batch_id`, `_loaded_at`. `raw_meta.load_log` remembers every file and its content hash, so each file is loaded once. |
| Staging | `staging` schema, `dbt/models/staging` | one model per source table: English names, real types, French formats parsed. The e-receipt email stays in the raw layer. |
| Intermediate | `intermediate` schema | building blocks, here one row per till ticket. |
| Marts | `marts` schema | the report tables. |

The first report table is **`marts.fct_pos_daily_sales`**: the net revenue (after discounts and returns, excluding VAT, as the glossary defines it), tickets and units of each store per day.

Its business test, `dbt/tests/assert_pos_daily_sales_match_z_reports.sql`, checks every store day against the till's end-of-day **Z report**: the same amount paid, to the cent, and the same number of tickets, as a store manager would. The end-to-end test shows that a Z report just one cent off makes `dbt build` fail.

Every source declares its refresh schedule and freshness thresholds in `dbt/models/staging/_sources.yml`, set from Part 4 §5: sources refreshed every 15 minutes warn after 1 hour, hourly sources after 3 hours, daily sources after 26 hours.

## Tests

After a first run of `run.py`, with the PoC environment:

```
poc/.venv/Scripts/python -m unittest discover poc/tests       # Windows
poc/.venv/bin/python -m unittest discover poc/tests           # macOS / Linux
```

(Any Python runs the generator tests; the others are skipped without dbt and DuckDB.)

- `test_generate.py`: same seed gives the same files, volumes match Part 0, the data looks like the company, and each source has its quirks.
- `test_ingest.py`: every record is loaded unchanged with its metadata, a second run loads only new files, a changed file replaces its old rows, and paths with an apostrophe work.
- `test_pipeline.py`: `dbt build` is green, the store sales match the tills, a Z report one cent off is caught, all 19 freshness checks pass, and a late source is flagged against its own schedule (2 hours late is a warning for the tills but fine for the ERP; 4 days late is an error for web analytics).

The same seed gives the same data with the same Python version; Python only promises the same random numbers within a version.

## Differences with the real platform

- **DuckDB instead of Fabric.** The SQL is standard; moving it to Fabric Warehouse (or BigQuery, Snowflake) means changing the dbt adapter and a few date functions.
- **Files instead of Fivetran and the Business Central link.** `ingest.py` does what the ELT tools would do: load without changing, add load metadata, load only what is new.
- **Stock once a week**, to keep the dataset small. The real platform keeps one snapshot per day (Part 4).
- **No real-time.** As in the study, POS data arrives in small batches.

"""Load the landing files into the raw layer of the DuckDB warehouse, unchanged.

This plays the part of Fivetran and the Business Central link (Part 1, section 8) in the
proof of concept. Each source gets its own schema (raw_shopify, raw_pos...). CSV files are
loaded with every column as text, JSON records are kept whole in a `payload` column, so
nothing is transformed. Every row gets load metadata: _source, _file (relative to the
landing folder), _batch_id and _loaded_at. raw_meta.load_log remembers each file and its
content hash, so a second run only loads new or changed files (incremental loading), and
a changed file replaces the rows it loaded before.

    python poc/ingest.py [--landing poc/data/landing] [--warehouse poc/data/warehouse.duckdb]
"""

import argparse
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

POC = Path(__file__).parent


@dataclass(frozen=True)
class Dataset:
    source: str
    table: str
    pattern: str        # glob, relative to the landing folder
    format: str         # csv, jsonl or json
    delimiter: str = ","


DATASETS = (
    Dataset("shopify", "customers", "shopify/customers.jsonl", "jsonl"),
    Dataset("shopify", "orders", "shopify/orders.jsonl", "jsonl"),
    Dataset("pos", "ticket_lines", "pos/*/tickets_*.csv", "csv", ";"),
    Dataset("pos", "z_reports", "pos/*/z_*.csv", "csv", ";"),
    Dataset("erp", "items", "erp/items.csv", "csv"),
    Dataset("erp", "locations", "erp/locations.csv", "csv"),
    Dataset("erp", "wholesale_customers", "erp/wholesale_customers.csv", "csv"),
    Dataset("erp", "sales_lines", "erp/sales_lines.csv", "csv"),
    Dataset("erp", "production_orders", "erp/production_orders.csv", "csv"),
    Dataset("erp", "gl_entries", "erp/gl_entries.csv", "csv"),
    Dataset("erp", "stock", "erp/stock/stock_*.csv", "csv"),
    Dataset("klaviyo", "profiles", "klaviyo/profiles.jsonl", "jsonl"),
    Dataset("klaviyo", "campaigns", "klaviyo/campaigns.jsonl", "jsonl"),
    Dataset("klaviyo", "events", "klaviyo/events.jsonl", "jsonl"),
    Dataset("ga4", "daily_traffic", "ga4/daily_traffic.csv", "csv"),
    Dataset("ga4", "consent_daily", "ga4/consent_daily.csv", "csv"),
    Dataset("social", "instagram", "social/instagram.jsonl", "jsonl"),
    Dataset("social", "facebook", "social/facebook.json", "json"),
    Dataset("social", "tiktok", "social/tiktok.csv", "csv"),
    Dataset("zendesk", "tickets", "zendesk/tickets.jsonl", "jsonl"),
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sql_text(value):
    """A SQL string literal, safe for paths with apostrophes."""
    return "'" + str(value).replace("'", "''") + "'"


def select_from(dataset, files):
    """SQL reading `files` exactly as they are, with the file name of each row."""
    paths = "[" + ", ".join(sql_text(f.as_posix()) for f in files) + "]"
    if dataset.format == "csv":
        return (f"select * from read_csv({paths}, delim = {sql_text(dataset.delimiter)}, header = true, "
                f"all_varchar = true, filename = '_file')")
    fmt = "newline_delimited" if dataset.format == "jsonl" else "auto"
    return (f"select json::varchar as payload, filename as _file "
            f"from read_json_objects({paths}, format = '{fmt}', filename = true)")


def load_dataset(con, ds, landing, files, hashes, batch_id):
    """Load `files` of one dataset in a single transaction; a changed file replaces its earlier rows."""
    target = f"raw_{ds.source}.{ds.table}"
    names = [f.relative_to(landing).as_posix() for f in files]
    prefix = landing.as_posix().rstrip("/") + "/"
    con.begin()
    con.execute(f"create schema if not exists raw_{ds.source}")
    con.execute(f"create temp table incoming as select * replace (replace(_file, {sql_text(prefix)}, '') as _file) "
                f"from ({select_from(ds, files)})")
    con.execute(f"""create table if not exists {target} as
        select *, ''::varchar as _source, ''::varchar as _batch_id, current_timestamp as _loaded_at
        from incoming limit 0""")
    con.execute(f"delete from {target} where _file in (select unnest(?))", [names])
    con.execute(f"""insert into {target} by name
        select *, {sql_text(ds.source)} as _source, {sql_text(batch_id)} as _batch_id, current_timestamp as _loaded_at
        from incoming""")
    counts = dict(con.execute("select _file, count(*) from incoming group by _file").fetchall())
    for f, name in zip(files, names):
        con.execute("insert into raw_meta.load_log values (?, ?, ?, ?, ?, current_timestamp, ?)",
                    [name, hashes[f], ds.source, ds.table, batch_id, counts.get(name, 0)])
    con.execute("drop table incoming")
    con.commit()
    return sum(counts.values())


def ingest(landing, warehouse):
    """Load every new or changed landing file. Returns {"<source>.<table>": rows loaded}."""
    landing, loaded = Path(landing), {}
    batch = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema if not exists raw_meta")
        con.execute("""create table if not exists raw_meta.load_log (
            file varchar, sha256 varchar, source varchar, table_name varchar,
            batch_id varchar, loaded_at timestamptz, row_count bigint)""")
        # The erasure suppression list (Part 6, section 4, step 3), filled by poc/erase.py: keyed hashes only
        con.execute("""create table if not exists raw_meta.erasure_suppression (
            key_hash varchar, kind varchar, request_id varchar, requested_at timestamptz)""")
        done = set(con.execute("select file, sha256 from raw_meta.load_log").fetchall())
        for ds in DATASETS:
            files = sorted(landing.glob(ds.pattern))
            hashes = {f: sha256(f) for f in files}
            new = [f for f in files if (f.relative_to(landing).as_posix(), hashes[f]) not in done]
            rows = load_dataset(con, ds, landing, new, hashes, f"{batch}-{ds.source}") if new else 0
            loaded[f"{ds.source}.{ds.table}"] = rows
    return loaded


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--landing", default=POC / "data" / "landing", type=Path)
    parser.add_argument("--warehouse", default=POC / "data" / "warehouse.duckdb", type=Path)
    args = parser.parse_args()
    for table, rows in ingest(args.landing, args.warehouse).items():
        print(f"{table:28} {rows:>9,} new rows")

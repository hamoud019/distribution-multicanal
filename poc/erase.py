"""Erase one person from the platform (Part 6, section 4: the right to erasure).

    py -3.12 poc/run.py --erase someone@example.com

The steps of governance/erasure_steps.csv that happen inside the platform:

  2. find every record of the person through the golden customer: all the Shopify customers, Klaviyo
     profiles, till tickets and Zendesk tickets matched to the golden customer of that email;
  3. put the keyed hashes of their emails, phones and source ids on the erasure suppression list, so the
     staging models drop or anonymize them if a tool sends them again;
  5. in the raw layer, delete the customer records, profiles and email events, and anonymize the
     purchases and tickets: orders and till tickets stay (accounting), support tickets stay (statistics),
     but without the email, name, address, customer id or free text;
  6. checkpoint the warehouse, so the deleted rows are not kept in its file;
  7-8. rebuild the dbt layers (run.py does it): the person's sales move to the "anonymous" customer key,
     so the sales totals do not change.

Steps 1, 4 and 9 to 12 (the DPO's register, deletion in the tools themselves, Power BI, backups) are
outside the proof of concept.
"""

import uuid
from datetime import datetime, timezone

import duckdb

from keys import email_key, pseudonymize

# What erasure does to each raw table holding the person, and how the person's rows are found there
DELETE = (
    ("raw_shopify.customers", "payload::json->>'id'", "Shopify"),
    ("raw_klaviyo.profiles", "payload::json->>'id'", "Klaviyo"),
    ("raw_klaviyo.events", "payload::json->>'$.attributes.profile_id'", "Klaviyo"),
)
ANONYMIZE = (  # JSON merge patch: a null removes the field
    ("raw_shopify.orders", "payload::json->>'$.customer.id'", "Shopify",
     '{"customer": null, "email": null, "shipping_address": null}'),
    ("raw_zendesk.tickets", "payload::json->>'id'", "Zendesk",
     '{"requester": null, "subject": null, "description": null}'),
)


def find_records(con, key):
    """Every record of the golden customer(s) of an email key: (record id, source, source id, email and phone keys)."""
    return con.execute("""
        select records.record_id, records.source, records.source_id, records.email_key, records.phone_key
        from intermediate.int_customers__records as records
        inner join intermediate.int_customers__identity_map as identities using (record_id)
        where identities.customer_key in (
            select identities.customer_key
            from intermediate.int_customers__records as records
            inner join intermediate.int_customers__identity_map as identities using (record_id)
            where records.email_key = ?)""", [key]).fetchall()


def erase(warehouse, email, key=None):
    """Erase the person with this email from the raw layer and put them on the suppression list.
    Returns {table: rows deleted or anonymized}. The dbt layers must be rebuilt afterwards."""
    with duckdb.connect(str(warehouse)) as con:
        records = find_records(con, email_key(email, key))
        if not records:
            raise LookupError("Nobody in the platform has this email.")
        ids = {source: [source_id for _, s, source_id, _, _ in records if s == source]
               for source in ("Shopify", "Klaviyo", "POS", "Zendesk")}
        hashes = {(pseudonymize(record_id, key), "source id") for record_id, *_ in records}
        hashes |= {(e, "email") for *_, e, _ in records if e} | {(p, "phone") for *_, p in records if p}

        done = {}
        con.begin()
        request = str(uuid.uuid4())
        for key_hash, kind in sorted(hashes):
            con.execute("insert into raw_meta.erasure_suppression values (?, ?, ?, ?)",
                        [key_hash, kind, request, datetime.now(timezone.utc)])
        for table, id_sql, source in DELETE:
            done[table] = con.execute(f"delete from {table} where ({id_sql}) in (select unnest(?))",
                                      [ids[source]]).fetchone()[0]
        for table, id_sql, source, patch in ANONYMIZE:
            done[table] = con.execute(f"""update {table} set payload = json_merge_patch(payload, '{patch}')::varchar
                                          where ({id_sql}) in (select unnest(?))""", [ids[source]]).fetchone()[0]
        done["raw_pos.ticket_lines"] = con.execute(
            "update raw_pos.ticket_lines set email_ticket = '' where ticket_no in (select unnest(?))",
            [ids["POS"]]).fetchone()[0]
        con.commit()
        con.execute("checkpoint")
    return done

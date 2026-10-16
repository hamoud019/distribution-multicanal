"""Synthetic source data for the proof of concept.

Generates a deterministic 1 % sample of Le Slip Français's activity over 2023-2025
(docs/deliverables/00-company-profile.md, section 4) for the 7 sources of the brief,
each in the format of its tool and with the problems the platform must solve:
different customer ids per tool, emails with mixed case and spaces, VAT-inclusive
prices on Shopify, French number and date formats on the tills, Business Central
column names, nested Klaviyo JSON, and so on.

Every person is fake: names come from short lists and emails use the reserved
example.com/.org/.net domains. Fields that Part 6 marks "drop" (IP address, payment
card, cashier name...) are not generated, as if the ELT tool's column blocking were on.

    python poc/generate.py [--out poc/data/landing] [--seed 2026] [--scale 1.0]
"""

import argparse
import bisect
import collections
import csv
import json
import math
import random
import shutil
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

POC = Path(__file__).parent
YEARS = (2023, 2024, 2025)
VAT = 0.20

# Yearly volumes of the 1 % sample (Part 0, section 4)
WEB_ORDERS_PER_YEAR = 2_400
POS_TICKETS_PER_YEAR = 300
WHOLESALE_ORDERS_PER_YEAR = 52
CUSTOMERS = 8_500
PRODUCTS = 300
SIZES = ("S", "M", "L", "XL", "XXL")  # 300 products x 5 sizes = 1,500 SKUs
CAMPAIGNS_PER_YEAR = 100
SUPPORT_TICKETS_PER_YEAR = 120
REPEAT_ORDER_SHARE = 0.42  # share of web orders placed by a returning customer: gives about 42 % repeat buyers

CATEGORIES = {  # category: (lowest, highest) shelf price incl. VAT in EUR
    "Briefs": (25, 35), "Boxers": (29, 39), "Socks": (12, 19), "Pyjamas": (59, 89), "T-shirts": (35, 49),
}
COLOURS = ("navy", "white", "black", "red", "grey", "blue-white-red", "green")
LOCATIONS = (  # code, name, type
    ("WH-AUB", "Aubervilliers factory and warehouse", "warehouse"),
    ("ST-PAR", "Paris Marais store", "store"),
    ("ST-TLS", "Toulouse store", "store"),
)
STORES = ("ST-PAR", "ST-TLS")
WHOLESALE_ACCOUNTS = tuple(  # a sample of the ~100 hypermarkets and the Monoprix stores, anonymous
    [(f"C{n:04d}", f"Carrefour hypermarket {n:02d}") for n in range(1, 9)]
    + [(f"C{n:04d}", f"Monoprix store {n - 8:02d}") for n in range(9, 11)]
)
FIRST_NAMES = ("Camille", "Lucas", "Léa", "Hugo", "Chloé", "Louis", "Manon", "Jules", "Inès", "Gabriel", "Sarah",
               "Arthur", "Emma", "Nathan", "Jade", "Paul", "Louise", "Tom", "Alice", "Adam", "Zoé", "Raphaël")
LAST_NAMES = ("Martin", "Bernard", "Thomas", "Petit", "Robert", "Richard", "Durand", "Dubois", "Moreau", "Laurent",
              "Simon", "Michel", "Lefebvre", "Leroy", "Roux", "David", "Bertrand", "Morel", "Fournier", "Girard")
CITIES = (("75011", "Paris"), ("69003", "Lyon"), ("31000", "Toulouse"), ("33000", "Bordeaux"), ("44000", "Nantes"),
          ("59000", "Lille"), ("13001", "Marseille"), ("67000", "Strasbourg"), ("35000", "Rennes"), ("34000", "Montpellier"))
DOMAINS = ("example.com", "example.org", "example.net")
# Our assumptions, where the study gives no figure (listed in poc/README.md)
MONTH_WEIGHTS = (6, 5, 6, 6, 7, 8, 7, 6, 7, 8, 13, 21)  # sales by month: Black Friday and Christmas peaks
FREE_SHIPPING_FROM = 69.0       # EUR incl. VAT; below it, shipping costs SHIPPING_FEE
SHIPPING_FEE = 4.90
DISCOUNT_RATES = (0, 0, 0, 0.1, 0.2)  # most web orders have no promotion
CANCELLED_SHARE = 0.02          # web orders cancelled
CLICK_AND_COLLECT_SHARE = 0.05  # web orders collected in a store
RETURN_SHARE = 0.08             # web orders with one item returned and refunded
STORE_SPLIT = (60, 40)          # tickets in Paris and in Toulouse
E_RECEIPT_SHARE = 0.60          # store tickets sent by email
STORE_RETURN_SHARE = 0.03       # store lines that are a return
UNIT_COST_SHARE = (0.30, 0.45)  # production cost as a share of the price excl. VAT
SUBSCRIBED_SHARE = 0.35         # people subscribed to emails (Part 3: 300,000 of 850,000)
WITHDRAWN_SHARE = 0.10          # subscribers who later unsubscribed in Klaviyo, while Shopify still says "subscribed"
HOUSEHOLD_SHARE = 0.03          # people who share a phone with a family member (same last name and address)
KLAVIYO_SHARE = 0.70            # people with a Klaviyo profile
OTHER_EMAIL_SHARE = 0.10        # Klaviyo profiles with another email than Shopify
OPEN_SHARE = 0.30               # subscribers who open a campaign (Part 3)
CLICK_SHARE = 0.10              # openers who also click
INSTAGRAM_FOLLOWERS = 150_000   # at the start of 2023
WHOLESALE_PRICE_SHARE = 0.5     # wholesale price as a share of the retail price excl. VAT
WEB_CONVERSION = 0.02           # orders per session (Part 0, section 4)
CONSENT_RATE = (0.55, 0.75)     # visitors who accept analytics cookies in the banner, each day
DENIED_ROW_SHARE = 0.10         # GA4 rows of visitors who refused (a tag firing before the banner), per day and source
FIRST_REPLY_HOURS = 4           # typical hours before an agent's first reply (log-normal around it, at most 72)
ORDER_FIELD, PRODUCT_FIELD = 360001, 360002  # Zendesk custom fields: order number and product SKU
SIZE_WEIGHTS = (10, 30, 30, 20, 10)  # sales by size: mostly M and L
POPULARITY_SPREAD = 1.5         # popularity of each product is log-normal: a few best sellers, a long tail
LEAD_WEEKS = {"WH-AUB": 3, "ST-PAR": 1, "ST-TLS": 1}  # weeks to make a batch in the factory / to restock a store
SAFETY_UNITS = {"WH-AUB": 1, "ST-PAR": 0, "ST-TLS": 0}  # units kept on top, for the SKUs a location sells
TARGET_COVER_WEEKS = (6, 16)    # a reorder brings the stock back to this many weeks of sales
OVERSTOCKED_SHARE = 0.08        # SKUs whose target is set far too high (a buying mistake)...
OVERSTOCKED_WEEKS = (35, 60)    # ...at this many weeks of sales
GL_ACCOUNTS = (  # French chart of accounts, 701: sales of finished products (the company makes its products)
    ("701100", "Web"), ("701200", "Store"), ("701300", "Wholesale"),
)
WEB_CHANNELS = ("Organic Search", "Paid Search", "Email", "Direct", "Organic Social", "Referral")


@dataclass
class Person:
    first_name: str
    last_name: str
    email: str
    phone: str
    postcode: str
    city: str
    birthday: date
    subscribed: bool
    withdrawn: bool = False  # unsubscribed later, in Klaviyo only


@dataclass
class Product:
    sku: str
    product_id: int
    name: str
    category: str
    size: str
    colour: str
    price_incl_vat: float  # shelf price on the website and in the stores
    unit_cost: float


def money(x):
    return round(x + 1e-9, 2)


def fr_number(x):
    """French decimal comma, as printed by the tills."""
    return f"{x:.2f}".replace(".", ",")


def paris_offset(moment_utc):
    """Hours ahead of UTC in Paris: summer time from the last Sunday of March to the last Sunday of October."""
    def last_sunday(year, month):
        d = date(year, month, 31)
        return d - timedelta(days=(d.weekday() + 1) % 7)
    y = moment_utc.year
    start = datetime.combine(last_sunday(y, 3), time(1), timezone.utc)
    end = datetime.combine(last_sunday(y, 10), time(1), timezone.utc)
    return 2 if start <= moment_utc < end else 1


def paris_iso(moment_utc):
    """Shopify style: local Paris time with its offset, e.g. 2025-03-04T15:12:00+01:00."""
    offset = timedelta(hours=paris_offset(moment_utc))
    return (moment_utc + offset).replace(tzinfo=timezone(offset)).isoformat()


def paris_local(moment_utc):
    return (moment_utc + timedelta(hours=paris_offset(moment_utc))).replace(tzinfo=None)


class Generator:
    def __init__(self, seed, scale):
        self.rng = random.Random(seed)
        # The identity problems of the golden customer (households, phone formats, withdrawn consent) use their
        # own draws, so adding them did not change the sales and stock drawn with self.rng.
        self.quirks = random.Random(f"{seed}-identities")
        self.scale = scale
        self.people = []
        self.products = []
        self.shopify_ids = {}     # person index -> Shopify customer id
        self.web_buyers = []      # people who have bought online at least once
        self.popularity = []      # cumulative sales weight of each SKU, for weighted picks
        self.sold = collections.Counter()  # units sold per (location that hands them over, SKU, day)
        self.purchases = []       # (person index, order number, UTC moment, SKUs) of web orders and e-receipt tickets
        self.newcomers = []       # people who have not bought online yet, in random order
        # net revenue excl. VAT by (year, month) and channel, written to the general ledger
        self.net = {channel: collections.Counter() for _, channel in GL_ACCOUNTS}

    def scaled(self, n):
        return max(1, round(n * self.scale))

    def random_moment(self, year, hours=(8, 23)):
        """A UTC moment in `year`, with the monthly seasonality of sales."""
        month = self.rng.choices(range(1, 13), weights=MONTH_WEIGHTS)[0]
        day = self.rng.randint(1, 28 if month == 2 else 30 if month in (4, 6, 9, 11) else 31)
        local = datetime(year, month, day, self.rng.randint(*hours), self.rng.randint(0, 59), tzinfo=timezone.utc)
        return local - timedelta(hours=paris_offset(local))

    def messy(self, email):
        """The same email as typed in another tool: sometimes capitalized, sometimes with spaces."""
        roll = self.rng.random()
        if roll < 0.15:
            return email.capitalize()
        if roll < 0.25:
            return f" {email.upper()} "
        return email

    def national(self, phone):
        """The phone as typed in France, sometimes: +33612345678 -> 06 12 34 56 78."""
        if self.quirks.random() < 0.5:
            digits = "0" + phone[3:]
            return " ".join(digits[n:n + 2] for n in range(0, 10, 2))
        return phone

    # --- master data -------------------------------------------------------------------------
    def make_people(self):
        for i in range(self.scaled(CUSTOMERS)):
            first, last = self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES)
            ascii_first = first.translate(str.maketrans("éèëç", "eeec")).lower()
            postcode, city = self.rng.choice(CITIES)
            self.people.append(Person(
                first, last, f"{ascii_first}.{last.lower()}{i}@{self.rng.choice(DOMAINS)}",
                f"+336{self.rng.randint(10_000_000, 99_999_999)}", postcode, city,
                date(self.rng.randint(1950, 2004), self.rng.randint(1, 12), self.rng.randint(1, 28)),
                self.rng.random() < SUBSCRIBED_SHARE,
            ))
        for i, p in enumerate(self.people):
            # a family member: same phone, last name and address, another first name (must not be merged)
            if i and self.quirks.random() < HOUSEHOLD_SHARE:
                head = self.people[self.quirks.randrange(i)]
                if head.first_name != p.first_name:
                    p.last_name, p.phone, p.postcode, p.city = head.last_name, head.phone, head.postcode, head.city
            p.withdrawn = p.subscribed and self.quirks.random() < WITHDRAWN_SHARE

    def make_products(self):
        total = 0.0
        for pid in range(1, self.scaled(PRODUCTS) + 1):
            category = self.rng.choice(list(CATEGORIES))
            low, high = CATEGORIES[category]
            price = float(self.rng.randint(low, high))
            colour = self.rng.choice(COLOURS)
            popularity = self.rng.lognormvariate(0, POPULARITY_SPREAD)
            for size, size_weight in zip(SIZES, SIZE_WEIGHTS):
                self.products.append(Product(
                    f"LSF-{pid:03d}-{size}", pid, f"{category[:-1]} {colour} {pid:03d}", category, size, colour, price,
                    money(price / (1 + VAT) * self.rng.uniform(*UNIT_COST_SHARE)),
                ))
                total += popularity * size_weight
                self.popularity.append(total)

    def pick_product(self):
        """A SKU, the best sellers more often than the others."""
        return self.products[bisect.bisect(self.popularity, self.rng.random() * self.popularity[-1])]

    def pick_web_buyer(self):
        """A web buyer: either a past buyer coming back or a newcomer (about 4 in 10 buyers buy again)."""
        if not self.newcomers and not self.web_buyers:
            self.newcomers = self.rng.sample(range(len(self.people)), len(self.people))
        if self.web_buyers and (self.rng.random() < REPEAT_ORDER_SHARE or not self.newcomers):
            return self.rng.choice(self.web_buyers)
        buyer = self.newcomers.pop()
        self.web_buyers.append(buyer)
        return buyer

    def pick_person(self):
        return self.rng.randrange(len(self.people))

    def pick_lines(self, max_lines):
        return [(self.pick_product(), self.rng.choices((1, 2, 3), weights=(80, 17, 3))[0])
                for _ in range(self.rng.choices(range(1, max_lines + 1), weights=(58, 28, 10, 4)[:max_lines])[0])]

    # --- e-commerce: Shopify ---------------------------------------------------------------------
    def shopify(self, out):
        orders = []
        order_id, line_id = 5_100_000_000, 13_000_000_000
        for year in YEARS:
            for _ in range(self.scaled(WEB_ORDERS_PER_YEAR)):
                person_index = self.pick_web_buyer()
                customer_id = self.shopify_ids.setdefault(person_index, 7_000_000_000 + person_index)
                created = self.random_moment(year)
                order_id += 1
                lines, discount_rate = [], self.rng.choice(DISCOUNT_RATES)
                for product, qty in self.pick_lines(4):
                    line_id += 1
                    lines.append({"id": line_id, "sku": product.sku, "title": product.name, "quantity": qty,
                                  "price": f"{product.price_incl_vat:.2f}",
                                  "total_discount": f"{money(product.price_incl_vat * qty * discount_rate):.2f}"})
                subtotal = sum(float(l["price"]) * l["quantity"] - float(l["total_discount"]) for l in lines)
                shipping = 0.0 if subtotal >= FREE_SHIPPING_FROM else SHIPPING_FEE
                total = money(subtotal + shipping)
                pickup = self.rng.random() < CLICK_AND_COLLECT_SHARE
                cancelled = self.rng.random() < CANCELLED_SHARE
                order = {
                    "id": order_id, "name": f"#{order_id - 5_100_000_000 + 1000}", "created_at": paris_iso(created),
                    "customer": {"id": customer_id}, "email": self.messy(self.people[person_index].email),
                    "currency": "EUR", "taxes_included": True, "total_price": f"{total:.2f}",
                    "total_tax": f"{money(total - total / (1 + VAT)):.2f}",
                    "total_discounts": f"{sum(float(l['total_discount']) for l in lines):.2f}",
                    "shipping_lines": [{"title": "Retrait en magasin" if pickup else "Colissimo",
                                        "price": "0.00" if pickup else f"{shipping:.2f}"}],
                    "fulfillment_location": self.rng.choice(STORES) if pickup else "WH-AUB",
                    "cancelled_at": paris_iso(created + timedelta(hours=2)) if cancelled else None,
                    "line_items": lines, "refunds": [],
                    "shipping_address": {"zip": self.people[person_index].postcode,
                                         "city": self.people[person_index].city},
                }
                if not cancelled:
                    local = paris_local(created)
                    self.net["Web"][(local.year, local.month)] += subtotal / (1 + VAT)
                    for line in lines:
                        self.sold[(order["fulfillment_location"], line["sku"], local.date())] += line["quantity"]
                    refunded_at = created + timedelta(days=self.rng.randint(5, 40))
                    # a return, refunded a few weeks later (unless that is after the end of the data)
                    if self.rng.random() < RETURN_SHARE and refunded_at.year <= YEARS[-1]:
                        line = self.rng.choice(lines)
                        amount = money(float(line["price"]) - float(line["total_discount"]) / line["quantity"])
                        order["refunds"].append({"created_at": paris_iso(refunded_at), "refund_line_items": [
                            {"line_item_id": line["id"], "quantity": 1, "subtotal": f"{amount:.2f}"}]})
                        local = paris_local(refunded_at)
                        self.net["Web"][(local.year, local.month)] -= amount / (1 + VAT)
                if not cancelled:
                    self.purchases.append((person_index, order["name"], created, [l["sku"] for l in lines]))
                orders.append(order)
        orders.sort(key=lambda o: o["created_at"])
        write_jsonl(out / "shopify" / "orders.jsonl", orders)

        # Customer accounts: every buyer, plus accounts created without buying
        account_holders = set(self.shopify_ids)
        for i in self.rng.sample(range(len(self.people)), len(self.people) // 10):
            account_holders.add(i)
            self.shopify_ids.setdefault(i, 7_000_000_000 + i)
        customers = []
        for i in sorted(account_holders):
            p = self.people[i]
            customers.append({
                "id": self.shopify_ids[i], "email": self.messy(p.email), "first_name": p.first_name,
                "last_name": p.last_name, "phone": p.phone if self.rng.random() < 0.6 else None,
                "default_address": {"zip": p.postcode, "city": p.city, "country_code": "FR"},
                "email_marketing_consent": {"state": "subscribed" if p.subscribed else "not_subscribed"},
            })
        write_jsonl(out / "shopify" / "customers.jsonl", customers)

    # --- POS: one small file per store and day, plus the till's end-of-day Z report ----------------
    def pos(self, out):
        tickets = {}
        number = 0
        for year in YEARS:
            for _ in range(self.scaled(POS_TICKETS_PER_YEAR)):
                store = self.rng.choices(STORES, weights=STORE_SPLIT)[0]
                moment = paris_local(self.random_moment(year, hours=(10, 19)))
                number += 1
                tickets.setdefault((store, moment.date()), []).append((f"T{number:06d}", moment))
        for (store, day), day_tickets in sorted(tickets.items()):
            rows, total = [], 0.0
            for ticket_no, moment in sorted(day_tickets, key=lambda t: t[1]):
                email, buyer, skus = "", None, []
                if self.rng.random() < E_RECEIPT_SHARE:
                    buyer = self.pick_person()
                    email = self.messy(self.people[buyer].email)
                for product, qty in self.pick_lines(3):
                    skus.append(product.sku)
                    if self.rng.random() < STORE_RETURN_SHARE:
                        qty = -1  # a return in store
                    discount = money(product.price_incl_vat * qty * 0.1) if self.rng.random() < 0.1 else 0.0
                    line_total = money(product.price_incl_vat * qty - discount)
                    total += line_total
                    if qty > 0:
                        self.sold[(store, product.sku, day)] += qty
                    rows.append([ticket_no, moment.strftime("%d/%m/%Y %H:%M"), store, product.sku, qty,
                                 fr_number(product.price_incl_vat), fr_number(discount), fr_number(line_total), email])
                if buyer is not None:
                    utc = moment.replace(tzinfo=timezone.utc)
                    self.purchases.append((buyer, ticket_no, utc - timedelta(hours=paris_offset(utc)), skus))
            self.net["Store"][(day.year, day.month)] += total / (1 + VAT)
            folder = out / "pos" / store
            write_csv(folder / f"tickets_{day:%Y%m%d}.csv", ["ticket_no", "date_heure", "magasin", "sku", "qte",
                      "prix_unitaire_ttc", "remise_ttc", "total_ligne_ttc", "email_ticket"], rows, delimiter=";")
            write_csv(folder / f"z_{day:%Y%m%d}.csv", ["magasin", "date", "nb_tickets", "total_ttc"],
                      [[store, day.strftime("%d/%m/%Y"), len(day_tickets), fr_number(total)]], delimiter=";")

    # --- ERP: Microsoft Dynamics 365 Business Central exports ----------------------------------------
    def erp(self, out):
        erp = out / "erp"
        write_csv(erp / "items.csv", ["No.", "Description", "Item Category Code", "Variant Size", "Colour",
                                      "Unit Price", "Unit Cost"],
                  [[p.sku, p.name, p.category, p.size, p.colour, f"{money(p.price_incl_vat / (1 + VAT)):.2f}",
                    f"{p.unit_cost:.2f}"] for p in self.products])
        write_csv(erp / "locations.csv", ["Code", "Name", "Location Type"], [list(l) for l in LOCATIONS])
        write_csv(erp / "wholesale_customers.csv", ["No.", "Name", "Customer Posting Group"],
                  [[no, name, "GMS"] for no, name in WHOLESALE_ACCOUNTS])

        lines, doc = [], 0
        for year in YEARS:
            for week in range(self.scaled(WHOLESALE_ORDERS_PER_YEAR)):
                posting = date(year, 1, 2) + timedelta(weeks=week % 52, days=self.rng.randint(0, 4))
                account = self.rng.choice(WHOLESALE_ACCOUNTS)[0]
                doc += 1
                products = {}
                for _ in range(self.rng.randint(3, 8)):  # a few SKUs, mostly best sellers, each once
                    product = self.pick_product()
                    products[product.sku] = product
                for n, product in enumerate(products.values(), 1):
                    qty = self.rng.choice((6, 6, 12))
                    self.sold[("WH-AUB", product.sku, posting)] += qty
                    price = money(product.price_incl_vat / (1 + VAT) * WHOLESALE_PRICE_SHARE)
                    lines.append([f"SO{doc:05d}", n * 10000, account, posting.isoformat(), product.sku, qty,
                                  f"{price:.2f}", f"{money(price * qty):.2f}"])
                    self.net["Wholesale"][(posting.year, posting.month)] += price * qty
        write_csv(erp / "sales_lines.csv", ["Document No.", "Line No.", "Sell-to Customer No.", "Posting Date",
                                            "No.", "Quantity", "Unit Price", "Line Amount"], lines)

        # Stock and production. Every location follows a reorder rule based on its own sales: when the stock
        # (plus what is already on its way) falls to the sales of the lead time, it is brought back up to a
        # target cover. The factory makes what the warehouse orders (the production orders); stores are
        # restocked in a week. A store only keeps the SKUs it sells. A full snapshot is taken every Monday
        # (Part 0: one snapshot a week per SKU and location), before the week's sales.
        mondays = []
        day = date(YEARS[0], 1, 2)
        while day.year <= YEARS[-1]:
            mondays.append(day)
            day += timedelta(weeks=1)
        weekly = collections.Counter()
        for (code, sku, day), qty in self.sold.items():
            weekly[(code, sku, min(max((day - mondays[0]).days // 7, 0), len(mondays) - 1))] += qty
        totals = collections.Counter()
        for (code, sku, _), qty in weekly.items():
            totals[(code, sku)] += qty

        # The planners' forecast: the SKU's average weekly sales at the location, times the season of the
        # month when a reorder would arrive (Black Friday and Christmas need more stock).
        season = [MONTH_WEIGHTS[monday.month - 1] * 12 / sum(MONTH_WEIGHTS) for monday in mondays]

        snapshots, production = [[] for _ in mondays], []
        for p in self.products:
            for code, _, _ in LOCATIONS:
                rate = totals[(code, p.sku)] / len(mondays)
                weeks = self.rng.uniform(*(OVERSTOCKED_WEEKS if self.rng.random() < OVERSTOCKED_SHARE
                                           else TARGET_COVER_WEEKS))
                lead, safety = LEAD_WEEKS[code], SAFETY_UNITS[code] if rate else 0

                def forecast(w):
                    return rate * season[min(w + lead, len(mondays) - 1)]

                def target(w):
                    return max(math.ceil(forecast(w) * weeks), safety + 1) if rate else 0

                stock, arriving = target(0), collections.Counter()
                for w in range(len(mondays)):
                    stock += arriving.pop(w, 0)
                    snapshots[w].append([p.sku, code, stock])
                    stock = max(0, stock - weekly[(code, p.sku, w)])
                    on_the_way = sum(arriving.values())
                    if rate and stock + on_the_way <= forecast(w) * lead + safety:
                        quantity = max(target(w) - stock - on_the_way, 1)
                        arriving[w + lead] += quantity
                        if code == "WH-AUB" and w + lead < len(mondays):
                            finished = mondays[w + lead] - timedelta(days=self.rng.randint(1, 4))
                            production.append([p.sku, quantity, finished.isoformat(), code])
        for monday, rows in zip(mondays, snapshots):
            write_csv(erp / "stock" / f"stock_{monday:%Y%m%d}.csv", ["Item No.", "Location Code", "Quantity"], rows)
        production.sort(key=lambda r: (r[2], r[0]))
        write_csv(erp / "production_orders.csv", ["No.", "Item No.", "Quantity", "Finished Date", "Location Code"],
                  [[f"PO{n:06d}", *row] for n, row in enumerate(production, 1)])

        # General ledger: monthly revenue per channel, as accounting credits (negative amounts)
        gl, entry = [], 0
        for year in YEARS:
            for month in range(1, 13):
                month_end = (date(year, month, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                for account, channel in GL_ACCOUNTS:
                    entry += 1
                    gl.append([entry, month_end.isoformat(), account, f"Revenue {channel}",
                               f"{-money(self.net[channel][(year, month)]):.2f}"])
        write_csv(erp / "gl_entries.csv", ["Entry No.", "Posting Date", "G/L Account No.", "Description", "Amount"], gl)

    # --- CRM: Klaviyo (JSON:API style) ----------------------------------------------------------------
    def klaviyo(self, out):
        profiles, ids = [], {}
        for i, p in enumerate(self.people):
            if self.rng.random() > KLAVIYO_SHARE:
                continue
            ids[i] = "01H" + "".join(self.rng.choice("0123456789ABCDEFGHJKMNPQRSTVWXYZ") for _ in range(23))
            email = p.email if self.rng.random() > OTHER_EMAIL_SHARE else f"{p.first_name.lower()}{i}@{self.rng.choice(DOMAINS)}"
            properties = {}
            if i in self.shopify_ids and self.rng.random() < 0.6:  # synced from Shopify: carries its id
                properties["shopify_customer_id"] = str(self.shopify_ids[i])
            profiles.append({"type": "profile", "id": ids[i], "attributes": {
                "email": self.messy(email), "phone_number": self.national(p.phone) if self.rng.random() < 0.4 else None,
                "first_name": p.first_name, "last_name": p.last_name,
                "location": {"city": p.city, "zip": p.postcode},
                "properties": {**properties, "birthday": p.birthday.isoformat() if self.rng.random() < 0.3 else None},
                "subscriptions": {"email": {"marketing": {
                    "consent": "UNSUBSCRIBED" if p.withdrawn else "SUBSCRIBED" if p.subscribed
                    else "NEVER_SUBSCRIBED"}}},
            }})
        write_jsonl(out / "klaviyo" / "profiles.jsonl", profiles)

        campaigns, events = [], []
        subscribed = [ids[i] for i in ids if self.people[i].subscribed]
        event_id = 0
        for year in YEARS:
            for n in range(self.scaled(CAMPAIGNS_PER_YEAR)):
                sent = datetime(year, 1, 3, 9, tzinfo=timezone.utc) + timedelta(days=n * 365 // CAMPAIGNS_PER_YEAR)
                campaign_id = f"C{year}{n:03d}"
                campaigns.append({"type": "campaign", "id": campaign_id, "attributes": {
                    "name": f"Newsletter {sent:%Y-%m-%d}", "send_time": sent.isoformat(), "status": "Sent",
                    "statistics": {"recipients": len(subscribed), "delivered": len(subscribed)}}})
                for profile_id in subscribed:
                    if self.rng.random() < OPEN_SHARE:
                        for metric in ("Opened Email",) + (("Clicked Email",) if self.rng.random() < CLICK_SHARE else ()):
                            event_id += 1
                            events.append({"type": "event", "id": f"E{event_id:08d}", "attributes": {
                                "metric": metric, "profile_id": profile_id, "campaign_id": campaign_id,
                                "datetime": (sent + timedelta(minutes=self.rng.randint(5, 4000))).isoformat()}})
        write_jsonl(out / "klaviyo" / "campaigns.jsonl", campaigns)
        write_jsonl(out / "klaviyo" / "events.jsonl", events)

    # --- web analytics: Google Analytics 4 export (daily totals only) ----------------------------------
    def ga4(self, out):
        """Daily sessions by traffic source. GA4 only loads after the visitor accepts cookies (Part 6), but a tag
        firing before the banner on a few pages sends some sessions of visitors who refused: GA4 marks them
        analytics_storage = "No", and the platform must drop them. The banner gives its own daily figures."""
        rows, banner = [], []
        day = date(YEARS[0], 1, 1)
        while day.year <= YEARS[-1]:
            orders_today = WEB_ORDERS_PER_YEAR * self.scale * MONTH_WEIGHTS[day.month - 1] / sum(MONTH_WEIGHTS) / 30
            accepted = 0
            for channel in WEB_CHANNELS:
                share = self.rng.uniform(0.05, 0.35)
                sessions = max(0, round(orders_today * share / WEB_CONVERSION * self.rng.uniform(0.8, 1.2)))
                rows.append([day.strftime("%Y%m%d"), channel, "Yes", sessions,
                             round(sessions * self.rng.uniform(0.01, 0.03))])
                accepted += sessions
                if self.rng.random() < DENIED_ROW_SHARE:
                    refused = max(1, round(sessions * self.rng.uniform(0.05, 0.3)))
                    rows.append([day.strftime("%Y%m%d"), channel, "No", refused, round(refused * 0.02)])
            rate = self.rng.uniform(*CONSENT_RATE)
            banner.append([day.isoformat(), round(accepted / rate), accepted])
            day += timedelta(days=1)
        write_csv(out / "ga4" / "daily_traffic.csv",
                  ["date", "sessionDefaultChannelGroup", "analytics_storage", "sessions", "conversions"], rows)
        write_csv(out / "ga4" / "consent_daily.csv", ["date", "banner_views", "accepted"], banner)

    # --- social media: three platforms, three formats -------------------------------------------------
    def social(self, out):
        instagram, facebook, tiktok = [], [], []
        day, followers = date(YEARS[0], 1, 1), INSTAGRAM_FOLLOWERS
        fans, tiktok_followers = INSTAGRAM_FOLLOWERS // 2, INSTAGRAM_FOLLOWERS // 5  # our assumption: smaller accounts
        while day.year <= YEARS[-1]:
            followers += self.rng.randint(-20, 80)
            fans += self.rng.randint(-10, 30)
            tiktok_followers += self.rng.randint(-10, 60)
            instagram.append({"date": day.isoformat(), "reach": self.rng.randint(5_000, 40_000),
                              "impressions": self.rng.randint(10_000, 80_000), "follower_count": followers,
                              "total_interactions": self.rng.randint(200, 3_000)})
            facebook.append({"end_time": f"{day.isoformat()}T08:00:00+0000", "page_impressions":
                             self.rng.randint(2_000, 20_000), "page_post_engagements": self.rng.randint(50, 900),
                             "page_fans": fans})
            tiktok.append([day.strftime("%m/%d/%Y"), self.rng.randint(1_000, 60_000), self.rng.randint(20, 3_000),
                           self.rng.randint(0, 200), self.rng.randint(0, 150), tiktok_followers])
            day += timedelta(days=1)
        write_jsonl(out / "social" / "instagram.jsonl", instagram)
        write_json(out / "social" / "facebook.json", {"data": facebook, "paging": {}})
        write_csv(out / "social" / "tiktok.csv", ["Date", "Video Views", "Likes", "Comments", "Shares", "Followers"],
                  tiktok)

    # --- customer support: Zendesk ---------------------------------------------------------------------
    def zendesk(self, out):
        """Each ticket is about one purchase, a few days after it: a web order or a store ticket with an
        e-receipt. The agent fills in the order number and the product (two custom fields)."""
        subjects = (("Where is my order?", "delivery"), ("Wrong size, can I exchange?", "exchange"),
                    ("Hole after two washes", "quality"), ("Refund not received", "refund"),
                    ("Skin reaction to the fabric", "quality"))
        tickets = []
        for year in YEARS:
            bought = [p for p in self.purchases if p[2].year == year]
            for n in range(self.scaled(SUPPORT_TICKETS_PER_YEAR)):
                person_index, order_number, bought_at, skus = self.rng.choice(bought)
                person = self.people[person_index]
                subject, category = self.rng.choice(subjects if order_number.startswith("#") else subjects[1:])
                created = bought_at + timedelta(days=self.rng.randint(2, 20), hours=self.rng.randint(0, 9))
                tickets.append({
                    "id": year * 10_000 + n, "created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "requester": {"email": self.messy(person.email), "name": f"{person.first_name} {person.last_name}"},
                    "subject": subject, "description": f"Hello, {subject.lower()} Thanks, {person.first_name}",
                    "tags": [category], "status": self.rng.choice(("solved", "solved", "closed", "open")),
                    "via": {"channel": self.rng.choice(("email", "web", "chat"))},
                    "satisfaction_rating": {"score": self.rng.choice(("good", "good", "bad", "unoffered"))},
                    "custom_fields": [{"id": ORDER_FIELD, "value": order_number},
                                      {"id": PRODUCT_FIELD, "value": self.rng.choice(skus)}],
                    "metrics": {"reply_time_in_minutes": {"calendar": min(
                        round(self.rng.lognormvariate(math.log(FIRST_REPLY_HOURS * 60), 0.8)), 72 * 60)}},
                })
        tickets.sort(key=lambda t: t["created_at"])
        write_jsonl(out / "zendesk" / "tickets.jsonl", tickets)


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8", newline="\n")


def write_csv(path, header, rows, delimiter=","):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=delimiter, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def generate(out, seed=2026, scale=1.0):
    """Write every source into `out` (emptied first). Same seed and scale give the same files."""
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    g = Generator(seed, scale)
    g.make_people()
    g.make_products()
    g.shopify(out)   # first: Shopify decides who has an account
    g.pos(out)
    g.erp(out)       # after Shopify and POS: the general ledger sums their sales
    g.klaviyo(out)
    g.ga4(out)
    g.social(out)
    g.zendesk(out)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=POC / "data" / "landing", type=Path)
    parser.add_argument("--seed", default=2026, type=int)
    parser.add_argument("--scale", default=1.0, type=float, help="fraction of the 1 %% sample, for quick tests")
    args = parser.parse_args()
    print(f"Synthetic sources written to {generate(args.out, args.seed, args.scale)}")

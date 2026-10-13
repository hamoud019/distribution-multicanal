"""Sales Performance dashboard (issue #10): the demo of the first use case of the study.

Open it with:  py -3.12 poc/run.py --dashboard

This file only draws the page. Every figure comes from sales.py, which reads the gold marts only.
"""

import calendar
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sales  # noqa: E402

THIS_YEAR_COLOUR, LAST_YEAR_COLOUR = "#2a78d6", "#8e8d87"  # blue for the chosen year, grey for last year
MONTHS = list(range(1, 13))
GLOSSARY = """
- **Net revenue**: what we sold minus discounts and returns, excluding VAT and shipping fees.
- **Margin**: net revenue minus the production cost of the units (unit cost from the ERP).
- **Units**: items sold minus items returned.
- **Order**: a confirmed purchase (a web order, a store ticket or a wholesale order); cancelled orders do not count.
- **Average basket**: net revenue divided by the number of orders.
- **Return**: counted on the day the refund is made, so it lowers the month of the refund.
- **Click-and-collect**: a web order collected in a store. It stays in the Web channel, and its location is the store,
  so the store gets the credit.
- **Last year**: the same months of the year before, with the same filters.
"""


def euros(value, cents=False):
    """1,234 € (or 63.40 € with cents); thousands as k€ to fit the tiles."""
    if pd.isna(value):
        return "–"
    if not cents and abs(value) >= 10_000:
        return f"{value / 1000:,.1f} k€"
    return f"{value:,.{2 if cents else 0}f} €"


def change(now, before):
    """Change against last year, in %, for the KPI tiles."""
    if pd.isna(now) or pd.isna(before) or before == 0:
        return None
    return f"{(now - before) / abs(before):+.1%}"


def sidebar_filters(choices):
    st.sidebar.header("Filters")
    year = st.sidebar.selectbox("Year", choices["years"], index=len(choices["years"]) - 1)
    first, last = st.sidebar.select_slider("Months", MONTHS, value=(1, 12), format_func=lambda m: calendar.month_abbr[m])
    channels = st.sidebar.multiselect("Channel", choices["channels"], placeholder="All channels")
    locations = st.sidebar.multiselect("Location (store)", list(choices["locations"]),
                                       format_func=choices["locations"].get, placeholder="All locations")
    st.sidebar.caption("Click-and-collect web orders count for the store that hands them over, "
                       "so a store manager sees them under their store (they stay in the Web channel).")
    categories = st.sidebar.multiselect("Category", choices["categories"], placeholder="All categories")
    st.sidebar.caption("An empty list means everything.")
    return sales.Filters(year, first, last, tuple(channels), tuple(locations), tuple(categories))


def kpi_tiles(total):
    row = total.iloc[0]
    tiles = st.columns(6)
    tiles[0].metric("Net revenue", euros(row.net_revenue), change(row.net_revenue, row.net_revenue_ly), border=True)
    tiles[1].metric("Margin", euros(row.margin), change(row.margin, row.margin_ly), border=True)
    points = None if pd.isna(row.margin_rate) or pd.isna(row.margin_rate_ly) else         f"{(row.margin_rate - row.margin_rate_ly) * 100:+.1f} pts"
    tiles[2].metric("Margin %", "–" if pd.isna(row.margin_rate) else f"{row.margin_rate:.1%}", points, border=True)
    tiles[3].metric("Units", f"{row.units:,.0f}", change(row.units, row.units_ly), border=True)
    tiles[4].metric("Orders", f"{row.orders:,.0f}", change(row.orders, row.orders_ly), border=True)
    tiles[5].metric("Average basket", euros(row.average_basket, cents=True),
                    change(row.average_basket, row.average_basket_ly), border=True)


def this_and_last_year(table, key, year):
    """The table in long form, one row per value and year, for the charts."""
    data = table.melt(key, ["net_revenue", "net_revenue_ly"], var_name="year", value_name="revenue")
    data["year"] = data["year"].map({"net_revenue": str(year), "net_revenue_ly": f"{year - 1} (last year)"})
    years = [str(year), f"{year - 1} (last year)"]
    colour = alt.Color("year:N", title=None, legend=alt.Legend(orient="top"),
                       scale=alt.Scale(domain=years, range=[THIS_YEAR_COLOUR, LAST_YEAR_COLOUR]))
    tooltip = [alt.Tooltip("year:N", title="Year"), alt.Tooltip("revenue:Q", title="Net revenue (€)", format=",.0f")]
    return data, years, colour, tooltip


def trend_chart(months, year):
    data, years, colour, tooltip = this_and_last_year(months, "month", year)
    return alt.Chart(data).mark_line(point=alt.OverlayMarkDef(size=60), strokeWidth=2).encode(
        x=alt.X("month:T", title=None, axis=alt.Axis(format="%b", tickCount="month")),
        y=alt.Y("revenue:Q", title="Net revenue (€, excl. VAT)"),
        color=colour,
        strokeDash=alt.StrokeDash("year:N", legend=None,  # last year dashed, so colour is not the only clue
                                  scale=alt.Scale(domain=years, range=[[1, 0], [5, 3]])),
        tooltip=[alt.Tooltip("month:T", title="Month", format="%B"), *tooltip],
    ).properties(height=300)


def breakdown_chart(table, year):
    data, years, colour, tooltip = this_and_last_year(table, "label", year)
    return alt.Chart(data).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("label:N", title=None, sort=list(table["label"])),
        yOffset=alt.YOffset("year:N", sort=years),
        x=alt.X("revenue:Q", title="Net revenue (€, excl. VAT)"),
        color=colour,
        tooltip=[alt.Tooltip("label:N", title="Row"), *tooltip],
    ).properties(height=alt.Step(16, **{"for": "offset"}))  # 16 px per bar


def breakdown_table(table, by, year):
    shown = pd.DataFrame({
        by: table["label"],
        f"Net revenue {year} (€)": table["net_revenue"].round(),
        f"Net revenue {year - 1} (€)": table["net_revenue_ly"].round(),
        "Change (%)": table["net_revenue_change"] * 100,
        "Margin (€)": table["margin"].round(),
        "Margin %": table["margin_rate"] * 100,
        "Units": table["units"],
        "Orders": table["orders"],
        "Average basket (€)": table["average_basket"],
    })
    formats = {"Change (%)": "%+.1f %%", "Margin %": "%.1f %%", "Average basket (€)": "%.2f"}
    columns = {name: st.column_config.NumberColumn(format=formats.get(name, "localized"))
               for name in shown.columns[1:]}
    st.dataframe(shown, hide_index=True, column_config=columns)


def main():
    st.set_page_config(page_title="Sales Performance", layout="wide")
    st.title("Sales Performance")
    st.caption("Le Slip Français, synthetic data (a 1 % sample, 2023–2025). All amounts in euros, excluding VAT. "
               "Read only from the gold marts: marts.fct_sales, dim_date, dim_product and dim_location.")

    if not sales.WAREHOUSE.exists():
        st.error("The warehouse is not built yet. Run `py -3.12 poc/run.py` first.")
        st.stop()
    with sales.connect() as con:  # opened read-only, and closed again so run.py can rebuild the warehouse
        filters = sidebar_filters(sales.options(con))
        total = sales.summary(con, filters)
        months = sales.monthly(con, filters)
        tables = {by: sales.summary(con, filters, by) for by in sales.BREAKDOWNS}

    period = f"{calendar.month_abbr[filters.first_month]}–{calendar.month_abbr[filters.last_month]} {filters.year}"
    st.subheader(f"{period}, compared with the same months of {filters.year - 1}")
    st.caption("Under each figure: the change against last year.")
    kpi_tiles(total)

    st.subheader("Net revenue by month")
    st.altair_chart(trend_chart(months, filters.year), use_container_width=True)

    st.subheader("Breakdown")
    tabs = st.tabs(["By channel", "By location (store)", "By category", "Top 15 products"])
    for tab, by in zip(tabs, sales.BREAKDOWNS):
        table = tables[by].head(15)
        with tab:
            if by == "Location":
                st.caption("Stores include the click-and-collect web orders they hand over. The warehouse "
                           "ships the other web orders and all wholesale orders.")
            if by in ("Category", "Product"):
                st.caption("An order with several categories or products counts once in each row, "
                           "so orders do not add up to the total.")
            st.altair_chart(breakdown_chart(table, filters.year), use_container_width=True)
            breakdown_table(table, by, filters.year)

    with st.expander("Definitions (business glossary)"):
        st.markdown(GLOSSARY)


main()

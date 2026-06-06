import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from typing import Optional

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Smart Shopping Price Tracker",
    page_icon="🛒",
    layout="wide",
)

# ─── API key ─────────────────────────────────────────────────────────────────

SERPAPI_KEY = ""
try:
    SERPAPI_KEY = st.secrets["SERPAPI_KEY"]
except Exception:
    pass

# ─── Constants ───────────────────────────────────────────────────────────────

STORE_SLUGS: dict[str, str] = {
    "amazon": "amazon",
    "walmart": "walmart",
    "target": "target",
    "walgreens": "walgreens",
    "cvs": "cvs-pharmacy",
    "costco": "costco",
    "samsclub": "sams-club",
    "sams": "sams-club",
    "bjswholesale": "bjs-wholesale-club",
    "bjs": "bjs-wholesale-club",
    "ulta": "ulta-beauty",
    "iherb": "iherb",
    "vitaminshoppe": "vitamin-shoppe",
    "dollargeneral": "dollar-general",
    "kroger": "kroger",
    "riteaid": "rite-aid",
}

FALLBACK_CASHBACK: dict[str, tuple[float, str]] = {
    "amazon": (5.0, "Rakuten"),
    "walmart": (3.5, "Rakuten"),
    "target": (4.0, "BeFrugal"),
    "walgreens": (7.0, "TopCashback"),
    "cvs": (5.0, "Rakuten"),
    "iherb": (8.0, "TopCashback"),
    "dollargeneral": (2.0, "Rakuten"),
    "costco": (1.0, "BeFrugal"),
    "ulta": (6.0, "TopCashback"),
    "vitaminshoppe": (5.0, "Rakuten"),
    "samsclub": (1.5, "Rakuten"),
    "kroger": (2.5, "BeFrugal"),
}

# Default shipping per order by store (assumes common free-shipping thresholds met)
DEFAULT_SHIPPING: dict[str, float] = {
    "amazon": 0.0,          # Amazon Prime
    "walmart": 0.0,         # Walmart+
    "target": 0.0,          # free over $35
    "walgreens": 4.99,
    "cvs": 4.99,
    "iherb": 2.99,
    "dollargeneral": 4.99,
    "costco": 0.0,          # member shipping
    "samsclub": 5.99,
    "ulta": 6.95,
    "vitaminshoppe": 5.95,
    "kroger": 3.99,
    "riteaid": 5.99,
}

# US state sales tax rates (approximate combined state+avg local)
STATE_TAX_RATES: dict[str, float] = {
    "No tax (OR/MT/NH/DE/AK)": 0.0,
    "CA — 8.68%": 8.68,
    "NY — 8.52%": 8.52,
    "TX — 8.19%": 8.19,
    "FL — 7.02%": 7.02,
    "IL — 8.73%": 8.73,
    "WA — 10.1%": 10.1,
    "PA — 6.0%": 6.0,
    "OH — 7.24%": 7.24,
    "GA — 7.35%": 7.35,
    "NC — 6.98%": 6.98,
    "AZ — 8.4%": 8.4,
    "NJ — 6.63%": 6.63,
    "VA — 5.73%": 5.73,
    "CO — 7.65%": 7.65,
    "MI — 6.0%": 6.0,
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def normalize_store(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def get_store_slug(name: str) -> Optional[str]:
    key = normalize_store(name)
    if key in STORE_SLUGS:
        return STORE_SLUGS[key]
    for k, slug in STORE_SLUGS.items():
        if k in key or key in k:
            return slug
    return None


def parse_unit_count(title: str) -> int:
    t = title.lower()
    for pattern in [
        r"pack\s+of\s+(\d+)",
        r"(\d+)\s*[-–]?\s*pack",
        r"(\d+)\s*count",
        r"(\d+)\s*ct\.?(?:\s|,|$)",
        r"set\s+of\s+(\d+)",
        r"(\d+)\s*piece",
        r"(\d+)\s*bottles?",
        r"(\d+)\s*tubes?",
        r"(\d+)\s*jars?",
    ]:
        m = re.search(pattern, t)
        if m:
            n = int(m.group(1))
            if 2 <= n <= 200:
                return n
    return 1


def default_shipping_for(store: str) -> float:
    return DEFAULT_SHIPPING.get(normalize_store(store), 4.99)


def effective_unit_price(
    unit_price: float,
    unit_count: int,
    shipping: float,
    tax_rate: float,
    cashback_rate: float,
) -> float:
    """True cost per unit: base + tax + shipping split − cashback (on product only)."""
    tax = unit_price * tax_rate / 100
    ship_per_unit = shipping / max(unit_count, 1)
    cashback_savings = unit_price * cashback_rate / 100
    return round(unit_price + tax + ship_per_unit - cashback_savings, 2)

# ─── Data fetching ───────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_cashback_rate(store: str) -> tuple[float, str]:
    key = normalize_store(store)
    fallback = FALLBACK_CASHBACK.get(key, (0.0, ""))
    slug = get_store_slug(store)
    if not slug:
        return fallback
    try:
        resp = requests.get(
            f"https://www.cashbackmonitor.com/cashback/{slug}/",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
            timeout=10,
        )
        text = BeautifulSoup(resp.text, "html.parser").get_text()
        rates = [
            float(m.group(1))
            for m in re.finditer(r"(\d+(?:\.\d+)?)\s*%", text)
            if 0 < float(m.group(1)) <= 40
        ]
        if rates:
            return max(rates), "CashbackMonitor"
    except Exception:
        pass
    return fallback


@st.cache_data(ttl=1800, show_spinner=False)
def search_products(query: str, api_key: str) -> tuple[list[dict], bool]:
    if not api_key:
        return _demo_data(query), True
    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_shopping",
                "q": query,
                "api_key": api_key,
                "num": 30,
            },
            timeout=15,
        )
        data = resp.json()
        if "error" in data:
            return _demo_data(query), True
        results = []
        for item in data.get("shopping_results", []):
            price = float(item.get("extracted_price") or 0)
            if price <= 0:
                continue
            title = item.get("title", "")
            store = item.get("source", "Unknown")
            unit_count = parse_unit_count(title)
            link = (item.get("link") or item.get("product_link") or "").strip()
            if not link:
                link = f"https://www.google.com/search?q={requests.compat.quote_plus(title)}+{requests.compat.quote_plus(store)}"
            results.append({
                "title": title,
                "store": store,
                "price": price,
                "unit_count": unit_count,
                "unit_price": round(price / max(unit_count, 1), 2),
                "link": link,
            })
        return (results, False) if results else (_demo_data(query), True)
    except Exception:
        return _demo_data(query), True


def _demo_data(query: str) -> list[dict]:
    stores = [
        ("Amazon", 8.49, [1, 6], 0.85, "https://www.amazon.com/s?k=" + query.replace(" ", "+")),
        ("Walmart", 7.97, [1, 2], 0.88, "https://www.walmart.com/search?q=" + query.replace(" ", "+")),
        ("Target", 8.99, [1], 1.0, "https://www.target.com/s?searchTerm=" + query.replace(" ", "+")),
        ("Walgreens", 9.99, [1], 1.0, "https://www.walgreens.com/search/results.jsp?Ntt=" + query.replace(" ", "+")),
        ("CVS", 10.49, [1], 1.0, "https://www.cvs.com/search?searchTerm=" + query.replace(" ", "+")),
        ("iHerb", 7.49, [1, 3], 0.90, "https://www.iherb.com/search?kw=" + query.replace(" ", "+")),
        ("Dollar General", 7.50, [1], 1.0, "https://www.dollargeneral.com/search?q=" + query.replace(" ", "+")),
        ("Costco", 34.99, [8], 0.82, "https://www.costco.com/CatalogSearch?keyword=" + query.replace(" ", "+")),
        ("Sam's Club", 32.99, [6], 0.84, "https://www.samsclub.com/search?searchTerm=" + query.replace(" ", "+")),
    ]
    out = []
    for store, base, packs, disc, base_link in stores:
        for pack in packs:
            total = round(base * pack * (disc if pack > 1 else 1.0), 2)
            out.append({
                "title": f"{query} (Pack of {pack})" if pack > 1 else query,
                "store": store,
                "price": total,
                "unit_count": pack,
                "unit_price": round(total / pack, 2),
                "link": base_link,
            })
    return out

# ─── Session state init ──────────────────────────────────────────────────────

for key, default in {
    "results": None,
    "is_demo": False,
    "last_query": "",
    "co_overrides": {},       # store → (min_rate, max_rate)
    "use_max_rate": True,
    "tax_rate": 7.02,         # Florida default
    "shipping_overrides": {}, # store → float (per order)
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ─── Header ──────────────────────────────────────────────────────────────────

st.markdown(
    """
    <div style="background:#0f172a;color:white;padding:1.5rem 2rem;
                border-radius:14px;margin-bottom:1.5rem;">
        <h1 style="margin:0;font-size:1.75rem;font-weight:700;">
            🛒 Smart Shopping Price Tracker
        </h1>
        <p style="margin:0.3rem 0 0;color:#94a3b8;font-size:0.9rem;">
            Compare prices with bulk savings, shipping, tax &amp; cashback — powered by CashbackMonitor
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─── Search bar ───────────────────────────────────────────────────────────────

col_q, col_btn = st.columns([5, 1])
with col_q:
    query_input = st.text_input(
        "Product search",
        value="",
        label_visibility="collapsed",
        placeholder="Search for a product…",
    )
with col_btn:
    search_btn = st.button("🔍 Search", type="primary", use_container_width=True)

if search_btn:
    with st.spinner("Searching for prices…"):
        r, demo = search_products(query_input, SERPAPI_KEY)
    st.session_state.results = r
    st.session_state.is_demo = demo
    st.session_state.last_query = query_input
    st.session_state.shipping_overrides = {}  # reset when new search

if st.session_state.results is None and query_input.strip():
    with st.spinner("Loading…"):
        r, demo = search_products(query_input, SERPAPI_KEY)
    st.session_state.results = r
    st.session_state.is_demo = demo
    st.session_state.last_query = query_input

if st.session_state.is_demo:
    st.warning(
        "**Demo mode** — sample prices shown. "
        "Add `SERPAPI_KEY` in Streamlit Cloud secrets (or `.streamlit/secrets.toml` locally) for live data.",
        icon="⚠️",
    )

results: list[dict] = st.session_state.results or []

# ─── Tax & Shipping settings ─────────────────────────────────────────────────

if results:
    unique_stores = sorted({r["store"] for r in results})

    with st.expander("🧾 Tax & Shipping Settings", expanded=False):
        # ── Tax ──────────────────────────────────────────────────────────────
        st.markdown("**Sales tax rate**")
        st.caption("Applied to product price. Cashback is calculated before tax is added.")

        tax_col1, tax_col2 = st.columns([2, 3])
        with tax_col1:
            tax_input = st.number_input(
                "Tax rate (%)",
                min_value=0.0, max_value=20.0,
                value=st.session_state.tax_rate,
                step=0.25,
                format="%.2f",
                key="tax_input",
            )
            st.session_state.tax_rate = tax_input

        with tax_col2:
            st.markdown("**Quick select by state:**")
            preset_cols = st.columns(4)
            state_items = list(STATE_TAX_RATES.items())
            for i, (label, rate) in enumerate(state_items):
                with preset_cols[i % 4]:
                    if st.button(label, key=f"tax_{label}", use_container_width=True):
                        st.session_state.tax_rate = rate
                        st.rerun()

        st.divider()

        # ── Shipping ─────────────────────────────────────────────────────────
        st.markdown("**Shipping cost per order** (edit inline)")
        st.caption(
            "Cost is split across units in a pack — bulk orders have lower shipping per unit. "
            "Defaults reflect typical free-shipping thresholds."
        )

        ship_data = pd.DataFrame([
            {
                "Store": s,
                "Shipping ($)": st.session_state.shipping_overrides.get(
                    s, default_shipping_for(s)
                ),
            }
            for s in unique_stores
        ])

        edited_ship = st.data_editor(
            ship_data,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "Store": st.column_config.TextColumn("Store", disabled=True),
                "Shipping ($)": st.column_config.NumberColumn(
                    "Shipping ($)", min_value=0.0, max_value=99.99,
                    step=0.50, format="$%.2f",
                ),
            },
            hide_index=True,
        )
        for _, row in edited_ship.iterrows():
            st.session_state.shipping_overrides[row["Store"]] = float(row["Shipping ($)"])

# ─── Capital One Shopping overrides ──────────────────────────────────────────

if results:
    with st.expander("💳 Capital One Shopping Overrides", expanded=False):
        st.caption(
            "Override per-store cashback with your personal Capital One Shopping offers. "
            "Supports ranges — e.g. enter 5 and 8 for a 5–8% offer."
        )

        st.session_state.use_max_rate = st.toggle(
            "Use max rate for ranges (optimistic)",
            value=st.session_state.use_max_rate,
        )
        st.divider()

        c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 1.5])
        with c1:
            new_store = st.selectbox("Store", [""] + unique_stores, key="new_store")
        with c2:
            new_min = st.number_input("Min %", 0.0, 50.0, 0.0, 0.5, key="new_min")
        with c3:
            new_max = st.number_input(
                "Max % (optional)", 0.0, 50.0, 0.0, 0.5, key="new_max",
                help="Leave at 0 to treat Min % as a fixed rate",
            )
        with c4:
            st.write("")
            if st.button("Add Override", type="secondary", use_container_width=True):
                if new_store and new_min > 0:
                    hi = new_max if new_max >= new_min else new_min
                    st.session_state.co_overrides[new_store] = (new_min, hi)
                    st.rerun()
                else:
                    st.warning("Select a store and enter a Min % > 0")

        if st.session_state.co_overrides:
            st.markdown("**Active overrides:**")
            to_remove: list[str] = []
            for store, (mn, mx) in list(st.session_state.co_overrides.items()):
                rate_str = f"{mn}%" if mn == mx else f"{mn}–{mx}%"
                oc1, oc2 = st.columns([6, 1])
                with oc1:
                    st.markdown(
                        f"<span style='background:#f3e8ff;border:1px solid #d8b4fe;"
                        f"border-radius:6px;padding:3px 12px;'>"
                        f"<b>{store}</b> — <span style='color:#7c3aed'>{rate_str}</span></span>",
                        unsafe_allow_html=True,
                    )
                with oc2:
                    if st.button("✕ Remove", key=f"rm_{store}"):
                        to_remove.append(store)
            for s in to_remove:
                del st.session_state.co_overrides[s]
            if to_remove:
                st.rerun()
        else:
            st.info("No overrides yet — add one above.")

# ─── Fetch cashback & build enriched results ─────────────────────────────────

if results:
    unique_stores_list = list({r["store"] for r in results})

    with st.spinner("Fetching cashback rates from CashbackMonitor…"):
        cashback_map: dict[str, tuple[float, str]] = {
            s: fetch_cashback_rate(s) for s in unique_stores_list
        }

    tax_rate = st.session_state.tax_rate

    rows = []
    for r in results:
        store = r["store"]
        unit_price = r["unit_price"]
        unit_count = r["unit_count"]

        # Shipping
        shipping = st.session_state.shipping_overrides.get(store, default_shipping_for(store))

        # Cashback
        if store in st.session_state.co_overrides:
            mn, mx = st.session_state.co_overrides[store]
            cb_rate = mx if st.session_state.use_max_rate else mn
            rate_range = f"{mn}–{mx}%" if mn != mx else f"{mn}%"
            via = f"💳 Capital One ({rate_range})"
        else:
            cb_rate, portal = cashback_map.get(store, (0.0, ""))
            via = f"🟢 {portal}" if cb_rate > 0 else "—"

        eff_unit = effective_unit_price(unit_price, unit_count, shipping, tax_rate, cb_rate)

        rows.append({
            "Store": store,
            "Product": r["title"],
            "Price": r["price"],
            "Pack": unit_count,
            "$/Unit": unit_price,
            "Ship.": shipping,
            "Cashback %": cb_rate,
            "Via": via,
            "Eff. $/Unit ★": eff_unit,
            "Link": r.get("link", "") or "",
            # Internal fields for card rendering
            "_tax_rate": tax_rate,
            "_shipping": shipping,
        })

    df = pd.DataFrame(rows)

    # Sort control
    sort_col, _ = st.columns([2, 5])
    with sort_col:
        sort_by = st.selectbox(
            "Sort by",
            ["Eff. $/Unit ★", "$/Unit", "Cashback %", "Price"],
            index=0,
        )

    ascending = sort_by != "Cashback %"
    df_sorted = df.sort_values(sort_by, ascending=ascending).reset_index(drop=True)

    # ── Top-3 deal cards ──────────────────────────────────────────────────────
    st.markdown("### 🏆 Top Deals")
    medals = ["🥇", "🥈", "🥉"]
    top_cols = st.columns(3)
    for i, (_, row) in enumerate(df_sorted.head(3).iterrows()):
        is_best = i == 0
        bg = "#f0fdf4" if is_best else "white"
        border = "#86efac" if is_best else "#e2e8f0"
        pack_str = f"Pack of {int(row['Pack'])}" if row["Pack"] > 1 else "Single"
        tax_amt = round(row["$/Unit"] * row["_tax_rate"] / 100, 2)
        ship_unit = round(row["_shipping"] / max(row["Pack"], 1), 2)
        cashback_amt = round(row["$/Unit"] * row["Cashback %"] / 100, 2)

        breakdown = (
            f'<div style="font-size:0.72rem;color:#64748b;margin-top:5px;line-height:1.6;">'
            f'${row["$/Unit"]:.2f} base'
            + (f' + ${tax_amt:.2f} tax' if tax_amt > 0 else '')
            + (f' + ${ship_unit:.2f} ship' if ship_unit > 0 else '')
            + (f' − ${cashback_amt:.2f} cashback' if cashback_amt > 0 else '')
            + '</div>'
        )
        cashback_html = (
            f'<div style="font-size:0.8rem;color:#7c3aed;margin-top:3px">'
            f'{row["Via"]} · {row["Cashback %"]:.1f}%</div>'
            if row["Cashback %"] > 0 else ""
        )
        link_html = (
            f'<div style="margin-top:6px"><a href="{row["Link"]}" target="_blank" '
            f'style="font-size:0.8rem;color:#3b82f6;text-decoration:none;">View product →</a></div>'
            if row["Link"] else ""
        )

        with top_cols[i]:
            st.markdown(
                f"""<div style="background:{bg};border:1px solid {border};
                border-radius:12px;padding:1rem;text-align:center;margin-bottom:0.5rem;">
                <div style="font-size:1.5rem">{medals[i]}</div>
                <div style="font-weight:700;font-size:1rem">{row['Store']}</div>
                <div style="font-size:1.6rem;font-weight:800;
                     color:{'#16a34a' if is_best else '#1e293b'}">
                    ${row['Eff. $/Unit ★']:.2f}
                    <span style="font-size:0.9rem;font-weight:400">/unit</span>
                </div>
                <div style="font-size:0.8rem;color:#64748b">
                    {pack_str} &middot; ${row['Price']:.2f} total
                </div>
                {cashback_html}{breakdown}{link_html}
                </div>""",
                unsafe_allow_html=True,
            )

    # ── Full results table ────────────────────────────────────────────────────
    st.markdown("### 📋 All Results")

    display_df = df_sorted[
        ["Store", "Product", "Price", "Pack", "$/Unit", "Ship.", "Cashback %", "Via", "Eff. $/Unit ★", "Link"]
    ].copy()
    display_df.index = display_df.index + 1

    st.dataframe(
        display_df,
        use_container_width=True,
        height=min(60 + len(display_df) * 38, 640),
        column_config={
            "Store": st.column_config.TextColumn("Store", width=110),
            "Product": st.column_config.TextColumn("Product", width=260),
            "Price": st.column_config.NumberColumn("Price", format="$%.2f", width=85),
            "Pack": st.column_config.NumberColumn("Pack", format="%d×", width=65),
            "$/Unit": st.column_config.NumberColumn("$/Unit", format="$%.2f", width=85),
            "Ship.": st.column_config.NumberColumn("Ship.", format="$%.2f", width=75),
            "Cashback %": st.column_config.NumberColumn("Cashback %", format="%.1f%%", width=100),
            "Via": st.column_config.TextColumn("Via", width=200),
            "Eff. $/Unit ★": st.column_config.NumberColumn("★ Eff. $/Unit", format="$%.2f", width=115),
            "Link": st.column_config.LinkColumn("Link", display_text="View", width=70),
        },
    )

    # Legend
    tax_note = f" + {tax_rate:.2f}% tax" if tax_rate > 0 else ""
    st.caption(
        f"🟢 CashbackMonitor rate &nbsp;·&nbsp; 💳 Capital One Shopping override &nbsp;·&nbsp; "
        f"★ Eff. $/Unit = $/Unit{tax_note} + ship/unit − cashback on product"
    )

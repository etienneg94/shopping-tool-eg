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

# ─── API key (from Streamlit secrets or env) ─────────────────────────────────

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

# ─── Data fetching ───────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_cashback_rate(store: str) -> tuple[float, str]:
    """Scrape CashbackMonitor for the best cashback rate at a store."""
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
    """Search Google Shopping via SerpAPI. Returns (results, is_demo)."""
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
            unit_count = parse_unit_count(title)
            results.append({
                "title": title,
                "store": item.get("source", "Unknown"),
                "price": price,
                "unit_count": unit_count,
                "unit_price": round(price / max(unit_count, 1), 2),
                "link": item.get("link", ""),
            })
        return (results, False) if results else (_demo_data(query), True)
    except Exception:
        return _demo_data(query), True


def _demo_data(query: str) -> list[dict]:
    stores = [
        ("Amazon", 8.49, [1, 6], 0.85),
        ("Walmart", 7.97, [1, 2], 0.88),
        ("Target", 8.99, [1], 1.0),
        ("Walgreens", 9.99, [1], 1.0),
        ("CVS", 10.49, [1], 1.0),
        ("iHerb", 7.49, [1, 3], 0.90),
        ("Dollar General", 7.50, [1], 1.0),
        ("Costco", 34.99, [8], 0.82),
        ("Sam's Club", 32.99, [6], 0.84),
    ]
    out = []
    for store, base, packs, disc in stores:
        for pack in packs:
            total = round(base * pack * (disc if pack > 1 else 1.0), 2)
            out.append({
                "title": f"{query} (Pack of {pack})" if pack > 1 else query,
                "store": store,
                "price": total,
                "unit_count": pack,
                "unit_price": round(total / pack, 2),
                "link": "",
            })
    return out

# ─── Session state init ──────────────────────────────────────────────────────

for key, default in {
    "results": None,
    "is_demo": False,
    "last_query": "",
    "co_overrides": {},     # store → (min_rate, max_rate)
    "use_max_rate": True,
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
            Compare prices with bulk savings &amp; cashback — powered by CashbackMonitor
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
        value="got2b gel",
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

# Auto-load on first visit
if st.session_state.results is None:
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

# ─── Capital One Shopping overrides ──────────────────────────────────────────

if results:
    unique_stores = sorted({r["store"] for r in results})

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
            st.write("")  # vertical spacer
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

    rows = []
    for r in results:
        store = r["store"]
        if store in st.session_state.co_overrides:
            mn, mx = st.session_state.co_overrides[store]
            cb_rate = mx if st.session_state.use_max_rate else mn
            rate_range = f"{mn}–{mx}%" if mn != mx else f"{mn}%"
            via = f"💳 Capital One ({rate_range})"
        else:
            cb_rate, portal = cashback_map.get(store, (0.0, ""))
            via = f"🟢 {portal}" if cb_rate > 0 else "—"

        eff_unit = round(r["unit_price"] * (1 - cb_rate / 100), 2)
        rows.append({
            "Store": store,
            "Product": r["title"],
            "Total $": r["price"],
            "Pack": r["unit_count"],
            "$/Unit": r["unit_price"],
            "Cashback %": cb_rate,
            "Via": via,
            "Eff. $/Unit ★": eff_unit,
            "_link": r.get("link", ""),
        })

    df = pd.DataFrame(rows)

    # Sort control
    sort_col, _ = st.columns([2, 5])
    with sort_col:
        sort_by = st.selectbox(
            "Sort by",
            ["Eff. $/Unit ★", "$/Unit", "Cashback %", "Total $"],
            index=0,
        )

    ascending = sort_by != "Cashback %"
    df_sorted = df.sort_values(sort_by, ascending=ascending).reset_index(drop=True)

    # ── Top-3 deal cards ──────────────────────────────────────────────────────
    st.markdown("### 🏆 Top Deals")
    medals = ["🥇", "🥈", "🥉"]
    top_cols = st.columns(3)
    for i, (_, row) in enumerate(df_sorted.head(3).iterrows()):
        savings = round(row["$/Unit"] - row["Eff. $/Unit ★"], 3)
        is_best = i == 0
        bg = "#f0fdf4" if is_best else "white"
        border = "#86efac" if is_best else "#e2e8f0"
        pack_str = f"Pack of {int(row['Pack'])}" if row["Pack"] > 1 else "Single"
        cashback_html = (
            f'<div style="font-size:0.8rem;color:#7c3aed;margin-top:4px">'
            f'{row["Via"]} · {row["Cashback %"]:.1f}%</div>'
            if row["Cashback %"] > 0 else ""
        )
        savings_html = (
            f'<div style="font-size:0.8rem;color:#16a34a">saves ${savings:.2f}/unit</div>'
            if savings > 0 else ""
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
                    {pack_str} &middot; ${row['Total $']:.2f} total
                </div>
                {cashback_html}{savings_html}
                </div>""",
                unsafe_allow_html=True,
            )

    # ── Full results table ────────────────────────────────────────────────────
    st.markdown("### 📋 All Results")

    display_df = df_sorted[
        ["Store", "Product", "Total $", "Pack", "$/Unit", "Cashback %", "Via", "Eff. $/Unit ★"]
    ].copy()
    display_df.index = display_df.index + 1

    st.dataframe(
        display_df,
        use_container_width=True,
        height=min(60 + len(display_df) * 38, 620),
        column_config={
            "Store": st.column_config.TextColumn("Store", width=120),
            "Product": st.column_config.TextColumn("Product", width=280),
            "Total $": st.column_config.NumberColumn("Total $", format="$%.2f", width=90),
            "Pack": st.column_config.NumberColumn("Pack", format="%d×", width=70),
            "$/Unit": st.column_config.NumberColumn("$/Unit", format="$%.2f", width=90),
            "Cashback %": st.column_config.NumberColumn("Cashback %", format="%.1f%%", width=105),
            "Via": st.column_config.TextColumn("Via", width=210),
            "Eff. $/Unit ★": st.column_config.NumberColumn("★ Eff. $/Unit", format="$%.2f", width=115),
        },
    )

    # Product links
    link_rows = df_sorted[df_sorted["_link"].str.len() > 0][["Store", "Product", "_link"]]
    if not link_rows.empty:
        with st.expander("🔗 Product Links"):
            for _, row in link_rows.iterrows():
                st.markdown(f"- [{row['Store']} — {row['Product'][:70]}]({row['_link']})")

    st.caption(
        "🟢 CashbackMonitor rate &nbsp;·&nbsp; 💳 Capital One Shopping override &nbsp;·&nbsp; "
        "★ Eff. $/Unit = $/Unit × (1 − Cashback%)"
    )

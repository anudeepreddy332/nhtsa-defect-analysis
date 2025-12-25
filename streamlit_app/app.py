import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
import os
from dotenv import load_dotenv
from pathlib import Path

# Load env
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Page config
st.set_page_config(
    page_title="NHTSA Silent Recall Detector",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database connection
@st.cache_resource
def get_connection_factory():
    db_url = os.getenv("SUPABASE_DB_URL") or st.secrets.get("SUPABASE_DB_URL")
    if not db_url:
        st.error("SUPABASE_DB_URL not configured")
        st.stop()
    return lambda: psycopg2.connect(db_url)

conn_factory = get_connection_factory()

# Sidebar
st.sidebar.title("🚗 NHTSA Dashboard")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    [
        "🏠 Overview",
        "🚨 Silent Recalls",
        "🧠 Systemic Risk",
        "📊 Components",
        "📈 Trends"
    ]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Data Freshness")

# ETL status
try:
    with conn_factory() as conn:
        etl_status = pd.read_sql(
            """
            SELECT key, value, updated_at
            FROM etl_state
            WHERE key IN ('last_recall_fetch', 'total_recalls_loaded')
            ORDER BY key
            """,
            conn
        )
    for _, row in etl_status.iterrows():
        st.sidebar.metric(row["key"], row["value"])
except Exception:
    st.sidebar.warning("ETL status unavailable")

st.sidebar.caption("Automated via GitHub Actions • Weekly")

# ======================
# Helper functions
# ======================

@st.cache_data(ttl=600)
def load_overview_metrics():
    with conn_factory() as conn:
        return pd.read_sql(
            """
            SELECT
                (SELECT COUNT(*) FROM flat_rcl) AS total_recalls,
                (SELECT COUNT(*) FROM flat_cmpl) AS total_complaints,
                (SELECT COUNT(*) FROM vehicle_risk_scores) AS vehicles_tracked,
                (SELECT COUNT(*) FROM vehicle_risk_scores
                 WHERE risk_category IN ('HIGH','CRITICAL')) AS high_risk_vehicles,
                (SELECT COUNT(*) FROM vehicle_risk_scores
                 WHERE total_recalls = 0
                   AND risk_category IN ('HIGH','CRITICAL')) AS zero_recall_high_risk
            """,
            conn
        ).iloc[0]

@st.cache_data(ttl=600)
def load_top_risk():
    with conn_factory() as conn:
        df = pd.read_sql(
            """
            SELECT
                MAKETXT AS make,
                MODELTXT AS model,
                YEARTXT AS year,
                total_complaints,
                total_recalls,
                ROUND((total_complaints::FLOAT / NULLIF(total_recalls, 0))::NUMERIC, 1) AS risk_ratio,
                risk_category
            FROM vehicle_risk_scores
            WHERE total_recalls > 0
            ORDER BY risk_ratio DESC
            """,
            conn
        )
    df = df.reset_index(drop=True)
    df.index = df.index + 1
    return df

@st.cache_data(ttl=600)
def load_zero_recall():
    with conn_factory() as conn:
        df = pd.read_sql(
            """
            SELECT
                MAKETXT AS make,
                MODELTXT AS model,
                YEARTXT AS year,
                total_complaints,
                risk_category
            FROM vehicle_risk_scores
            WHERE total_recalls = 0
              AND risk_category IN ('HIGH','CRITICAL')
            ORDER BY total_complaints DESC
            """,
            conn
        )
    df = df.reset_index(drop=True)
    df.index = df.index + 1
    return df

@st.cache_data(ttl=600)
def load_repeat_offenders():
    with conn_factory() as conn:
        df = pd.read_sql(
            """
            SELECT
                MAKETXT AS make,
                MODELTXT AS model,
                years_in_top10,
                total_complaints,
                problem_years
            FROM repeat_offenders
            ORDER BY years_in_top10 DESC, total_complaints DESC
            """,
            conn
        )
    df = df.reset_index(drop=True)
    df.index = df.index + 1
    return df


@st.cache_data(ttl=600)
def load_component_cost_impact():
    with conn_factory() as conn:
        df = pd.read_sql(
            """
            SELECT
                COMPDESC AS component,
                total_complaints,
                crash_count,
                total_injuries,
                estimated_cost,
                savings_if_reduced_10pct
            FROM component_cost_impact
            ORDER BY estimated_cost DESC
            """,
            conn
        )
    df = df.reset_index(drop=True)
    df.index = df.index + 1
    return df


# ======================
# Pages
# ======================

if page == "🏠 Overview":
    st.title("🚗 NHTSA Silent Recall Analysis")
    st.markdown("**Detecting vehicles with unusually high complaints relative to recalls**")

    m = load_overview_metrics()
    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Total Recalls", f"{m.total_recalls:,}")
    c2.metric("Total Complaints", f"{m.total_complaints:,}")
    c3.metric("Vehicles Tracked", f"{m.vehicles_tracked:,}")
    c4.metric(
        "High Risk Vehicles",
        f"{m.high_risk_vehicles:,}",
        help="Includes extreme complaint-to-recall ratios and zero-recall cases"
    )
    c5.metric(
        "🚨 Zero-Recall High Risk",
        f"{m.zero_recall_high_risk:,}",
        help="Vehicles with many complaints and ZERO recalls (highest priority)"
    )

    st.markdown("---")
    st.subheader("🚨 Zero-Recall High-Risk Vehicles")

    zr = load_zero_recall()
    if zr.empty:
        st.success("No zero-recall high-risk vehicles detected.")
    else:
        st.warning("High complaint volume with **ZERO recalls**")
        st.dataframe(zr, use_container_width=True)

    st.markdown("---")
    st.subheader("🧨 Top Silent Recall Candidates")

    top_risk = load_top_risk()

    fig = px.bar(
        top_risk,
        x="model",
        y="risk_ratio",
        color="risk_category",
        hover_data=["make", "year", "total_complaints", "total_recalls"],
        title="Complaints per Recall (Higher = Worse)",
        color_discrete_map={
            'CRITICAL': '#ff4444',
            'HIGH': '#ff8800',
            'MEDIUM': '#ffbb33',
            'LOW': '#00C851'
        }
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(top_risk, use_container_width=True)

elif page == "🚨 Silent Recalls":
    st.title("🚨 Silent Recalls Detector")

    with conn_factory() as conn:
        makes = pd.read_sql(
            "SELECT DISTINCT MAKETXT FROM vehicle_risk_scores ORDER BY MAKETXT",
            conn
        )["maketxt"].tolist()

    selected_makes = st.multiselect("Select Manufacturers", makes, default=makes[:5])

    if selected_makes:
        placeholders = ",".join(["%s"] * len(selected_makes))
        with conn_factory() as conn:
            df = pd.read_sql(
                f"""
                SELECT
                    MAKETXT AS make,
                    MODELTXT AS model,
                    YEARTXT AS year,
                    total_complaints,
                    total_recalls,
                    risk_category
                FROM vehicle_risk_scores
                WHERE MAKETXT IN ({placeholders})
                ORDER BY total_complaints DESC
                """,
                conn,
                params=selected_makes
            )

        df = df.reset_index(drop=True)
        df.index = df.index + 1

        fig = px.scatter(
            df,
            x="total_recalls",
            y="total_complaints",
            size="total_complaints",
            color="risk_category",
            hover_data=["make", "model", "year"],
            title="Complaints vs Recalls"
        )

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)

    else:
        st.warning("Select at least one manufacturer")

    st.markdown("---")
    st.subheader("📦 Vehicles With Multiple Recalls (Manufacturer Acknowledged Issues)")

    with conn_factory() as conn:
        trv = pd.read_sql(
            """
            SELECT
                MAKETXT AS make,
                MODELTXT AS model,
                YEARTXT AS year,
                recall_count,
                total_units_affected
            FROM top_recalled_vehicles
            ORDER BY recall_count DESC
            LIMIT 20
            """,
            conn
        )

    trv = trv.reset_index(drop=True)
    trv.index = trv.index + 1

    st.caption(
        "These vehicles have multiple official recalls, indicating acknowledged safety action "
        "(contrast with zero-recall high-risk vehicles above)."
    )
    st.dataframe(trv, use_container_width=True)


elif page == "🧠 Systemic Risk":
    st.title("🧠 Systemic Safety Risk Analysis")
    st.markdown(
        """
        This section highlights **long-term and structural safety risks** that are **not visible through short-term recall activity alone**.
        """
    )

    # =====================
    # Repeat Offenders
    # =====================
    st.markdown("---")
    st.subheader("🔁 Repeat Offender Vehicles")
    st.caption(
        "Vehicles that ranked in the **top 10 complaint volume** for at least **3 different years** (2020–2024)."
    )

    repeat_df = load_repeat_offenders()

    if repeat_df.empty:
        st.info("No repeat offenders detected for this period.")
    else:
        st.warning(
            "These vehicles show **persistent safety issues across multiple years**, "
            "indicating systemic defects rather than isolated incidents."
        )
        st.dataframe(repeat_df, use_container_width=True)

    # =====================
    # Component Cost Impact
    # =====================
    st.markdown("---")
    st.subheader("💰 Component-Level Cost & Injury Impact")
    st.caption(
        "Estimated economic and injury burden based on complaint volume, crashes, and injuries."
    )

    cost_df = load_component_cost_impact()

    if cost_df.empty:
        st.info("No component cost data available.")
    else:
        fig = px.bar(
            cost_df.head(15),
            x="component",
            y="estimated_cost",
            hover_data=[
                "total_complaints",
                "crash_count",
                "total_injuries",
                "savings_if_reduced_10pct"
            ],
            title="Top Components by Estimated Safety Cost (2020–2024)",
            labels={"estimated_cost": "Estimated Cost ($)"}
        )

        fig.update_layout(
            xaxis_title="Component",
            yaxis_title="Estimated Cost ($)",
            height=500
        )

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(cost_df, use_container_width=True)

    st.markdown(
        """
        **Why this matters:**  
        These insights help prioritize **preventive engineering fixes** and
        **regulatory action** where they would reduce the most harm.
        """
    )



elif page == "📊 Components":
    st.title("📊 Component Failure Analysis")

    with conn_factory() as conn:
        df = pd.read_sql(
            """
            SELECT
                COMPDESC AS component,
                total_complaints,
                crash_related,
                fire_related,
                total_injuries
            FROM component_analysis
            ORDER BY total_complaints DESC
            LIMIT 20
            """,
            conn
        )

    df = df.reset_index(drop=True)
    df.index = df.index + 1

    fig = go.Figure()
    fig.add_bar(
        x=df.component,
        y=df.total_complaints,
        name="Total Complaints"
    )
    fig.add_scatter(
        x=df.component,
        y=df.total_complaints.cumsum() / df.total_complaints.sum() * 100,
        name="Cumulative %",
        yaxis="y2"
    )
    fig.update_layout(
        yaxis2=dict(overlaying="y", side="right", title="Cumulative %"),
        legend=dict(title="Metric"),
        title="Component Pareto Chart"
    )

    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True)

elif page == "📈 Trends":
    st.title("📈 Complaint Trends Over Time")

    with conn_factory() as conn:
        trends = pd.read_sql(
            """
            SELECT 
                year,
                total_complaints,
                crashes,
                fires,
                injuries,
                deaths
            FROM yearly_trends
            ORDER BY year
            """,
            conn
        )

    trends = trends.reset_index(drop=True)
    trends.index = trends.index + 1

    fig = px.line(
        trends,
        x="year",
        y=["total_complaints", "crashes", "fires"],
        title="Yearly Complaint Trends",
        labels={"value": "Count", "variable": "Category"}
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(trends, use_container_width=True)

st.markdown("---")
st.caption("NHTSA • Supabase PostgreSQL • GitHub Actions • Streamlit")
import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
import os
from dotenv import load_dotenv
from pathlib import Path

project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
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
    """Returns a function that creates NEW DB connections when called.
    This avoids stale connections in Streamlit."""

    # Try environment variable first (local development)
    db_url = os.getenv("SUPABASE_DB_URL")

    # Fall back to Streamlit secrets (cloud deployment)
    if not db_url:
        try:
            db_url = st.secrets["SUPABASE_DB_URL"]
        except Exception:
            pass

    if not db_url:
        st.error("⚠️ Database URL not found. Add SUPABASE_DB_URL to .env file or Streamlit secrets.")
        st.stop()

    return lambda: psycopg2.connect(db_url)


conn_factory = get_connection_factory()

# Sidebar
st.sidebar.title("🚗 NHTSA Dashboard")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    ["🏠 Overview", "🚨 Silent Recalls", "📊 Components", "📈 Trends"]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Data Freshness")

# Get ETL status without crashing
try:
    with conn_factory() as conn:
        etl_status = pd.read_sql("""
            SELECT key, value, updated_at
            FROM etl_state
            WHERE key IN ('last_recall_fetch', 'total_recalls_loaded')
            ORDER BY key
        """, conn)

    for _, row in etl_status.iterrows():
        if row['key'] == 'last_recall_fetch':
            st.sidebar.metric("Last ETL Run", row['value'])
        elif row['key'] == 'total_recalls_loaded':
            st.sidebar.metric("Recalls Tracked", row['value'])


except Exception:
    st.sidebar.warning("ETL status unavailable")

st.sidebar.caption("Automated via GitHub Actions * Updates weekly")

# ==== Helper Functions ====

@st.cache_data(ttl=600)
def load_overview_metrics():
    with conn_factory() as conn:
        return pd.read_sql(
            """
            SELECT
                (SELECT COUNT(*) FROM flat_rcl) AS total_recalls,
                (SELECT COUNT(*) FROM flat_cmpl) AS total_complaints,
                (SELECT COUNT(DISTINCT MAKETXT || MODELTXT || YEARTXT) FROM flat_rcl) AS vehicles_tracked,
                (SELECT COUNT(*) FROM vehicle_risk_scores WHERE risk_category IN ('HIGH', 'CRITICAL')) AS high_risk_vehicles
            """,
        conn).iloc[0]

@st.cache_data(ttl=600)
def load_top_risk():
    with conn_factory() as conn:
        return pd.read_sql(
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
            """,
        conn)

# ==== Overview Page ====

if page == "🏠 Overview":
    st.title("🚗 NHTSA Silent Recall Analysis")
    st.markdown("**Detecting vehicles with unusually high complaints relative to recalls**")

    metrics = load_overview_metrics()

    # Hero metrics
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Recalls", f"{metrics['total_recalls']:,}")
    col2.metric("Total Complaints", f"{metrics['total_complaints']:,}")
    col3.metric("Vehicles Tracked", f"{metrics['vehicles_tracked']:,}")
    col4.metric("High Risk Vehicles", f"{metrics['high_risk_vehicles']:,}")

    st.markdown("---")
    st.subheader("🧨 Top Silent Recall Candidates")

    top_risk = load_top_risk()

    # Bar chart
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
    st.dataframe(top_risk, use_container_width=True, hide_index=True)
    st.info(
        f"""
        **Key Insight:**
        {top_risk.iloc[0]['make']} {top_risk.iloc[0]['model']} ({top_risk.iloc[0]['year']})
        shows **{top_risk.iloc[0]['risk_ratio']} complaints per recall**
        """
    )

# ==== Silent Recall Page ====

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
        st.dataframe(df, use_container_width=True, hide_index=True)

    else:
        st.warning("Select at least one manufacturer")

# ==== Components Page ====

elif page == "📊 Components":
    st.title("📊 Component Failure Analysis")

    with conn_factory() as conn:
        components = pd.read_sql(
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
            """, conn
        )

    components["cumulative_pct"] = (
        components["total_complaints"].cumsum() /
        components["total_complaints"].sum()
        * 100
    )

    fig = go.Figure()
    fig.add_bar(
        x=components["component"],
        y=components["total_complaints"],
        name="Complaints"
    )
    fig.add_scatter(
        x=components["component"],
        y=components["cumulative_pct"],
        name="Cumulative %",
        yaxis="y2"
    )
    fig.update_layout(
        yaxis2=dict(overlaying="y", side="right", range=[0,100]),
        title="Component Pareto Chart"
    )

    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(components, use_container_width=True, hide_index=True)

# ==== Trends Page ====
elif page == "📈 Trends":
    st.title("📈 Complaint Trends Over Time")

    try:
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

            # Multi-line chart
        fig = px.line(
            trends,
            x="year",
            y=["total_complaints", "crashes", "fires"],
            labels={"value": "Count", "variable": "Category"},
            title="Yearly Complaint Trends (2015-2024)"
        )
        fig.update_layout(height=500, hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)

        # Show data table
        st.dataframe(
            trends.style.background_gradient(subset=['total_complaints'], cmap='Reds'),
            use_container_width=True,
            hide_index=True
        )

        # Recall volume by manufacturer
        st.markdown("---")
        st.subheader("📦 Recall Volume by Manufacturer")

        with conn_factory() as conn:
            recalls_by_make = pd.read_sql(
                """
                SELECT 
                    MAKETXT AS make,
                    COUNT(*) AS recall_count,
                    SUM(POTAFF) AS total_vehicles_affected
                FROM flat_rcl
                GROUP BY MAKETXT
                ORDER BY recall_count DESC
                LIMIT 15
                """,
                conn
            )

        fig2 = px.bar(
            recalls_by_make,
            x="make",
            y="recall_count",
            hover_data=["total_vehicles_affected"],
            labels={"recall_count": "Number of Recalls", "make": "Manufacturer"},
            title="Top 15 Manufacturers by Recall Count",
            color="recall_count",
            color_continuous_scale="Reds"
        )

        fig2.update_layout(height=500)
        st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(recalls_by_make, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Could not load trend  {e}")
        st.info("The yearly_trends table may not exist. Run the ETL pipeline to generate it.")

# ==== Footer ====
st.markdown("---")
st.caption(
    "Data: NHTSA • Database: Supabase PostgreSQL • ETL: GitHub Actions • Dashboard: Streamlit"
)
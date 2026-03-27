import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
import toml
import time
import psutil
import json
import base64

# Add monorepo root directory to Python path for shared modules
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

# Import performance monitoring
from common.utils.performance_monitor import (
    performance_monitor, 
    time_it, 
    monitor_cache, 
    monitor_db_operation,
    measure_time,
    measure_memory
)

# Environment detection and session setup
@st.cache_resource
@monitor_cache("get_snowflake_session")
def get_snowflake_session():
    """
    Cached Snowflake session to avoid re-authentication on every page load.
    Get Snowflake session - either from SiS (get_active_session) or standalone (connector)
    Returns: (session, deployment_mode) tuple
    """
    # First, always try SiS (Streamlit in Snowflake) mode
    try:
        from snowflake.snowpark.context import get_active_session
        session = get_active_session()
        # Test the session with a simple query to ensure it's working
        session.sql("SELECT CURRENT_VERSION()").collect()
        return session, 'SiS'
    except Exception as sis_error:
        # If SiS fails, fall back to standalone mode
        try:
            return _get_standalone_session()
        except Exception as standalone_error:
            st.error("Failed to establish Snowflake connection in both SiS and standalone modes")
            st.error(f"SiS Error: {str(sis_error)}")
            st.error(f"Standalone Error: {str(standalone_error)}")
            st.info("""
            **This app is designed to run in Streamlit in Snowflake (SiS).**
            
            If you're seeing this error in SiS:
            1. Ensure the app was deployed using `snow streamlit deploy`
            2. Check that your Snowflake account has Cortex AI Services enabled
            3. Verify you have the required permissions (see README.md)
            
            For standalone mode, ensure `~/.snowflake/config.toml` is configured with JWT key-pair authentication.
            """)
            st.stop()

def _get_standalone_session():
    """Helper for standalone session creation with caching. Returns (session, mode) tuple."""
    try:
        from snowflake.snowpark import Session
        from snowflake.connector import connect
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        
        # Load configuration — prefer local config.toml in repo root, fall back to ~/.snowflake/config.toml
        local_config = os.path.join(os.path.dirname(__file__), "config.toml")
        global_config = os.path.expanduser("~/.snowflake/config.toml")
        config_path = local_config if os.path.exists(local_config) else global_config
        if not os.path.exists(config_path):
            st.error(f"Configuration file not found: {config_path}")
            st.info("Copy `config.toml.example` to `config.toml` and fill in your credentials.")
            st.stop()
        
        config = toml.load(config_path)
        
        # Use default connection
        conn_config = config['connections']['default']
        
        # Load private key — support both 'private_key_path' and 'private_key_file' (Snowflake CLI)
        key_path = conn_config.get('private_key_path') or conn_config.get('private_key_file')
        with open(os.path.expanduser(key_path), 'rb') as key_file:
            private_key = load_pem_private_key(
                key_file.read(),
                password=None
            )
        
        # Convert private key to DER bytes for Snowpark (expects bytes, not base64 string)
        private_key_der = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        # Create Snowpark session for standalone mode
        session_configs = {
            'account': conn_config['account'],
            'user': conn_config['user'],
            'private_key': private_key_der,
        }
        for optional in ('warehouse', 'database', 'schema', 'role'):
            if optional in conn_config:
                session_configs[optional] = conn_config[optional]
        session = Session.builder.configs(session_configs).create()
        
        # Test the session with a simple query to ensure it's working
        session.sql("SELECT CURRENT_VERSION()").collect()
        
        return session, 'Standalone'
        
    except Exception as e:
        st.error(f"Failed to establish Snowflake connection: {str(e)}")
        st.info("""
        **Connection Options:**
        1. **Streamlit in Snowflake**: Deploy using `snow streamlit deploy`
        2. **Standalone**: Ensure `~/.snowflake/config.toml` is configured with JWT key-pair authentication
        """)
        st.info("**Debug Information:**")
        local_cfg = os.path.join(os.path.dirname(__file__), "config.toml")
        active_cfg = local_cfg if os.path.exists(local_cfg) else os.path.expanduser("~/.snowflake/config.toml")
        st.code(f"Config path: {active_cfg}")
        st.code(f"Error details: {str(e)}")
        st.stop()

# Import custom modules from common library
try:
    from common.analytics import SnowflakeDataLoader, ReconciliationEngine
    from common.utils import format_credits, get_status_color
except ImportError as e:
    st.error(f"Module import error: {e}")
    st.info("Please ensure all required modules are deployed with the application.")
    st.info("In monorepo structure, ensure common/ directory is in artifacts.")
    st.stop()

@st.cache_data
@time_it("get_cortex_logo_base64")
def get_cortex_logo_base64():
    """Load Cortex logo and convert to base64 for HTML embedding"""
    try:
        logo_path = os.path.join(os.path.dirname(__file__), 'common', 'assets', 'cortex_logo.png')
        with open(logo_path, "rb") as f:
            logo_data = f.read()
            logo_base64 = base64.b64encode(logo_data).decode()
            return logo_base64
    except Exception:
        # Return empty string if logo not found - will hide the image
        return ""

def apply_snowflake_chart_styling(fig, title=None):
    """Apply consistent Snowflake branding to Plotly charts"""
    fig.update_layout(
        title_font_color='#11567F',
        title_font_size=16,
        title_font_family='Arial',
        font_family='Arial',
        xaxis_title_font_color='#11567F',
        yaxis_title_font_color='#11567F',
        legend_font_color='#11567F'
    )
    if title:
        fig.update_layout(title=title)
    return fig

def get_snowflake_colors():
    """Return official Snowflake brand color palette from style guide"""
    return [
        '#29B5E8',  # Snowflake Blue (primary)
        '#11567F',  # Mid-Blue
        '#75CDD7',  # Star Blue
        '#FF9F36',  # Valencia Orange
        '#7254A3',  # Purple Moon
        '#D45B90',  # Firstlight
        '#5B5B5B',  # Medium Gray
        '#000000'   # Midnight (black)
    ]

@st.cache_data
@time_it("load_custom_css")
def load_custom_css():
    """Cached CSS with Snowflake branding guidelines"""
    return """
    <style>
    /* Snowflake Brand Colors from Style Guide */
    :root {
        --snowflake-blue: #29B5E8;
        --mid-blue: #11567F;
        --star-blue: #75CDD7;
        --valencia-orange: #FF9F36;
        --purple-moon: #7254A3;
        --firstlight: #D45B90;
        --medium-gray: #5B5B5B;
        --midnight: #000000;
    }
    
    /* Override Streamlit's default font family to Arial (Snowflake standard) */
    .main .block-container, .sidebar .block-container {
        font-family: Arial, sans-serif;
    }
    
    /* Header styling with Snowflake branding */
    .main-header {
        background: linear-gradient(135deg, var(--snowflake-blue), var(--mid-blue));
        padding: 2rem 1rem 1rem 1rem;
        border-radius: 0.5rem;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    
    .main-title {
        font-family: Arial, sans-serif;
        font-weight: bold;
        font-size: 2.5rem;
        color: white;
        margin: 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    
    .cortex-logo {
        height: 60px;
        margin-right: 1rem;
        vertical-align: middle;
    }
    
    /* Metric cards with Snowflake styling */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border-left: 4px solid var(--snowflake-blue);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    
    .metric-card:hover {
        box-shadow: 0 4px 12px rgba(41, 181, 232, 0.2);
        transform: translateY(-2px);
        transition: all 0.3s ease;
    }
    
    /* Status colors aligned with Snowflake palette */
    .status-excellent { 
        color: var(--snowflake-blue); 
        font-weight: bold;
    }
    .status-good { 
        color: var(--star-blue); 
        font-weight: bold;
    }
    .status-warning { 
        color: var(--valencia-orange); 
        font-weight: bold;
    }
    .status-critical { 
        color: var(--firstlight); 
        font-weight: bold;
    }
    
    /* Data freshness indicator */
    .data-freshness { 
        font-size: 0.9rem; 
        color: var(--medium-gray); 
        text-align: right;
        background: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        border: 2px solid var(--snowflake-blue);
        font-weight: 500;
    }
    
    /* Sidebar styling */
    .sidebar .block-container {
        background: linear-gradient(180deg, #f8f9fa, #e9ecef);
        border-radius: 0.5rem;
    }
    
    /* Section headers with Snowflake styling */
    .section-header {
        color: var(--mid-blue);
        font-weight: bold;
        border-bottom: 2px solid var(--snowflake-blue);
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
    }
    
    /* Tab styling - Remove default underlines and borders */
    .stTabs [data-baseweb="tab-list"] {
        background: linear-gradient(90deg, var(--snowflake-blue), var(--star-blue));
        border-radius: 0.5rem 0.5rem 0 0;
        border-bottom: none !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        color: white;
        font-weight: 500;
        border: none !important;
        border-bottom: none !important;
        text-decoration: none !important;
        box-shadow: none !important;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: white !important;
        color: var(--mid-blue) !important;
        font-weight: bold;
        border: none !important;
        border-bottom: none !important;
        text-decoration: none !important;
        box-shadow: none !important;
    }
    
    /* Remove any red underlines or borders */
    .stTabs [data-baseweb="tab"]:focus,
    .stTabs [data-baseweb="tab"]:hover,
    .stTabs [data-baseweb="tab"]:active {
        border: none !important;
        border-bottom: none !important;
        text-decoration: none !important;
        outline: none !important;
        box-shadow: none !important;
    }
    
    /* Remove underlines from tab content */
    .stTabs [data-baseweb="tab-list"] button {
        text-decoration: none !important;
        border-bottom: none !important;
    }
    
    /* Override any Streamlit default tab styling */
    .stTabs div[data-baseweb="tab-list"] div[role="tab"] {
        border-bottom: none !important;
        text-decoration: none !important;
    }
    
    /* Remove red/error styling from tabs */
    .stTabs [data-baseweb="tab-list"] [role="tab"][aria-selected="false"] {
        border-bottom: none !important;
        box-shadow: none !important;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, var(--snowflake-blue), var(--mid-blue));
        color: white;
        border: none;
        border-radius: 0.5rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, var(--mid-blue), var(--snowflake-blue));
        box-shadow: 0 4px 12px rgba(41, 181, 232, 0.3);
    }
    
    /* Deployment mode indicator */
    .deployment-mode {
        background: var(--snowflake-blue);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        text-align: center;
        font-weight: bold;
        margin-top: 1rem;
        box-shadow: 0 2px 8px rgba(41, 181, 232, 0.3);
    }
    
    /* Info boxes with Snowflake branding */
    .stAlert {
        border-left: 4px solid var(--snowflake-blue);
        background: linear-gradient(90deg, rgba(41, 181, 232, 0.05), rgba(255, 255, 255, 0.05));
    }
    
    /* Chart container styling */
    .chart-container {
        background: white;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-top: 3px solid var(--snowflake-blue);
    }
    </style>
    """

@st.cache_resource
@monitor_cache("get_app_components")
def get_app_components(_session):
    """
    Cached component initialization to avoid re-creating objects on every page interaction.
    Note: _ prefix for unhashable parameters (session objects)
    Expected 30-40% improvement in page load times.
    """
    data_loader = SnowflakeDataLoader(session=_session)
    reconciler = ReconciliationEngine(data_loader=data_loader)
    return data_loader, reconciler

@time_it("main_app")
def main():
    """Main Streamlit application for Cortex AI Services Cost Analyzer"""
    # Track app rerun
    performance_monitor.track_streamlit_rerun()
    
    # Set page icon to Cortex logo
    cortex_icon_path = os.path.join(project_root, 'assets', 'cortex_logo.png')
    
    st.set_page_config(
        page_title="Cortex AI Services Cost Analyzer",
        page_icon=cortex_icon_path,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS for better styling (cached)
    st.markdown(load_custom_css(), unsafe_allow_html=True)
    
    # Get Snowflake session (works for both SiS and standalone)
    # Always ensure deployment mode is set correctly, even with caching
    if 'deployment_mode' not in st.session_state:
        st.session_state['deployment_mode'] = 'Unknown'
    
    session_result = get_snowflake_session()
    if isinstance(session_result, tuple):
        session, deployment_mode = session_result
        # Always update the deployment mode, even if cached
        st.session_state['deployment_mode'] = deployment_mode
    else:
        # Fallback for compatibility
        session = session_result
        # If we have a session but no mode info, try to determine it
        if session and st.session_state['deployment_mode'] == 'Unknown':
            try:
                # Test if this is a SiS session by checking for specific attributes
                from snowflake.snowpark.context import get_active_session
                test_session = get_active_session()
                if test_session == session:
                    st.session_state['deployment_mode'] = 'SiS'
                else:
                    st.session_state['deployment_mode'] = 'Standalone'
            except:
                st.session_state['deployment_mode'] = 'Standalone'
    
    # Initialize components with caching for better performance
    try:
        data_loader, reconciler = get_app_components(session)
    except Exception as e:
        st.error(f"Failed to initialize application components: {str(e)}")
        st.stop()
    
    # Header with Snowflake branding and Cortex logo
    header_html = f"""
    <div class="main-header">
        <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 1rem;">
            <img src="data:image/png;base64,{get_cortex_logo_base64()}" class="cortex-logo" alt="Cortex Logo">
            <h1 class="main-title">CORTEX AI SERVICES COST ANALYZER</h1>
        </div>
        <div style="font-size: 1.1rem; opacity: 0.9;">
            Comprehensive AI billing analysis and reconciliation dashboard
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)
    
    
    # Sidebar Configuration
    st.sidebar.header("📊 Analysis Configuration")
    
    # Date range selection
    st.sidebar.subheader("Date Range")
    
    # Quick date range buttons
    col1, col2, col3 = st.sidebar.columns(3)
    with col1:
        if st.button("📅 7d"):
            st.session_state.date_range_start = datetime.now().date() - timedelta(days=7)
            st.session_state.date_range_end = datetime.now().date()
    with col2:
        if st.button("📅 30d"):
            st.session_state.date_range_start = datetime.now().date() - timedelta(days=30)
            st.session_state.date_range_end = datetime.now().date()
    with col3:
        if st.button("📅 90d"):
            st.session_state.date_range_start = datetime.now().date() - timedelta(days=90)
            st.session_state.date_range_end = datetime.now().date()

    # Date inputs
    start_date = st.sidebar.date_input(
        "Start Date",
        value=st.session_state.get('date_range_start', datetime.now().date() - timedelta(days=90)),
        max_value=datetime.now().date()
    )
    
    end_date = st.sidebar.date_input(
        "End Date", 
        value=st.session_state.get('date_range_end', datetime.now().date()),
        min_value=start_date,
        max_value=datetime.now().date()
    )
    
    # Analysis granularity
    granularity = st.sidebar.selectbox(
        "Analysis Granularity",
        ["Daily", "Hourly"],
        index=0
    )
    
    # Get all available services (no user selection needed)
    available_services = data_loader.get_available_services()
    services_filter = available_services  # Always include all services
    
    # Main Dashboard Content
    st.markdown('<h2 class="section-header">📊 Reconciliation Summary</h2>', unsafe_allow_html=True)
    
    # Combined Documentation & Resources Expander
    with st.expander("📚 Documentation & Resources", expanded=False):
        st.markdown("""
        **Billing Domain Notes:**
        - **CORTEX_REST_API_USAGE_HISTORY**: Billed in USD/million tokens — NOT in AI_SERVICES credits. Excluded from reconciliation.
        - **CORTEX_AI_FUNCTIONS_USAGE_HISTORY**: Excluded from sum — exact duplicate of CORTEX_AISQL_USAGE_HISTORY (identical credits).
        - **CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY**: Excluded from reconciliation sum — Snowflake billing event type change (Nov 2025) stopped populating this view (0 rows returned). Credits are still billed under METERING_HISTORY AI_SERVICES (Tier 2) but cannot be broken out at granular level until Snowflake resolves the view.

        ---

        **Billing & Metering:**
        - [Learn about metering](https://docs.snowflake.com/en/user-guide/cost-understanding-compute) - Understanding compute costs
        - [Account Usage Views](https://docs.snowflake.com/en/sql-reference/account-usage) - Usage monitoring views
        - [Snowflake Services Consumption Table](https://www.snowflake.com/legal-files/CreditConsumptionTable.pdf) - Credit consumption rates
        
        **Core Cortex AI Services:**
        - [Cortex AI Overview](https://docs.snowflake.com/en/user-guide/snowflake-cortex/overview) - Complete Cortex AI platform overview
        - [Cortex LLM Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) - COMPLETE, EMBED, COUNT_TOKENS, etc.
        - [Cortex AISQL](https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql) - Plain-language data queries
        - [Snowflake Copilot](https://docs.snowflake.com/en/user-guide/snowflake-copilot) - Conversational AI for structured data
        - [Cortex Analyst](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst) - Build conversational data applications
        - [Cortex Search](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview) - Semantic search over Snowflake data
        - [Cortex Fine-Tuning](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-finetuning) - Customize LLMs for your use case
        
        **Document Processing:**
        - [Document AI](https://docs.snowflake.com/en/user-guide/snowflake-cortex/document-ai/overview) - Extract data from PDFs and documents
        - [AI_EXTRACT Function](https://docs.snowflake.com/en/sql-reference/functions/ai_extract) - Extract structured data from documents
        
        **Specialized Functions:**
        - [TRANSLATE](https://docs.snowflake.com/en/sql-reference/functions/translate-snowflake-cortex) - Language translation
        - [CLASSIFY_TEXT](https://docs.snowflake.com/en/sql-reference/functions/classify_text-snowflake-cortex) - Text classification
        - [SENTIMENT](https://docs.snowflake.com/en/sql-reference/functions/sentiment-snowflake-cortex) - Sentiment analysis
        - [SUMMARIZE](https://docs.snowflake.com/en/sql-reference/functions/summarize-snowflake-cortex) - Text summarization
        - [EXTRACT_ANSWER](https://docs.snowflake.com/en/sql-reference/functions/extract_answer-snowflake-cortex) - Question answering
        """)
    
    st.markdown(f"**Analysis Period:** {start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}")
    
    # Get reconciliation data with caching and progress indicator
    with st.spinner('Loading AI Services reconciliation data...'):
        with measure_time("reconciliation_data_load"):
            with measure_memory("reconciliation_memory"):
                try:
                    summary_data = data_loader.get_ai_services_reconciliation_cached(start_date, end_date)
                    if summary_data.get('reconciliation_status') == 'ERROR':
                        st.error("❌ Reconciliation query failed. Please check the error logs.")
                        summary_data = None
                    elif summary_data.get('reconciliation_status') == 'NO_DATA':
                        st.warning("⚠️ No data available for the selected date range.")
                    else:
                        pass  # Reconciliation loaded successfully
                except Exception as e:
                    st.error(f"❌ Failed to load reconciliation data: {str(e)}")
                    summary_data = None
    
    if summary_data:
        # Key metrics in columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "AI Services Baseline",
                format_credits(summary_data['ai_services_baseline']),
                help="Total credits from ACCOUNT_USAGE.METERING_HISTORY"
            )
        
        with col2:
            st.metric(
                "Individual Services Total",
                format_credits(summary_data['total_individual']),
                help=(
                    "Sum of all individual Cortex service views:\n"
                    "• CORTEX_AISQL (excl. query_tag=cortex_code_cli rows)\n"
                    "• CORTEX_CODE_CLI  ★ now included\n"
                    "• CORTEX_CODE_SNOWSIGHT  ★ now included\n"
                    "• CORTEX_ANALYST\n"
                    "• CORTEX_AGENT\n"
                    "• SNOWFLAKE_INTELLIGENCE\n"
                    "• CORTEX_SEARCH_SERVING\n"
                    "• CORTEX_SEARCH_DAILY  ★ now included\n"
                    "• CORTEX_SEARCH_BATCH_QUERY  ★ now included\n"
                    "• CORTEX_PROVISIONED_THROUGHPUT  ★ now included\n"
                    "• CORTEX_FINE_TUNING\n"
                    "• DOCUMENT_AI\n"
                    "• CORTEX_DOCUMENT_PROCESSING (FALLBACK — excluded until fixed)\n"
                    "────────────────────────\n"
                    "Excluded: CORTEX_AI_FUNCTIONS (duplicate of AISQL)\n"
                    "Excluded: CORTEX_REST_API (USD-billed, not credits)"
                )
            )
        
        with col3:
            variance = summary_data.get('variance_pct', 0)
            variance_delta = f"{variance:+.2f}%" if variance != 0 else "0%"
            st.metric(
                "Variance",
                f"{variance:.2f}%",
                delta=variance_delta,
                delta_color="inverse"
            )
        
        with col4:
            status = summary_data.get('reconciliation_status', 'UNKNOWN')
            status_color = get_status_color(status)
            st.markdown(f'<h3 style="color: {status_color};">{status}</h3>', unsafe_allow_html=True)
    
    else:
        st.warning("No reconciliation data available for the selected date range.")
        st.info("This might be because:")
        st.info("• No AI Services usage in the selected period")
        st.info("• Insufficient permissions to access ACCOUNT_USAGE views")
        st.info("• Data latency (ACCOUNT_USAGE views have up to 3-hour delay)")

    # Per-service credit attribution bar chart
    if summary_data and summary_data.get('individual_services'):
        svc = summary_data['individual_services']
        svc_df = pd.DataFrame([
            {'Service': k, 'Credits': v}
            for k, v in svc.items() if v > 0
        ]).sort_values('Credits', ascending=True)

        if not svc_df.empty:
            fig = px.bar(
                svc_df, x='Credits', y='Service', orientation='h',
                title='Credit Attribution by Service (Tier 3 Breakdown)',
                color_discrete_sequence=['#29B5E8'],
                text='Credits'
            )
            fig.update_traces(
                texttemplate='%{text:.3f}',
                textposition='outside',
                marker_color='#29B5E8',
                marker_line_color='#11567F',
                marker_line_width=1
            )
            fig.update_layout(
                xaxis_title='Credits',
                yaxis_title='',
                showlegend=False,
                margin=dict(l=0, r=80, t=40, b=0),
            )
            apply_snowflake_chart_styling(fig)
            st.plotly_chart(fig, use_container_width=True)

    # Data freshness warning
    try:
        with st.spinner('Checking data freshness...'):
            freshness = data_loader.get_data_freshness()
        lagging = {k: v for k, v in freshness.items() if v > 2}
        if lagging:
            lag_parts = ', '.join(f'**{k}** ({v}d behind)' for k, v in sorted(lagging.items(), key=lambda x: -x[1]))
            st.warning(
                f"⚠️ **Data Freshness Warning**: {lag_parts}. "
                "Variance shown above may be higher than the true steady-state value until these "
                "granular views catch up to METERING_HISTORY."
            )
    except Exception:
        pass  # Non-blocking — freshness check should never break the dashboard
    
    # Enhanced Detailed Analysis Section
    st.markdown('<h2 class="section-header">📈 Detailed Analysis</h2>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["Model Analysis", "Service Details", "Time Series", "Raw Data"])
    
    with tab1:
        # Model-level token analysis
        with st.spinner('Loading model analysis...'):
            try:
                with measure_time("model_analysis_load"):
                    model_analysis = data_loader.get_model_token_analysis(start_date, end_date)
                    specialized_functions = data_loader.get_specialized_functions_analysis(start_date, end_date)
                
                if not model_analysis.empty:
                    # Split data by model type
                    explicit_models = model_analysis[model_analysis['MODEL_TYPE'] == 'EXPLICIT_MODEL']
                    specialized_entry = model_analysis[model_analysis['MODEL_TYPE'] == 'SPECIALIZED']
                    
                    # Overview metrics - ONLY for models
                    st.subheader("🤖 Model Utilisation", help="Analysis of LLM model usage including tokens, invocations, and credit consumption.\n\n📚 [Learn more about Cortex LLM Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions)")
                    col1, col2, col3, col4 = st.columns(4)

                    total_tokens = explicit_models["TOTAL_TOKENS"].sum()
                    total_invocations = explicit_models["INVOCATIONS"].sum()
                    total_credits = explicit_models['TOTAL_CREDITS'].sum()
                    avg_tokens_per_call = (
                        total_tokens / total_invocations if total_invocations > 0 else 0
                    )

                    with col1:
                        st.metric("Total Tokens", f"{total_tokens:,.0f}")
                    with col2:
                        st.metric("Total Invocations", f"{total_invocations:,.0f}")
                    with col3:
                        st.metric("Avg Tokens/Call", f"{avg_tokens_per_call:.1f}")
                    with col4:
                        st.metric("Total Credits", f"{total_credits:.2f}")
                    
                    # Visual analysis - ONLY models
                    st.subheader("🎯 Models Distribution", help="Visual breakdown showing credit distribution and efficiency metrics across different models")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Show only models in the pie chart
                        if not explicit_models.empty:
                            # Official Snowflake color palette from style guide
                            snowflake_colors = [
                                '#29B5E8',  # Snowflake Blue (primary)
                                '#11567F',  # Mid-Blue
                                '#75CDD7',  # Star Blue
                                '#FF9F36',  # Valencia Orange
                                '#7254A3',  # Purple Moon
                                '#D45B90',  # Firstlight
                                '#5B5B5B',  # Medium Gray
                                '#000000'   # Midnight (black)
                            ]
                            
                            # Create extended palette with variations for more segments
                            extended_palette = [
                                '#29B5E8',  # Snowflake Blue
                                '#11567F',  # Mid-Blue
                                '#75CDD7',  # Star Blue
                                '#FF9F36',  # Valencia Orange
                                '#7254A3',  # Purple Moon
                                '#D45B90',  # Firstlight
                                '#5B5B5B',  # Medium Gray
                                '#4DC2E8',  # Lighter Snowflake Blue
                                '#2B6F9F',  # Lighter Mid-Blue
                                '#95DDE7',  # Lighter Star Blue
                                '#FFB856',  # Lighter Valencia Orange
                                '#9274C3'   # Lighter Purple Moon
                            ]
                            
                            # Assign colors sequentially using official Snowflake palette
                            colors = []
                            for i, _ in enumerate(explicit_models.iterrows()):
                                colors.append(extended_palette[i % len(extended_palette)])
                            
                            # Create the pie chart with explicit color mapping
                            fig = px.pie(
                                explicit_models,
                                values="TOTAL_CREDITS",
                                names="MODEL_NAME",
                                title="Model Credit Distribution",
                                hole=0.4
                            )
                            
                            # Manually set colors using update_traces
                            fig.update_traces(
                                textposition="inside", 
                                textinfo="percent+label",
                                textfont_size=10,
                                marker=dict(
                                    colors=colors,
                                    line=dict(color='#FFFFFF', width=2)
                                )
                            )
                            apply_snowflake_chart_styling(fig)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No explicit model data available for the selected period.")

                    with col2:
                        # Efficiency comparison for models only
                        if not explicit_models.empty:
                            fig = px.bar(
                                explicit_models,
                                x="MODEL_NAME",
                                y="TOKENS_PER_CREDIT",
                                title="Model Efficiency (Tokens per Credit)",
                                text="TOKENS_PER_CREDIT",
                                color_discrete_sequence=['#29B5E8']
                            )
                            fig.update_traces(
                                texttemplate="%{text:.0f}",
                                marker_color='#29B5E8',
                                marker_line_color='#11567F',
                                marker_line_width=1
                            )
                            fig.update_xaxes(tickangle=45)
                            apply_snowflake_chart_styling(fig)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No models found - only specialized functions used in this period.")

                    # Model breakdown
                    if not explicit_models.empty:
                        st.subheader("📋 Model Breakdown", help="Detailed table showing all model usage statistics including tokens, credits, and efficiency metrics")
                        display_df = explicit_models.copy()
                        
                        # Remove MODEL_TYPE column for display
                        if 'MODEL_TYPE' in display_df.columns:
                            display_df = display_df.drop('MODEL_TYPE', axis=1)
                        
                        # Format numeric columns
                        for col in ['TOTAL_TOKENS', 'TOTAL_CREDITS', 'AVG_TOKENS_PER_CALL', 'AVG_CREDITS_PER_CALL']:
                            if col in display_df.columns:
                                display_df[col] = display_df[col].apply(lambda x: f"{x:,.3f}" if x < 1 else f"{x:,.2f}")
                        
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    # Add divider between Model breakdown and Specialized functions
                    if not explicit_models.empty and not specialized_functions.empty:
                        st.markdown("---")
                    
                    # Specialized functions breakdown
                    if not specialized_functions.empty:
                        st.subheader("🔧 Specialized Functions Breakdown", help="Functions like TRANSLATE, CLASSIFY_TEXT, SENTIMENT that don't specify model names.\n\n📚 [View all specialized functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions#label-cortex-llm-specialized-functions)")
                        
                        # Specialized Functions KPIs
                        col1, col2, col3, col4 = st.columns(4)

                        spec_total_tokens = specialized_functions["TOTAL_TOKENS"].sum()
                        spec_total_invocations = specialized_functions["INVOCATIONS"].sum()
                        spec_total_credits = specialized_functions['TOTAL_CREDITS'].sum()
                        spec_avg_tokens_per_call = (
                            spec_total_tokens / spec_total_invocations if spec_total_invocations > 0 else 0
                        )

                        with col1:
                            st.metric("Total Tokens", f"{spec_total_tokens:,.0f}")
                        with col2:
                            st.metric("Total Invocations", f"{spec_total_invocations:,.0f}")
                        with col3:
                            st.metric("Avg Tokens/Call", f"{spec_avg_tokens_per_call:.1f}")
                        with col4:
                            st.metric("Total Credits", f"{spec_total_credits:.2f}")
                        
                        # Function details chart
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            fig = px.pie(
                                specialized_functions,
                                values="TOTAL_CREDITS",
                                names="FUNCTION_NAME",
                                title="Specialized Functions Credit Distribution",
                                color_discrete_sequence=get_snowflake_colors()
                            )
                            fig.update_traces(
                                textposition="inside", 
                                textinfo="percent+label",
                                textfont_size=10,
                                marker=dict(line=dict(color='#FFFFFF', width=2))
                            )
                            apply_snowflake_chart_styling(fig)
                            st.plotly_chart(fig, use_container_width=True)
                        
                        with col2:
                            # Function efficiency - match colors from pie chart
                            # Create color mapping to match the pie chart legend
                            snowflake_palette = get_snowflake_colors()
                            bar_colors = []
                            for i, _ in enumerate(specialized_functions.iterrows()):
                                bar_colors.append(snowflake_palette[i % len(snowflake_palette)])
                            
                            fig = px.bar(
                                specialized_functions,
                                x="FUNCTION_NAME",
                                y="TOKENS_PER_CREDIT",
                                title="Function Efficiency (Tokens per Credit)",
                                text="TOKENS_PER_CREDIT",
                                color_discrete_sequence=bar_colors
                            )
                            fig.update_traces(
                                texttemplate="%{text:.0f}",
                                marker_line_color='#FFFFFF',  # White border for contrast
                                marker_line_width=1
                            )
                            fig.update_xaxes(tickangle=45)
                            apply_snowflake_chart_styling(fig)
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # Detailed functions table
                        display_functions = specialized_functions.copy()
                        
                        # Format numeric columns
                        for col in ['TOTAL_TOKENS', 'TOTAL_CREDITS', 'AVG_TOKENS_PER_CALL', 'AVG_CREDITS_PER_CALL']:
                            if col in display_functions.columns:
                                display_functions[col] = display_functions[col].apply(lambda x: f"{x:,.3f}" if x < 1 else f"{x:,.2f}")
                        
                        # Format date columns
                        for col in ['FIRST_USAGE', 'LAST_USAGE']:
                            if col in display_functions.columns:
                                display_functions[col] = pd.to_datetime(display_functions[col]).dt.strftime('%Y-%m-%d %H:%M')
                        
                        st.dataframe(display_functions, use_container_width=True, hide_index=True)
                        
                    
                    
                else:
                    st.info("No model usage data available for the selected period.")
                    
            except Exception as e:
                st.error(f"Error loading model analysis: {str(e)}")
                st.info("Model analysis requires CORTEX_AISQL_USAGE_HISTORY table access.")
    
    with tab2:
        st.subheader("🔧 Service Details & Breakdown", help="Detailed breakdown of all Snowflake Cortex AI services.\n\n📚 [Cortex AI Overview](https://docs.snowflake.com/en/user-guide/snowflake-cortex/overview)")

        st.info(
            "ℹ️ **CORTEX_AI_FUNCTIONS_USAGE_HISTORY** is excluded from all totals — "
            "it is an exact duplicate of CORTEX_AISQL_USAGE_HISTORY (same credits, same rows). "
            "**CORTEX_REST_API_USAGE_HISTORY** is also excluded — it is billed in USD/million tokens, not AI_SERVICES credits."
        )

        with st.spinner('Loading service details...'):
            try:
                with measure_time("service_breakdown_load"):
                    service_breakdown = data_loader.get_service_breakdown_cached(start_date, end_date, services_filter)

                if not service_breakdown.empty:
                    # Two-column layout: table left, pie chart right
                    col_table, col_chart = st.columns([3, 2])

                    with col_table:
                        display_df = service_breakdown.copy()
                        if 'total_credits' in display_df.columns:
                            display_df['total_credits'] = display_df['total_credits'].apply(format_credits)
                        if 'percentage' in display_df.columns:
                            display_df['percentage'] = display_df['percentage'].apply(lambda x: f"{x:.2f}%")
                        st.dataframe(display_df, use_container_width=True, hide_index=True)

                    with col_chart:
                        active = service_breakdown[service_breakdown['total_credits'] > 0]
                        if not active.empty:
                            fig = px.pie(
                                active,
                                values='total_credits',
                                names='service_type',
                                title='Service Credit Share',
                                hole=0.4,
                                color_discrete_sequence=get_snowflake_colors()
                            )
                            fig.update_traces(
                                textinfo='percent+label',
                                textfont_size=9,
                                marker=dict(line=dict(color='#FFFFFF', width=2))
                            )
                            apply_snowflake_chart_styling(fig)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No active services with credits in the selected period.")

                    # Service-specific insights
                    for service in service_breakdown['service_type'].unique():
                        service_data = service_breakdown[service_breakdown['service_type'] == service]
                        if not service_data.empty and service_data.iloc[0]['total_credits'] > 0:
                            # Skip CORTEX_FUNCTIONS_USAGE as it's covered by CORTEX_FUNCTIONS_QUERY
                            if service == 'CORTEX_FUNCTIONS_USAGE':
                                continue
                            
                            # Standard service display
                            with st.expander(f"🔍 {service} Details"):
                                st.write(f"**Granularity**: {service_data.iloc[0].get('granularity', 'Unknown')}")
                                st.write(f"**Records**: {service_data.iloc[0].get('record_count', 0):,}")
                                try:
                                    additional_details = data_loader.get_service_specific_details(service, start_date, end_date)
                                    if not additional_details.empty:
                                        st.dataframe(additional_details.head(10), use_container_width=True)
                                except Exception:
                                    st.info("Detailed breakdown not available for this service.")
                else:
                    st.info("No service breakdown data available for the selected period.")
            except Exception as e:
                st.error(f"Error loading service breakdown: {str(e)}")

        # Doc Processing warning banner
        st.subheader("📄 Doc Processing")
        st.warning(
            "⚠️ **Doc Processing credits are not available at granular level.** "
            "A Snowflake internal billing event type change (Nov 2025) stopped populating "
            "`CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY` — the view exists but returns 0 rows. "
            "Document processing credits are still billed and visible in **METERING_HISTORY** "
            "under `AI_SERVICES` (Tier 2), but cannot be broken out per-job until Snowflake fixes the view. "
            "This service is excluded from the Tier 3 reconciliation sum."
        )

        # Cortex Agents — GA Feb 25 2026
        st.subheader("🤖 Cortex Agents", help="Usage of Cortex Agents (GA Feb 25 2026). TOKEN_CREDITS column. Note: AGENT_NAME is NULL for Snowsight CoCo traffic until CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY rolls out.")
        try:
            agent_df = data_loader.get_cortex_agent_analysis(start_date, end_date)
            if not agent_df.empty:
                total_agent_credits = float(agent_df['TOTAL_CREDITS'].sum())
                total_agent_requests = int(agent_df['TOTAL_REQUESTS'].sum())
                c1, c2 = st.columns(2)
                c1.metric("Total Agent Credits", f"{total_agent_credits:,.4f}")
                c2.metric("Total Agent Requests", f"{total_agent_requests:,}")
                st.dataframe(agent_df, use_container_width=True, hide_index=True)
            else:
                st.info("No Cortex Agent usage in the selected period.")
        except Exception as e:
            st.warning(f"Cortex Agent data not available: {e}")

        # Snowflake Intelligence — GA Feb 25 2026
        st.subheader("✨ Snowflake Intelligence", help="Usage of Snowflake Intelligence (GA Feb 25 2026). Does NOT include Cortex Agent requests — those appear in the Cortex Agents section above.")
        try:
            si_df = data_loader.get_snowflake_intelligence_analysis(start_date, end_date)
            if not si_df.empty:
                total_si_credits = float(si_df['TOTAL_CREDITS'].sum())
                total_si_requests = int(si_df['TOTAL_REQUESTS'].sum())
                c1, c2 = st.columns(2)
                c1.metric("Total SI Credits", f"{total_si_credits:,.4f}")
                c2.metric("Total SI Requests", f"{total_si_requests:,}")
                st.dataframe(si_df, use_container_width=True, hide_index=True)
            else:
                st.info("No Snowflake Intelligence usage in the selected period.")
        except Exception as e:
            st.warning(f"Snowflake Intelligence data not available: {e}")

        # Cortex Code CLI
        st.subheader("💻 Cortex Code CLI", help="Cortex Code CLI usage by user. CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY (Snowsight traffic) is not yet fully rolled out — Snowsight CoCo traffic appears in Cortex Agents with AGENT_NAME = NULL.")
        try:
            code_df = data_loader.get_cortex_code_analysis(start_date, end_date)
            if not code_df.empty:
                total_code_credits = float(code_df['TOTAL_CREDITS'].sum())
                total_code_requests = int(code_df['TOTAL_REQUESTS'].sum())
                c1, c2 = st.columns(2)
                c1.metric("Total Cortex Code Credits", f"{total_code_credits:,.4f}")
                c2.metric("Total Code Requests", f"{total_code_requests:,}")
                st.dataframe(code_df, use_container_width=True, hide_index=True)
            else:
                st.info("No Cortex Code CLI usage in the selected period.")
        except Exception as e:
            st.warning(f"Cortex Code CLI data not available: {e}")

    with tab3:
        st.subheader(f"📈 Usage Trends ({granularity})", help="Time series analysis showing credit consumption trends over time with individual function breakdown for models and specialized functions")
        
        with st.spinner('Loading time series data...'):
            try:
                with measure_time("time_series_load"):
                    time_series_data = data_loader.get_time_series_data(start_date, end_date, granularity.lower())
                
                if not time_series_data.empty:
                    # Check if specialized functions are present in the data
                    specialized_functions = time_series_data[time_series_data['service_type'].isin([
                        'TRANSLATE', 'CLASSIFY_TEXT', 'SENTIMENT', 
                        'SUMMARIZE', 'EMBED_TEXT', 'EXTRACT_ANSWER', 
                        'AI_EXTRACT', 'AI_AGG', 'AI_CLASSIFY', 'Other Specialized'
                    ])]
                    
                    # Check if explicit model functions are present  
                    explicit_model_functions = time_series_data[time_series_data['service_type'].isin([
                        'COMPLETE', 'EMBED_TEXT_768', 'EMBED_TEXT_1024', 
                        'EMBED_TEXT_EXPLICIT', 'FINETUNE', 'COUNT_TOKENS', 'Other Explicit'
                    ])]
                    
                    # Create time series chart with Snowflake branding
                    fig = px.line(
                        time_series_data, 
                        x='period', 
                        y='credits', 
                        color='service_type',
                        title=f"{granularity} AI Services Usage Trends - Individual Function Breakdown",
                        labels={'credits': 'Credits Used', 'period': 'Period'},
                        color_discrete_sequence=get_snowflake_colors()
                    )
                    fig.update_layout(hovermode='x unified')
                    fig.update_traces(line=dict(width=3))
                    apply_snowflake_chart_styling(fig)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Peak usage analysis
                    total_by_period = time_series_data.groupby('period')['credits'].sum().reset_index()
                    if len(total_by_period) > 1:
                        peak_usage = total_by_period.loc[total_by_period['credits'].idxmax()]
                        st.info(f"📊 **Peak Usage**: {peak_usage['period']} ({format_credits(peak_usage['credits'])} credits)")
                    
                else:
                    st.info("No time series data available for the selected period.")
            except Exception as e:
                st.error(f"Error loading time series analysis: {str(e)}")
    
    with tab4:
        st.subheader("📋 Raw Data Export", help="Export detailed raw data from all Cortex services in CSV format for further analysis")
        
        with st.spinner('Loading raw data...'):
            try:
                with measure_time("raw_data_export_load"):
                    with measure_memory("raw_data_memory"):
                        # Limit to 10,000 rows to prevent memory issues (limit applied in method)
                        export_data = data_loader.get_raw_export_data(start_date, end_date)
                
                if not export_data.empty:
                    st.write(f"**Total Records**: {len(export_data):,} (limited to 10,000 for performance)")
                    st.write(f"**Date Range**: {start_date} to {end_date}")
                    
                    # Show unified credit total if TOTAL_CREDITS column exists
                    if 'TOTAL_CREDITS' in export_data.columns:
                        total_credits = export_data['TOTAL_CREDITS'].sum()
                        st.write(f"**Total Credits**: {total_credits:.6f} (unified across all service types)")
                        st.info("💡 Use the **TOTAL_CREDITS** column for accurate credit totals (combines TOKEN_CREDITS, CREDITS, and CREDITS_USED)")
                    
                    # Show sample of raw data
                    st.subheader("Data Preview (First 100 rows)")
                    st.dataframe(export_data.head(100), use_container_width=True)
                    
                    # Download options
                    csv_data = export_data.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Full Dataset (CSV)",
                        data=csv_data,
                        file_name=f"cortex_raw_data_{start_date}_{end_date}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No raw data available for export.")
            except Exception as e:
                st.error(f"Error loading raw data: {str(e)}")
    
    # Debug and Admin Section
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 Debug & Admin")
    
    # Cache clearing for troubleshooting
    if st.sidebar.button("🗑️ Clear Session Cache", help="Clear cached Snowflake session (useful for connection issues)"):
        st.cache_resource.clear()
        # Clear deployment mode to force re-detection
        if 'deployment_mode' in st.session_state:
            del st.session_state['deployment_mode']
        st.success("Session cache cleared. Please refresh the page.")
        st.rerun()
    
    # Performance Debugging Section (only show in development/debug mode)
    show_debug = st.sidebar.checkbox("🔍 Show Performance Debug", help="Display performance monitoring dashboard")
    
    # Deployment mode indicator at bottom of sidebar
    st.sidebar.markdown("---")
    mode = st.session_state.get('deployment_mode', 'Unknown')
    mode_emoji = {
        'SiS': "☁️",
        'Standalone': "💻", 
        'Unknown': "❓",
        'Configuration Error': "⚠️",
        'Connection Failed': "❌"
    }.get(mode, "❓")
    
    mode_color = {
        'SiS': "#28a745",
        'Standalone': "#007bff",
        'Unknown': "#6c757d", 
        'Configuration Error': "#ffc107",
        'Connection Failed': "#dc3545"
    }.get(mode, "#6c757d")
    
    st.sidebar.markdown(f'<div class="deployment-mode">{mode_emoji} Mode: {mode}</div>',
                       unsafe_allow_html=True)

    # Show connected account details
    try:
        session_result = get_snowflake_session()
        if session_result:
            _session, _ = session_result
            row = _session.sql("SELECT CURRENT_ACCOUNT() AS acct, CURRENT_USER() AS usr, CURRENT_ROLE() AS rol, CURRENT_WAREHOUSE() AS wh").collect()[0]
            st.sidebar.markdown(
                f"<div style='font-size:0.72rem;color:#888;margin-top:6px;line-height:1.6'>"
                f"<b>Account:</b> {row['ACCT']}<br>"
                f"<b>User:</b> {row['USR']}<br>"
                f"<b>Role:</b> {row['ROL']}<br>"
                f"<b>Warehouse:</b> {row['WH']}"
                f"</div>",
                unsafe_allow_html=True
            )
    except Exception:
        pass
    
    # Show performance debugging dashboard if enabled
    if show_debug:
        st.markdown('<h2 class="section-header">🔍 Performance Debugging Dashboard</h2>', unsafe_allow_html=True)
        
        # Show performance summary
        performance_monitor.display_performance_dashboard()
        
        # Additional debug information
        with st.expander("📊 Detailed Performance Metrics"):
            # Session state size
            session_state_size = len(str(st.session_state))
            st.metric("Session State Size", f"{session_state_size:,} characters")
            
            # Memory usage
            try:
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                st.metric("Process Memory", f"{memory_mb:.1f} MB")
            except Exception:
                st.metric("Process Memory", "N/A")
            
            # Operation timings
            if hasattr(st.session_state, 'operation_times'):
                st.subheader("⏱️ Operation Timings")
                for operation, times in st.session_state.operation_times.items():
                    avg_time = sum(times) / len(times) if times else 0
                    st.write(f"**{operation}**: {avg_time*1000:.1f}ms avg ({len(times)} calls)")
            
            # Memory usage by operation
            if hasattr(st.session_state, 'memory_usage'):
                st.subheader("💾 Memory Usage by Operation")
                for operation, usage_list in st.session_state.memory_usage.items():
                    if usage_list:
                        avg_delta = sum(u['delta'] for u in usage_list) / len(usage_list)
                        st.write(f"**{operation}**: {avg_delta:+.1f}MB avg delta ({len(usage_list)} calls)")
            
            # Cache performance
            st.subheader("🎯 Cache Performance")
            cache_info = {
                'get_snowflake_session': 'Session initialization',
                'get_app_components': 'Component initialization', 
                'get_ai_services_reconciliation_cached': 'Reconciliation data',
                'get_service_breakdown_cached': 'Service breakdown'
            }
            
            for cache_name, description in cache_info.items():
                # This would show actual cache stats in a real implementation
                st.write(f"**{description}**: Cache enabled")
        
        # Export performance report
        if st.button("📥 Export Performance Report"):
            try:
                report = performance_monitor.export_performance_report()
                report_json = json.dumps(report, indent=2, default=str)
                
                st.download_button(
                    label="Download Performance Report (JSON)",
                    data=report_json,
                    file_name=f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            except Exception as e:
                st.error(f"Failed to generate performance report: {str(e)}")

if __name__ == "__main__":
    main()
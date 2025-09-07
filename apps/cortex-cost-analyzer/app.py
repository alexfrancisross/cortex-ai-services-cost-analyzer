import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
import toml

# Add monorepo root directory to Python path for shared modules
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# Environment detection and session setup
@st.cache_resource
def get_snowflake_session():
    """
    Cached Snowflake session to avoid re-authentication on every page load.
    Get Snowflake session - either from SiS (get_active_session) or standalone (connector)
    """
    try:
        # Try to get active session first (SiS environment)
        from snowflake.snowpark.context import get_active_session
        session = get_active_session()
        # Only set mode to SiS if we successfully got the session
        st.session_state['deployment_mode'] = 'SiS'
        return session
    except Exception as e:
        # Fallback to standalone mode with key-pair authentication
        return _get_standalone_session()

@st.cache_resource
def _get_standalone_session():
    """Helper for standalone session creation with caching"""
    try:
        from snowflake.snowpark import Session
        from snowflake.connector import connect
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        
        # Load configuration from config.toml
        config_path = os.path.expanduser("~/.snowflake/config.toml")
        if not os.path.exists(config_path):
            st.error(f"Configuration file not found: {config_path}")
            st.stop()
        
        config = toml.load(config_path)
        
        # Use default connection
        conn_config = config['connections']['default']
        
        # Load private key
        with open(os.path.expanduser(conn_config['private_key_path']), 'rb') as key_file:
            private_key = load_pem_private_key(
                key_file.read(),
                password=None
            )
        
        # Convert private key to DER format and base64 encode for Snowpark
        import base64
        private_key_der = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        private_key_b64 = base64.b64encode(private_key_der).decode('utf-8')
        
        # Create Snowpark session for standalone mode
        session = Session.builder.configs({
            'account': conn_config['account'],
            'user': conn_config['user'],
            'private_key': private_key_b64,
            'warehouse': conn_config['warehouse'],
            'database': conn_config['database'],
            'schema': conn_config['schema'],
            'role': conn_config['role']
        }).create()
        
        # Only set mode to Standalone if we successfully created the session
        st.session_state['deployment_mode'] = 'Standalone'
        return session
        
    except Exception as e:
        st.error(f"Failed to establish Snowflake connection: {str(e)}")
        st.info("""
        **Connection Options:**
        1. **Streamlit in Snowflake**: Deploy using `snow streamlit deploy`
        2. **Standalone**: Ensure `~/.snowflake/config.toml` is configured with JWT key-pair authentication
        """)
        st.stop()

# Import custom modules from shared library
try:
    from shared.analytics import SnowflakeDataLoader, ReconciliationEngine
    from shared.components import CortexVisualizer
    from shared.utils import format_credits, get_status_color, calculate_percentage_change
except ImportError as e:
    st.error(f"Module import error: {e}")
    st.info("Please ensure all required modules are deployed with the application.")
    st.info("In monorepo structure, ensure shared/ directory is in artifacts.")
    st.stop()

@st.cache_data
def load_custom_css():
    """Cached CSS to avoid parsing on every render"""
    return """
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .status-excellent { color: #28a745; }
    .status-good { color: #ffc107; }
    .status-warning { color: #fd7e14; }
    .status-critical { color: #dc3545; }
    .data-freshness { 
        font-size: 0.8rem; 
        color: #6c757d; 
        text-align: right; 
    }
    </style>
    """

@st.cache_resource
def get_app_components(_session):
    """
    Cached component initialization to avoid re-creating objects on every page interaction.
    Note: _ prefix for unhashable parameters (session objects)
    Expected 30-40% improvement in page load times.
    """
    data_loader = SnowflakeDataLoader(session=_session)
    reconciler = ReconciliationEngine(data_loader=data_loader)
    visualizer = CortexVisualizer()
    return data_loader, reconciler, visualizer

def main():
    """Main Streamlit application for Cortex AI Services Cost Analyzer"""
    st.set_page_config(
        page_title="Cortex AI Services Cost Analyzer",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS for better styling (cached)
    st.markdown(load_custom_css(), unsafe_allow_html=True)
    
    # Get Snowflake session (works for both SiS and standalone)
    session = get_snowflake_session()
    
    # Initialize components with caching for better performance
    try:
        data_loader, reconciler, visualizer = get_app_components(session)
    except Exception as e:
        st.error(f"Failed to initialize application components: {str(e)}")
        st.stop()
    
    # Header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.title("🧠 Cortex AI Services Cost Analyzer")
    with col2:
        # Deployment mode indicator
        mode = st.session_state.get('deployment_mode', 'Unknown')
        mode_emoji = "☁️" if mode == 'SiS' else "💻" if mode == 'Standalone' else "❓"
        st.markdown(f'<div class="data-freshness">{mode_emoji} Mode: {mode}</div>', 
                   unsafe_allow_html=True)
    with col3:
        # Data freshness indicator
        try:
            freshness = data_loader.get_data_freshness()
            freshness_hours = freshness.total_seconds() / 3600 if freshness else 0
            freshness_color = "🔴" if freshness_hours > 6 else "🟡" if freshness_hours > 3 else "🟢"
            st.markdown(f'<div class="data-freshness">{freshness_color} Data: {freshness_hours:.1f}h old</div>', 
                       unsafe_allow_html=True)
        except Exception:
            st.markdown('<div class="data-freshness">❓ Data: Unknown</div>', 
                       unsafe_allow_html=True)
    
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
        value=st.session_state.get('date_range_start', datetime.now().date() - timedelta(days=30)),
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
    st.header("📊 Reconciliation Summary")
    st.markdown(f"**Analysis Period:** {start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}")
    
    # Get reconciliation data with caching and progress indicator
    with st.spinner('Loading AI Services reconciliation data...'):
        summary_data = data_loader.get_ai_services_reconciliation_cached(start_date, end_date)
    
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
                help="Sum of all individual Cortex service tables"
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
    
        # Service breakdown
        st.subheader("💰 Service Breakdown")
        
        individual_services = summary_data.get('individual_services', {})
        if individual_services:
            # Create DataFrame for visualization
            service_data = []
            for service, credits in individual_services.items():
                service_data.append({
                    'Service': service,
                    'Credits': float(credits),
                    'Percentage': (float(credits) / summary_data['total_individual'] * 100) if summary_data['total_individual'] > 0 else 0
                })
            
            df_services = pd.DataFrame(service_data)
            df_services = df_services.sort_values('Credits', ascending=False)
            
            # Display as chart and table
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if not df_services.empty:
                    fig = px.pie(
                        df_services, 
                        values='Credits', 
                        names='Service',
                        title="Credit Distribution by Service"
                    )
                    fig.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Format the DataFrame for display
                display_df = df_services.copy()
                display_df['Credits'] = display_df['Credits'].apply(format_credits)
                display_df['Percentage'] = display_df['Percentage'].apply(lambda x: f"{x:.2f}%")
                st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No reconciliation data available for the selected date range.")
        st.info("This might be because:")
        st.info("• No AI Services usage in the selected period")  
        st.info("• Insufficient permissions to access ACCOUNT_USAGE views")
        st.info("• Data latency (ACCOUNT_USAGE views have up to 3-hour delay)")
    
    # Enhanced Detailed Analysis Section
    st.header("📈 Enhanced Detailed Analysis")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Model Analysis", "Service Details", "Time Series", "Raw Data"])
    
    with tab1:
        # Model-level token analysis
        st.subheader("🤖 Model Token & Credit Analysis")
        
        with st.spinner('Loading model analysis...'):
            try:
                model_analysis = data_loader.get_model_token_analysis(start_date, end_date)
                
                if not model_analysis.empty:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Credits by model pie chart
                        fig = px.pie(
                            model_analysis,
                            values="TOTAL_CREDITS",
                            names="MODEL_NAME",
                            title="Credit Distribution by Model",
                            hole=0.4,
                        )
                        fig.update_traces(textposition="inside", textinfo="percent+label")
                        st.plotly_chart(fig, use_container_width=True)

                    with col2:
                        # Efficiency comparison
                        fig = px.bar(
                            model_analysis,
                            x="MODEL_NAME",
                            y="TOKENS_PER_CREDIT",
                            title="Tokens per Credit by Model (Efficiency)",
                            text="TOKENS_PER_CREDIT",
                        )
                        fig.update_traces(texttemplate="%{text:.0f}")
                        fig.update_xaxes(tickangle=45)
                        st.plotly_chart(fig, use_container_width=True)

                    # Token usage metrics
                    st.subheader("📊 Token Usage Metrics")
                    col1, col2, col3, col4 = st.columns(4)

                    total_tokens = model_analysis["TOTAL_TOKENS"].sum()
                    total_invocations = model_analysis["INVOCATIONS"].sum()
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
                        st.metric("Total Credits", f"{model_analysis['TOTAL_CREDITS'].sum():.2f}")

                    # Detailed model table
                    st.subheader("📋 Detailed Model Breakdown")
                    display_df = model_analysis.copy()
                    
                    # Format numeric columns
                    for col in ['TOTAL_TOKENS', 'TOTAL_CREDITS', 'AVG_TOKENS_PER_CALL', 'AVG_CREDITS_PER_CALL']:
                        if col in display_df.columns:
                            display_df[col] = display_df[col].apply(lambda x: f"{x:,.3f}" if x < 1 else f"{x:,.2f}")
                    
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                else:
                    st.info("No model usage data available for the selected period.")
            except Exception as e:
                st.error(f"Error loading model analysis: {str(e)}")
                st.info("Model analysis requires CORTEX_FUNCTIONS_USAGE_HISTORY table access.")
    
    with tab2:
        st.subheader("🔧 Service Details & Breakdown")
        
        with st.spinner('Loading service details...'):
            try:
                service_breakdown = data_loader.get_service_breakdown_cached(start_date, end_date, services_filter)
                
                if not service_breakdown.empty:
                    # Service breakdown table
                    display_df = service_breakdown.copy()
                    if 'total_credits' in display_df.columns:
                        display_df['total_credits'] = display_df['total_credits'].apply(format_credits)
                    if 'percentage' in display_df.columns:
                        display_df['percentage'] = display_df['percentage'].apply(lambda x: f"{x:.2f}%")
                    
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    # Service-specific insights
                    for service in service_breakdown['service_type'].unique():
                        service_data = service_breakdown[service_breakdown['service_type'] == service]
                        if not service_data.empty and service_data.iloc[0]['total_credits'] > 0:
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
    
    with tab3:
        st.subheader(f"📈 Usage Trends ({granularity})")
        
        with st.spinner('Loading time series data...'):
            try:
                time_series_data = data_loader.get_time_series_data(start_date, end_date, granularity.lower())
                
                if not time_series_data.empty:
                    # Create time series chart
                    fig = px.line(
                        time_series_data, 
                        x='period', 
                        y='credits', 
                        color='service_type',
                        title=f"{granularity} AI Services Usage Trends",
                        labels={'credits': 'Credits Used', 'period': 'Period'}
                    )
                    fig.update_layout(hovermode='x unified')
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
        st.subheader("📋 Raw Data Export")
        
        with st.spinner('Loading raw data...'):
            try:
                export_data = data_loader.get_raw_export_data(start_date, end_date)
                
                if not export_data.empty:
                    st.write(f"**Total Records**: {len(export_data):,}")
                    st.write(f"**Date Range**: {start_date} to {end_date}")
                    
                    # Show sample of raw data
                    st.subheader("Data Preview (First 100 rows)")
                    st.dataframe(export_data.head(100), use_container_width=True)
                    
                    # Download options
                    col1, col2 = st.columns(2)
                    with col1:
                        csv_data = export_data.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Full Dataset (CSV)",
                            data=csv_data,
                            file_name=f"cortex_raw_data_{start_date}_{end_date}.csv",
                            mime="text/csv"
                        )
                    
                    with col2:
                        st.info("💡 Excel export available in production version")
                else:
                    st.info("No raw data available for export.")
            except Exception as e:
                st.error(f"Error loading raw data: {str(e)}")

if __name__ == "__main__":
    main()
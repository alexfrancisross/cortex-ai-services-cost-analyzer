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

# Add monorepo root directory to Python path for shared modules
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# Import performance monitoring
from shared.utils.performance_monitor import (
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
    try:
        # Try to get active session first (SiS environment)
        from snowflake.snowpark.context import get_active_session
        session = get_active_session()
        # Test the session with a simple query to ensure it's working
        session.sql("SELECT CURRENT_VERSION()").collect()
        return session, 'SiS'
    except Exception:
        # Fallback to standalone mode with key-pair authentication
        return _get_standalone_session()

def _get_standalone_session():
    """Helper for standalone session creation with caching. Returns (session, mode) tuple."""
    try:
        from snowflake.snowpark import Session
        from snowflake.connector import connect
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        
        # Load configuration from config.toml
        config_path = os.path.expanduser("~/.snowflake/config.toml")
        if not os.path.exists(config_path):
            st.error(f"Configuration file not found: {config_path}")
            st.info("Please ensure `~/.snowflake/config.toml` is configured with JWT key-pair authentication")
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
        st.code(f"Config path: {os.path.expanduser('~/.snowflake/config.toml')}")
        st.code(f"Error details: {str(e)}")
        st.stop()

# Import custom modules from shared library
try:
    from shared.analytics import SnowflakeDataLoader, ReconciliationEngine
    from shared.utils import format_credits, get_status_color, calculate_percentage_change
except ImportError as e:
    st.error(f"Module import error: {e}")
    st.info("Please ensure all required modules are deployed with the application.")
    st.info("In monorepo structure, ensure shared/ directory is in artifacts.")
    st.stop()

@st.cache_data
@time_it("load_custom_css")
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
    
    st.set_page_config(
        page_title="Cortex AI Services Cost Analyzer",
        page_icon="🧠",
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
    
    # Header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.title("🧠 Cortex AI Services Cost Analyzer")
    with col2:
        # Reserved for future use
        st.empty()
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
    st.header("📊 Reconciliation Summary")
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
                with measure_time("model_analysis_load"):
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
                with measure_time("service_breakdown_load"):
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
                with measure_time("time_series_load"):
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
                        # Excel export functionality
                        try:
                            from io import BytesIO
                            
                            # Fix timezone-aware datetime columns for Excel compatibility
                            excel_data_copy = export_data.copy()
                            
                            # Convert timezone-aware datetime columns to timezone-naive
                            for col in excel_data_copy.columns:
                                if excel_data_copy[col].dtype == 'datetime64[ns, UTC]' or 'datetime' in str(excel_data_copy[col].dtype):
                                    if hasattr(excel_data_copy[col].dtype, 'tz') and excel_data_copy[col].dtype.tz is not None:
                                        excel_data_copy[col] = excel_data_copy[col].dt.tz_localize(None)
                            
                            excel_buffer = BytesIO()
                            excel_data_copy.to_excel(excel_buffer, index=False, engine='openpyxl')
                            excel_data = excel_buffer.getvalue()
                            
                            st.download_button(
                                label="📊 Download Full Dataset (Excel)",
                                data=excel_data,
                                file_name=f"cortex_raw_data_{start_date}_{end_date}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        except ImportError:
                            st.info("💡 Excel export requires openpyxl package")
                        except Exception as e:
                            st.warning(f"Excel export unavailable: {str(e)}")
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
        st.session_state['deployment_mode'] = 'Unknown'
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
    
    st.sidebar.markdown(f'<div style="color: {mode_color}; font-weight: bold; text-align: center; margin-top: 1rem;">{mode_emoji} Mode: {mode}</div>', 
                       unsafe_allow_html=True)
    
    # Show performance debugging dashboard if enabled
    if show_debug:
        st.header("🔍 Performance Debugging Dashboard")
        
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
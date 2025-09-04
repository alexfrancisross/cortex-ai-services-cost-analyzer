import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
import toml

# Add current directory and shared libraries to Python path for module imports
sys.path.append(os.path.dirname(__file__))
# Add shared libraries path for monorepo structure
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'libs', 'cortex-analytics', 'src'))

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
    from data_layer import SnowflakeDataLoader
    from reconciliation import ReconciliationEngine
    from visualizations import CortexVisualizer
    from utils import format_credits, get_status_color, calculate_percentage_change
except ImportError as e:
    st.error(f"Module import error: {e}")
    st.info("Please ensure all required modules are deployed with the application.")
    st.info("In monorepo structure, ensure libs/cortex-analytics/src is in artifacts.")
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
            st.markdown(f'<div class="data-freshness">{freshness_color} Data Fresh: {freshness_hours:.1f}h ago</div>', 
                       unsafe_allow_html=True)
        except:
            st.markdown('<div class="data-freshness">⚪ Data freshness unknown</div>', 
                       unsafe_allow_html=True)
    
    # Sidebar controls
    with st.sidebar:
        st.header("⚙️ Analysis Controls")
        
        # Initialize session state for date range defaults - 90 days
        if 'date_range_start' not in st.session_state:
            st.session_state.date_range_start = (datetime.now() - timedelta(days=90)).date()
        if 'date_range_end' not in st.session_state:
            st.session_state.date_range_end = datetime.now().date()
        
        # Quick date range buttons (placed before date picker to update session state)
        st.subheader("🚀 Quick Select")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📅 7d", help="Last 7 days"):
                st.session_state.date_range_start = (datetime.now() - timedelta(days=7)).date()
                st.session_state.date_range_end = datetime.now().date()
                st.rerun()
        with col2:
            if st.button("📅 30d", help="Last 30 days"):
                st.session_state.date_range_start = (datetime.now() - timedelta(days=30)).date()
                st.session_state.date_range_end = datetime.now().date()
                st.rerun()
        with col3:
            if st.button("📅 90d", help="Last 90 days"):
                st.session_state.date_range_start = (datetime.now() - timedelta(days=90)).date()
                st.session_state.date_range_end = datetime.now().date()
                st.rerun()
        
        # Date range selector using session state
        date_range = st.date_input(
            "📅 Analysis Period",
            value=(st.session_state.date_range_start, st.session_state.date_range_end),
            max_value=datetime.now().date(),
            help="Select the date range for analysis (defaults to last 90 days)",
            key="date_range_picker"
        )
        
        # Update session state when date picker changes
        if len(date_range) == 2:
            start_date, end_date = date_range
            st.session_state.date_range_start = start_date
            st.session_state.date_range_end = end_date
        else:
            start_date = date_range[0] if date_range else st.session_state.date_range_start
            end_date = st.session_state.date_range_end
        
        # Service filter
        available_services = data_loader.get_available_services()
        services_filter = st.multiselect(
            "🔧 Cortex Services",
            options=available_services,
            default=available_services,
            help="Select which Cortex services to include in analysis"
        )
        
        # Granularity selector
        granularity = st.selectbox(
            "📊 View Granularity",
            options=["Daily", "Hourly"],
            index=0,
            help="Choose the time granularity for detailed analysis"
        )
        
        # Export options
        st.subheader("📤 Export Options")
        if st.button("📥 Export CSV"):
            try:
                df = data_loader.get_service_breakdown(start_date, end_date, services_filter)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"cortex_analysis_{start_date}_{end_date}.csv",
                    mime="text/csv"
                )
            except Exception as e:
                st.error(f"Export failed: {str(e)}")
    
    # Main dashboard content
    try:
        render_executive_summary(data_loader, reconciler, start_date, end_date)
        render_service_breakdown(data_loader, visualizer, services_filter, start_date, end_date)
        render_reconciliation_analysis(reconciler, start_date, end_date)
        render_detailed_analysis(data_loader, start_date, end_date, granularity)
    except Exception as e:
        st.error(f"Dashboard rendering failed: {str(e)}")
        st.exception(e)

def render_executive_summary(data_loader, reconciler, start_date, end_date):
    """Render executive summary cards with clear AI_SERVICES reconciliation"""
    st.header("📊 Executive Summary")
    
    try:
        # Get AI Services reconciliation (the key insight)
        ai_recon = data_loader.get_ai_services_reconciliation(start_date, end_date)
        
        # Calculate trend (compare with previous period)
        period_days = (end_date - start_date).days
        prev_start = start_date - timedelta(days=period_days)
        prev_end = start_date
        prev_credits = data_loader.get_total_ai_services(prev_start, prev_end)
        trend_pct = calculate_percentage_change(prev_credits, ai_recon['ai_services_baseline'])
        
        # Clear reconciliation explanation
        st.info("""
        📋 **Reconciliation Logic**: AI_SERVICES (billing baseline) should equal the sum of all individual Cortex services.
        This ensures accurate cost attribution and validates our service breakdown.
        """)
        
        # Summary cards with clear reconciliation metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="💰 AI_SERVICES (Baseline)",
                value=f"{format_credits(ai_recon['ai_services_baseline'])} credits",
                delta=f"{trend_pct:+.1f}%" if trend_pct is not None else None,
                help="Authoritative billing total from METERING_HISTORY"
            )
        
        with col2:
            recon_status = ai_recon['reconciliation_status']
            recon_variance = ai_recon['variance_pct']
            
            status_emoji = {"EXCELLENT": "✅", "GOOD": "⚠️", "WARNING": "🟡", "CRITICAL": "🔴"}.get(recon_status, "⚪")
            
            st.metric(
                label="🎯 Service Reconciliation",
                value=f"{recon_variance:+.2f}%",
                delta=f"{status_emoji} {recon_status}",
                help="Variance between AI_SERVICES baseline and sum of individual services"
            )
        
        with col3:
            # Service coverage (what % of AI_SERVICES we can explain)
            coverage = ai_recon['coverage_pct']
            st.metric(
                label="📈 Service Coverage",
                value=f"{coverage:.2f}%",
                delta="Complete" if coverage > 99.5 else "Partial",
                help="Percentage of AI_SERVICES explained by individual service breakdown"
            )
        
        with col4:
            # Individual services total
            individual_total = ai_recon['total_individual']
            st.metric(
                label="🔧 Individual Services",
                value=f"{format_credits(individual_total)} credits",
                delta=f"{(individual_total - ai_recon['ai_services_baseline']):+.3f}",
                help="Sum of all individual Cortex service tables"
            )
        
        # Show reconciliation breakdown table
        if ai_recon['individual_services']:
            with st.expander("🔍 View Service Reconciliation Breakdown"):
                breakdown_data = []
                for service, credits in ai_recon['individual_services'].items():
                    if credits > 0:
                        breakdown_data.append({
                            'Service': service,
                            'Credits': format_credits(credits),
                            'Pct of Baseline': f"{(credits / ai_recon['ai_services_baseline'] * 100):.2f}%" if ai_recon['ai_services_baseline'] > 0 else "0%"
                        })
                
                breakdown_data.append({
                    'Service': '🔺 TOTAL INDIVIDUAL',
                    'Credits': format_credits(ai_recon['total_individual']),
                    'Pct of Baseline': f"{ai_recon['coverage_pct']:.2f}%"
                })
                
                breakdown_data.append({
                    'Service': '📊 AI_SERVICES BASELINE',
                    'Credits': format_credits(ai_recon['ai_services_baseline']),
                    'Pct of Baseline': "100.00%"
                })
                
                st.dataframe(pd.DataFrame(breakdown_data), use_container_width=True, hide_index=True)
            
    except Exception as e:
        st.error(f"Failed to load executive summary: {str(e)}")
        # Show placeholder metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💰 Total AI Services", "Loading...")
        with col2:
            st.metric("🎯 Reconciliation", "Loading...")
        with col3:
            st.metric("📈 Service Coverage", "Loading...")
        with col4:
            st.metric("⏰ Analysis Period", "Loading...")

def render_service_breakdown(data_loader, visualizer, services_filter, start_date, end_date):
    """Render enhanced service breakdown with clear AI_SERVICES reconciliation"""
    st.header("🔧 Service Breakdown & Reconciliation")
    
    try:
        # Get AI Services reconciliation data
        ai_recon = data_loader.get_ai_services_reconciliation(start_date, end_date)
        
        if ai_recon['ai_services_baseline'] == 0:
            st.warning("No AI Services usage data available for the selected period.")
            return
        
        # Prepare service breakdown data (excluding AI_SERVICES to avoid double counting)
        service_breakdown = []
        for service, credits in ai_recon['individual_services'].items():
            if credits > 0:
                service_breakdown.append({
                    'CATEGORY': service,
                    'CREDITS': credits
                })
        
        if not service_breakdown:
            st.info("No individual service usage in selected period")
            return
        
        service_breakdown_df = pd.DataFrame(service_breakdown)
        
        # Reconciliation summary at the top
        st.markdown(f"""
        **🎯 Reconciliation Summary:**
        - **AI_SERVICES Baseline**: {format_credits(ai_recon['ai_services_baseline'])} credits
        - **Individual Services Total**: {format_credits(ai_recon['total_individual'])} credits  
        - **Variance**: {ai_recon['variance_pct']:+.2f}% ({ai_recon['reconciliation_status']})
        - **Coverage**: {ai_recon['coverage_pct']:.2f}%
        """)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Enhanced service breakdown pie chart
            fig = px.pie(
                service_breakdown_df,
                values="CREDITS",
                names="CATEGORY",
                title=f"Individual Services Breakdown ({format_credits(ai_recon['total_individual'])} credits)",
                hole=0.4,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label+value")
            st.plotly_chart(fig, use_container_width=True)
            
            # Daily trend chart
            st.subheader("📈 Daily Usage Trends")
            daily_trend = data_loader.get_daily_trend_all_services(start_date, end_date)
            
            if not daily_trend.empty:
                fig_trend = px.line(
                    daily_trend,
                    x="USAGE_DATE",
                    y="CREDITS",
                    color="SERVICE",
                    title="Daily AI Credit Consumption Trend",
                    markers=True,
                )
                fig_trend.update_layout(
                    xaxis_title="Date", yaxis_title="Credits", hovermode="x unified"
                )
                st.plotly_chart(fig_trend, use_container_width=True)
        
        with col2:
            # Reconciliation table showing individual vs baseline
            st.subheader("🔍 Reconciliation Table")
            
            reconciliation_data = []
            for service, credits in ai_recon['individual_services'].items():
                if credits > 0:
                    reconciliation_data.append({
                        'Service': service,
                        'Credits': format_credits(credits),
                        '% of Baseline': f"{(credits / ai_recon['ai_services_baseline'] * 100):.2f}%"
                    })
            
            # Add totals row
            reconciliation_data.append({
                'Service': '🔺 INDIVIDUAL TOTAL',
                'Credits': format_credits(ai_recon['total_individual']),
                '% of Baseline': f"{ai_recon['coverage_pct']:.2f}%"
            })
            
            reconciliation_data.append({
                'Service': '📊 AI_SERVICES BASELINE',
                'Credits': format_credits(ai_recon['ai_services_baseline']),
                '% of Baseline': "100.00%"
            })
            
            st.dataframe(pd.DataFrame(reconciliation_data), use_container_width=True, hide_index=True)
            
            # Reconciliation status
            status_color = {"EXCELLENT": "🟢", "GOOD": "🟡", "WARNING": "🟠", "CRITICAL": "🔴"}.get(ai_recon['reconciliation_status'], "⚪")
            st.markdown(f"""
            **Reconciliation Status**: {status_color} {ai_recon['reconciliation_status']}
            
            **Variance Explanation**:
            - **Positive**: Individual services > AI_SERVICES
            - **Negative**: Individual services < AI_SERVICES  
            - **Target**: ±1% (Excellent), ±2% (Good)
            """)
        
        # Top cost drivers section
        st.subheader("💰 Top Cost Drivers (Model-Level Detail)")
        top_drivers = data_loader.get_top_cost_drivers(start_date, end_date, limit=15)
        
        if not top_drivers.empty:
            fig_drivers = px.bar(
                top_drivers,
                x="CREDITS",
                y="SERVICE",
                orientation="h",
                title="Top 15 AI Cost Drivers by Model",
                text="PCT_OF_TOTAL",
                labels={"CREDITS": "Credits", "SERVICE": "Service/Model"},
            )
            fig_drivers.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_drivers.update_layout(height=500)
            st.plotly_chart(fig_drivers, use_container_width=True)
            
            with st.expander("🔍 View Detailed Cost Driver Data"):
                st.dataframe(top_drivers, use_container_width=True)
        
    except Exception as e:
        st.error(f"Failed to load enhanced service breakdown: {str(e)}")

def render_reconciliation_analysis(reconciler, start_date, end_date):
    """Render reconciliation validation section"""
    st.header("🔍 Reconciliation Analysis")
    
    try:
        recon_results = reconciler.perform_three_tier_reconciliation(start_date, end_date)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Reconciliation tier comparison
            st.subheader("Three-Tier Validation")
            
            tiers_data = {
                'Tier': ['Organization', 'Account Hourly', 'Granular Services'],
                'Credits': [
                    recon_results.get('organization', 0),
                    recon_results.get('account_hourly', 0),
                    recon_results.get('granular_services', 0)
                ],
                'Description': [
                    'Billing baseline',
                    'Hourly metering',
                    'Sum of 6 services'
                ]
            }
            
            tiers_df = pd.DataFrame(tiers_data)
            tiers_df['Credits'] = tiers_df['Credits'].apply(format_credits)
            st.dataframe(tiers_df, use_container_width=True, hide_index=True)
        
        with col2:
            # Reconciliation status
            st.subheader("Validation Status")
            
            status = recon_results.get('reconciliation_status', 'UNKNOWN')
            variance = recon_results.get('variance_hourly_granular', 0)
            
            status_color = get_status_color(status)
            st.markdown(f'<h3 style="color: {status_color};">{status}</h3>', unsafe_allow_html=True)
            
            if variance is not None:
                st.metric("Variance", f"{variance:+.4f}%")
                
                if abs(variance) <= 1.0:
                    st.success("✅ Excellent reconciliation accuracy")
                elif abs(variance) <= 2.0:
                    st.warning("⚠️ Good reconciliation - minor variance")
                else:
                    st.error("❌ High variance - investigation needed")
            
            # Reconciliation methodology
            with st.expander("📖 Methodology"):
                st.write("""
                **Three-Tier Validation**:
                1. **Organization Level**: Billing reconciliation baseline
                2. **Account Hourly**: Hourly metering data
                3. **Granular Services**: Sum of all 6 service tables
                
                **Accuracy Targets**:
                - ≤1%: Excellent (✅)
                - 1-2%: Good (⚠️)
                - >2%: Investigate (❌)
                """)
    
    except Exception as e:
        st.error(f"Failed to load reconciliation analysis: {str(e)}")

def render_detailed_analysis(data_loader, start_date, end_date, granularity):
    """Render enhanced detailed analysis section with model-level insights"""
    st.header("📈 Enhanced Detailed Analysis")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Model Analysis", "Service Details", "Time Series", "Raw Data"])
    
    with tab1:
        # Model-level token analysis (new from monitoring dashboard)
        st.subheader("🤖 Model Token & Credit Analysis")
        
        with st.spinner('Loading model analysis...'):
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
                st.metric("Avg Tokens/Call", f"{avg_tokens_per_call:,.1f}")
            with col4:
                st.metric("Models Used", len(model_analysis))
            
            # Detailed model analysis table
            st.subheader("🔍 Detailed Model Metrics")
            display_df = model_analysis.copy()
            for col in ['TOTAL_TOKENS', 'TOTAL_CREDITS', 'AVG_TOKENS_PER_CALL', 'AVG_CREDITS_PER_CALL']:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(lambda x: f"{x:,.3f}" if x < 1 else f"{x:,.2f}")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
        else:
            st.info("No model usage data available for the selected period.")
    
    with tab2:
        try:
            with st.spinner('Loading service details...'):
                service_details = data_loader.get_detailed_service_breakdown(start_date, end_date)
            
            if not service_details.empty:
                st.subheader("Service Breakdown Details")
                
                # Format the dataframe for display
                display_df = service_details.copy()
                if 'total_credits' in display_df.columns:
                    display_df['total_credits'] = display_df['total_credits'].apply(format_credits)
                if 'percentage' in display_df.columns:
                    display_df['percentage'] = display_df['percentage'].apply(lambda x: f"{x:.2f}%")
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                # Service-specific insights
                for service in service_details['service_type'].unique():
                    service_data = service_details[service_details['service_type'] == service]
                    if not service_data.empty and service_data.iloc[0]['total_credits'] > 0:
                        with st.expander(f"🔍 {service} Details"):
                            st.write(f"**Granularity**: {service_data.iloc[0].get('granularity', 'Unknown')}")
                            st.write(f"**Records**: {service_data.iloc[0].get('record_count', 0):,}")
                            st.write(f"**Credits**: {format_credits(service_data.iloc[0]['total_credits'])}")
                            
                            # Show additional service-specific details
                            additional_details = data_loader.get_service_specific_details(service, start_date, end_date)
                            if not additional_details.empty:
                                st.dataframe(additional_details.head(10), use_container_width=True)
            else:
                st.info("No detailed service data available for the selected period.")
                
        except Exception as e:
            st.error(f"Failed to load service details: {str(e)}")
    
    with tab3:
        try:
            # Time series analysis
            st.subheader(f"Usage Trends ({granularity})")
            
            with st.spinner('Loading time series data...'):
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
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
                
                # Usage pattern insights
                total_by_period = time_series_data.groupby('period')['credits'].sum().reset_index()
                if len(total_by_period) > 1:
                    peak_usage = total_by_period.loc[total_by_period['credits'].idxmax()]
                    st.info(f"📊 **Peak Usage**: {peak_usage['period']} ({format_credits(peak_usage['credits'])} credits)")
            else:
                st.info("No time series data available for the selected period.")
                
        except Exception as e:
            st.error(f"Failed to load time series analysis: {str(e)}")
    
    with tab4:
        try:
            # Raw data export
            st.subheader("Raw Data Export")
            
            with st.spinner('Loading raw data...'):
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
                    # Excel export would require additional libraries
                    st.info("💡 Excel export available in production version")
            else:
                st.info("No raw data available for export.")
                
        except Exception as e:
            st.error(f"Failed to load raw data: {str(e)}")

if __name__ == "__main__":
    main()

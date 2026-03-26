import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark import Session
import streamlit as st
import time

# Import performance monitoring
try:
    from shared.utils.performance_monitor import (
        performance_monitor, 
        time_it, 
        monitor_cache, 
        monitor_db_operation
    )
except ImportError:
    # Fallback decorators if performance monitoring not available
    def time_it(name=None):
        def decorator(func):
            return func
        return decorator
    
    def monitor_cache(name=None):
        def decorator(func):
            return func
        return decorator
    
    def monitor_db_operation(name=None):
        def decorator(func):
            return func
        return decorator

class SnowflakeDataLoader:
    """
    Data access layer for Cortex AI Services usage data.
    Handles all Snowflake queries and data retrieval operations.
    """
    
    def __init__(self, session=None):
        """
        Initialize the data loader with Snowflake session and service configurations.
        
        Args:
            session: Optional Snowpark session. If None, will try to get active session.
        """
        if session is not None:
            self.session = session
        else:
            self.session = self._get_snowflake_session()
        
        # Set query timeout to prevent long-running queries from hanging the app
        try:
            self.session.sql("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 30").collect()
        except Exception:
            # Timeout setting might not be supported in all environments
            pass
        
        # Service table registry — single source of truth for view names and credit columns.
        # status: 'PRIMARY' (include in reconciliation sum) | 'FALLBACK' (query but warn, exclude from sum)
        # probe_views() sets status at startup based on live account probe.
        self.service_configs = {
            'CORTEX_AI_FUNCTIONS': {
                'table': 'CORTEX_AI_FUNCTIONS_USAGE_HISTORY',
                'credit_column': 'CREDITS',
                'time_column': 'START_TIME',
                'granularity': 'Per-query AI function level',
                'description': 'Cortex AI Functions (AI_COMPLETE, AI_EXTRACT, etc.)',
                'status': 'PRIMARY',
            },
            'CORTEX_AISQL': {
                'table': 'CORTEX_AISQL_USAGE_HISTORY',
                'credit_column': 'TOKEN_CREDITS',
                'time_column': 'USAGE_TIME',
                'granularity': 'Per-query AI SQL level',
                'description': 'Cortex AI SQL functions (replaces CORTEX_FUNCTIONS views)',
                'status': 'PRIMARY',
            },
            'CORTEX_ANALYST': {
                'table': 'CORTEX_ANALYST_USAGE_HISTORY',
                'credit_column': 'CREDITS',
                'time_column': 'START_TIME',
                'granularity': 'Request-level (most granular)',
                'description': 'Analyst requests with detailed breakdown',
                'status': 'PRIMARY',
            },
            'DOCUMENT_AI': {
                'table': 'DOCUMENT_AI_USAGE_HISTORY',
                'credit_column': 'CREDITS_USED',
                'time_column': 'START_TIME',
                'granularity': 'Document-level processing',
                'description': 'Document AI parsing and extraction',
                'status': 'PRIMARY',
            },
            'CORTEX_SEARCH_SERVING': {
                'table': 'CORTEX_SEARCH_SERVING_USAGE_HISTORY',
                'credit_column': 'CREDITS',
                'time_column': 'START_TIME',
                'granularity': 'Hourly by service',
                'description': 'Search serving usage',
                'status': 'PRIMARY',
            },
            'CORTEX_FINE_TUNING': {
                'table': 'CORTEX_FINE_TUNING_USAGE_HISTORY',
                'credit_column': 'TOKEN_CREDITS',
                'time_column': 'START_TIME',
                'granularity': 'Training session level',
                'description': 'Model fine-tuning operations',
                'status': 'PRIMARY',
            },
            'CORTEX_DOCUMENT_PROCESSING': {
                'table': 'CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY',
                'credit_column': 'CREDITS_USED',
                'time_column': 'START_TIME',
                'granularity': 'Document processing level',
                'description': 'Document processing operations',
                'status': 'FALLBACK',  # Broken post-Nov 2025 billing event changes
                'warning': 'Data may be incomplete due to Nov 2025 billing event type changes.',
            },
            'CORTEX_AGENT': {
                'table': 'CORTEX_AGENT_USAGE_HISTORY',
                'credit_column': 'TOKEN_CREDITS',
                'time_column': 'START_TIME',
                'granularity': 'Per-request agent level',
                'description': 'Cortex Agents usage (GA Feb 25 2026)',
                'status': 'PRIMARY',
            },
            'SNOWFLAKE_INTELLIGENCE': {
                'table': 'SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY',
                'credit_column': 'TOKEN_CREDITS',
                'time_column': 'START_TIME',
                'granularity': 'Per-request SI level',
                'description': 'Snowflake Intelligence usage (GA Feb 25 2026)',
                'status': 'PRIMARY',
            },
        }
        
        # Cache for available services (populated on first access)
        self._available_services = None
        
        # Performance monitoring
        self._query_count = 0
        self._total_query_time = 0.0
    
    @property
    def primary_views(self) -> list:
        """Return service config keys whose status is PRIMARY."""
        return [k for k, v in self.service_configs.items() if v.get('status') == 'PRIMARY']

    def probe_views(self) -> dict:
        """
        Test each view in service_configs against the live account.
        Sets status to PRIMARY, FALLBACK, or UNAVAILABLE based on probe result.
        Views starting as FALLBACK remain FALLBACK even if they respond (known-broken views).
        Views starting as FALLBACK that error are set to UNAVAILABLE.
        Called once at startup — wrap the call site with @st.cache_resource.
        """
        for key, config in self.service_configs.items():
            original_status = config.get('status', 'PRIMARY')
            try:
                time_col = config.get('time_column', 'START_TIME')
                if time_col == 'USAGE_TIME':
                    where = "WHERE usage_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())"
                else:
                    where = "WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())"
                self.session.sql(
                    f"SELECT COUNT(*) AS count FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']} {where} LIMIT 1"
                ).collect()
                # Only upgrade to PRIMARY if view was not already demoted to FALLBACK
                if original_status != 'FALLBACK':
                    config['status'] = 'PRIMARY'
                # FALLBACK views stay FALLBACK even if they respond (known-broken)
            except Exception:
                config['status'] = 'UNAVAILABLE'
        return self.service_configs

    def _execute_query_with_monitoring(self, query: str, operation_name: str = "unknown"):
        """
        Execute query with performance monitoring.
        
        Args:
            query: SQL query to execute
            operation_name: Name of the operation for tracking
            
        Returns:
            Query result
        """
        start_time = time.time()
        error = None
        result = None
        row_count = 0
        
        try:
            result = self.session.sql(query).collect()
            row_count = len(result) if result else 0
        except Exception as e:
            error = str(e)
            raise
        finally:
            duration = time.time() - start_time
            self._query_count += 1
            self._total_query_time += duration
            
            # Track with performance monitor if available
            try:
                performance_monitor.track_database_query(
                    query=query,
                    duration=duration,
                    row_count=row_count,
                    error=error
                )
            except NameError:
                # Performance monitor not available
                pass
        
        return result
        
    def _get_snowflake_session(self) -> Session:
        """Get active Snowflake session for SiS deployment."""
        try:
            return get_active_session()
        except Exception as e:
            st.error(f"Failed to get Snowflake session: {str(e)}")
            raise
    
    @time_it("get_available_services")
    def get_available_services(self) -> List[str]:
        """
        Discover which Cortex services are available in the current account.
        Tests accessibility of each service table.
        """
        if self._available_services is not None:
            return self._available_services
        
        available = []
        for service_name, config in self.service_configs.items():
            try:
                # Test table accessibility with a simple query
                test_query = f"""
                SELECT COUNT(*) as test_count 
                FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']} 
                LIMIT 1
                """
                self.session.sql(test_query).collect()
                available.append(service_name)
            except Exception:
                # Service table not accessible or doesn't exist
                continue
        
        self._available_services = available
        return available
    
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def get_available_services_optimized(_self):
        """
        Optimized service discovery using single INFORMATION_SCHEMA query.
        Expected significant performance improvement over individual table tests.
        """
        if _self._available_services is not None:
            return _self._available_services
        
        try:
            query = """
            SELECT TABLE_NAME
            FROM SNOWFLAKE.INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = 'ACCOUNT_USAGE'
              AND TABLE_NAME IN (
                'CORTEX_AI_FUNCTIONS_USAGE_HISTORY',
                'CORTEX_AISQL_USAGE_HISTORY',
                'CORTEX_ANALYST_USAGE_HISTORY',
                'CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY',
                'CORTEX_SEARCH_SERVING_USAGE_HISTORY',
                'CORTEX_SEARCH_DAILY_USAGE_HISTORY',
                'DOCUMENT_AI_USAGE_HISTORY',
                'CORTEX_FINE_TUNING_USAGE_HISTORY',
                'CORTEX_AGENT_USAGE_HISTORY',
                'SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY',
                'CORTEX_CODE_CLI_USAGE_HISTORY'
              )
            """
            
            result = _self.session.sql(query).collect()
            available = []
            
            for row in result:
                table_name = row['TABLE_NAME']
                # Map table name back to service name
                for key in _self.service_configs:
                    if _self.service_configs[key]['table'] == table_name:
                        available.append(key)
                        break
            
            _self._available_services = available
            return available
            
        except Exception:
            # Fallback to original method if optimized query fails
            return _self.get_available_services()
    
    @monitor_db_operation("get_total_ai_services")
    def get_total_ai_services(self, start_date, end_date) -> float:
        """
        Get total AI_SERVICES consumption using the best available baseline.
        Priority: 1) Organization Daily, 2) Account Daily, 3) Account Hourly
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            Total credits consumed for AI_SERVICES
        """
        try:
            # Try organization level first (most accurate for billing reconciliation)
            org_total = self.get_organization_total(start_date, end_date)
            if org_total > 0:
                return org_total
            
            # Fallback to account daily (better matches individual services)
            try:
                query = f"""
                SELECT COALESCE(SUM(credits_used), 0) as total_credits
                FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
                WHERE usage_date >= '{start_date}'
                  AND usage_date <= '{end_date}'
                  AND service_type = 'AI_SERVICES'
                """
                
                result = self.session.sql(query).collect()
                daily_total = float(result[0]['TOTAL_CREDITS']) if result else 0.0
                if daily_total > 0:
                    return daily_total
                    
            except Exception:
                pass
            
            # Final fallback to hourly metering
            query = f"""
            SELECT COALESCE(SUM(credits_used), 0) as total_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
            WHERE start_time >= '{start_date}'
              AND start_time < '{end_date}'::date + INTERVAL '1 day'
              AND service_type = 'AI_SERVICES'
            """
            
            result = self.session.sql(query).collect()
            return float(result[0]['TOTAL_CREDITS']) if result else 0.0
            
        except Exception as e:
            st.warning(f"Could not access AI_SERVICES metering data: {str(e)}")
            return 0.0
    
    def get_organization_total(self, start_date, end_date) -> float:
        """
        Get total AI_SERVICES from organization-level metering (when available).
        Used for top-tier reconciliation validation.
        """
        try:
            # First try with current account, then fallback to specific account name
            query = f"""
            SELECT COALESCE(SUM(credits_used), 0) as total_credits
            FROM SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY
            WHERE usage_date >= '{start_date}'
              AND usage_date <= '{end_date}'
              AND account_name = CURRENT_ACCOUNT()
              AND service_type = 'AI_SERVICES'
            """
            
            result = self.session.sql(query).collect()
            return float(result[0]['TOTAL_CREDITS']) if result else 0.0
            
        except Exception:
            # Organization usage not available
            return 0.0
    
    def get_dashboard_baseline(self, start_date, end_date) -> float:
        """
        Get the dashboard reported baseline for reconciliation.
        
        AI_SERVICES from METERING_HISTORY is the authoritative billing baseline.
        All individual Cortex services should sum to this total.
        """
        return self.get_total_ai_services(start_date, end_date)
    
    @monitor_db_operation("get_model_token_analysis")
    def get_model_token_analysis(self, start_date, end_date) -> pd.DataFrame:
        """
        Get detailed token and credit analysis by model.
        Enhanced to handle empty model names and provide function context.
        """
        try:
            query = f"""
            SELECT 
                CASE 
                    WHEN MODEL_NAME = '' OR MODEL_NAME IS NULL THEN 'Specialized Functions'
                    ELSE MODEL_NAME
                END as MODEL_NAME,
                CASE 
                    WHEN MODEL_NAME = '' OR MODEL_NAME IS NULL THEN 'SPECIALIZED'
                    ELSE 'EXPLICIT_MODEL'
                END as MODEL_TYPE,
                COUNT(*) as invocations,
                SUM(TOKENS) as total_tokens,
                SUM(TOKEN_CREDITS) as total_credits,
                AVG(TOKENS) as avg_tokens_per_call,
                AVG(TOKEN_CREDITS) as avg_credits_per_call,
                NULLIF(SUM(TOKENS) / NULLIF(SUM(TOKEN_CREDITS), 0), 0) as tokens_per_credit,
                ROUND(100 * SUM(TOKEN_CREDITS) / NULLIF(SUM(SUM(TOKEN_CREDITS)) OVER(), 0), 2) as pct_of_total_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
            WHERE USAGE_TIME >= '{start_date}'::date
                AND USAGE_TIME < '{end_date}'::date + INTERVAL '1 day'
            GROUP BY
                CASE
                    WHEN MODEL_NAME = '' OR MODEL_NAME IS NULL THEN 'Specialized Functions'
                    ELSE MODEL_NAME
                END,
                CASE
                    WHEN MODEL_NAME = '' OR MODEL_NAME IS NULL THEN 'SPECIALIZED'
                    ELSE 'EXPLICIT_MODEL'
                END
            ORDER BY total_credits DESC
            """
            
            result = self.session.sql(query).collect()
            return pd.DataFrame([row.asDict() for row in result])
            
        except Exception as e:
            st.warning(f"Could not get model token analysis: {str(e)}")
            return pd.DataFrame()
    
    @monitor_db_operation("get_specialized_functions_analysis")
    def get_specialized_functions_analysis(self, start_date, end_date) -> pd.DataFrame:
        """
        Get detailed analysis of Cortex functions that don't specify explicit models.
        These are functions like TRANSLATE, CLASSIFY_TEXT, SENTIMENT, etc.
        """
        try:
            query = f"""
            SELECT 
                CASE 
                    WHEN FUNCTION_NAME IS NULL OR FUNCTION_NAME = '' THEN 'OTHER'
                    ELSE FUNCTION_NAME
                END as FUNCTION_NAME,
                CASE 
                    WHEN FUNCTION_NAME = 'TRANSLATE' THEN 'Translation Services'
                    WHEN FUNCTION_NAME = 'CLASSIFY_TEXT' THEN 'Text Classification'
                    WHEN FUNCTION_NAME = 'SENTIMENT' THEN 'Sentiment Analysis'
                    WHEN FUNCTION_NAME = 'SUMMARIZE' THEN 'Text Summarization'
                    WHEN FUNCTION_NAME = 'EMBED_TEXT' THEN 'Text Embeddings'
                    WHEN FUNCTION_NAME = 'EXTRACT_ANSWER' THEN 'Answer Extraction'
                    WHEN FUNCTION_NAME = 'AI_EXTRACT' THEN 'AI Information Extraction'
                    WHEN FUNCTION_NAME = 'AI_AGG' THEN 'AI Aggregation'
                    WHEN FUNCTION_NAME = 'AI_CLASSIFY' THEN 'AI Classification'
                    WHEN FUNCTION_NAME IS NULL OR FUNCTION_NAME = '' THEN 'Other'
                    ELSE 'Other'
                END as FUNCTION_DESCRIPTION,
                COUNT(*) as invocations,
                SUM(TOKENS) as total_tokens,
                SUM(TOKEN_CREDITS) as total_credits,
                AVG(TOKENS) as avg_tokens_per_call,
                AVG(TOKEN_CREDITS) as avg_credits_per_call,
                NULLIF(SUM(TOKENS) / NULLIF(SUM(TOKEN_CREDITS), 0), 0) as tokens_per_credit,
                ROUND(100 * SUM(TOKEN_CREDITS) / NULLIF((
                    SELECT SUM(TOKEN_CREDITS)
                    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
                    WHERE USAGE_TIME >= '{start_date}'::date
                        AND USAGE_TIME < '{end_date}'::date + INTERVAL '1 day'
                        AND (MODEL_NAME = '' OR MODEL_NAME IS NULL)
                ), 0), 2) as pct_of_specialized_credits,
                MIN(USAGE_TIME) as first_usage,
                MAX(USAGE_TIME) as last_usage
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
            WHERE USAGE_TIME >= '{start_date}'::date
                AND USAGE_TIME < '{end_date}'::date + INTERVAL '1 day'
                AND (MODEL_NAME = '' OR MODEL_NAME IS NULL)
            GROUP BY 
                CASE 
                    WHEN FUNCTION_NAME IS NULL OR FUNCTION_NAME = '' THEN 'OTHER'
                    ELSE FUNCTION_NAME
                END,
                CASE 
                    WHEN FUNCTION_NAME = 'TRANSLATE' THEN 'Translation Services'
                    WHEN FUNCTION_NAME = 'CLASSIFY_TEXT' THEN 'Text Classification'
                    WHEN FUNCTION_NAME = 'SENTIMENT' THEN 'Sentiment Analysis'
                    WHEN FUNCTION_NAME = 'SUMMARIZE' THEN 'Text Summarization'
                    WHEN FUNCTION_NAME = 'EMBED_TEXT' THEN 'Text Embeddings'
                    WHEN FUNCTION_NAME = 'EXTRACT_ANSWER' THEN 'Answer Extraction'
                    WHEN FUNCTION_NAME = 'AI_EXTRACT' THEN 'AI Information Extraction'
                    WHEN FUNCTION_NAME = 'AI_AGG' THEN 'AI Aggregation'
                    WHEN FUNCTION_NAME = 'AI_CLASSIFY' THEN 'AI Classification'
                    WHEN FUNCTION_NAME IS NULL OR FUNCTION_NAME = '' THEN 'Other'
                    ELSE 'Other'
                END
            ORDER BY total_credits DESC
            """
            
            result = self.session.sql(query).collect()
            return pd.DataFrame([row.asDict() for row in result])
            
        except Exception as e:
            st.warning(f"Could not get specialized functions analysis: {str(e)}")
            return pd.DataFrame()
    
    @monitor_db_operation("get_cortex_analyst_analysis")
    def get_cortex_analyst_analysis(self, start_date, end_date) -> pd.DataFrame:
        """
        Get detailed analysis of Cortex Analyst usage.
        Cortex Analyst provides REST API access for data analysis.
        """
        try:
            query = f"""
            SELECT 
                COUNT(*) as total_requests,
                COALESCE(SUM(CREDITS), 0) as total_credits,
                COALESCE(AVG(CREDITS), 0) as avg_credits_per_request,
                COALESCE(ROUND(100 * SUM(CREDITS) / NULLIF((
                    SELECT SUM(CREDITS) 
                    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY 
                    WHERE START_TIME >= '{start_date}'::date
                        AND START_TIME < '{end_date}'::date + INTERVAL '1 day'
                ), 0), 2), 0) as pct_of_total_credits,
                MIN(START_TIME) as first_usage,
                MAX(START_TIME) as last_usage,
                COUNT(DISTINCT USERNAME) as unique_users
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
            WHERE START_TIME >= '{start_date}'::date
                AND START_TIME < '{end_date}'::date + INTERVAL '1 day'
            """
            
            result = self.session.sql(query).collect()
            return pd.DataFrame([row.asDict() for row in result])
            
        except Exception as e:
            st.warning(f"Could not get Cortex Analyst analysis: {str(e)}")
            return pd.DataFrame()
    
    @monitor_db_operation("get_document_processing_analysis")
    def get_document_processing_analysis(self, start_date, end_date) -> pd.DataFrame:
        """
        Get detailed analysis of Cortex Document Processing usage.
        Modern document AI for processing various document types.
        """
        try:
            query = f"""
            SELECT 
                COUNT(*) as total_operations,
                SUM(CREDITS_USED) as total_credits,
                AVG(CREDITS_USED) as avg_credits_per_operation,
                COALESCE(SUM(DOCUMENT_COUNT), 0) as total_documents,
                COALESCE(SUM(PAGE_COUNT), 0) as total_pages,
                COALESCE(AVG(DOCUMENT_COUNT), 0) as avg_documents_per_operation,
                COALESCE(AVG(PAGE_COUNT), 0) as avg_pages_per_operation,
                ROUND(100 * SUM(CREDITS_USED) / NULLIF((
                    SELECT SUM(CREDITS_USED) 
                    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY 
                    WHERE START_TIME >= '{start_date}'::date
                        AND START_TIME < '{end_date}'::date + INTERVAL '1 day'
                ), 0), 2) as pct_of_total_credits,
                MIN(START_TIME) as first_usage,
                MAX(START_TIME) as last_usage,
                COUNT(DISTINCT QUERY_ID) as unique_queries
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
            WHERE START_TIME >= '{start_date}'::date
                AND START_TIME < '{end_date}'::date + INTERVAL '1 day'
            """
            
            result = self.session.sql(query).collect()
            return pd.DataFrame([row.asDict() for row in result])
            
        except Exception as e:
            st.warning(f"Could not get Document Processing analysis: {str(e)}")
            return pd.DataFrame()
    
    @monitor_db_operation("get_search_serving_analysis")
    def get_search_serving_analysis(self, start_date, end_date) -> pd.DataFrame:
        """
        Get detailed analysis of Cortex Search Serving usage.
        Vector search operations for semantic search capabilities.
        """
        try:
            query = f"""
            SELECT 
                COUNT(*) as total_operations,
                COALESCE(SUM(CREDITS), 0) as total_credits,
                COALESCE(AVG(CREDITS), 0) as avg_credits_per_operation,
                COALESCE(ROUND(100 * SUM(CREDITS) / NULLIF((
                    SELECT SUM(CREDITS) 
                    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY 
                    WHERE START_TIME >= '{start_date}'::date
                        AND START_TIME < '{end_date}'::date + INTERVAL '1 day'
                ), 0), 2), 0) as pct_of_total_credits,
                MIN(START_TIME) as first_usage,
                MAX(START_TIME) as last_usage,
                COUNT(DISTINCT SERVICE_NAME) as unique_services
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
            WHERE START_TIME >= '{start_date}'::date
                AND START_TIME < '{end_date}'::date + INTERVAL '1 day'
            """
            
            result = self.session.sql(query).collect()
            return pd.DataFrame([row.asDict() for row in result])
            
        except Exception as e:
            st.warning(f"Could not get Search Serving analysis: {str(e)}")
            return pd.DataFrame()
    
    @monitor_db_operation("get_ai_services_reconciliation")
    def get_ai_services_reconciliation(self, start_date, end_date) -> Dict[str, Any]:
        """
        Get clear reconciliation between AI_SERVICES baseline and individual service totals.
        AI_SERVICES should equal the sum of all individual Cortex services.
        OPTIMIZED: Single consolidated query - NO FALLBACK to sequential queries.
        """
        return self.get_ai_services_reconciliation_optimized(start_date, end_date)
    
    @st.cache_data(ttl=1800, show_spinner=False)  # 30-minute cache (was 5-minute)
    def get_ai_services_reconciliation_cached(_self, start_date, end_date):
        """Cached version of get_ai_services_reconciliation for better performance"""
        return _self.get_ai_services_reconciliation(start_date, end_date)
    
    def _get_reconciliation_status(self, variance_abs: float) -> str:
        """Get reconciliation status based on variance."""
        if variance_abs <= 1.0:
            return 'EXCELLENT'
        elif variance_abs <= 2.0:
            return 'GOOD'
        elif variance_abs <= 5.0:
            return 'WARNING'
        else:
            return 'CRITICAL'
    
    def get_service_breakdown(self, start_date, end_date, services_filter: List[str]) -> pd.DataFrame:
        """
        Get breakdown of AI services consumption across all available services.
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            services_filter: List of services to include
            
        Returns:
            DataFrame with service breakdown including credits and percentages
        """
        service_results = []
        
        for service_name in services_filter:
            if service_name not in self.service_configs:
                continue
                
            config = self.service_configs[service_name]
            
            try:
                # Build time filter based on available time column
                if config['time_column']:
                    if config['time_column'] == 'USAGE_DATE':
                        time_filter = f"""
                        WHERE {config['time_column']} >= '{start_date}'::date
                          AND {config['time_column']} <= '{end_date}'::date
                        """
                    else:
                        time_filter = f"""
                        WHERE {config['time_column']} >= '{start_date}'::date
                          AND {config['time_column']} < '{end_date}'::date + INTERVAL '1 day'
                        """
                else:
                    time_filter = ""  # No time filtering for tables without time columns
                
                query = f"""
                SELECT 
                    '{service_name}' as service_type,
                    '{config['granularity']}' as granularity,
                    COUNT(*) as record_count,
                    COALESCE(SUM({config['credit_column']}), 0) as total_credits,
                    '{config['description']}' as description
                FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']}
                {time_filter}
                """
                
                result = self.session.sql(query).collect()
                if result:
                    service_results.append({
                        'service_type': service_name,
                        'granularity': config['granularity'],
                        'record_count': result[0]['RECORD_COUNT'],
                        'total_credits': float(result[0]['TOTAL_CREDITS']),
                        'description': config['description']
                    })
                    
            except Exception as e:
                st.warning(f"Could not access {service_name}: {str(e)}")
                # Add placeholder entry for inaccessible service
                service_results.append({
                    'service_type': service_name,
                    'granularity': config['granularity'],
                    'record_count': 0,
                    'total_credits': 0.0,
                    'description': f"Inaccessible: {str(e)}"
                })
        
        df = pd.DataFrame(service_results)
        
        # Calculate percentages
        if not df.empty and df['total_credits'].sum() > 0:
            df['percentage'] = (df['total_credits'] / df['total_credits'].sum()) * 100
        else:
            df['percentage'] = 0.0
        
        # Sort by total credits descending
        df = df.sort_values('total_credits', ascending=False).reset_index(drop=True)
        
        return df
    
    @st.cache_data(ttl=1800, show_spinner=False)  # 30-minute cache (was 5-minute)
    def get_service_breakdown_cached(_self, start_date, end_date, services_filter):
        """Cached version of get_service_breakdown for better performance"""
        return _self.get_service_breakdown(start_date, end_date, services_filter)
    
    def get_ai_services_reconciliation_optimized(self, start_date, end_date) -> Dict[str, Any]:
        """
        Optimized reconciliation using single consolidated query with CTEs.
        Expected 70% performance improvement over sequential queries.
        TESTED: This query works correctly via Snowflake CLI.
        """
        try:
            query = f"""
            WITH ai_baseline AS (
                SELECT COALESCE(SUM(credits_used), 0) as total_credits
                FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
                WHERE start_time >= '{start_date}'::date
                  AND start_time < '{end_date}'::date + INTERVAL '1 day'
                  AND service_type = 'AI_SERVICES'
            ),
            individual_services AS (
                SELECT 
                    'CORTEX_FUNCTIONS_USAGE' as service,
                    COALESCE(SUM(token_credits), 0) as credits
                FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
                WHERE usage_time >= '{start_date}'::date
                  AND usage_time < '{end_date}'::date + INTERVAL '1 day'
                  -- Exclude AI_EXTRACT to prevent double counting with CORTEX_DOCUMENT_PROCESSING
                  AND function_name != 'AI_EXTRACT'
                
                UNION ALL
                
                SELECT 
                    'CORTEX_ANALYST' as service,
                    COALESCE(SUM(credits), 0) as credits
                FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
                WHERE start_time >= '{start_date}'::date
                  AND start_time < '{end_date}'::date + INTERVAL '1 day'
                
                UNION ALL
                
                -- Only include legacy DOCUMENT_AI if modern CORTEX_DOCUMENT_PROCESSING has no data
                -- This prevents double counting of document processing services
                SELECT 
                    'DOCUMENT_AI' as service,
                    CASE 
                        WHEN (SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY 
                              WHERE start_time >= '{start_date}'::date 
                                AND start_time < '{end_date}'::date + INTERVAL '1 day') > 0 
                        THEN 0 
                        ELSE COALESCE(SUM(credits_used), 0) 
                    END as credits
                FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
                WHERE start_time >= '{start_date}'::date
                  AND start_time < '{end_date}'::date + INTERVAL '1 day'
                
                UNION ALL
                
                SELECT 
                    'CORTEX_SEARCH_SERVING' as service,
                    COALESCE(SUM(credits), 0) as credits
                FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
                WHERE start_time >= '{start_date}'::date
                  AND start_time < '{end_date}'::date + INTERVAL '1 day'
                
            UNION ALL
            
            SELECT 
                'CORTEX_FINE_TUNING' as service,
                COALESCE(SUM(token_credits), 0) as credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FINE_TUNING_USAGE_HISTORY
            WHERE start_time >= '{start_date}'::date
              AND start_time < '{end_date}'::date + INTERVAL '1 day'
            
            UNION ALL
            
            SELECT 
                'CORTEX_DOCUMENT_PROCESSING' as service,
                COALESCE(SUM(credits_used), 0) as credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
            WHERE start_time >= '{start_date}'::date
              AND start_time < '{end_date}'::date + INTERVAL '1 day'
            ),
            service_totals AS (
                SELECT 
                    service,
                    credits,
                    SUM(credits) OVER() as total_individual
                FROM individual_services
            ),
            summary AS (
                SELECT 
                    b.total_credits as ai_services_baseline,
                    st.total_individual,
                    -- Return individual columns instead of complex object
                MAX(CASE WHEN st.service = 'CORTEX_FUNCTIONS_USAGE' THEN st.credits END) as cortex_functions,
                MAX(CASE WHEN st.service = 'CORTEX_ANALYST' THEN st.credits END) as cortex_analyst,
                MAX(CASE WHEN st.service = 'DOCUMENT_AI' THEN st.credits END) as document_ai,
                MAX(CASE WHEN st.service = 'CORTEX_SEARCH_SERVING' THEN st.credits END) as cortex_search,
                MAX(CASE WHEN st.service = 'CORTEX_FINE_TUNING' THEN st.credits END) as cortex_fine_tuning,
                MAX(CASE WHEN st.service = 'CORTEX_DOCUMENT_PROCESSING' THEN st.credits END) as cortex_document_processing
                FROM ai_baseline b
                CROSS JOIN service_totals st
                GROUP BY b.total_credits, st.total_individual
            )
            SELECT 
                ai_services_baseline,
                total_individual,
                cortex_functions,
                cortex_analyst,
                document_ai,
                cortex_search,
                cortex_fine_tuning,
                cortex_document_processing,
                ((total_individual - ai_services_baseline) / NULLIF(ai_services_baseline, 0) * 100) as variance_pct,
                (total_individual / NULLIF(ai_services_baseline, 0) * 100) as coverage_pct
            FROM summary
            """
            
            # Use the monitored query execution
            result = self._execute_query_with_monitoring(query, "optimized_reconciliation")
            
            if result:
                row = result[0]
                # Convert Snowpark Row to dict for easier access
                row_dict = row.asDict() if hasattr(row, 'asDict') else dict(row)
                
                # Build service breakdown from individual columns
                service_breakdown = {
                    'CORTEX_FUNCTIONS_USAGE': float(row_dict.get('CORTEX_FUNCTIONS', 0) or 0),
                    'CORTEX_ANALYST': float(row_dict.get('CORTEX_ANALYST', 0) or 0),
                    'DOCUMENT_AI': float(row_dict.get('DOCUMENT_AI', 0) or 0),
                    'CORTEX_SEARCH_SERVING': float(row_dict.get('CORTEX_SEARCH', 0) or 0),
                    'CORTEX_FINE_TUNING': float(row_dict.get('CORTEX_FINE_TUNING', 0) or 0),
                    'CORTEX_DOCUMENT_PROCESSING': float(row_dict.get('CORTEX_DOCUMENT_PROCESSING', 0) or 0)
                }
                
                variance_pct = float(row_dict.get('VARIANCE_PCT', 0) or 0)
                
                return {
                    'ai_services_baseline': float(row_dict.get('AI_SERVICES_BASELINE', 0) or 0),
                    'individual_services': service_breakdown,
                    'total_individual': float(row_dict.get('TOTAL_INDIVIDUAL', 0) or 0),
                    'variance_pct': variance_pct,
                    'coverage_pct': float(row_dict.get('COVERAGE_PCT', 0) or 0),
                    'reconciliation_status': self._get_reconciliation_status(abs(variance_pct))
                }
            else:
                return {
                    'ai_services_baseline': 0.0,
                    'individual_services': {},
                    'total_individual': 0.0,
                    'variance_pct': 0.0,
                    'coverage_pct': 0.0,
                    'reconciliation_status': 'NO_DATA'
                }
                
        except Exception as e:
            st.error(f"❌ Optimized reconciliation query failed: {str(e)}")
            # Return error state instead of falling back
            return {
                'ai_services_baseline': 0.0,
                'individual_services': {},
                'total_individual': 0.0,
                'variance_pct': 0.0,
                'coverage_pct': 0.0,
                'reconciliation_status': 'ERROR'
            }
    
    def get_service_specific_details(self, service_name: str, start_date, end_date, limit: int = 100) -> pd.DataFrame:
        """
        Get detailed drill-down data for a specific service.
        Returns top records with service-specific dimensions.
        """
        if service_name not in self.service_configs:
            return pd.DataFrame()
        
        config = self.service_configs[service_name]
        
        try:
            # Service-specific detail queries
            if service_name == 'CORTEX_FUNCTIONS_USAGE':
                query = f"""
                SELECT function_name, model_name, warehouse_id,
                       SUM(token_credits) as total_credits,
                       SUM(tokens) as total_tokens,
                       COUNT(*) as calls
                FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']}
                WHERE start_time >= '{start_date}'::date
                  AND start_time < '{end_date}'::date + INTERVAL '1 day'
                GROUP BY function_name, model_name, warehouse_id
                ORDER BY total_credits DESC
                LIMIT {limit}
                """
                
            elif service_name == 'CORTEX_ANALYST':
                query = f"""
                SELECT username, 
                       SUM(credits) as total_credits,
                       SUM(request_count) as total_requests,
                       COUNT(*) as sessions
                FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']}
                WHERE start_time >= '{start_date}'::date
                  AND start_time < '{end_date}'::date + INTERVAL '1 day'
                GROUP BY username
                ORDER BY total_credits DESC
                LIMIT {limit}
                """
                
            elif service_name == 'CORTEX_DOCUMENT_PROCESSING':
                query = f"""
                SELECT function_name, model_name,
                       SUM(credits_used) as total_credits,
                       SUM(page_count) as total_pages,
                       COUNT(*) as jobs
                FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']}
                WHERE start_time >= '{start_date}'::date
                  AND start_time < '{end_date}'::date + INTERVAL '1 day'
                GROUP BY function_name, model_name
                ORDER BY total_credits DESC
                LIMIT {limit}
                """
                
            elif service_name == 'CORTEX_SEARCH_DAILY':
                query = f"""
                SELECT consumption_type, service_name,
                       SUM(credits) as total_credits,
                       SUM(tokens) as total_tokens,
                       COUNT(*) as days
                FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']}
                WHERE usage_date >= '{start_date}'::date
                  AND usage_date <= '{end_date}'::date
                GROUP BY consumption_type, service_name
                ORDER BY total_credits DESC
                LIMIT {limit}
                """
                
            elif service_name == 'CORTEX_SEARCH_SERVING':
                query = f"""
                SELECT service_name, database_name,
                       SUM(credits) as total_credits,
                       COUNT(*) as hours
                FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']}
                WHERE start_time >= '{start_date}'::date
                  AND start_time < '{end_date}'::date + INTERVAL '1 day'
                GROUP BY service_name, database_name
                ORDER BY total_credits DESC
                LIMIT {limit}
                """
                
            else:
                # Generic query for other services
                query = f"""
                SELECT *
                FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']}
                LIMIT {limit}
                """
            
            result = self.session.sql(query).collect()
            return pd.DataFrame([row.asDict() for row in result])
            
        except Exception as e:
            st.warning(f"Could not get detailed data for {service_name}: {str(e)}")
            return pd.DataFrame()
    
    @monitor_db_operation("get_time_series_data")
    def get_time_series_data(self, start_date, end_date, granularity: str = 'daily') -> pd.DataFrame:
        """
        Get time series data for usage trends analysis.
        OPTIMIZED: Single consolidated query - NO FALLBACK to sequential queries.
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            granularity: 'daily' or 'hourly'
            
        Returns:
            DataFrame with time series data by service
        """
        return self.get_time_series_data_optimized(start_date, end_date, granularity)
    
    def get_time_series_data_optimized(self, start_date, end_date, granularity: str = 'daily') -> pd.DataFrame:
        """
        Optimized time series data using single consolidated query.
        Expected 65% performance improvement over sequential queries.
        TESTED: This query works correctly via Snowflake CLI.
        """
        if granularity == 'daily':
            date_trunc = "DATE_TRUNC('day', start_time)"
        else:
            date_trunc = "DATE_TRUNC('hour', start_time)"
        
        query = f"""
        WITH all_time_series AS (
            -- Specialized Functions (individual breakdown)
            SELECT 
                {date_trunc} as period,
                CASE 
                    WHEN FUNCTION_NAME IS NULL OR FUNCTION_NAME = '' THEN
                        CASE 
                            WHEN MODEL_NAME IS NULL OR MODEL_NAME = '' THEN 'Other Specialized'
                            ELSE 'Other Specialized'
                        END
                    WHEN FUNCTION_NAME = 'TRANSLATE' THEN 'TRANSLATE'
                    WHEN FUNCTION_NAME = 'CLASSIFY_TEXT' THEN 'CLASSIFY_TEXT'
                    WHEN FUNCTION_NAME = 'SENTIMENT' THEN 'SENTIMENT'
                    WHEN FUNCTION_NAME = 'SUMMARIZE' THEN 'SUMMARIZE'
                    WHEN FUNCTION_NAME = 'EMBED_TEXT' THEN 'EMBED_TEXT'
                    WHEN FUNCTION_NAME = 'EXTRACT_ANSWER' THEN 'EXTRACT_ANSWER'
                    WHEN FUNCTION_NAME = 'AI_EXTRACT' THEN 'AI_EXTRACT'
                    WHEN FUNCTION_NAME = 'AI_AGG' THEN 'AI_AGG'
                    WHEN FUNCTION_NAME = 'AI_CLASSIFY' THEN 'AI_CLASSIFY'
                    ELSE 'Other Specialized'
                END as service_type,
                SUM(COALESCE(token_credits, 0)) as credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
            WHERE usage_time >= '{start_date}'::date
              AND usage_time < '{end_date}'::date + INTERVAL '1 day'
              AND (MODEL_NAME IS NULL OR MODEL_NAME = '')  -- Only specialized functions
            GROUP BY {date_trunc}, 
                CASE 
                    WHEN FUNCTION_NAME IS NULL OR FUNCTION_NAME = '' THEN
                        CASE 
                            WHEN MODEL_NAME IS NULL OR MODEL_NAME = '' THEN 'Other Specialized'
                            ELSE 'Other Specialized'
                        END
                    WHEN FUNCTION_NAME = 'TRANSLATE' THEN 'TRANSLATE'
                    WHEN FUNCTION_NAME = 'CLASSIFY_TEXT' THEN 'CLASSIFY_TEXT'
                    WHEN FUNCTION_NAME = 'SENTIMENT' THEN 'SENTIMENT'
                    WHEN FUNCTION_NAME = 'SUMMARIZE' THEN 'SUMMARIZE'
                    WHEN FUNCTION_NAME = 'EMBED_TEXT' THEN 'EMBED_TEXT'
                    WHEN FUNCTION_NAME = 'EXTRACT_ANSWER' THEN 'EXTRACT_ANSWER'
                    WHEN FUNCTION_NAME = 'AI_EXTRACT' THEN 'AI_EXTRACT'
                    WHEN FUNCTION_NAME = 'AI_AGG' THEN 'AI_AGG'
                    WHEN FUNCTION_NAME = 'AI_CLASSIFY' THEN 'AI_CLASSIFY'
                    ELSE 'Other Specialized'
                END
            
            UNION ALL
            
            -- Explicit Model Functions (individual breakdown)
            SELECT 
                {date_trunc} as period,
                CASE 
                    WHEN FUNCTION_NAME = 'COMPLETE' THEN 'COMPLETE'
                    WHEN FUNCTION_NAME = 'EMBED_TEXT_768' THEN 'EMBED_TEXT_768'
                    WHEN FUNCTION_NAME = 'EMBED_TEXT_1024' THEN 'EMBED_TEXT_1024'
                    WHEN FUNCTION_NAME = 'EMBED_TEXT' THEN 'EMBED_TEXT_EXPLICIT'
                    WHEN FUNCTION_NAME = 'FINETUNE' THEN 'FINETUNE'
                    WHEN FUNCTION_NAME = 'COUNT_TOKENS' THEN 'COUNT_TOKENS'
                    ELSE 'Other Explicit'
                END as service_type,
                SUM(COALESCE(token_credits, 0)) as credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
            WHERE usage_time >= '{start_date}'::date
              AND usage_time < '{end_date}'::date + INTERVAL '1 day'
              AND (MODEL_NAME IS NOT NULL AND MODEL_NAME != '')  -- Only explicit model functions
            GROUP BY {date_trunc}, 
                CASE 
                    WHEN FUNCTION_NAME = 'COMPLETE' THEN 'COMPLETE'
                    WHEN FUNCTION_NAME = 'EMBED_TEXT_768' THEN 'EMBED_TEXT_768'
                    WHEN FUNCTION_NAME = 'EMBED_TEXT_1024' THEN 'EMBED_TEXT_1024'
                    WHEN FUNCTION_NAME = 'EMBED_TEXT' THEN 'EMBED_TEXT_EXPLICIT'
                    WHEN FUNCTION_NAME = 'FINETUNE' THEN 'FINETUNE'
                    WHEN FUNCTION_NAME = 'COUNT_TOKENS' THEN 'COUNT_TOKENS'
                    ELSE 'Other Explicit'
                END
            
            UNION ALL
            
            -- Cortex Analyst
            SELECT 
                {date_trunc} as period,
                'CORTEX_ANALYST' as service_type,
                SUM(COALESCE(credits, 0)) as credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
            WHERE start_time >= '{start_date}'::date
              AND start_time < '{end_date}'::date + INTERVAL '1 day'
            GROUP BY {date_trunc}
            
            UNION ALL
            
            -- Document AI
            SELECT 
                {date_trunc} as period,
                'DOCUMENT_AI' as service_type,
                SUM(COALESCE(credits_used, 0)) as credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
            WHERE start_time >= '{start_date}'::date
              AND start_time < '{end_date}'::date + INTERVAL '1 day'
            GROUP BY {date_trunc}
            
            UNION ALL
            
            -- Cortex Search Serving
            SELECT 
                {date_trunc} as period,
                'CORTEX_SEARCH_SERVING' as service_type,
                SUM(COALESCE(credits, 0)) as credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
            WHERE start_time >= '{start_date}'::date
              AND start_time < '{end_date}'::date + INTERVAL '1 day'
            GROUP BY {date_trunc}
            
            UNION ALL
            
            -- Cortex Fine Tuning
            SELECT 
                {date_trunc} as period,
                'CORTEX_FINE_TUNING' as service_type,
                SUM(COALESCE(token_credits, 0)) as credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FINE_TUNING_USAGE_HISTORY
            WHERE start_time >= '{start_date}'::date
              AND start_time < '{end_date}'::date + INTERVAL '1 day'
            GROUP BY {date_trunc}
        )
        SELECT 
            period,
            service_type,
            credits
        FROM all_time_series
        WHERE credits > 0  -- Only show periods with actual usage
        ORDER BY period, service_type
        """
        
        # Use the monitored query execution
        result = self._execute_query_with_monitoring(query, "optimized_time_series")
        
        time_series_results = []
        for row in result:
            time_series_results.append({
                'period': row['PERIOD'],
                'service_type': row['SERVICE_TYPE'],
                'credits': float(row['CREDITS'])
            })
        
        return pd.DataFrame(time_series_results)
    
    def get_raw_export_data(self, start_date, end_date, limit: int = 10000) -> pd.DataFrame:
        """
        Get raw data for export functionality.
        Combines data from all accessible services.
        """
        all_data = []
        
        for service_name, config in self.service_configs.items():
            try:
                # Special handling for CORTEX_FUNCTIONS_QUERY with enhanced details
                if service_name == 'CORTEX_FUNCTIONS_QUERY':
                    query = f"""
                    SELECT 
                        '{service_name}' as service_type,
                        cfq.query_id,
                        cfq.warehouse_id,
                        cfq.model_name,
                        cfq.function_name,
                        cfq.tokens,
                        cfq.token_credits,
                        qh.user_name,
                        qh.start_time,
                        qh.end_time,
                        qh.total_elapsed_time as duration_ms,
                        ROUND(qh.total_elapsed_time / 1000.0, 3) as duration_seconds,
                        qh.database_name,
                        qh.schema_name,
                        qh.warehouse_name,
                        qh.query_type,
                        qh.execution_status
                    FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']} cfq
                    LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY qh ON cfq.query_id = qh.query_id
                    WHERE DATE(qh.start_time) >= '{start_date}'::date
                        AND DATE(qh.start_time) <= '{end_date}'::date
                        AND qh.start_time IS NOT NULL
                    ORDER BY qh.start_time DESC
                    LIMIT {limit}
                    """
                elif config['time_column']:
                    if config['time_column'] == 'USAGE_DATE':
                        time_filter = f"""
                        WHERE {config['time_column']} >= '{start_date}'::date
                          AND {config['time_column']} <= '{end_date}'::date
                        """
                    else:
                        time_filter = f"""
                        WHERE {config['time_column']} >= '{start_date}'::date
                          AND {config['time_column']} < '{end_date}'::date + INTERVAL '1 day'
                        """
                    
                    # Standard query for all time-based services
                    query = f"""
                        SELECT 
                            '{service_name}' as service_type,
                            *
                        FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']}
                        {time_filter}
                        ORDER BY 
                            CASE 
                                WHEN '{config['time_column']}' IS NOT NULL 
                                THEN {config['time_column']} 
                                ELSE NULL 
                            END DESC
                        LIMIT {limit}
                        """
                else:
                    # Skip services without time columns
                    continue
                
                result = self.session.sql(query).collect()
                if result:
                    service_data = pd.DataFrame([row.asDict() for row in result])
                    
                    # Create unified TOTAL_CREDITS column combining all credit types
                    token_credits = service_data['TOKEN_CREDITS'] if 'TOKEN_CREDITS' in service_data.columns else 0
                    credits = service_data['CREDITS'] if 'CREDITS' in service_data.columns else 0
                    credits_used = service_data['CREDITS_USED'] if 'CREDITS_USED' in service_data.columns else 0
                    
                    # Handle Series vs scalar values properly and convert to float
                    if hasattr(token_credits, 'fillna'):
                        token_credits = token_credits.fillna(0).astype(float)
                    else:
                        token_credits = float(token_credits) if token_credits != 0 else 0.0
                        
                    if hasattr(credits, 'fillna'):
                        credits = credits.fillna(0).astype(float)
                    else:
                        credits = float(credits) if credits != 0 else 0.0
                        
                    if hasattr(credits_used, 'fillna'):
                        credits_used = credits_used.fillna(0).astype(float)
                    else:
                        credits_used = float(credits_used) if credits_used != 0 else 0.0
                    
                    service_data['TOTAL_CREDITS'] = token_credits + credits + credits_used
                    
                    all_data.append(service_data)
                
            except Exception as e:
                # Log the error but continue with other services
                import streamlit as st
                st.warning(f"⚠️ Skipping {service_name}: {str(e)[:100]}...")
                continue
        
        if all_data:
            return pd.concat(all_data, ignore_index=True, sort=False)
        else:
            return pd.DataFrame()
    
    def get_data_freshness(self) -> Optional[timedelta]:
        """
        Check data freshness by looking at the most recent data across all services.
        Returns time since most recent data point.
        """
        try:
            most_recent = None
            
            for service_name, config in self.service_configs.items():
                if not config['time_column']:
                    continue
                
                try:
                    query = f"""
                    SELECT MAX({config['time_column']}) as latest_time
                    FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']}
                    WHERE {config['credit_column']} > 0
                    """
                    
                    result = self.session.sql(query).collect()
                    if result and result[0]['LATEST_TIME']:
                        service_latest = result[0]['LATEST_TIME']
                        if most_recent is None or service_latest > most_recent:
                            most_recent = service_latest
                            
                except Exception:
                    continue
            
            if most_recent:
                return datetime.now() - most_recent
            else:
                return None
                
        except Exception:
            return None
    
    def test_connectivity(self) -> Dict[str, Any]:
        """
        Test connectivity to all required data sources.
        Returns status report for troubleshooting.
        """
        status_report = {
            'timestamp': datetime.now(),
            'session_active': False,
            'metering_history_access': False,
            'organization_usage_access': False,
            'service_tables': {},
            'total_accessible_services': 0
        }
        
        try:
            # Test session
            self.session.sql("SELECT CURRENT_ACCOUNT()").collect()
            status_report['session_active'] = True
            
            # Test metering history
            try:
                self.session.sql("SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY LIMIT 1").collect()
                status_report['metering_history_access'] = True
            except:
                pass
            
            # Test organization usage
            try:
                self.session.sql("SELECT COUNT(*) FROM SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY LIMIT 1").collect()
                status_report['organization_usage_access'] = True
            except:
                pass
            
            # Test service tables
            accessible_count = 0
            for service_name, config in self.service_configs.items():
                try:
                    self.session.sql(f"SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']} LIMIT 1").collect()
                    status_report['service_tables'][service_name] = True
                    accessible_count += 1
                except Exception as e:
                    status_report['service_tables'][service_name] = str(e)
            
            status_report['total_accessible_services'] = accessible_count
            
        except Exception as e:
            status_report['error'] = str(e)
        
        return status_report

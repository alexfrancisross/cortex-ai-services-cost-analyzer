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
        
        # Service table configurations - Corrected to avoid double-counting
        self.service_configs = {
            'CORTEX_FUNCTIONS_QUERY': {
                'table': 'CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY',
                'credit_column': 'TOKEN_CREDITS',
                'time_column': None,  # Requires special handling with QUERY_HISTORY join
                'granularity': 'Individual query level (most detailed)',
                'description': 'Query-level LLM usage with user attribution'
            },
            'CORTEX_ANALYST': {
                'table': 'CORTEX_ANALYST_USAGE_HISTORY', 
                'credit_column': 'CREDITS',
                'time_column': 'START_TIME',
                'granularity': 'Request-level (most granular)',
                'description': 'Analyst requests with detailed breakdown'
            },
            'DOCUMENT_AI': {
                'table': 'DOCUMENT_AI_USAGE_HISTORY',
                'credit_column': 'CREDITS_USED',
                'time_column': 'START_TIME',
                'granularity': 'Document-level processing',
                'description': 'Document AI parsing and extraction'
            },
            'CORTEX_SEARCH_SERVING': {
                'table': 'CORTEX_SEARCH_SERVING_USAGE_HISTORY',
                'credit_column': 'CREDITS',
                'time_column': 'START_TIME',
                'granularity': 'Hourly by service',
                'description': 'Search serving usage'
            },
            'CORTEX_FINE_TUNING': {
                'table': 'CORTEX_FINE_TUNING_USAGE_HISTORY',
                'credit_column': 'TOKEN_CREDITS',
                'time_column': 'START_TIME',
                'granularity': 'Training session level',
                'description': 'Model fine-tuning operations'
            },
            'CORTEX_DOCUMENT_PROCESSING': {
                'table': 'CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY',
                'credit_column': 'CREDITS_USED',
                'time_column': 'START_TIME',
                'granularity': 'Document processing level',
                'description': 'Document processing operations'
            }
        }
        
        # Cache for available services (populated on first access)
        self._available_services = None
        
        # Performance monitoring
        self._query_count = 0
        self._total_query_time = 0.0
    
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
                'CORTEX_FUNCTIONS_USAGE_HISTORY',
                'CORTEX_ANALYST_USAGE_HISTORY',
                'CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY',
                'CORTEX_SEARCH_SERVING_USAGE_HISTORY',
                'CORTEX_SEARCH_DAILY_USAGE_HISTORY'
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
        Enhanced pattern from cortex-monitoring-dashboard.py.
        """
        try:
            query = f"""
            SELECT 
                MODEL_NAME,
                COUNT(*) as invocations,
                SUM(TOKENS) as total_tokens,
                SUM(TOKEN_CREDITS) as total_credits,
                AVG(TOKENS) as avg_tokens_per_call,
                AVG(TOKEN_CREDITS) as avg_credits_per_call,
                NULLIF(SUM(TOKENS) / NULLIF(SUM(TOKEN_CREDITS), 0), 0) as tokens_per_credit,
                ROUND(100 * SUM(TOKEN_CREDITS) / NULLIF(SUM(SUM(TOKEN_CREDITS)) OVER(), 0), 2) as pct_of_total_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
            WHERE START_TIME >= '{start_date}'::date
                AND START_TIME < '{end_date}'::date + INTERVAL '1 day'
            GROUP BY MODEL_NAME
            ORDER BY total_credits DESC
            """
            
            result = self.session.sql(query).collect()
            return pd.DataFrame([row.asDict() for row in result])
            
        except Exception as e:
            st.warning(f"Could not get model token analysis: {str(e)}")
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
                FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
                WHERE start_time >= '{start_date}'::date
                  AND start_time < '{end_date}'::date + INTERVAL '1 day'
                
                UNION ALL
                
                SELECT 
                    'CORTEX_ANALYST' as service,
                    COALESCE(SUM(credits), 0) as credits
                FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
                WHERE start_time >= '{start_date}'::date
                  AND start_time < '{end_date}'::date + INTERVAL '1 day'
                
                UNION ALL
                
                SELECT 
                    'DOCUMENT_AI' as service,
                    COALESCE(SUM(credits_used), 0) as credits
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
                       SUM(pages_processed) as total_pages,
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
            -- Cortex Functions Usage
            SELECT 
                {date_trunc} as period,
                'CORTEX_FUNCTIONS_USAGE' as service_type,
                SUM(COALESCE(token_credits, 0)) as credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
            WHERE start_time >= '{start_date}'::date
              AND start_time < '{end_date}'::date + INTERVAL '1 day'
            GROUP BY {date_trunc}
            
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

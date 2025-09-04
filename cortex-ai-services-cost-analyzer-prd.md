# Cortex AI Services Cost Analyzer - Product Requirements Document

## 1. Executive Summary

This PRD defines a Streamlit in Snowflake application that provides comprehensive analysis and breakdown of AI_SERVICES costs at the account level. Based on real-world testing and reconciliation analysis, this application addresses enterprise needs for accurate cost attribution, reconciliation validation, and service-level transparency across all Cortex AI services.

**Key Value Proposition**: Deliver 99.98% reconciliation accuracy with complete service attribution across 6 Cortex AI service categories, deployable to any Snowflake account without custom data materialization.

## 2. Background and Problem Statement

### Current Challenges
1. **Limited Visibility**: Customers see AI_SERVICES as a single line item without service-level breakdown
2. **Reconciliation Complexity**: Multiple usage views with different granularities create confusion
3. **Hidden Services**: Document processing and other services often go unnoticed in cost analysis
4. **Manual Analysis**: No self-service tool for comprehensive Cortex cost analysis
5. **Account Variability**: Different accounts have varying usage patterns requiring flexible analysis

### Proven Solution Architecture
Through testing with DEMO_AROSS account (71.5 credits over 3 months), we have validated:
- **99.96% accuracy** between dashboard and system data
- **99.98% reconciliation** between hourly metering and granular services
- **Complete service coverage** across 6 distinct AI service categories
- **Robust methodology** for handling data latency and attribution

## 3. Goals and Non-Goals

### Goals
- **✅ Total Cost Transparency**: Display complete AI_SERVICES consumption with confidence indicators
- **✅ Service Attribution**: Break down costs across all 6 proven service categories
- **✅ Reconciliation Validation**: Implement tested reconciliation methodology with variance analysis
- **✅ Universal Deployment**: Function correctly on any Snowflake account without customization
- **✅ Real-time Analysis**: Leverage existing views for up-to-date cost analysis
- **✅ Executive Reporting**: Generate exportable reports for finance and operations teams

### Non-Goals
- ❌ Historical data materialization or custom table creation
- ❌ Real-time alerting or automated notifications
- ❌ Cost optimization recommendations or ML-based insights
- ❌ Multi-account aggregation or organization-level rollups
- ❌ Custom billing rate management or currency conversion

## 4. Target Users and Use Cases

### Primary Users
- **Finance Teams**: Monthly cost reconciliation and chargeback preparation
- **Platform Engineers**: Understanding AI service adoption and usage patterns
- **Data Scientists**: Analyzing cost efficiency of different Cortex services
- **Executives**: High-level AI spending overview and service breakdown

### Core Use Cases
1. **Monthly Financial Reconciliation**: Validate AI_SERVICES billing against granular usage
2. **Service Cost Analysis**: Understand relative costs of Functions vs Analyst vs Document Processing
3. **Usage Pattern Discovery**: Identify peak usage periods and dominant service types
4. **Budget Planning**: Historical trend analysis for future AI spending forecasts
5. **Anomaly Detection**: Spot unusual spikes or discrepancies in AI consumption

## 5. Functional Requirements

### 5.1 Data Integration Requirements

#### Primary Data Sources (Validated Schema)
```sql
-- Organization-level validation (99.96% accuracy with dashboard)
SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY
WHERE service_type = 'AI_SERVICES' AND account_name = CURRENT_ACCOUNT()

-- Account-level hourly metering (reconciliation baseline)
SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
WHERE service_type = 'AI_SERVICES'

-- Granular service breakdown (6 proven tables)
SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY       -- token_credits
SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY         -- credits
SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY -- credits_used
SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY -- token_credits
SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY    -- credits
SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY  -- credits
```

#### Data Quality Requirements
- **Freshness Validation**: Flag data older than 6 hours as provisional
- **Completeness Check**: Verify all 6 service tables are accessible
- **Schema Validation**: Handle column name variations across service tables
- **Account Context**: Dynamically adapt to current account context

### 5.2 Core Application Features

#### 5.2.1 Executive Dashboard
**Main Metrics Display**:
- **Total AI_SERVICES Consumption**: Last 30/90/365 days with trend indicators
- **Reconciliation Status**: Real-time variance between hourly and granular services
- **Service Distribution**: Visual breakdown across 6 service categories
- **Cost Trend Analysis**: Daily/weekly usage patterns with growth indicators

**Key Performance Indicators**:
```python
# Example metrics based on testing results
Total_AI_Services: 71.474 credits
Reconciliation_Accuracy: 99.98%
Service_Coverage: 100.016%
Data_Freshness: < 3 hours
```

#### 5.2.2 Service Breakdown Analysis
**Service Categories with Validated Usage Patterns**:

1. **CORTEX_FUNCTIONS_USAGE** (60.1% of usage)
   - Aggregated hourly by function/model
   - Breakdown by: function_name, model_name, warehouse_id
   - Columns: token_credits, tokens, function_name, model_name

2. **CORTEX_ANALYST** (36.4% of usage)
   - Request-level granularity (most detailed)
   - Breakdown by: username, request_count
   - Columns: credits, request_count, username

3. **CORTEX_DOCUMENT_PROCESSING** (3.5% of usage) ← Critical Discovery
   - Document processing and parsing functions
   - Breakdown by: function_name, model_name
   - Columns: credits_used, pages_processed

4. **CORTEX_FUNCTIONS_QUERY** (0.0% of usage)
   - SQL-embedded function calls
   - Query-level detail with query_id
   - Columns: token_credits, query_id, function_name

5. **CORTEX_SEARCH_DAILY** (0.0% of usage)
   - Daily aggregation by consumption type
   - Breakdown by: consumption_type, service_name
   - Columns: credits, consumption_type, tokens

6. **CORTEX_SEARCH_SERVING** (0.0% of usage)
   - Hourly serving usage by service
   - Breakdown by: service_name, database_name
   - Columns: credits, service_name

#### 5.2.3 Reconciliation Engine
**Three-Tier Validation** (Proven Methodology):
```sql
-- Tier 1: Organization vs Account validation (99.96% accuracy)
-- Tier 2: Hourly vs Daily metering comparison 
-- Tier 3: Granular services vs Hourly reconciliation (99.98% accuracy)
```

**Variance Analysis**:
- Acceptable threshold: ±1.0% variance
- Warning threshold: ±2.0% variance  
- Alert threshold: >5.0% variance
- Expected infrastructure overhead: ~0.02% (based on testing)

#### 5.2.4 Interactive Features
- **Date Range Selector**: Last 7/30/90/365 days with custom range option
- **Service Filter**: Toggle individual services on/off for focused analysis
- **Granularity Switch**: Daily vs hourly view toggle
- **Export Functions**: CSV/Excel export for financial reporting
- **Drill-down Capability**: Click-through from summary to detailed tables

### 5.3 User Interface Requirements

#### Layout Structure
```
┌─ Header: Account Context + Data Freshness Indicator ─┐
├─ Summary Cards: Total | Reconciliation | Trend | Alert ─┤  
├─ Service Breakdown: [Pie Chart] [Bar Chart] [Data Table] ─┤
├─ Reconciliation Panel: [Variance Chart] [Tier Analysis] ─┤
├─ Detailed Analysis: [Service Drill-down] [Time Series] ─┤
└─ Export Options: [CSV] [Excel] [PDF Report] ─┘
```

#### Visual Design Requirements
- **Responsive Layout**: Adapt to different screen sizes
- **Color Coding**: Green (≤1%), Yellow (1-2%), Red (>2%) for variance indicators
- **Progressive Disclosure**: Summary → Details → Raw Data flow
- **Accessibility**: High contrast mode, keyboard navigation support
- **Performance**: <2 second load time for 90-day analysis

### 5.4 Technical Architecture

#### Streamlit in Snowflake Implementation
```python
# Application structure
src/
├── app.py                 # Main Streamlit application
├── data_layer.py         # Snowflake query functions
├── reconciliation.py     # Reconciliation logic
├── visualizations.py     # Chart and graph components
└── utils.py             # Helper functions and constants
```

#### Core Query Templates (Parameterized for Universal Deployment)
```sql
-- Dynamic service aggregation query
WITH all_services AS (
  SELECT 'CORTEX_FUNCTIONS_USAGE' as service_type,
         COUNT(*) as records,
         SUM(COALESCE(token_credits, 0)) as credits
  FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
  WHERE start_time >= ?date_filter?
  
  UNION ALL
  -- ... additional services with dynamic date filtering
)
SELECT * FROM all_services WHERE credits > 0;
```

## 6. Non-Functional Requirements

### 6.1 Performance Requirements
- **Dashboard Load Time**: <3 seconds for 90-day analysis
- **Query Response Time**: <2 seconds for filtered views
- **Data Refresh**: Every 10 minutes during business hours
- **Concurrent Users**: Support 20+ simultaneous users
- **Memory Usage**: <512MB per session

### 6.2 Security and Access Control
```sql
-- Minimum required privileges
GRANT USAGE ON DATABASE SNOWFLAKE TO ROLE <app_role>;
GRANT USAGE ON SCHEMA ACCOUNT_USAGE TO ROLE <app_role>;
GRANT USAGE ON SCHEMA ORGANIZATION_USAGE TO ROLE <app_role>;
GRANT SELECT ON ALL VIEWS IN SCHEMA ACCOUNT_USAGE TO ROLE <app_role>;
```

### 6.3 Data Quality and Reliability
- **Data Latency Handling**: Flag provisional data with visual indicators
- **Error Handling**: Graceful degradation when service tables are unavailable
- **Schema Evolution**: Robust handling of column name changes
- **Missing Data**: Clear messaging when tables contain no records

### 6.4 Universal Deployment Requirements
- **Account Agnostic**: No hardcoded account identifiers or warehouse names
- **Permission Adaptive**: Gracefully handle missing access to certain views
- **Configuration Free**: Zero-configuration deployment to any account
- **Auto-Discovery**: Automatically detect available Cortex services in target account

## 7. Implementation Specifications

### 7.1 Core Application Code Structure

#### Main Application (app.py)
```python
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from data_layer import SnowflakeDataLoader
from reconciliation import ReconciliationEngine
from visualizations import CortexVisualizer

def main():
    st.set_page_config(
        page_title="Cortex AI Services Cost Analyzer",
        page_icon="🧠",
        layout="wide"
    )
    
    # Initialize components
    data_loader = SnowflakeDataLoader()
    reconciler = ReconciliationEngine()
    visualizer = CortexVisualizer()
    
    # Sidebar controls
    with st.sidebar:
        date_range = st.date_input(
            "Analysis Period",
            value=(datetime.now() - timedelta(days=30), datetime.now())
        )
        
        services_filter = st.multiselect(
            "Cortex Services",
            options=data_loader.get_available_services(),
            default=data_loader.get_available_services()
        )
    
    # Main dashboard
    render_executive_summary(data_loader, date_range)
    render_service_breakdown(data_loader, services_filter, date_range)
    render_reconciliation_analysis(reconciler, date_range)
    render_detailed_analysis(data_loader, date_range)
```

#### Data Layer (data_layer.py)
```python
class SnowflakeDataLoader:
    def __init__(self):
        self.session = self._get_snowflake_session()
        self.service_configs = {
            'CORTEX_FUNCTIONS_USAGE': {
                'table': 'CORTEX_FUNCTIONS_USAGE_HISTORY',
                'credit_column': 'TOKEN_CREDITS',
                'time_column': 'START_TIME'
            },
            'CORTEX_ANALYST': {
                'table': 'CORTEX_ANALYST_USAGE_HISTORY', 
                'credit_column': 'CREDITS',
                'time_column': 'START_TIME'
            },
            'CORTEX_DOCUMENT_PROCESSING': {
                'table': 'CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY',
                'credit_column': 'CREDITS_USED', 
                'time_column': 'START_TIME'
            },
            # ... other services
        }
    
    def get_total_ai_services(self, start_date, end_date):
        """Get total AI_SERVICES from hourly metering"""
        query = f"""
        SELECT SUM(credits_used) as total_credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
        WHERE service_type = 'AI_SERVICES'
          AND start_time BETWEEN '{start_date}' AND '{end_date}'
        """
        return self.session.sql(query).collect()[0]['TOTAL_CREDITS']
    
    def get_service_breakdown(self, start_date, end_date, services_filter):
        """Get breakdown across all available services"""
        service_results = []
        
        for service_name, config in self.service_configs.items():
            if service_name in services_filter:
                try:
                    query = f"""
                    SELECT 
                        '{service_name}' as service_type,
                        COUNT(*) as record_count,
                        SUM(COALESCE({config['credit_column']}, 0)) as total_credits
                    FROM SNOWFLAKE.ACCOUNT_USAGE.{config['table']}
                    WHERE {config['time_column']} BETWEEN '{start_date}' AND '{end_date}'
                    """
                    result = self.session.sql(query).collect()[0]
                    service_results.append(result)
                except Exception as e:
                    st.warning(f"Could not access {service_name}: {str(e)}")
        
        return pd.DataFrame(service_results)
```

#### Reconciliation Engine (reconciliation.py)
```python
class ReconciliationEngine:
    def __init__(self):
        self.tolerance_threshold = 0.01  # 1% tolerance
        
    def perform_three_tier_reconciliation(self, start_date, end_date):
        """Implement proven 3-tier reconciliation methodology"""
        results = {}
        
        # Tier 1: Organization level
        results['organization'] = self._get_organization_total(start_date, end_date)
        
        # Tier 2: Account hourly
        results['account_hourly'] = self._get_account_hourly_total(start_date, end_date)
        
        # Tier 3: Granular services
        results['granular_services'] = self._get_granular_services_total(start_date, end_date)
        
        # Calculate variances
        results['variance_org_hourly'] = self._calculate_variance(
            results['organization'], results['account_hourly']
        )
        results['variance_hourly_granular'] = self._calculate_variance(
            results['account_hourly'], results['granular_services']
        )
        
        # Determine reconciliation status
        results['reconciliation_status'] = self._determine_status(results)
        
        return results
    
    def _calculate_variance(self, baseline, comparison):
        """Calculate percentage variance between two values"""
        if baseline == 0:
            return None
        return ((comparison - baseline) / baseline) * 100
    
    def _determine_status(self, results):
        """Determine overall reconciliation health"""
        variance_hourly_granular = abs(results['variance_hourly_granular'] or 0)
        
        if variance_hourly_granular <= 1.0:
            return "EXCELLENT"
        elif variance_hourly_granular <= 2.0:
            return "GOOD" 
        elif variance_hourly_granular <= 5.0:
            return "WARNING"
        else:
            return "CRITICAL"
```

### 7.2 Key SQL Templates

#### Universal Service Aggregation Query
```sql
-- Template for any Snowflake account
WITH service_breakdown AS (
    -- Functions Usage (Hourly aggregated)
    SELECT 'CORTEX_FUNCTIONS_USAGE' as service_type,
           'Hourly by function/model' as granularity,
           COUNT(*) as record_count,
           SUM(COALESCE(token_credits, 0)) as total_credits,
           MIN(start_time) as earliest_usage,
           MAX(start_time) as latest_usage
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
    WHERE start_time >= :start_date
    
    UNION ALL
    
    -- Analyst Usage (Request-level)
    SELECT 'CORTEX_ANALYST',
           'Request-level (most granular)',
           COUNT(*),
           SUM(COALESCE(credits, 0)),
           MIN(start_time),
           MAX(start_time)
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
    WHERE start_time >= :start_date
    
    UNION ALL
    
    -- Document Processing (Critical for complete reconciliation)
    SELECT 'CORTEX_DOCUMENT_PROCESSING',
           'Hourly by function/model',
           COUNT(*),
           SUM(COALESCE(credits_used, 0)),
           MIN(start_time),
           MAX(start_time)
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
    WHERE start_time >= :start_date
    
    UNION ALL
    
    -- Functions Query (SQL-embedded)
    SELECT 'CORTEX_FUNCTIONS_QUERY',
           'Query-level with query_id',
           COUNT(*),
           SUM(COALESCE(token_credits, 0)),
           NULL, -- No time columns in this table
           NULL
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY
    
    UNION ALL
    
    -- Search Daily Usage
    SELECT 'CORTEX_SEARCH_DAILY',
           'Daily by consumption type',
           COUNT(*),
           SUM(COALESCE(credits, 0)),
           MIN(usage_date),
           MAX(usage_date)
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
    WHERE usage_date >= :start_date
    
    UNION ALL
    
    -- Search Serving Usage  
    SELECT 'CORTEX_SEARCH_SERVING',
           'Hourly by service',
           COUNT(*),
           SUM(COALESCE(credits, 0)),
           MIN(start_time),
           MAX(start_time)
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
    WHERE start_time >= :start_date
)
SELECT 
    service_type,
    granularity,
    record_count,
    total_credits,
    ROUND(total_credits / SUM(total_credits) OVER () * 100, 2) as percentage,
    earliest_usage,
    latest_usage,
    CASE 
        WHEN total_credits > 0 THEN 'ACTIVE'
        WHEN record_count > 0 THEN 'INACTIVE' 
        ELSE 'NO_DATA'
    END as status
FROM service_breakdown
ORDER BY total_credits DESC;
```

#### Reconciliation Validation Query
```sql
-- Proven reconciliation methodology
WITH reconciliation_tiers AS (
    -- Tier 1: Organization level (when available)
    SELECT 'ORGANIZATION' as tier,
           SUM(credits_used) as credits,
           'Billing reconciliation baseline' as description
    FROM SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY
    WHERE service_type = 'AI_SERVICES'
      AND account_name = CURRENT_ACCOUNT()
      AND usage_date >= :start_date
    
    UNION ALL
    
    -- Tier 2: Account hourly (reconciliation baseline)
    SELECT 'ACCOUNT_HOURLY',
           SUM(credits_used),
           'Hourly metering baseline'
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
    WHERE service_type = 'AI_SERVICES'
      AND start_time >= :start_date
    
    UNION ALL
    
    -- Tier 3: Sum of all granular services
    SELECT 'GRANULAR_SERVICES',
           SUM(all_credits),
           'Sum of 6 service tables'
    FROM (
        SELECT SUM(COALESCE(token_credits, 0)) as all_credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
        WHERE start_time >= :start_date
        
        UNION ALL
        
        SELECT SUM(COALESCE(credits, 0))
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
        WHERE start_time >= :start_date
        
        UNION ALL
        
        SELECT SUM(COALESCE(credits_used, 0))
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
        WHERE start_time >= :start_date
        
        UNION ALL
        
        SELECT SUM(COALESCE(token_credits, 0))
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY
        
        UNION ALL
        
        SELECT SUM(COALESCE(credits, 0))
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
        WHERE usage_date >= :start_date
        
        UNION ALL
        
        SELECT SUM(COALESCE(credits, 0))
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
        WHERE start_time >= :start_date
    )
)
SELECT 
    tier,
    credits,
    description,
    credits - LAG(credits) OVER (ORDER BY credits DESC) as variance_from_higher,
    ROUND((credits - LAG(credits) OVER (ORDER BY credits DESC)) / 
          NULLIF(LAG(credits) OVER (ORDER BY credits DESC), 0) * 100, 4) as variance_percentage,
    CASE 
        WHEN ABS((credits - LAG(credits) OVER (ORDER BY credits DESC)) / 
                 NULLIF(LAG(credits) OVER (ORDER BY credits DESC), 0) * 100) <= 1.0 
        THEN '✅ EXCELLENT'
        WHEN ABS((credits - LAG(credits) OVER (ORDER BY credits DESC)) / 
                 NULLIF(LAG(credits) OVER (ORDER BY credits DESC), 0) * 100) <= 2.0 
        THEN '⚠️ GOOD'
        ELSE '❌ INVESTIGATE'
    END as reconciliation_status
FROM reconciliation_tiers
ORDER BY credits DESC;
```

## 8. User Interface Mockups

### Dashboard Layout
```
🧠 Cortex AI Services Cost Analyzer                    [Account: DEMO_AROSS] [📊 Data Fresh: 2.3h ago]

┌─────────────────── EXECUTIVE SUMMARY ───────────────────┐
│ 💰 Total AI Services    🎯 Reconciliation     📈 Trend  │
│    71.474 credits          99.98% ✅         +15.2%     │
│                                                          │
│ 📊 Service Coverage     ⏰ Period           🔄 Status    │
│    100.016% ✅           Last 90 days       Active      │
└──────────────────────────────────────────────────────────┘

┌────────── SERVICE BREAKDOWN ──────────┐  ┌─── RECONCILIATION ───┐
│                                       │  │                      │
│ [PIE CHART]                          │  │ [VARIANCE CHART]     │
│ • Functions Usage: 60.1%             │  │                      │
│ • Analyst: 36.4%                     │  │ Tier 1: Organization │
│ • Document Processing: 3.5% ⭐       │  │ Tier 2: Hourly       │ 
│ • Functions Query: 0.0%              │  │ Tier 3: Granular     │
│ • Search Daily: 0.0%                 │  │                      │
│ • Search Serving: 0.0%               │  │ Variance: -0.016% ✅ │
│                                       │  │                      │
│ [BAR CHART - Detailed View]          │  └──────────────────────┘
└───────────────────────────────────────┘

┌──────────────────── DETAILED ANALYSIS ────────────────────┐
│ [TAB: Service Details] [TAB: Time Series] [TAB: Export]   │
│                                                            │
│ Service Type          | Records | Credits  | Granularity  │
│ ────────────────────────────────────────────────────────  │
│ CORTEX_FUNCTIONS_USAGE|   130   | 42.946   | Hourly       │
│ CORTEX_ANALYST        |    68   | 25.996   | Request      │
│ CORTEX_DOCUMENT_PROC  |     4   |  2.531   | Hourly   ⭐  │
│ CORTEX_FUNCTIONS_QUERY|    40   |  0.011   | Query-level  │
│ CORTEX_SEARCH_DAILY   |   216   |  0.001   | Daily        │
│ CORTEX_SEARCH_SERVING |  4888   |  0.001   | Hourly       │
└────────────────────────────────────────────────────────────┘

[📥 Export CSV] [📊 Export Excel] [📄 Generate Report]
```

## 9. Deployment Specifications

### 9.1 Streamlit in Snowflake Setup
```sql
-- Create Streamlit application
CREATE STREAMLIT CORTEX_AI_COST_ANALYZER
ROOT_LOCATION = '@ANALYTICS_STAGE/cortex_analyzer/'
MAIN_FILE = 'app.py'
QUERY_WAREHOUSE = COMPUTE_WH;

-- Grant access
GRANT USAGE ON STREAMLIT CORTEX_AI_COST_ANALYZER TO ROLE ANALYST_ROLE;
```

### 9.2 Required Permissions
```sql
-- Minimum permissions for universal deployment
GRANT USAGE ON DATABASE SNOWFLAKE TO ROLE <app_role>;
GRANT USAGE ON SCHEMA SNOWFLAKE.ACCOUNT_USAGE TO ROLE <app_role>;
GRANT USAGE ON SCHEMA SNOWFLAKE.ORGANIZATION_USAGE TO ROLE <app_role>;

-- Read access to all usage views
GRANT SELECT ON SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY TO ROLE <app_role>;
GRANT SELECT ON SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY TO ROLE <app_role>;
GRANT SELECT ON SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY TO ROLE <app_role>;
GRANT SELECT ON SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY TO ROLE <app_role>;
GRANT SELECT ON SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY TO ROLE <app_role>;
GRANT SELECT ON SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY TO ROLE <app_role>;
GRANT SELECT ON SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY TO ROLE <app_role>;

-- Organization usage (when available)
GRANT SELECT ON SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY TO ROLE <app_role>;
```

### 9.3 Zero-Configuration Deployment
The application automatically adapts to any Snowflake account by:
- **Dynamic Service Discovery**: Tests availability of each service table
- **Schema Resilience**: Handles column name variations gracefully
- **Permission Adaptation**: Gracefully degrades when certain views are inaccessible
- **Account Context**: Uses `CURRENT_ACCOUNT()` for dynamic filtering

## 10. Testing and Validation

### 10.1 Acceptance Criteria
✅ **Total Cost Display**: Show accurate AI_SERVICES total with <1% variance from billing  
✅ **Service Attribution**: Break down across all 6 service categories with proper percentages  
✅ **Reconciliation Accuracy**: Achieve >99% accuracy between tiers  
✅ **Universal Deployment**: Deploy to any account without configuration  
✅ **Performance**: Load dashboard in <3 seconds for 90-day analysis  
✅ **Error Handling**: Graceful degradation when services are unavailable  

### 10.2 Test Scenarios
1. **New Account Deployment**: Deploy to account with no AI usage
2. **High Usage Account**: Test with accounts having >1000 credits usage
3. **Partial Access**: Test with limited permissions to some usage views
4. **Missing Services**: Test behavior when certain Cortex services aren't used
5. **Data Latency**: Test handling of provisional and stale data

### 10.3 Validation Queries
```sql
-- Validate deployment success
SELECT 
    'DEPLOYMENT_VALIDATION' as test_type,
    COUNT(*) as accessible_tables,
    SUM(CASE WHEN table_name LIKE '%CORTEX%' THEN 1 ELSE 0 END) as cortex_tables
FROM INFORMATION_SCHEMA.TABLES 
WHERE table_schema = 'ACCOUNT_USAGE';

-- Expected result: accessible_tables >= 6, cortex_tables >= 6
```

## 11. Success Metrics and KPIs

### 11.1 Technical Metrics
- **Reconciliation Accuracy**: Target >99.5% variance accuracy
- **Data Coverage**: Target 100% of AI_SERVICES attributed to services
- **Performance**: Target <3s dashboard load time
- **Availability**: Target 99.9% uptime
- **Deployment Success**: Target 100% successful deployments across account types

### 11.2 Business Metrics
- **User Adoption**: Target 80% of finance users using monthly
- **Cost Transparency**: Target 100% AI_SERVICES costs broken down by service
- **Reconciliation Efficiency**: Target 90% reduction in manual reconciliation time
- **Financial Accuracy**: Target <0.1% variance in monthly cost reports

## 12. Maintenance and Operations

### 12.1 Monitoring Requirements
- **Data Freshness**: Alert when data is >6 hours stale
- **Reconciliation Health**: Alert when variance exceeds 2%
- **Performance**: Monitor query response times and user session metrics
- **Error Tracking**: Log and alert on application errors

### 12.2 Update Strategy
- **Schema Evolution**: Monitor Snowflake for new Cortex service tables
- **Feature Enhancement**: Quarterly reviews for new visualization needs
- **Performance Optimization**: Monthly query performance analysis
- **User Feedback**: Bi-weekly user feedback collection and incorporation

## 13. Risk Mitigation

### 13.1 Technical Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Schema Changes | High | Version-aware queries, fallback logic |
| New Service Types | Medium | Extensible service discovery framework |
| Performance Degradation | Medium | Query optimization, caching strategies |
| Data Latency | Low | Clear provisional data indicators |

### 13.2 Business Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Inaccurate Reconciliation | High | Comprehensive testing, variance alerts |
| User Adoption | Medium | Training materials, executive sponsorship |
| Compliance Issues | Medium | Audit trail, export capabilities |

## 14. Appendices

### A. Reference Implementation Files
- `app.py`: Main Streamlit application
- `data_layer.py`: Snowflake data access layer
- `reconciliation.py`: Three-tier reconciliation engine
- `visualizations.py`: Chart and visualization components
- `utils.py`: Utility functions and constants

### B. SQL Query Library
- Universal service aggregation queries
- Reconciliation validation queries  
- Data freshness validation queries
- Performance optimization queries

### C. Deployment Guide
- Step-by-step deployment instructions
- Permission setup checklist
- Troubleshooting guide
- Configuration options

---

This PRD provides a comprehensive blueprint for building a production-ready Cortex AI Services Cost Analyzer that leverages the proven reconciliation methodology and service discovery insights gained through real-world testing. The application will deliver enterprise-grade cost transparency with universal deployment capabilities across any Snowflake account.

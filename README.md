# Cortex AI Services Cost Analyzer

[![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=for-the-badge&logo=snowflake&logoColor=white)](https://www.snowflake.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)

A cost analysis and reconciliation dashboard for **Snowflake Cortex AI Services**. Provides detailed insights into AI service consumption, billing reconciliation, and performance analytics with individual function breakdown.

![Demo](img/demo.gif)

## 🛠️ Prerequisites

### Snowflake Requirements
- Snowflake account with **Cortex AI Services enabled**
- **Snowflake CLI**
- Access to `SNOWFLAKE.ACCOUNT_USAGE` views:
  - `METERING_HISTORY` (AI Services baseline for reconciliation)
  - `CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY` (Query-level LLM function usage with user attribution)
  - `CORTEX_ANALYST_USAGE_HISTORY` (Business intelligence and analytics queries)
  - `CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY` (Modern document processing operations)
  - `CORTEX_SEARCH_SERVING_USAGE_HISTORY` (Vector search and semantic search operations)
  - `CORTEX_FINE_TUNING_USAGE_HISTORY` (Model fine-tuning and customization)
  - `DOCUMENT_AI_USAGE_HISTORY` (Legacy document processing - auto-excluded when modern exists)

### Required Permissions
```sql
-- Grant access to system views (required for cost analysis)
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE <YOUR_ROLE>;

-- Database and schema access
GRANT USAGE ON DATABASE ANALYTICS TO ROLE <YOUR_ROLE>;
GRANT USAGE ON SCHEMA ANALYTICS.CORTEX_APPS TO ROLE <YOUR_ROLE>;
GRANT CREATE STREAMLIT ON SCHEMA ANALYTICS.CORTEX_APPS TO ROLE <YOUR_ROLE>;
GRANT READ, WRITE ON STAGE ANALYTICS.CORTEX_APPS.CORTEX_ANALYZER_STAGE TO ROLE <YOUR_ROLE>;

-- Warehouse access for query execution
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE <YOUR_ROLE>;
```

## 🚀 Quick Start

### Deploy to Snowflake (Recommended)

1. **Install Snowflake CLI**
   ```bash
   pip install snowflake-cli-labs
   ```

2. **Configure Connection**
   ```bash
   snow connection add
   ```

3. **Setup Database**
   ```bash
   snow sql -f setup.sql
   ```

4. **Deploy Application**
   ```bash
   # Initial deployment
   snow streamlit deploy cortex_cost_analyzer
   
   # Update existing deployment
   snow streamlit deploy cortex_cost_analyzer --replace
   ```

5. **Access Your App**
   - Navigate to Snowsight > Data > Streamlit Apps
   - Open "CORTEX_AI_COST_ANALYZER"
   - Or use the URL provided in deployment output (e.g., `https://app.snowflake.com/.../streamlit-apps/...`)

### Deployment Examples

```bash
# Initial deployment (first time)
snow streamlit deploy cortex_cost_analyzer

# Update existing deployment
snow streamlit deploy cortex_cost_analyzer --replace

# Deploy to specific connection
snow streamlit deploy cortex_cost_analyzer --replace -c production

# Check deployment status
snow streamlit list
snow streamlit describe cortex_cost_analyzer
```

### Run Locally (Development)

1. **Setup Environment**
   ```bash
   git clone <repository-url>
   cd cortex-ai-services-cost-analyzer
   conda env create -f environment.yml
   conda activate cortex_cost_analyzer
   ```

2. **Configure Authentication**
   Create `~/.snowflake/config.toml`:
   ```toml
   [connections.default]
   account = "your-account"
   user = "your-username"
   private_key_path = "~/.snowflake/rsa_key.p8"
   warehouse = "COMPUTE_WH"
   database = "ANALYTICS"
   schema = "CORTEX_APPS"
   role = "SYSADMIN"
   ```

3. **Run Application**
   ```bash
   streamlit run streamlit_app.py
   ```

## 📖 Usage Guide

### Dashboard Overview
- **Reconciliation Summary**: Overall billing reconciliation status with variance analysis
- **Service Breakdown**: Credit distribution across all Cortex services
- **Key Metrics**: Total credits, variance percentages, and status indicators
- **Date Range Selection**: Flexible period analysis with performance optimization

### Analysis Tabs

#### 📊 Model Analysis
- **Enhanced Usage Overview**: Total tokens, invocations, credits, and efficiency metrics
- **Explicit Model Breakdown**: Dedicated analysis for named models (claude-4-sonnet, llama3.3-70b, etc.)
- **Specialized Functions Analysis**: Detailed breakdown of TRANSLATE, CLASSIFY_TEXT, SENTIMENT, etc.
- **Visual Analytics**: Color-coded charts distinguishing models vs. specialized functions
- **Educational Information**: Explanations of Snowflake's managed AI services

#### 🔧 Service Details
- **Document Processing & AI_EXTRACT**: Modern document processing with AI extraction
- **Cortex Analyst**: REST API usage with request-level insights
- **Cortex Search**: Vector search operations analytics
- **Performance Metrics**: Service-specific insights and metadata
- **Historical Usage Patterns**: Trend analysis and optimization recommendations

#### 📈 Time Series
- **Individual Function Trends**: TRANSLATE, CLASSIFY_TEXT, COMPLETE, AI_EXTRACT, etc.
- **Daily/Hourly Granularity**: Flexible time series analysis
- **Peak Usage Identification**: Automated detection of usage spikes
- **Service-Level Tracking**: Comprehensive temporal analytics

#### 📋 Raw Data
- **Unified Export**: Consistent TOTAL_CREDITS column across all data
- **Multiple Formats**: CSV and Excel export options
- **Performance Optimized**: Intelligent data retrieval and caching
- **Comprehensive Coverage**: All services and functions included

## 🔧 Configuration

### Snowflake CLI Configuration (`snowflake.yml`)
```yaml
definition_version: 2

entities:
  cortex_cost_analyzer:
    type: streamlit
    identifier:
      name: "CORTEX_AI_COST_ANALYZER"
      schema: "CORTEX_APPS"
      database: "ANALYTICS"
    stage: "ANALYTICS.CORTEX_APPS.CORTEX_ANALYZER_STAGE"
    query_warehouse: "COMPUTE_WH"
    main_file: "streamlit_app.py"
    title: "Cortex AI Services Cost Analyzer"
    comment: "Production-ready cost analysis and reconciliation for Snowflake Cortex AI Services"
    artifacts:
      - "streamlit_app.py"
      - "environment.yml"
      - "setup.sql"
      - "common/__init__.py"
      - "common/analytics/__init__.py"
      - "common/analytics/data_layer.py"
      - "common/analytics/reconciliation.py"
      - "common/utils/__init__.py"
      - "common/utils/data_helpers.py"
      - "common/utils/performance_monitor.py"
      - "common/assets/cortex_logo.png"
```

**Key Configuration Points:**
- **Entity ID**: `cortex_cost_analyzer` - used in deployment commands
- **Database/Schema**: Customize to match your environment
- **Stage**: Where application files are uploaded
- **Warehouse**: Compute resource for query execution
- **Artifacts**: All files deployed to Snowflake stage

### Dependencies (`environment.yml`)
- `streamlit` - Web application framework
- `snowflake-snowpark-python` - Snowflake connectivity and data processing
- `pandas`, `numpy` - Advanced data processing and analytics
- `plotly` - Interactive visualizations and charts
- `openpyxl`, `xlsxwriter` - Excel export support with multiple engines
- `psutil` - Performance monitoring and system metrics
- `cryptography` - JWT authentication for secure connections
- `toml` - Configuration file parsing

### Service Table Configurations
The application intelligently handles different credit column names and granularities:

| Service | Table | Credit Column | Granularity |
|---------|-------|---------------|-------------|
| **Cortex Functions Query** | CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY | TOKEN_CREDITS | Individual query (most detailed) |
| **Cortex Analyst** | CORTEX_ANALYST_USAGE_HISTORY | CREDITS | Request-level |
| **Document AI** | DOCUMENT_AI_USAGE_HISTORY | CREDITS_USED | Document-level |
| **Cortex Search Serving** | CORTEX_SEARCH_SERVING_USAGE_HISTORY | CREDITS | Hourly by service |
| **Cortex Fine Tuning** | CORTEX_FINE_TUNING_USAGE_HISTORY | TOKEN_CREDITS | Training session |
| **Cortex Document Processing** | CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY | CREDITS_USED | Document processing |

## 🔍 Advanced Troubleshooting

### Common Issues

1. **"No data available for the selected date range"**
   - **ACCOUNT_USAGE Latency**: Views have 2-3 hour data delay
   - **Date Range**: Ensure selected period has actual Cortex AI usage
   - **Permissions**: Verify `GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE`
   - **Service Status**: Confirm Cortex AI services are enabled in your account
   - **Resolution**: Use "Clear Session Cache" button and try a longer date range

2. **High Variance Percentages in Reconciliation**
   - **Expected Variance**: Small differences (≤2%) are normal due to timing
   - **AI_EXTRACT**: Automatically excluded from Cortex Functions to prevent duplication
   - **Legacy Services**: Document AI auto-excluded when modern processing exists
   - **Investigation**: Check Service Details tab for individual service breakdowns
   - **Resolution**: Variances >5% warrant checking for new service types

3. **Deployment Errors**
   - **"Object already exists"**: Use `--replace` flag for updates
   - **Permission Denied**: Ensure role has CREATE STREAMLIT privilege
   - **Stage Access**: Verify READ/WRITE permissions on stage
   - **CLI Version**: Update to latest Snowflake CLI: `pip install --upgrade snowflake-cli-labs`
   - **Resolution**: Run `snow streamlit deploy cortex_cost_analyzer --replace`

4. **Connection Issues**
   - **SiS Mode**: Ensure app deployed via `snow streamlit deploy`
   - **Standalone Mode**: Check `~/.snowflake/config.toml` configuration
   - **JWT Auth**: Verify private key path and permissions
   - **Warehouse**: Confirm COMPUTE_WH (or configured warehouse) is running
   - **Resolution**: Check deployment mode indicator in sidebar

5. **Performance Issues**
   - **Date Range**: Use ≤90 days for optimal performance
   - **Cache**: 30-minute TTL prevents excessive re-querying
   - **Warehouse Size**: Consider larger warehouse for complex queries
   - **Debug Mode**: Enable "Show Performance Debug" to identify bottlenecks
   - **Resolution**: Monitor query execution times in performance dashboard

## 📚 Additional Resources

### SQL Analysis Script
The `sql/cortex_credit_consumption_analysis.sql` file provides standalone SQL analysis that mirrors the Streamlit app functionality:

### Key Components
- **`streamlit_app.py`**: Main application entry point with Snowflake branding and enhanced UI
- **`common/analytics/data_layer.py`**: Advanced Snowflake data access with optimized CTEs and caching (30-min TTL)
- **`common/analytics/reconciliation.py`**: Business logic for 3-tier cost reconciliation and validation
- **`common/utils/performance_monitor.py`**: Comprehensive performance tracking with bottleneck identification
- **`common/utils/data_helpers.py`**: Data formatting utilities and status helpers
- **`common/assets/cortex_logo.png`**: Snowflake Cortex branding asset
- **`snowflake.yml`**: Snowflake CLI configuration for deployment
- **`environment.yml`**: Conda environment with dependencies
- **`setup.sql`**: Database initialization and permissions script
## 🆘 Support & Resources

### Documentation
- [Snowflake Cortex AI Documentation](https://docs.snowflake.com/en/guides-overview-ai-features) - Complete Cortex AI overview
- [Snowflake CLI Documentation](https://docs.snowflake.com/en/developer-guide/snowflake-cli/index) - CLI usage and commands
- [Account Usage Views](https://docs.snowflake.com/en/sql-reference/account-usage) - System usage monitoring
---

*Cost analysis for Snowflake Cortex AI Services with advanced reconciliation.*
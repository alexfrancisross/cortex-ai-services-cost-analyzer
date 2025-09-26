# Cortex AI Services Cost Analyzer

[![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=for-the-badge&logo=snowflake&logoColor=white)](https://www.snowflake.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)

A cost analysis and reconciliation dashboard for **Snowflake Cortex AI Services**. Provides detailed insights into AI service consumption, billing reconciliation, and performance analytics with individual function breakdown and **advanced double-counting prevention**.

![Demo](img/demo.gif)

## 🚀 Key Features

### 📊 Advanced Reconciliation Analysis
- **AI Services Baseline** vs **Individual Services** reconciliation with 99.98% accuracy
- **Smart Double-Counting Prevention**: Eliminates AI_EXTRACT and Document AI overlaps
- **Variance analysis** to identify billing discrepancies with precise thresholds
- **Real-time reconciliation status** monitoring (EXCELLENT ≤1%, GOOD 1-2%, WARNING 2-5%, CRITICAL >5%)
- **Multi-tier reconciliation**: Organization, Account, and Service-level validation

### 🤖 Enhanced Model & Function Analysis
- **Specialized Functions Analysis**: Clear breakdown of TRANSLATE, CLASSIFY_TEXT, SENTIMENT, etc.
- **Model Utilization**: Token usage and credit consumption by explicit LLM models
- **AI_EXTRACT Integration**: Properly categorized under Document Processing to prevent duplication
- **Efficiency metrics**: Tokens per credit for models and functions
- **Color-coded visualizations**: Orange for specialized functions, blue for explicit models

### 📈 Comprehensive Service Breakdown
- **Document Processing & AI_EXTRACT**: Combined modern document processing analytics
- **Cortex Analyst**: REST API access analytics with request-level insights
- **Cortex Search**: Vector search operations with service-level metrics
- **Cortex Functions**: LLM/AI functions with individual breakdowns (excluding AI_EXTRACT)
- **Fine Tuning**: Model customization services tracking

### 📈 Time Series Analytics
- **Individual function trend lines** for detailed analysis
- **Daily and hourly usage patterns** with peak identification
- **Service-specific consumption tracking** across all Cortex services
- **Function-level granularity** for precise usage analysis

### 📋 Production-Ready Data Export
- **Raw data export** in CSV and Excel formats
- **Unified TOTAL_CREDITS column** across all exports
- **Performance-optimized** data retrieval with intelligent caching
- **Comprehensive usage reports** with accurate credit calculations

### 🔧 Performance & Monitoring
- **Advanced caching** with configurable TTL (30-minute default)
- **Performance monitoring** with detailed execution metrics
- **Memory usage tracking** and optimization
- **Query execution monitoring** with timing analysis

## 🛠️ Prerequisites

### Snowflake Requirements
- Snowflake account with **Cortex AI Services enabled**
- Access to `SNOWFLAKE.ACCOUNT_USAGE` views:
  - `METERING_HISTORY` (AI Services baseline)
  - `CORTEX_FUNCTIONS_USAGE_HISTORY` (LLM/AI function usage)
  - `CORTEX_ANALYST_USAGE_HISTORY` (Business intelligence queries)
  - `CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY` (Modern document processing + AI_EXTRACT)
  - `CORTEX_SEARCH_SERVING_USAGE_HISTORY` (Vector search operations)
  - `CORTEX_FINE_TUNING_USAGE_HISTORY` (Model fine-tuning)
  - `DOCUMENT_AI_USAGE_HISTORY` (Legacy document processing - auto-excluded when modern exists)

### Required Permissions
```sql
-- Grant access to system views
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE <YOUR_ROLE>;

-- Database and schema access
GRANT USAGE ON DATABASE ANALYTICS TO ROLE <YOUR_ROLE>;
GRANT USAGE ON SCHEMA ANALYTICS.CORTEX_APPS TO ROLE <YOUR_ROLE>;
GRANT READ, WRITE ON STAGE ANALYTICS.CORTEX_APPS.CORTEX_ANALYZER_STAGE TO ROLE <YOUR_ROLE>;
```

## 🚀 Quick Start

### Deploy to Snowflake (Recommended)

1. **Install Snowflake CLI**
   ```bash
   pip install snowflake-cli-labs
   ```

2. **Configure Connection**
   ```bash
   snow configure
   ```

3. **Setup Database**
   ```bash
   snow sql -f setup.sql
   ```

4. **Deploy Application**
   ```bash
   snow streamlit deploy
   ```

5. **Access Your App**
   - Navigate to Snowsight > Projects > Streamlit
   - Open "CORTEX_AI_COST_ANALYZER"

### Multi-Account Deployment

Deploy to specific Snowflake connections:
```bash
# Deploy to different accounts
snow streamlit deploy -c gsma --replace
snow streamlit deploy -c nttdata --replace
snow streamlit deploy -c production --replace
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

### Snowflake CLI (`snowflake.yml`)
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
```

### Dependencies (`environment.yml`)
- `streamlit` - Web application framework
- `snowflake-snowpark-python` - Snowflake connectivity and data processing
- `pandas`, `numpy` - Advanced data processing and analytics
- `plotly` - Interactive visualizations and charts
- `openpyxl`, `xlsxwriter` - Excel export support with multiple engines
- `psutil` - Performance monitoring and system metrics
- `cryptography` - JWT authentication for secure connections
- `toml` - Configuration file parsing

## 📊 Data Sources & Smart Processing

### Primary Tables
1. **METERING_HISTORY**: Overall AI Services baseline credits with service type filtering
2. **CORTEX_FUNCTIONS_USAGE_HISTORY**: LLM/AI function usage (AI_EXTRACT excluded to prevent double counting)
3. **CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY**: Modern document processing including AI_EXTRACT functions
4. **CORTEX_ANALYST_USAGE_HISTORY**: Business intelligence queries and analytics requests
5. **CORTEX_SEARCH_SERVING_USAGE_HISTORY**: Vector search operations and semantic search
6. **CORTEX_FINE_TUNING_USAGE_HISTORY**: Model fine-tuning and customization services
7. **DOCUMENT_AI_USAGE_HISTORY**: Legacy document processing (auto-excluded when modern data exists)

### Advanced Reconciliation Logic
1. **Smart Service Aggregation**: Prevents double counting between legacy and modern services
2. **AI_EXTRACT Deduplication**: Excludes from Cortex Functions when present in Document Processing
3. **Baseline Comparison**: Compares individual service sum against AI_SERVICES metering baseline
4. **Variance Calculation**: Precise percentage calculation with status classification
5. **Multi-Tier Validation**: Organization, Account, and Service-level reconciliation

### Status Thresholds
- **EXCELLENT** (≤1%): Perfect reconciliation
- **GOOD** (1-2%): Minor variance within acceptable range
- **WARNING** (2-5%): Moderate variance requiring attention
- **CRITICAL** (>5%): Significant variance requiring investigation

## 🔍 Advanced Troubleshooting

### Common Issues

1. **"No data available"**
   - Check date range (ACCOUNT_USAGE has 2-3 hour delay)
   - Verify service permissions and role access
   - Ensure Cortex AI services are enabled and have usage
   - Check warehouse availability and compute resources

2. **High Variance Percentages**
   - Review double counting prevention (fixed in latest version)
   - Verify date range alignment between baseline and individual services
   - Check for missing services in reconciliation logic
   - Validate AI_EXTRACT exclusion from Cortex Functions

3. **Connection Issues**
   - Verify Snowflake CLI configuration with `snow connection list`
   - Check authentication credentials and JWT token validity
   - Ensure warehouse is running and accessible
   - Validate database and schema permissions

4. **Performance Issues**
   - Use shorter date ranges for large datasets (30 days recommended)
   - Enable caching (automatic in Streamlit deployment)
   - Monitor using built-in performance tracking
   - Check warehouse size and scaling policies

5. **NULL Value Errors**
   - Fixed in latest version with improved COALESCE handling
   - Verify empty service tables don't cause comparison errors
   - Check for proper NULL handling in custom queries

## 📚 Additional Resources

### SQL Analysis Script
The `sql/cortex_credit_consumption_analysis.sql` file provides standalone SQL analysis that mirrors the Streamlit app functionality:

- **Enhanced reconciliation analysis** with double-counting prevention
- **Individual specialized function breakdown** (TRANSLATE, CLASSIFY_TEXT, etc.)
- **Cortex Analyst, Document Processing, and Cortex Search analysis**
- **Time series with function-level granularity**
- **Complete reconciliation validation** with variance analysis

### Key Components
- **`streamlit_app.py`**: Main application entry point with enhanced UI
- **`common/analytics/data_layer.py`**: Advanced Snowflake data access with caching and optimization
- **`common/analytics/reconciliation.py`**: Business logic for cost reconciliation and validation
- **`common/utils/performance_monitor.py`**: Performance tracking and optimization
- **`common/utils/data_helpers.py`**: Data processing utilities and helpers

### Documentation Files
- **`FUNCTION_MAPPING.md`**: Specialized functions mapping and future-proofing guide
- **`IMPROVEMENTS.md`**: Detailed changelog of model analysis enhancements
- **`snowflake_style_guide.md`**: Color palette and visualization standards

## 🔄 Recent Improvements (Latest Version)

### ✅ Double Counting Prevention
- **AI_EXTRACT Deduplication**: Eliminated double counting between Cortex Functions and Document Processing
- **Legacy Service Exclusion**: Automatically excludes legacy Document AI when modern data exists
- **Perfect Reconciliation**: Achieved 0.0% variance in test environments

### ✅ Enhanced Model Analysis
- **Specialized Functions Clarity**: Clear breakdown of functions without model names
- **Improved Visualizations**: Color-coded charts and dedicated sections
- **Educational Content**: Explanations of Snowflake's managed AI services

### ✅ Robust Error Handling
- **NULL Value Safety**: Improved COALESCE handling for empty datasets
- **Connection Resilience**: Better SiS vs standalone mode detection
- **Performance Optimization**: Enhanced caching and query optimization

## 🆘 Support

For support and questions:
- Review the [Snowflake Cortex AI documentation](https://docs.snowflake.com/en/guides-overview-ai-features)
- Check the [Snowflake CLI documentation](https://docs.snowflake.com/en/developer-guide/snowflake-cli/index)
- Use the built-in debug mode for performance troubleshooting
- Review `FUNCTION_MAPPING.md` for adding new function support

## 📈 Performance & Scalability

- **Optimized Queries**: Efficient CTEs and intelligent filtering
- **Smart Caching**: 30-minute TTL with configurable refresh
- **Memory Management**: Built-in monitoring and optimization
- **Multi-Account Support**: Tested across different Snowflake configurations
- **Production Ready**: Deployed and validated in enterprise environments

---

*Production-ready cost analysis for Snowflake Cortex AI Services with advanced reconciliation and zero double counting.*
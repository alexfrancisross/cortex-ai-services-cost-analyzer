# Cortex AI Services Cost Analyzer

[![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=for-the-badge&logo=snowflake&logoColor=white)](https://www.snowflake.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)

A comprehensive cost analysis and reconciliation dashboard for **Snowflake Cortex AI Services**. Provides detailed insights into AI service consumption, billing reconciliation, and performance analytics with individual function breakdown.

![Demo](img/demo.gif)

## 🚀 Features

### 📊 Reconciliation Analysis
- **AI Services Baseline** vs **Individual Services** reconciliation
- Variance analysis to identify billing discrepancies
- Real-time reconciliation status monitoring
- Support for all Cortex AI service types

### 🤖 Model & Function Analysis
- **Model Utilisation**: Token usage and credit consumption by LLM models
- **Specialized Functions**: Individual breakdown of TRANSLATE, CLASSIFY_TEXT, SENTIMENT, etc.
- **Service Analysis**: Dedicated sections for Cortex Analyst, Document AI, and Cortex Search
- Efficiency metrics (tokens per credit) for models and functions

### 📈 Time Series Analytics
- Individual function trend lines for detailed analysis
- Daily and hourly usage patterns
- Peak usage identification by specific function
- Service-specific consumption tracking

### 🔧 Service Breakdown
- **Cortex Functions**: LLM/AI Functions with individual breakdown
- **Cortex Analyst**: REST API access for data analysis
- **Document AI**: Document processing with page/document metrics
- **Cortex Search**: Vector search operations analytics
- **Fine Tuning**: Model customization services

### 📋 Data Export
- Raw data export in CSV and Excel formats
- Comprehensive usage reports with unified credit calculations
- Performance-optimized data retrieval

## 🛠️ Prerequisites

### Snowflake Requirements
- Snowflake account with Cortex AI Services enabled
- Access to `SNOWFLAKE.ACCOUNT_USAGE` views:
  - `METERING_HISTORY`
  - `CORTEX_FUNCTIONS_USAGE_HISTORY`
  - `CORTEX_ANALYST_USAGE_HISTORY`
  - `CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY`
  - `CORTEX_SEARCH_SERVING_USAGE_HISTORY`
  - `CORTEX_FINE_TUNING_USAGE_HISTORY`

### Required Permissions
```sql
-- Grant access to system views
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE <YOUR_ROLE>;

-- Database and schema access
GRANT USAGE ON DATABASE ANALYTICS TO ROLE <YOUR_ROLE>;
GRANT USAGE ON SCHEMA ANALYTICS.CORTEX_APPS TO ROLE <YOUR_ROLE>;
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
- **Reconciliation Summary**: Overall billing reconciliation status
- **Service Breakdown**: Credit distribution across Cortex services
- **Key Metrics**: Total credits, variance percentages, and status indicators

### Analysis Tabs

#### Model Analysis
- **Model Utilisation**: Credit distribution by explicit LLM models
- **Specialized Functions**: Individual analysis of AI functions
- **Service Sections**: Cortex Analyst, Document AI, and Cortex Search analytics
- Token efficiency analysis with visual charts

#### Service Details
- Detailed breakdown by service type
- Service-specific insights and metadata
- Historical usage patterns

#### Time Series
- Individual function trend lines (TRANSLATE, CLASSIFY_TEXT, COMPLETE, etc.)
- Visual trends with function-level granularity
- Peak usage identification

#### Raw Data
- Export functionality with unified TOTAL_CREDITS column
- Performance-optimized data retrieval
- CSV and Excel export options

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
    query_warehouse: "COMPUTE_WH"
    main_file: "streamlit_app.py"
```

### Dependencies (`environment.yml`)
- `streamlit` - Web application framework
- `snowflake-snowpark-python` - Snowflake connectivity
- `pandas`, `numpy` - Data processing
- `plotly` - Interactive visualizations
- `openpyxl` - Excel export support

## 📊 Data Sources

### Primary Tables
1. **METERING_HISTORY**: Overall AI Services baseline credits
2. **CORTEX_FUNCTIONS_USAGE_HISTORY**: LLM/AI function usage
3. **CORTEX_ANALYST_USAGE_HISTORY**: Business intelligence queries
4. **CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY**: Document processing
5. **CORTEX_SEARCH_SERVING_USAGE_HISTORY**: Vector search operations
6. **CORTEX_FINE_TUNING_USAGE_HISTORY**: Model fine-tuning

### Reconciliation Logic
1. Sum all individual service credits
2. Compare against AI_SERVICES baseline from METERING_HISTORY
3. Calculate variance percentage
4. Provide status: EXCELLENT (≤1%), GOOD (1-2%), WARNING (2-5%), CRITICAL (>5%)

## 🔍 Troubleshooting

### Common Issues

1. **"No data available"**
   - Check date range (ACCOUNT_USAGE has 2-3 hour delay)
   - Verify service permissions
   - Ensure Cortex AI services are enabled

2. **Connection Issues**
   - Verify Snowflake CLI configuration
   - Check authentication credentials
   - Ensure warehouse is running

3. **Performance Issues**
   - Use shorter date ranges for large datasets
   - Enable caching (automatic in Streamlit deployment)
   - Monitor using debug mode

## 📚 Additional Resources

### SQL Analysis Script
The `sql/cortex_credit_consumption_analysis.sql` file provides standalone SQL analysis that mirrors the Streamlit app functionality:

- Individual specialized function analysis
- Cortex Analyst, Document AI, and Cortex Search analysis
- Enhanced time series with function breakdown
- Complete reconciliation validation

### Key Components
- **`streamlit_app.py`**: Main application entry point
- **`data_layer.py`**: Snowflake data access and caching
- **`reconciliation.py`**: Business logic for cost reconciliation
- **`performance_monitor.py`**: Performance tracking

## 🆘 Support

For support and questions:
- Review the [Snowflake Cortex AI documentation](https://docs.snowflake.com/en/guides-overview-ai-features)
- Check the [Snowflake CLI documentation](https://docs.snowflake.com/en/developer-guide/snowflake-cli/index)
- Use the debug mode for performance troubleshooting

---
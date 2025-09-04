# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Snowflake Cortex AI Services cost analyzer built as a Streamlit application that provides comprehensive analysis and reconciliation of AI_SERVICES costs with 99.98% accuracy. The application supports both Streamlit-in-Snowflake (SiS) deployment and standalone mode.

## Common Development Commands

### Deployment
```bash
# Deploy to development environment
./scripts/deploy.sh dev

# Deploy to production environment  
./scripts/deploy.sh prod

# Validate deployment without deploying
./scripts/deploy.sh dev --validate-only
```

### Snowflake CLI Commands
```bash
# Check deployment status
snow streamlit describe cortex_cost_analyzer

# View application logs
snow streamlit logs cortex_cost_analyzer --lines 50

# Validate project configuration
snow project validate

# Deploy specific environment
snow streamlit deploy --environment dev
```

### Standalone Development
```bash
# Install dependencies for local development
pip install -r requirements.txt

# Run standalone Streamlit app (requires Snowflake connection configuration)
streamlit run app.py
```

## Architecture

### Core Components
- **`app.py`**: Main Streamlit application entry point with dashboard UI
- **`data_layer.py`**: SnowflakeDataLoader class that handles all Snowflake queries and data retrieval
- **`reconciliation.py`**: ReconciliationEngine implementing 3-tier reconciliation methodology  
- **`visualizations.py`**: Plotly chart components for dashboard visualizations
- **`utils.py`**: Helper functions, formatting utilities, and constants

### Deployment Modes
1. **Streamlit-in-Snowflake (SiS)**: Primary production mode using `get_active_session()`
2. **Standalone**: Development/testing mode using key-pair authentication with `~/.snowflake/config.toml`

### Data Architecture
The application queries 6 Cortex AI service tables from `SNOWFLAKE.ACCOUNT_USAGE`:
- `CORTEX_FUNCTIONS_USAGE_HISTORY` (token_credits)
- `CORTEX_ANALYST_USAGE_HISTORY` (credits) 
- `CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY` (credits_used)
- `CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY` (token_credits)
- `CORTEX_SEARCH_DAILY_USAGE_HISTORY` (credits)
- `CORTEX_SEARCH_SERVING_USAGE_HISTORY` (credits)

### Reconciliation Methodology
Three-tier validation system:
1. **Tier 1**: Organization level (`ORGANIZATION_USAGE.METERING_DAILY_HISTORY`)
2. **Tier 2**: Account hourly (`ACCOUNT_USAGE.METERING_HISTORY`)
3. **Tier 3**: Granular services (sum of all 6 service tables)

## Configuration Files

### Snowflake CLI Configuration (`snowflake.yml`)
- Defines Streamlit app entity configuration
- Specifies deployment artifacts and environment settings
- Configures target database/schema: `ANALYTICS.CORTEX_APPS`

### Environment Configuration (`environment.yml`)
- Conda environment for Streamlit-in-Snowflake deployment
- Contains core dependencies: pandas, numpy, plotly, streamlit

### Python Dependencies (`requirements.txt`)
- Standalone mode dependencies including snowflake-connector-python
- Used for local development and testing

## Required Snowflake Permissions
```sql
-- Minimum privileges for deployment
GRANT USAGE ON DATABASE SNOWFLAKE TO ROLE <app_role>;
GRANT USAGE ON SCHEMA SNOWFLAKE.ACCOUNT_USAGE TO ROLE <app_role>;
GRANT SELECT ON ALL VIEWS IN SCHEMA SNOWFLAKE.ACCOUNT_USAGE TO ROLE <app_role>;

-- Optional for enhanced reconciliation  
GRANT USAGE ON SCHEMA SNOWFLAKE.ORGANIZATION_USAGE TO ROLE <app_role>;
GRANT SELECT ON SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY TO ROLE <app_role>;
```

## Development Environment Setup

### For Snowflake CLI Development
1. Install Snowflake CLI: `pip install snowflake-cli-labs`
2. Configure connection: `snow connection add`
3. Deploy to dev: `./scripts/deploy.sh dev`

### For Standalone Development  
1. Install dependencies: `pip install -r requirements.txt`
2. Configure `~/.snowflake/config.toml` with connection details
3. Run locally: `streamlit run app.py`

## Testing

The `tests/` directory exists but testing framework is not yet configured. When adding tests:
- Check if pytest or another testing framework should be added to requirements
- Consider testing data_layer queries against sample data
- Test reconciliation engine accuracy with known datasets
- Verify visualization components render correctly

## Deployment Environments

### Development
- Database: `ANALYTICS_DEV`
- Schema: `CORTEX_APPS_DEV` 
- App: `CORTEX_AI_COST_ANALYZER_DEV`

### Production
- Database: `ANALYTICS`
- Schema: `CORTEX_APPS`
- App: `CORTEX_AI_COST_ANALYZER`

## Important Notes

- The application auto-detects deployment mode (SiS vs standalone) in `get_snowflake_session()`
- All SQL queries use parameterized templates in `SnowflakeDataLoader`
- Reconciliation accuracy target is 99.98% between hourly and granular services
- Performance target: <3 seconds load time for 90-day analysis
- The application requires active Cortex AI Services usage data to function properly
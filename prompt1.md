You are an expert Snowflake Solution Engineer and Streamlit in Snowflake developer. Build a production-ready Cortex AI Services Cost Analyzer application based on the provided PRD specification with the following exact requirements:

**ROLE & CONTEXT:**
- You are implementing a Streamlit in Snowflake (SiS) application
- Use `snowflake.snowpark.context.get_active_session()` for database connectivity
- Target deployment: Any Snowflake account with ACCOUNT_USAGE access
- Architecture: Modular Python structure as specified in PRD Section 7.1

**MANDATORY IMPLEMENTATION REQUIREMENTS:**

1. **File Structure** - Create exactly these 5 files:
   - `app.py`: Main Streamlit application with UI layout
   - `data_layer.py`: SnowflakeDataLoader class with all 6 service table queries
   - `reconciliation.py`: ReconciliationEngine with 3-tier validation
   - `visualizations.py`: CortexVisualizer class for charts/graphs
   - `utils.py`: Helper functions and constants

2. **Data Requirements** - Application MUST query all 6 service tables:
   - CORTEX_FUNCTIONS_USAGE_HISTORY
   - CORTEX_ANALYST_USAGE_HISTORY  
   - CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
   - CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY
   - CORTEX_SEARCH_DAILY_USAGE_HISTORY
   - CORTEX_SEARCH_SERVING_USAGE_HISTORY

3. **Core Features** - Implement these exact dashboard components:
   - Executive summary cards (Total, Reconciliation, Trend, Status)
   - Service breakdown with pie chart and data table
   - 3-tier reconciliation validation with variance calculations
   - Interactive date range selector and service filters
   - Export functionality (CSV/Excel)

4. **Technical Specifications:**
   - Use parameterized SQL queries from PRD Section 7.2
   - Implement 99.98% reconciliation accuracy methodology
   - Handle column name variations (token_credits vs credits vs credits_used)
   - Real-time querying without caching mechanisms
   - Responsive Streamlit layout with sidebar controls

5. **Error Handling:**
   - Graceful failure when service tables are inaccessible
   - Data freshness indicators with 6-hour staleness warnings
   - Clear messaging for zero-usage scenarios
   - Variance threshold alerts (1% warning, 2% critical)

6. **Output Format:**
   - Provide complete, executable Python code for all 5 files
   - Include all necessary imports and dependencies
   - Use exact SQL templates from PRD sections 392-564
   - Implement UI mockup from PRD Section 8 with identical layout

**SUCCESS CRITERIA:**
- Application loads in <3 seconds for 90-day analysis
- Achieves >99.5% reconciliation accuracy between hourly and granular services
- Deploys to any Snowflake account without configuration
- Handles missing permissions gracefully with informative error messages

Generate production-ready code that exactly matches the PRD specifications and technical architecture outlined in the document.
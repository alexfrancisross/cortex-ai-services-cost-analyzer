-- =============================================================================
-- CORTEX AI SERVICES COST ANALYSIS
-- =============================================================================
-- This script provides all insights from the Cortex Cost Analyzer Streamlit app.
-- Includes: Reconciliation, Enhanced Model Analysis, Specialized Functions,
--           Individual Service Analysis, Time Series with Function Breakdown, Raw Data
--
-- Billing Domain Notes:
--   CORTEX_AI_FUNCTIONS_USAGE_HISTORY   — excluded from all sums; exact duplicate of
--                                         CORTEX_AISQL_USAGE_HISTORY (identical credits).
--   CORTEX_AISQL_USAGE_HISTORY          — rows tagged query_tag LIKE '%cortex_code_cli%'
--                                         are ALSO in CORTEX_CODE_CLI_USAGE_HISTORY.
--                                         Filter them out to avoid double-counting.
--   CORTEX_REST_API_USAGE_HISTORY       — billed in USD/million tokens, NOT in AI_SERVICES
--                                         credits. Excluded from reconciliation entirely.
--   CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY — FALLBACK: billing event type changed
--                                         Nov 2025; view may return 0 on some accounts.
--                                         Zeroed out in reconciliation sum.
--
-- Key Views and Time Columns:
--   CORTEX_AISQL / CODE_CLI / CODE_SNOWSIGHT  → USAGE_TIME
--   CORTEX_SEARCH_DAILY                        → USAGE_DATE (DATE, not TIMESTAMP)
--   CORTEX_PROVISIONED_THROUGHPUT              → INTERVAL_START_TIME
--   All other views                            → START_TIME
--
-- Author: Alex Ross
-- Updated: 2026-03-27
-- =============================================================================

-- Set date range variables (adjust as needed)
-- Example last-30-days: SET start_date = DATEADD('day', -30, CURRENT_DATE())::DATE::VARCHAR;
SET start_date = '2024-09-01';
SET end_date = '2024-09-26';

-- =============================================================================
-- 1. AI SERVICES RECONCILIATION ANALYSIS
-- =============================================================================
-- Purpose: Reconcile AI_SERVICES baseline against sum of individual services
-- Expected: Variance should be close to 0% for accurate billing reconciliation
-- Thresholds: EXCELLENT ≤1%, GOOD ≤2%, WARNING ≤5%, CRITICAL >5%

WITH ai_baseline AS (
    -- Tier 2: METERING_HISTORY is the authoritative billing baseline
    SELECT COALESCE(SUM(credits_used), 0) as total_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
      AND service_type = 'AI_SERVICES'
),
individual_services AS (
    -- CORTEX_AISQL: exclude rows tagged app:cortex_code_cli (also in CODE_CLI — double-count)
    -- NOTE: CORTEX_AI_FUNCTIONS_USAGE_HISTORY excluded — exact duplicate of CORTEX_AISQL
    SELECT
        'CORTEX_AISQL' as service,
        COALESCE(SUM(token_credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
    WHERE usage_time >= $start_date::date
      AND usage_time < $end_date::date + INTERVAL '1 day'
      AND NOT (query_tag LIKE '%cortex_code_cli%')

    UNION ALL

    -- Cortex Code CLI (terminal / VS Code extension)
    SELECT
        'CORTEX_CODE_CLI' as service,
        COALESCE(SUM(token_credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY
    WHERE usage_time >= $start_date::date
      AND usage_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Code in Snowsight
    SELECT
        'CORTEX_CODE_SNOWSIGHT' as service,
        COALESCE(SUM(token_credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY
    WHERE usage_time >= $start_date::date
      AND usage_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Analyst (REST API usage)
    SELECT
        'CORTEX_ANALYST' as service,
        COALESCE(SUM(credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Agents (GA Feb 25 2026)
    SELECT
        'CORTEX_AGENT' as service,
        COALESCE(SUM(token_credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Snowflake Intelligence (GA Feb 25 2026)
    SELECT
        'SNOWFLAKE_INTELLIGENCE' as service,
        COALESCE(SUM(token_credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Search Serving (vector search query operations)
    SELECT
        'CORTEX_SEARCH_SERVING' as service,
        COALESCE(SUM(credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Search Daily (index build/refresh — uses USAGE_DATE, a DATE column)
    SELECT
        'CORTEX_SEARCH_DAILY' as service,
        COALESCE(SUM(credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
    WHERE usage_date >= $start_date::date
      AND usage_date <= $end_date::date

    UNION ALL

    -- Cortex Search Batch Queries
    SELECT
        'CORTEX_SEARCH_BATCH_QUERY' as service,
        COALESCE(SUM(credits_used), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_BATCH_QUERY_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Fine Tuning (model customization)
    SELECT
        'CORTEX_FINE_TUNING' as service,
        COALESCE(SUM(token_credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FINE_TUNING_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Provisioned Throughput Units (uses INTERVAL_START_TIME and PTU_CREDITS)
    SELECT
        'CORTEX_PROVISIONED_THROUGHPUT' as service,
        COALESCE(SUM(ptu_credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_PROVISIONED_THROUGHPUT_USAGE_HISTORY
    WHERE interval_start_time >= $start_date::date
      AND interval_start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Document AI (legacy, pre-Cortex document processing)
    -- Only include if CORTEX_DOCUMENT_PROCESSING has no data (prevent double-count)
    SELECT
        'DOCUMENT_AI' as service,
        CASE
            WHEN (SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
                  WHERE start_time >= $start_date::date
                    AND start_time < $end_date::date + INTERVAL '1 day') > 0
            THEN 0
            ELSE COALESCE(SUM(credits_used), 0)
        END as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Document Processing — FALLBACK: zeroed due to billing event type change (Nov 2025)
    -- View exists but credits_used may be unreliable on some accounts post-Nov 2025.
    -- Re-enable when Snowflake confirms the fix.
    SELECT
        'CORTEX_DOCUMENT_PROCESSING' as service,
        0 as credits
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
        MAX(CASE WHEN st.service = 'CORTEX_AISQL'                  THEN st.credits END) as cortex_aisql,
        MAX(CASE WHEN st.service = 'CORTEX_CODE_CLI'               THEN st.credits END) as cortex_code_cli,
        MAX(CASE WHEN st.service = 'CORTEX_CODE_SNOWSIGHT'         THEN st.credits END) as cortex_code_snowsight,
        MAX(CASE WHEN st.service = 'CORTEX_ANALYST'                THEN st.credits END) as cortex_analyst,
        MAX(CASE WHEN st.service = 'CORTEX_AGENT'                  THEN st.credits END) as cortex_agent,
        MAX(CASE WHEN st.service = 'SNOWFLAKE_INTELLIGENCE'        THEN st.credits END) as snowflake_intelligence,
        MAX(CASE WHEN st.service = 'CORTEX_SEARCH_SERVING'         THEN st.credits END) as cortex_search_serving,
        MAX(CASE WHEN st.service = 'CORTEX_SEARCH_DAILY'           THEN st.credits END) as cortex_search_daily,
        MAX(CASE WHEN st.service = 'CORTEX_SEARCH_BATCH_QUERY'     THEN st.credits END) as cortex_search_batch_query,
        MAX(CASE WHEN st.service = 'CORTEX_FINE_TUNING'            THEN st.credits END) as cortex_fine_tuning,
        MAX(CASE WHEN st.service = 'CORTEX_PROVISIONED_THROUGHPUT' THEN st.credits END) as cortex_provisioned_throughput,
        MAX(CASE WHEN st.service = 'DOCUMENT_AI'                   THEN st.credits END) as document_ai,
        MAX(CASE WHEN st.service = 'CORTEX_DOCUMENT_PROCESSING'    THEN st.credits END) as cortex_document_processing
    FROM ai_baseline b
    CROSS JOIN service_totals st
    GROUP BY b.total_credits, st.total_individual
)
SELECT
    '1. RECONCILIATION ANALYSIS' as analysis_type,
    ai_services_baseline,
    total_individual,
    cortex_aisql,
    cortex_code_cli,
    cortex_code_snowsight,
    cortex_analyst,
    cortex_agent,
    snowflake_intelligence,
    cortex_search_serving,
    cortex_search_daily,
    cortex_search_batch_query,
    cortex_fine_tuning,
    cortex_provisioned_throughput,
    document_ai,
    cortex_document_processing,
    ((total_individual - ai_services_baseline) / NULLIF(ai_services_baseline, 0) * 100) as variance_pct,
    (total_individual / NULLIF(ai_services_baseline, 0) * 100) as coverage_pct,
    CASE
        WHEN ABS((total_individual - ai_services_baseline) / NULLIF(ai_services_baseline, 0) * 100) <= 1 THEN 'EXCELLENT'
        WHEN ABS((total_individual - ai_services_baseline) / NULLIF(ai_services_baseline, 0) * 100) <= 2 THEN 'GOOD'
        WHEN ABS((total_individual - ai_services_baseline) / NULLIF(ai_services_baseline, 0) * 100) <= 5 THEN 'WARNING'
        ELSE 'CRITICAL'
    END as reconciliation_status
FROM summary;

-- =============================================================================
-- 2. MODEL TOKEN & CREDIT ANALYSIS (Enhanced with Model Types)
-- =============================================================================
-- Purpose: Analyze token consumption and credit costs by AI model with type classification
-- Insights: Model efficiency, usage patterns, explicit vs specialized function breakdown

SELECT
    '2a. MODEL ANALYSIS - EXPLICIT MODELS' as analysis_type,
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
    ROUND(100 * SUM(TOKEN_CREDITS) / NULLIF(SUM(SUM(TOKEN_CREDITS)) OVER(), 0), 2) as pct_of_total_credits,
    -- Efficiency ranking
    RANK() OVER (ORDER BY NULLIF(SUM(TOKENS) / NULLIF(SUM(TOKEN_CREDITS), 0), 0) DESC) as efficiency_rank
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
-- Cortex AI SQL (replaces CORTEX_FUNCTIONS_USAGE_HISTORY for LLM calls)
WHERE USAGE_TIME >= $start_date::date
    AND USAGE_TIME < $end_date::date + INTERVAL '1 day'
GROUP BY
    CASE
        WHEN MODEL_NAME = '' OR MODEL_NAME IS NULL THEN 'Specialized Functions'
        ELSE MODEL_NAME
    END,
    CASE
        WHEN MODEL_NAME = '' OR MODEL_NAME IS NULL THEN 'SPECIALIZED'
        ELSE 'EXPLICIT_MODEL'
    END
ORDER BY total_credits DESC;

-- =============================================================================
-- 2b. SPECIALIZED FUNCTIONS ANALYSIS
-- =============================================================================
-- Purpose: Detailed breakdown of specialized functions (TRANSLATE, CLASSIFY_TEXT, etc.)
-- Insights: Function-specific usage patterns and efficiency

SELECT
    '2b. SPECIALIZED FUNCTIONS ANALYSIS' as analysis_type,
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
        WHERE USAGE_TIME >= $start_date::date
            AND USAGE_TIME < $end_date::date + INTERVAL '1 day'
            AND (MODEL_NAME = '' OR MODEL_NAME IS NULL)
    ), 0), 2) as pct_of_specialized_credits,
    MIN(USAGE_TIME) as first_usage,
    MAX(USAGE_TIME) as last_usage
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
WHERE USAGE_TIME >= $start_date::date
    AND USAGE_TIME < $end_date::date + INTERVAL '1 day'
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
ORDER BY total_credits DESC;

-- =============================================================================
-- 3. SERVICE BREAKDOWN & UTILIZATION
-- =============================================================================
-- Purpose: Detailed breakdown of each AI service with usage metrics
-- Insights: Service adoption, cost distribution, optimization targets
-- Note: CORTEX_AI_FUNCTIONS excluded (duplicate of CORTEX_AISQL)
--       CORTEX_DOCUMENT_PROCESSING shown as FALLBACK — credits zeroed (see header notes)

WITH service_breakdown AS (
    -- Cortex AI SQL — excludes rows tagged app:cortex_code_cli (counted in CODE_CLI)
    SELECT
        'CORTEX_AISQL' as service_type,
        'Token-based LLM function calls (excl. code_cli tagged rows)' as description,
        'Individual function call level' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(token_credits, 0)) as total_credits,
        MIN(usage_time) as first_usage,
        MAX(usage_time) as last_usage,
        COUNT(DISTINCT model_name) as unique_models,
        COUNT(DISTINCT function_name) as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
    WHERE usage_time >= $start_date::date
      AND usage_time < $end_date::date + INTERVAL '1 day'
      AND NOT (query_tag LIKE '%cortex_code_cli%')

    UNION ALL

    -- Cortex Code CLI (terminal / VS Code extension)
    SELECT
        'CORTEX_CODE_CLI' as service_type,
        'Cortex Code CLI (terminal / VS Code extension)' as description,
        'Per-session user level' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(token_credits, 0)) as total_credits,
        MIN(usage_time) as first_usage,
        MAX(usage_time) as last_usage,
        NULL as unique_models,
        NULL as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY
    WHERE usage_time >= $start_date::date
      AND usage_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Code in Snowsight
    SELECT
        'CORTEX_CODE_SNOWSIGHT' as service_type,
        'Cortex Code in Snowsight (rolling out 2026)' as description,
        'Per-session Snowsight level' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(token_credits, 0)) as total_credits,
        MIN(usage_time) as first_usage,
        MAX(usage_time) as last_usage,
        NULL as unique_models,
        NULL as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY
    WHERE usage_time >= $start_date::date
      AND usage_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Analyst
    SELECT
        'CORTEX_ANALYST' as service_type,
        'REST API requests for data analysis' as description,
        'Request level' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(credits, 0)) as total_credits,
        MIN(start_time) as first_usage,
        MAX(start_time) as last_usage,
        NULL as unique_models,
        NULL as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Agents (GA Feb 25 2026)
    SELECT
        'CORTEX_AGENT' as service_type,
        'Cortex Agent requests (GA Feb 25 2026)' as description,
        'Request level' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(token_credits, 0)) as total_credits,
        MIN(start_time) as first_usage,
        MAX(start_time) as last_usage,
        NULL as unique_models,
        NULL as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Snowflake Intelligence (GA Feb 25 2026)
    SELECT
        'SNOWFLAKE_INTELLIGENCE' as service_type,
        'Snowflake Intelligence requests (GA Feb 25 2026)' as description,
        'Request level' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(token_credits, 0)) as total_credits,
        MIN(start_time) as first_usage,
        MAX(start_time) as last_usage,
        NULL as unique_models,
        NULL as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Search Serving
    SELECT
        'CORTEX_SEARCH_SERVING' as service_type,
        'Vector search query operations' as description,
        'Hourly aggregation' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(credits, 0)) as total_credits,
        MIN(start_time) as first_usage,
        MAX(start_time) as last_usage,
        NULL as unique_models,
        NULL as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Search Daily (index build/refresh — uses USAGE_DATE)
    SELECT
        'CORTEX_SEARCH_DAILY' as service_type,
        'Cortex Search index build/refresh (daily)' as description,
        'Daily by service' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(credits, 0)) as total_credits,
        MIN(usage_date)::TIMESTAMP_NTZ as first_usage,
        MAX(usage_date)::TIMESTAMP_NTZ as last_usage,
        NULL as unique_models,
        NULL as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
    WHERE usage_date >= $start_date::date
      AND usage_date <= $end_date::date

    UNION ALL

    -- Cortex Search Batch Queries
    SELECT
        'CORTEX_SEARCH_BATCH_QUERY' as service_type,
        'Cortex Search batch queries' as description,
        'Per-batch query level' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(credits_used, 0)) as total_credits,
        MIN(start_time) as first_usage,
        MAX(start_time) as last_usage,
        NULL as unique_models,
        NULL as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_BATCH_QUERY_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Fine Tuning
    SELECT
        'CORTEX_FINE_TUNING' as service_type,
        'Model fine-tuning operations' as description,
        'Token-based training usage' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(token_credits, 0)) as total_credits,
        MIN(start_time) as first_usage,
        MAX(start_time) as last_usage,
        COUNT(DISTINCT model_name) as unique_models,
        NULL as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FINE_TUNING_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Provisioned Throughput (uses INTERVAL_START_TIME and PTU_CREDITS)
    SELECT
        'CORTEX_PROVISIONED_THROUGHPUT' as service_type,
        'Cortex Provisioned Throughput Units' as description,
        'Hourly interval level' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(ptu_credits, 0)) as total_credits,
        MIN(interval_start_time) as first_usage,
        MAX(interval_start_time) as last_usage,
        NULL as unique_models,
        NULL as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_PROVISIONED_THROUGHPUT_USAGE_HISTORY
    WHERE interval_start_time >= $start_date::date
      AND interval_start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Document AI (legacy)
    SELECT
        'DOCUMENT_AI' as service_type,
        'Legacy document processing' as description,
        'Document level' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(credits_used, 0)) as total_credits,
        MIN(start_time) as first_usage,
        MAX(start_time) as last_usage,
        NULL as unique_models,
        NULL as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'

    UNION ALL

    -- Cortex Document Processing — FALLBACK: zeroed (billing event type change Nov 2025)
    SELECT
        'CORTEX_DOCUMENT_PROCESSING (FALLBACK)' as service_type,
        'Modern document AI — EXCLUDED: billing event type change broke credits Nov 2025' as description,
        'Document processing operations' as granularity,
        0 as record_count,
        0 as total_credits,
        NULL as first_usage,
        NULL as last_usage,
        NULL as unique_models,
        NULL as unique_functions
)
SELECT
    '3. SERVICE BREAKDOWN' as analysis_type,
    service_type,
    description,
    granularity,
    record_count,
    total_credits,
    ROUND(100 * total_credits / NULLIF(SUM(total_credits) OVER(), 0), 2) as percentage_of_total,
    first_usage,
    last_usage,
    DATEDIFF('day', first_usage, last_usage) + 1 as days_active,
    unique_models,
    unique_functions,
    CASE
        WHEN record_count = 0 THEN 'NO_USAGE'
        WHEN record_count < 100 THEN 'LOW'
        WHEN record_count < 1000 THEN 'MEDIUM'
        WHEN record_count < 10000 THEN 'HIGH'
        ELSE 'VERY_HIGH'
    END as usage_intensity
FROM service_breakdown
WHERE total_credits > 0
ORDER BY total_credits DESC;

-- =============================================================================
-- 2c. CORTEX ANALYST ANALYSIS
-- =============================================================================
-- Purpose: Detailed analysis of Cortex Analyst usage (REST API access)

SELECT
    '2c. CORTEX ANALYST ANALYSIS' as analysis_type,
    COUNT(*) as total_requests,
    SUM(CREDITS) as total_credits,
    AVG(CREDITS) as avg_credits_per_request,
    ROUND(100 * SUM(CREDITS) / NULLIF((
        SELECT SUM(CREDITS)
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
        WHERE START_TIME >= $start_date::date
            AND START_TIME < $end_date::date + INTERVAL '1 day'
    ), 0), 2) as pct_of_total_credits,
    MIN(START_TIME) as first_usage,
    MAX(START_TIME) as last_usage,
    COUNT(DISTINCT USERNAME) as unique_users
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
WHERE START_TIME >= $start_date::date
    AND START_TIME < $end_date::date + INTERVAL '1 day';

-- =============================================================================
-- 2d. DOCUMENT AI ANALYSIS
-- =============================================================================
-- Purpose: Detailed analysis of Document AI usage (modern document processing)

SELECT
    '2d. DOCUMENT AI ANALYSIS' as analysis_type,
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
        WHERE START_TIME >= $start_date::date
            AND START_TIME < $end_date::date + INTERVAL '1 day'
    ), 0), 2) as pct_of_total_credits,
    MIN(START_TIME) as first_usage,
    MAX(START_TIME) as last_usage,
    COUNT(DISTINCT QUERY_ID) as unique_queries
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
WHERE START_TIME >= $start_date::date
    AND START_TIME < $end_date::date + INTERVAL '1 day';

-- =============================================================================
-- 2e. CORTEX SEARCH ANALYSIS
-- =============================================================================
-- Purpose: Detailed analysis of Cortex Search usage (vector search operations)

SELECT
    '2e. CORTEX SEARCH ANALYSIS' as analysis_type,
    COUNT(*) as total_operations,
    SUM(CREDITS) as total_credits,
    AVG(CREDITS) as avg_credits_per_operation,
    ROUND(100 * SUM(CREDITS) / NULLIF((
        SELECT SUM(CREDITS)
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
        WHERE START_TIME >= $start_date::date
            AND START_TIME < $end_date::date + INTERVAL '1 day'
    ), 0), 2) as pct_of_total_credits,
    MIN(START_TIME) as first_usage,
    MAX(START_TIME) as last_usage,
    COUNT(DISTINCT SERVICE_NAME) as unique_services
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
WHERE START_TIME >= $start_date::date
    AND START_TIME < $end_date::date + INTERVAL '1 day';

-- =============================================================================
-- 4. DAILY TIME SERIES ANALYSIS (Enhanced with Individual Function Breakdown)
-- =============================================================================
-- Purpose: Track daily usage trends across all AI services
-- Insights: Usage patterns, peak periods, growth trends

WITH daily_time_series AS (
    -- Specialized Functions (individual breakdown)
    SELECT
        DATE_TRUNC('day', usage_time) as period,
        CASE
            WHEN FUNCTION_NAME IS NULL OR FUNCTION_NAME = '' THEN 'Other Specialized'
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
        SUM(COALESCE(token_credits, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
    WHERE usage_time >= $start_date::date
      AND usage_time < $end_date::date + INTERVAL '1 day'
      AND (MODEL_NAME IS NULL OR MODEL_NAME = '')  -- Only specialized functions
    GROUP BY 1, 2

    UNION ALL

    -- Explicit Model Functions (individual breakdown)
    SELECT
        DATE_TRUNC('day', usage_time) as period,
        CASE
            WHEN FUNCTION_NAME = 'COMPLETE' THEN 'COMPLETE'
            WHEN FUNCTION_NAME = 'EMBED_TEXT_768' THEN 'EMBED_TEXT_768'
            WHEN FUNCTION_NAME = 'EMBED_TEXT_1024' THEN 'EMBED_TEXT_1024'
            WHEN FUNCTION_NAME = 'EMBED_TEXT' THEN 'EMBED_TEXT_EXPLICIT'
            WHEN FUNCTION_NAME = 'FINETUNE' THEN 'FINETUNE'
            WHEN FUNCTION_NAME = 'COUNT_TOKENS' THEN 'COUNT_TOKENS'
            ELSE 'Other Explicit'
        END as service_type,
        SUM(COALESCE(token_credits, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
    WHERE usage_time >= $start_date::date
      AND usage_time < $end_date::date + INTERVAL '1 day'
      AND (MODEL_NAME IS NOT NULL AND MODEL_NAME != '')  -- Only explicit model functions
    GROUP BY 1, 2

    UNION ALL

    -- Cortex Code CLI
    SELECT
        DATE_TRUNC('day', usage_time) as period,
        'CORTEX_CODE_CLI' as service_type,
        SUM(COALESCE(token_credits, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY
    WHERE usage_time >= $start_date::date
      AND usage_time < $end_date::date + INTERVAL '1 day'
    GROUP BY 1

    UNION ALL

    -- Cortex Code Snowsight
    SELECT
        DATE_TRUNC('day', usage_time) as period,
        'CORTEX_CODE_SNOWSIGHT' as service_type,
        SUM(COALESCE(token_credits, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY
    WHERE usage_time >= $start_date::date
      AND usage_time < $end_date::date + INTERVAL '1 day'
    GROUP BY 1

    UNION ALL

    -- Cortex Analyst
    SELECT
        DATE_TRUNC('day', start_time) as period,
        'CORTEX_ANALYST' as service_type,
        SUM(COALESCE(credits, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
    GROUP BY 1

    UNION ALL

    -- Cortex Agents
    SELECT
        DATE_TRUNC('day', start_time) as period,
        'CORTEX_AGENT' as service_type,
        SUM(COALESCE(token_credits, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
    GROUP BY 1

    UNION ALL

    -- Snowflake Intelligence
    SELECT
        DATE_TRUNC('day', start_time) as period,
        'SNOWFLAKE_INTELLIGENCE' as service_type,
        SUM(COALESCE(token_credits, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
    GROUP BY 1

    UNION ALL

    -- Document AI
    SELECT
        DATE_TRUNC('day', start_time) as period,
        'DOCUMENT_AI' as service_type,
        SUM(COALESCE(credits_used, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
    GROUP BY 1

    UNION ALL

    -- Cortex Search Serving
    SELECT
        DATE_TRUNC('day', start_time) as period,
        'CORTEX_SEARCH_SERVING' as service_type,
        SUM(COALESCE(credits, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
    GROUP BY 1

    UNION ALL

    -- Cortex Search Daily (USAGE_DATE — truncate to day directly)
    SELECT
        usage_date::TIMESTAMP_NTZ as period,
        'CORTEX_SEARCH_DAILY' as service_type,
        SUM(COALESCE(credits, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
    WHERE usage_date >= $start_date::date
      AND usage_date <= $end_date::date
    GROUP BY 1

    UNION ALL

    -- Cortex Search Batch Queries
    SELECT
        DATE_TRUNC('day', start_time) as period,
        'CORTEX_SEARCH_BATCH_QUERY' as service_type,
        SUM(COALESCE(credits_used, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_BATCH_QUERY_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
    GROUP BY 1

    UNION ALL

    -- Cortex Fine Tuning
    SELECT
        DATE_TRUNC('day', start_time) as period,
        'CORTEX_FINE_TUNING' as service_type,
        SUM(COALESCE(token_credits, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FINE_TUNING_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
    GROUP BY 1

    UNION ALL

    -- Cortex Provisioned Throughput (uses INTERVAL_START_TIME)
    SELECT
        DATE_TRUNC('day', interval_start_time) as period,
        'CORTEX_PROVISIONED_THROUGHPUT' as service_type,
        SUM(COALESCE(ptu_credits, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_PROVISIONED_THROUGHPUT_USAGE_HISTORY
    WHERE interval_start_time >= $start_date::date
      AND interval_start_time < $end_date::date + INTERVAL '1 day'
    GROUP BY 1

    -- NOTE: CORTEX_DOCUMENT_PROCESSING excluded (FALLBACK — billing change Nov 2025)
),
daily_totals AS (
    SELECT
        period,
        SUM(credits) as total_daily_credits,
        SUM(operation_count) as total_daily_operations
    FROM daily_time_series
    GROUP BY period
),
peak_analysis AS (
    SELECT
        period,
        total_daily_credits,
        total_daily_operations,
        RANK() OVER (ORDER BY total_daily_credits DESC) as credit_rank,
        RANK() OVER (ORDER BY total_daily_operations DESC) as operation_rank
    FROM daily_totals
)
SELECT
    '4. DAILY TIME SERIES' as analysis_type,
    dts.period,
    dts.service_type,
    dts.credits,
    dts.operation_count,
    dt.total_daily_credits,
    dt.total_daily_operations,
    ROUND(100 * dts.credits / NULLIF(dt.total_daily_credits, 0), 2) as pct_of_daily_credits,
    CASE WHEN pa.credit_rank = 1 THEN 'PEAK_CREDIT_DAY' ELSE NULL END as peak_credit_indicator,
    CASE WHEN pa.operation_rank = 1 THEN 'PEAK_OPERATION_DAY' ELSE NULL END as peak_operation_indicator
FROM daily_time_series dts
JOIN daily_totals dt ON dts.period = dt.period
JOIN peak_analysis pa ON dts.period = pa.period
WHERE dts.credits > 0
ORDER BY dts.period DESC, dts.credits DESC;

-- =============================================================================
-- 5. DETAILED RAW DATA EXPORT (LIMITED TO 1000 RECORDS)
-- =============================================================================
-- Purpose: Provide granular transaction-level data for deep analysis
-- Matches get_raw_export_data() from data_layer.py

-- 5a. Cortex AI SQL Usage
SELECT
    '5a. RAW DATA - CORTEX_AISQL' as analysis_type,
    usage_time,
    model_name,
    function_name,
    tokens,
    token_credits,
    username,
    token_credits as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
WHERE usage_time >= $start_date::date
    AND usage_time <= $end_date::date
ORDER BY usage_time DESC
LIMIT 500;

-- 5b. Cortex Analyst Usage
SELECT
    '5b. RAW DATA - CORTEX_ANALYST' as analysis_type,
    start_time,
    end_time,
    username,
    credits,
    request_count,
    credits as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
WHERE start_time >= $start_date::date
    AND start_time <= $end_date::date
ORDER BY start_time DESC
LIMIT 200;

-- 5c. Document AI Usage
SELECT
    '5c. RAW DATA - DOCUMENT_AI' as analysis_type,
    start_time,
    credits_used,
    operation_name,
    page_count,
    document_count,
    feature_count,
    credits_used as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
WHERE start_time >= $start_date::date
    AND start_time <= $end_date::date
ORDER BY start_time DESC
LIMIT 100;

-- 5d. Cortex Search Serving Usage
SELECT
    '5d. RAW DATA - CORTEX_SEARCH_SERVING' as analysis_type,
    start_time,
    end_time,
    database_name,
    schema_name,
    service_name,
    service_id,
    credits,
    credits as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
WHERE start_time >= $start_date::date
    AND start_time <= $end_date::date
ORDER BY start_time DESC
LIMIT 100;

-- 5e. Cortex Document Processing Usage (FALLBACK — may return 0 rows post-Nov 2025)
SELECT
    '5e. RAW DATA - CORTEX_DOCUMENT_PROCESSING (FALLBACK)' as analysis_type,
    start_time,
    credits_used,
    operation_name,
    page_count,
    document_count,
    credits_used as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
WHERE start_time >= $start_date::date
    AND start_time <= $end_date::date
ORDER BY start_time DESC
LIMIT 100;

-- 5f. Cortex Agents Usage (GA Feb 25 2026)
SELECT
    '5f. RAW DATA - CORTEX_AGENT' as analysis_type,
    start_time,
    agent_name,
    agent_database_name,
    agent_schema_name,
    token_credits,
    token_credits as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
WHERE start_time >= $start_date::date
    AND start_time <= $end_date::date
ORDER BY start_time DESC
LIMIT 100;

-- 5g. Snowflake Intelligence Usage (GA Feb 25 2026)
SELECT
    '5g. RAW DATA - SNOWFLAKE_INTELLIGENCE' as analysis_type,
    start_time,
    snowflake_intelligence_name,
    token_credits,
    token_credits as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY
WHERE start_time >= $start_date::date
    AND start_time <= $end_date::date
ORDER BY start_time DESC
LIMIT 100;

-- 5h. Cortex Code CLI Usage
SELECT
    '5h. RAW DATA - CORTEX_CODE_CLI' as analysis_type,
    usage_time,
    username,
    token_credits,
    token_credits as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY
WHERE usage_time >= $start_date::date
    AND usage_time <= $end_date::date
ORDER BY usage_time DESC
LIMIT 200;

-- 5i. Cortex Code Snowsight Usage
SELECT
    '5i. RAW DATA - CORTEX_CODE_SNOWSIGHT' as analysis_type,
    usage_time,
    username,
    token_credits,
    token_credits as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY
WHERE usage_time >= $start_date::date
    AND usage_time <= $end_date::date
ORDER BY usage_time DESC
LIMIT 200;

-- 5j. Cortex Search Daily Usage (USAGE_DATE — index build/refresh charges)
SELECT
    '5j. RAW DATA - CORTEX_SEARCH_DAILY' as analysis_type,
    usage_date,
    service_name,
    database_name,
    schema_name,
    credits,
    credits as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
WHERE usage_date >= $start_date::date
    AND usage_date <= $end_date::date
ORDER BY usage_date DESC
LIMIT 200;

-- 5k. Cortex Search Batch Query Usage
SELECT
    '5k. RAW DATA - CORTEX_SEARCH_BATCH_QUERY' as analysis_type,
    start_time,
    end_time,
    service_name,
    database_name,
    schema_name,
    credits_used,
    credits_used as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_BATCH_QUERY_USAGE_HISTORY
WHERE start_time >= $start_date::date
    AND start_time <= $end_date::date
ORDER BY start_time DESC
LIMIT 100;

-- 5l. Cortex Provisioned Throughput Usage
SELECT
    '5l. RAW DATA - CORTEX_PROVISIONED_THROUGHPUT' as analysis_type,
    interval_start_time,
    interval_end_time,
    model_name,
    ptu_credits,
    ptu_credits as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_PROVISIONED_THROUGHPUT_USAGE_HISTORY
WHERE interval_start_time >= $start_date::date
    AND interval_start_time <= $end_date::date
ORDER BY interval_start_time DESC
LIMIT 100;

-- =============================================================================
-- 6. SUMMARY INSIGHTS
-- =============================================================================
-- Purpose: High-level summary with actionable insights (CORTEX_AISQL focus)

WITH summary_stats AS (
    SELECT
        COUNT(DISTINCT DATE(usage_time)) as active_days,
        SUM(token_credits) as total_llm_credits,
        COUNT(*) as total_llm_calls,
        COUNT(DISTINCT model_name) as unique_models,
        COUNT(DISTINCT function_name) as unique_functions,
        AVG(tokens) as avg_tokens_per_call,
        MAX(token_credits) as max_single_call_cost
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
    WHERE usage_time >= $start_date::date
      AND usage_time < $end_date::date + INTERVAL '1 day'
),
cost_distribution AS (
    SELECT
        SUM(CASE WHEN token_credits < 0.01 THEN token_credits ELSE 0 END) as low_cost_calls,
        SUM(CASE WHEN token_credits >= 0.01 AND token_credits < 0.1 THEN token_credits ELSE 0 END) as medium_cost_calls,
        SUM(CASE WHEN token_credits >= 0.1 THEN token_credits ELSE 0 END) as high_cost_calls,
        COUNT(CASE WHEN token_credits < 0.01 THEN 1 END) as low_cost_count,
        COUNT(CASE WHEN token_credits >= 0.01 AND token_credits < 0.1 THEN 1 END) as medium_cost_count,
        COUNT(CASE WHEN token_credits >= 0.1 THEN 1 END) as high_cost_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
    WHERE usage_time >= $start_date::date
      AND usage_time < $end_date::date + INTERVAL '1 day'
)
SELECT
    '6. SUMMARY INSIGHTS' as analysis_type,
    ss.active_days,
    ss.total_llm_credits,
    ss.total_llm_calls,
    ss.unique_models,
    ss.unique_functions,
    ROUND(ss.avg_tokens_per_call, 0) as avg_tokens_per_call,
    ss.max_single_call_cost,
    ROUND(ss.total_llm_credits / NULLIF(ss.active_days, 0), 2) as avg_daily_cost,
    ROUND(ss.total_llm_credits / NULLIF(ss.total_llm_calls, 0), 4) as avg_cost_per_call,
    ROUND(cd.low_cost_calls, 2) as low_cost_total,
    cd.low_cost_count,
    ROUND(cd.medium_cost_calls, 2) as medium_cost_total,
    cd.medium_cost_count,
    ROUND(cd.high_cost_calls, 2) as high_cost_total,
    cd.high_cost_count,
    ROUND(100 * cd.high_cost_calls / NULLIF(ss.total_llm_credits, 0), 1) as pct_high_cost_impact
FROM summary_stats ss
CROSS JOIN cost_distribution cd;

-- =============================================================================
-- USAGE NOTES:
-- =============================================================================
-- 1. Adjust the date range variables at the top of the script (lines ~25-26)
--    For last 30 days: SET start_date = DATEADD('day', -30, CURRENT_DATE())::DATE::VARCHAR;
--                      SET end_date   = CURRENT_DATE()::VARCHAR;
-- 2. Run individual sections as needed for focused analysis
-- 3. Export results to CSV for further analysis or reporting
-- 4. Use analysis_type column to filter results by section
-- 5. Reconciliation variance thresholds: EXCELLENT ≤1%, GOOD ≤2%, WARNING ≤5%
-- 6. High-cost calls (>0.1 credits) may indicate optimization opportunities
-- 7. CORTEX_AI_FUNCTIONS_USAGE_HISTORY is intentionally excluded from all sums —
--    it is an exact duplicate of CORTEX_AISQL_USAGE_HISTORY.
-- 8. CORTEX_REST_API_USAGE_HISTORY is billed in USD, not AI_SERVICES credits.
--    It does not appear in METERING_HISTORY AI_SERVICES. Probe manually if needed.
-- =============================================================================

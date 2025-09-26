-- =============================================================================
-- CORTEX AI SERVICES COST ANALYSIS (Enhanced with Individual Function Breakdown)
-- =============================================================================
-- This script provides all insights from the Cortex Cost Analyzer Streamlit app
-- Includes: Reconciliation, Enhanced Model Analysis, Specialized Functions, 
--          Individual Service Analysis, Time Series with Function Breakdown, Raw Data
-- 
-- New Features:
-- - Individual specialized function breakdown (TRANSLATE, CLASSIFY_TEXT, etc.)
-- - Explicit model vs specialized function separation
-- - Cortex Analyst, Document AI, and Cortex Search analysis
-- - Enhanced time series with individual function lines
-- 
-- Author: Alex Ross
-- Date: 2025-09-26 (Updated to match Streamlit app v2.0)
-- =============================================================================

-- Set date range variables (adjust as needed)
SET start_date = '2024-06-28';
SET end_date = '2025-09-26';

-- =============================================================================
-- 1. AI SERVICES RECONCILIATION ANALYSIS
-- =============================================================================
-- Purpose: Reconcile AI_SERVICES baseline against sum of individual services
-- Expected: Variance should be close to 0% for accurate billing reconciliation

WITH ai_baseline AS (
    -- Get AI_SERVICES baseline from metering history
    SELECT COALESCE(SUM(credits_used), 0) as total_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
      AND service_type = 'AI_SERVICES'
),
individual_services AS (
    -- Cortex Functions Usage (LLM token-based usage)
    -- Exclude AI_EXTRACT to prevent double counting with CORTEX_DOCUMENT_PROCESSING
    SELECT 
        'CORTEX_FUNCTIONS_USAGE' as service,
        COALESCE(SUM(token_credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
      AND function_name != 'AI_EXTRACT'
    
    UNION ALL
    
    -- Cortex Analyst (REST API usage)
    SELECT 
        'CORTEX_ANALYST' as service,
        COALESCE(SUM(credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
    
    UNION ALL
    
    -- Document AI (legacy, pre-Cortex document processing)
    -- Only include if modern CORTEX_DOCUMENT_PROCESSING has no data to prevent double counting
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
    
    -- Cortex Search Serving (vector search operations)
    SELECT 
        'CORTEX_SEARCH_SERVING' as service,
        COALESCE(SUM(credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
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
    
    -- Cortex Document Processing (modern document AI)
    SELECT 
        'CORTEX_DOCUMENT_PROCESSING' as service,
        COALESCE(SUM(credits_used), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
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
        -- Individual service breakdowns
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
    '1. RECONCILIATION ANALYSIS' as analysis_type,
    ai_services_baseline,
    total_individual,
    cortex_functions,
    cortex_analyst,
    document_ai,
    cortex_search,
    cortex_fine_tuning,
    cortex_document_processing,
    ((total_individual - ai_services_baseline) / NULLIF(ai_services_baseline, 0) * 100) as variance_pct,
    (total_individual / NULLIF(ai_services_baseline, 0) * 100) as coverage_pct,
    CASE 
        WHEN ABS((total_individual - ai_services_baseline) / NULLIF(ai_services_baseline, 0) * 100) <= 1 THEN 'EXCELLENT'
        WHEN ABS((total_individual - ai_services_baseline) / NULLIF(ai_services_baseline, 0) * 100) <= 5 THEN 'GOOD'
        WHEN ABS((total_individual - ai_services_baseline) / NULLIF(ai_services_baseline, 0) * 100) <= 15 THEN 'WARNING'
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
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
WHERE START_TIME >= $start_date::date
    AND START_TIME < $end_date::date + INTERVAL '1 day'
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
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY 
        WHERE START_TIME >= $start_date::date
            AND START_TIME < $end_date::date + INTERVAL '1 day'
            AND (MODEL_NAME = '' OR MODEL_NAME IS NULL)
    ), 0), 2) as pct_of_specialized_credits,
    MIN(START_TIME) as first_usage,
    MAX(START_TIME) as last_usage
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
WHERE START_TIME >= $start_date::date
    AND START_TIME < $end_date::date + INTERVAL '1 day'
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
        WHEN FUNCTION_NAME IS NULL OR FUNCTION_NAME = '' THEN 'Other'
        ELSE 'Other'
    END
ORDER BY total_credits DESC;

-- =============================================================================
-- 3. SERVICE BREAKDOWN & UTILIZATION
-- =============================================================================
-- Purpose: Detailed breakdown of each AI service with usage metrics
-- Insights: Service adoption, cost distribution, optimization targets

WITH service_breakdown AS (
    -- Cortex Functions Usage
    SELECT 
        'CORTEX_FUNCTIONS_USAGE' as service_type,
        'Token-based LLM function calls' as description,
        'Individual function call level' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(token_credits, 0)) as total_credits,
        MIN(start_time) as first_usage,
        MAX(start_time) as last_usage,
        COUNT(DISTINCT model_name) as unique_models,
        COUNT(DISTINCT function_name) as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
    
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
    
    -- Document AI
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
    
    -- Cortex Search Serving
    SELECT 
        'CORTEX_SEARCH_SERVING' as service_type,
        'Vector search operations' as description,
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
    
    -- Cortex Document Processing
    SELECT 
        'CORTEX_DOCUMENT_PROCESSING' as service_type,
        'Modern document AI processing' as description,
        'Document processing operations' as granularity,
        COUNT(*) as record_count,
        SUM(COALESCE(credits_used, 0)) as total_credits,
        MIN(start_time) as first_usage,
        MAX(start_time) as last_usage,
        NULL as unique_models,
        NULL as unique_functions
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
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
    -- Usage intensity
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
        DATE_TRUNC('day', start_time) as period,
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
            ELSE 'Other Specialized'
        END as service_type,
        SUM(COALESCE(token_credits, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
      AND (MODEL_NAME IS NULL OR MODEL_NAME = '')  -- Only specialized functions
    GROUP BY DATE_TRUNC('day', start_time), 
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
            ELSE 'Other Specialized'
        END
    
    UNION ALL
    
    -- Explicit Model Functions (individual breakdown)
    SELECT 
        DATE_TRUNC('day', start_time) as period,
        CASE 
            WHEN FUNCTION_NAME = 'COMPLETE' THEN 'COMPLETE'
            WHEN FUNCTION_NAME = 'EMBED_TEXT_768' THEN 'EMBED_TEXT_768'
            WHEN FUNCTION_NAME = 'EMBED_TEXT_1024' THEN 'EMBED_TEXT_1024'
            WHEN FUNCTION_NAME = 'FINETUNE' THEN 'FINETUNE'
            WHEN FUNCTION_NAME = 'COUNT_TOKENS' THEN 'COUNT_TOKENS'
            ELSE 'Other Explicit'
        END as service_type,
        SUM(COALESCE(token_credits, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
      AND (MODEL_NAME IS NOT NULL AND MODEL_NAME != '')  -- Only explicit model functions
    GROUP BY DATE_TRUNC('day', start_time), 
        CASE 
            WHEN FUNCTION_NAME = 'COMPLETE' THEN 'COMPLETE'
            WHEN FUNCTION_NAME = 'EMBED_TEXT_768' THEN 'EMBED_TEXT_768'
            WHEN FUNCTION_NAME = 'EMBED_TEXT_1024' THEN 'EMBED_TEXT_1024'
            WHEN FUNCTION_NAME = 'FINETUNE' THEN 'FINETUNE'
            WHEN FUNCTION_NAME = 'COUNT_TOKENS' THEN 'COUNT_TOKENS'
            ELSE 'Other Explicit'
        END
    
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
    GROUP BY DATE_TRUNC('day', start_time)
    
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
    GROUP BY DATE_TRUNC('day', start_time)
    
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
    GROUP BY DATE_TRUNC('day', start_time)
    
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
    GROUP BY DATE_TRUNC('day', start_time)
    
    UNION ALL
    
    -- Cortex Document Processing
    SELECT 
        DATE_TRUNC('day', start_time) as period,
        'CORTEX_DOCUMENT_PROCESSING' as service_type,
        SUM(COALESCE(credits_used, 0)) as credits,
        COUNT(*) as operation_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
    GROUP BY DATE_TRUNC('day', start_time)
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
    -- Peak indicators
    CASE WHEN pa.credit_rank = 1 THEN 'PEAK_CREDIT_DAY' ELSE NULL END as peak_credit_indicator,
    CASE WHEN pa.operation_rank = 1 THEN 'PEAK_OPERATION_DAY' ELSE NULL END as peak_operation_indicator
FROM daily_time_series dts
JOIN daily_totals dt ON dts.period = dt.period
JOIN peak_analysis pa ON dts.period = pa.period
WHERE dts.credits > 0  -- Only show periods with actual usage
ORDER BY dts.period DESC, dts.credits DESC;

-- =============================================================================
-- 5. DETAILED RAW DATA EXPORT (LIMITED TO 1000 RECORDS)
-- =============================================================================
-- Purpose: Provide granular transaction-level data for deep analysis
-- Note: Limited to 1000 records for performance - adjust as needed

-- Cortex Functions Query Usage (Most detailed - query level)
SELECT 
    '5a. RAW DATA - CORTEX_FUNCTIONS_QUERY' as analysis_type,
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
    qh.execution_status,
    -- Unified credit column
    cfq.token_credits as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY cfq
LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY qh ON cfq.query_id = qh.query_id
WHERE DATE(qh.start_time) >= $start_date::date
    AND DATE(qh.start_time) <= $end_date::date
    AND qh.start_time IS NOT NULL
ORDER BY qh.start_time DESC
LIMIT 500;

-- Cortex Analyst Usage
SELECT 
    '5b. RAW DATA - CORTEX_ANALYST' as analysis_type,
    start_time,
    end_time,
    username,
    credits,
    request_count,
    -- Unified credit column
    credits as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
WHERE start_time >= $start_date::date
    AND start_time <= $end_date::date
ORDER BY start_time DESC
LIMIT 200;

-- Document AI Usage
SELECT 
    '5c. RAW DATA - DOCUMENT_AI' as analysis_type,
    start_time,
    credits_used,
    operation_name,
    page_count,
    document_count,
    feature_count,
    -- Unified credit column
    credits_used as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
WHERE start_time >= $start_date::date
    AND start_time <= $end_date::date
ORDER BY start_time DESC
LIMIT 100;

-- Cortex Search Serving Usage
SELECT 
    '5d. RAW DATA - CORTEX_SEARCH_SERVING' as analysis_type,
    start_time,
    end_time,
    database_name,
    schema_name,
    service_name,
    service_id,
    credits,
    -- Unified credit column
    credits as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
WHERE start_time >= $start_date::date
    AND start_time <= $end_date::date
ORDER BY start_time DESC
LIMIT 100;

-- Cortex Document Processing Usage
SELECT 
    '5e. RAW DATA - CORTEX_DOCUMENT_PROCESSING' as analysis_type,
    start_time,
    credits_used,
    operation_name,
    page_count,
    document_count,
    -- Unified credit column
    credits_used as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
WHERE start_time >= $start_date::date
    AND start_time <= $end_date::date
ORDER BY start_time DESC
LIMIT 100;

-- =============================================================================
-- 6. SUMMARY STATISTICS & KEY INSIGHTS
-- =============================================================================
-- Purpose: High-level summary with actionable insights

WITH summary_stats AS (
    SELECT 
        COUNT(DISTINCT DATE(start_time)) as active_days,
        SUM(token_credits) as total_llm_credits,
        COUNT(*) as total_llm_calls,
        COUNT(DISTINCT model_name) as unique_models,
        COUNT(DISTINCT function_name) as unique_functions,
        AVG(tokens) as avg_tokens_per_call,
        MAX(token_credits) as max_single_call_cost
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
),
cost_distribution AS (
    SELECT 
        SUM(CASE WHEN token_credits < 0.01 THEN token_credits ELSE 0 END) as low_cost_calls,
        SUM(CASE WHEN token_credits >= 0.01 AND token_credits < 0.1 THEN token_credits ELSE 0 END) as medium_cost_calls,
        SUM(CASE WHEN token_credits >= 0.1 THEN token_credits ELSE 0 END) as high_cost_calls,
        COUNT(CASE WHEN token_credits < 0.01 THEN 1 END) as low_cost_count,
        COUNT(CASE WHEN token_credits >= 0.01 AND token_credits < 0.1 THEN 1 END) as medium_cost_count,
        COUNT(CASE WHEN token_credits >= 0.1 THEN 1 END) as high_cost_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
    WHERE start_time >= $start_date::date
      AND start_time < $end_date::date + INTERVAL '1 day'
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
    -- Cost distribution insights
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
-- SCRIPT EXECUTION SUMMARY
-- =============================================================================
-- Purpose: Confirm successful execution and provide usage guidance

SELECT 
    'SCRIPT EXECUTION COMPLETE' as status,
    CURRENT_TIMESTAMP() as execution_time,
    $start_date as analysis_start_date,
    $end_date as analysis_end_date,
    DATEDIFF('day', $start_date::date, $end_date::date) as analysis_period_days,
    'All enhanced insights from Cortex Cost Analyzer Streamlit app v2.0 have been generated - includes individual function breakdown' as message;

-- =============================================================================
-- USAGE NOTES:
-- =============================================================================
-- 1. Adjust the date range variables at the top of the script
-- 2. Run individual sections as needed for focused analysis
-- 3. Export results to CSV for further analysis or reporting
-- 4. Use analysis_type column to filter results by section
-- 5. Reconciliation variance should be < 5% for accurate billing
-- 6. High-cost calls (>0.1 credits) may indicate optimization opportunities
-- 
-- ENHANCED FEATURES IN THIS VERSION:
-- - Section 2a: Explicit models vs specialized functions breakdown
-- - Section 2b: Individual specialized function analysis (TRANSLATE, CLASSIFY_TEXT, etc.)
-- - Section 2c: Cortex Analyst REST API analysis
-- - Section 2d: Document AI processing analysis
-- - Section 2e: Cortex Search vector operations analysis
-- - Section 4: Time series with individual function breakdown instead of aggregated services
-- 
-- ALIGNMENT WITH STREAMLIT APP:
-- - All queries match the enhanced data_layer.py methods
-- - Consistent use of CORTEX_FUNCTIONS_USAGE_HISTORY for reconciliation
-- - Same specialized function mapping and "OTHER" handling
-- - Individual function names in time series (TRANSLATE, COMPLETE, etc.)
-- =============================================================================

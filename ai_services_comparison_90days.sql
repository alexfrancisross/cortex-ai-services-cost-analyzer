-- =============================================================================
-- AI Services Consumption Comparison - Last 90 Days
-- =============================================================================
-- Purpose: Compare overall AI_SERVICES consumption with individual services
-- Period: Last 90 days from current date
-- Author: Generated for NTT Data Cortex Analysis
-- =============================================================================

-- Set session parameters for 90-day period
SET start_date = DATEADD('day', -90, CURRENT_DATE());
SET end_date = CURRENT_DATE();

-- Display analysis period
SELECT 
    '=== ANALYSIS PERIOD ===' as section,
    $start_date as start_date,
    $end_date as end_date,
    DATEDIFF('day', $start_date, $end_date) as days_analyzed;

-- =============================================================================
-- QUERY 1: Overall AI_SERVICES Total (Organization Level)
-- =============================================================================
SELECT '=== OVERALL AI_SERVICES CONSUMPTION ===' as section;

SELECT 
    'AI_SERVICES_TOTAL' as metric,
    'Organization Level' as source,
    SUM(credits_used) as total_credits,
    COUNT(DISTINCT usage_date) as days_with_usage,
    AVG(credits_used) as avg_daily_credits,
    MIN(usage_date) as first_usage_date,
    MAX(usage_date) as last_usage_date
FROM SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY
WHERE service_type = 'AI_SERVICES'
    AND account_name = CURRENT_ACCOUNT()
    AND usage_date BETWEEN $start_date AND $end_date;

-- =============================================================================
-- QUERY 2: Individual Services Breakdown
-- =============================================================================
SELECT '=== INDIVIDUAL SERVICES BREAKDOWN ===' as section;

WITH individual_services AS (
    -- Cortex Functions Usage (Direct function calls)
    SELECT 
        'CORTEX_FUNCTIONS_USAGE' as service_type,
        'Direct function invocations via APIs/SQL' as description,
        SUM(token_credits) as credits,
        COUNT(*) as usage_records,
        COUNT(DISTINCT function_name) as unique_functions,
        COUNT(DISTINCT DATE(start_time)) as active_days,
        MIN(start_time) as first_usage,
        MAX(start_time) as last_usage
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
    WHERE DATE(start_time) BETWEEN $start_date AND $end_date
    
    UNION ALL
    
    -- Cortex Functions Query (SQL-embedded function calls with date filtering via JOIN)
    SELECT 
        'CORTEX_FUNCTIONS_QUERY' as service_type,
        'SQL-embedded function calls' as description,
        SUM(cfq.token_credits) as credits,
        COUNT(*) as usage_records,
        COUNT(DISTINCT cfq.function_name) as unique_functions,
        COUNT(DISTINCT DATE(qh.start_time)) as active_days,
        MIN(qh.start_time) as first_usage,
        MAX(qh.start_time) as last_usage
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY cfq
    LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY qh ON cfq.query_id = qh.query_id
    WHERE DATE(qh.start_time) BETWEEN $start_date AND $end_date
        AND qh.start_time IS NOT NULL
    
    UNION ALL
    
    -- Cortex Analyst (Natural language SQL generation)
    SELECT 
        'CORTEX_ANALYST' as service_type,
        'Natural language SQL generation' as description,
        SUM(credits) as credits,
        COUNT(*) as usage_records,
        COUNT(DISTINCT username) as unique_users,
        COUNT(DISTINCT DATE(start_time)) as active_days,
        MIN(start_time) as first_usage,
        MAX(start_time) as last_usage
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
    WHERE DATE(start_time) BETWEEN $start_date AND $end_date
    
    UNION ALL
    
    -- Document AI (Document processing and extraction)
    SELECT 
        'DOCUMENT_AI' as service_type,
        'Document processing and extraction' as description,
        COALESCE(SUM(credits_used), 0) as credits,
        COUNT(*) as usage_records,
        0 as unique_users,  -- Assuming no user column
        COUNT(DISTINCT DATE(start_time)) as active_days,
        MIN(start_time) as first_usage,
        MAX(start_time) as last_usage
    FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
    WHERE DATE(start_time) BETWEEN $start_date AND $end_date
    
    UNION ALL
    
    -- Cortex Search Serving (Search service operations)
    SELECT 
        'CORTEX_SEARCH_SERVING' as service_type,
        'Search service operations' as description,
        COALESCE(SUM(credits), 0) as credits,
        COUNT(*) as usage_records,
        0 as unique_users,  -- Assuming no user column
        COUNT(DISTINCT DATE(start_time)) as active_days,
        MIN(start_time) as first_usage,
        MAX(start_time) as last_usage
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
    WHERE DATE(start_time) BETWEEN $start_date AND $end_date
)
SELECT 
    service_type,
    description,
    COALESCE(credits, 0) as credits,
    COALESCE(usage_records, 0) as usage_records,
    COALESCE(unique_functions, 0) as unique_functions_or_users,
    COALESCE(active_days, 0) as active_days,
    first_usage,
    last_usage
FROM individual_services
ORDER BY credits DESC;

-- =============================================================================
-- QUERY 3: Summary Comparison
-- =============================================================================
SELECT '=== SUMMARY COMPARISON ===' as section;

WITH org_total AS (
    SELECT 
        SUM(credits_used) as org_credits
    FROM SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY
    WHERE service_type = 'AI_SERVICES'
        AND account_name = CURRENT_ACCOUNT()
        AND usage_date BETWEEN $start_date AND $end_date
),
services_total AS (
    SELECT 
        SUM(COALESCE(credits, 0)) as services_credits
    FROM (
        SELECT SUM(token_credits) as credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
        WHERE DATE(start_time) BETWEEN $start_date AND $end_date
        
        UNION ALL
        
        SELECT SUM(cfq.token_credits) as credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY cfq
        LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY qh ON cfq.query_id = qh.query_id
        WHERE DATE(qh.start_time) BETWEEN $start_date AND $end_date
            AND qh.start_time IS NOT NULL
        
        UNION ALL
        
        SELECT SUM(credits) as credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
        WHERE DATE(start_time) BETWEEN $start_date AND $end_date
        
        UNION ALL
        
        SELECT COALESCE(SUM(credits_used), 0) as credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
        WHERE DATE(start_time) BETWEEN $start_date AND $end_date
        
        UNION ALL
        
        SELECT COALESCE(SUM(credits), 0) as credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
        WHERE DATE(start_time) BETWEEN $start_date AND $end_date
    )
)
SELECT 
    'COMPARISON SUMMARY' as analysis,
    o.org_credits as ai_services_total,
    s.services_credits as individual_services_total,
    o.org_credits - s.services_credits as variance,
    ROUND((o.org_credits - s.services_credits) / NULLIF(o.org_credits, 0) * 100, 2) as variance_percentage,
    CASE 
        WHEN ABS(o.org_credits - s.services_credits) / NULLIF(o.org_credits, 0) <= 0.05 THEN '✅ GOOD MATCH'
        WHEN ABS(o.org_credits - s.services_credits) / NULLIF(o.org_credits, 0) <= 0.10 THEN '⚠️ ACCEPTABLE'
        ELSE '❌ SIGNIFICANT VARIANCE'
    END as reconciliation_status
FROM org_total o, services_total s;

-- =============================================================================
-- QUERY 4: Daily Trend Analysis
-- =============================================================================
SELECT '=== DAILY TREND ANALYSIS ===' as section;

WITH daily_comparison AS (
    SELECT 
        usage_date,
        SUM(credits_used) as daily_ai_services_credits
    FROM SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY
    WHERE service_type = 'AI_SERVICES'
        AND account_name = CURRENT_ACCOUNT()
        AND usage_date BETWEEN $start_date AND $end_date
    GROUP BY usage_date
),
daily_services AS (
    SELECT 
        usage_date,
        SUM(daily_credits) as daily_services_credits
    FROM (
        SELECT DATE(start_time) as usage_date, SUM(token_credits) as daily_credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
        WHERE DATE(start_time) BETWEEN $start_date AND $end_date
        GROUP BY usage_date
        
        UNION ALL
        
        SELECT DATE(start_time) as usage_date, SUM(credits) as daily_credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
        WHERE DATE(start_time) BETWEEN $start_date AND $end_date
        GROUP BY usage_date
        
        UNION ALL
        
        SELECT DATE(start_time) as usage_date, COALESCE(SUM(credits_used), 0) as daily_credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
        WHERE DATE(start_time) BETWEEN $start_date AND $end_date
        GROUP BY usage_date
        
        UNION ALL
        
        SELECT DATE(start_time) as usage_date, COALESCE(SUM(credits), 0) as daily_credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
        WHERE DATE(start_time) BETWEEN $start_date AND $end_date
        GROUP BY usage_date
    )
    GROUP BY usage_date
)
SELECT 
    COALESCE(c.usage_date, s.usage_date) as usage_date,
    COALESCE(c.daily_ai_services_credits, 0) as ai_services_credits,
    COALESCE(s.daily_services_credits, 0) as individual_services_credits,
    COALESCE(c.daily_ai_services_credits, 0) - COALESCE(s.daily_services_credits, 0) as daily_variance,
    CASE 
        WHEN COALESCE(c.daily_ai_services_credits, 0) = 0 AND COALESCE(s.daily_services_credits, 0) = 0 THEN 'NO_USAGE'
        WHEN COALESCE(c.daily_ai_services_credits, 0) = 0 THEN 'SERVICES_ONLY'
        WHEN COALESCE(s.daily_services_credits, 0) = 0 THEN 'AI_SERVICES_ONLY'
        WHEN ABS(COALESCE(c.daily_ai_services_credits, 0) - COALESCE(s.daily_services_credits, 0)) / NULLIF(COALESCE(c.daily_ai_services_credits, 0), 0) <= 0.01 THEN 'MATCH'
        ELSE 'VARIANCE'
    END as daily_status
FROM daily_comparison c
FULL OUTER JOIN daily_services s ON c.usage_date = s.usage_date
WHERE COALESCE(c.daily_ai_services_credits, 0) > 0 OR COALESCE(s.daily_services_credits, 0) > 0
ORDER BY usage_date DESC
LIMIT 30;

-- =============================================================================
-- QUERY 5: Service Distribution Analysis
-- =============================================================================
SELECT '=== SERVICE DISTRIBUTION ANALYSIS ===' as section;

WITH service_percentages AS (
    SELECT 
        service_type,
        credits,
        SUM(credits) OVER () as total_credits,
        ROUND(credits / SUM(credits) OVER () * 100, 2) as percentage
    FROM (
        SELECT 'CORTEX_FUNCTIONS_USAGE' as service_type, 
               COALESCE(SUM(token_credits), 0) as credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
        WHERE DATE(start_time) BETWEEN $start_date AND $end_date
        
        UNION ALL
        
        SELECT 'CORTEX_FUNCTIONS_QUERY' as service_type,
               COALESCE(SUM(cfq.token_credits), 0) as credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY cfq
        LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY qh ON cfq.query_id = qh.query_id
        WHERE DATE(qh.start_time) BETWEEN $start_date AND $end_date
            AND qh.start_time IS NOT NULL
        
        UNION ALL
        
        SELECT 'CORTEX_ANALYST' as service_type,
               COALESCE(SUM(credits), 0) as credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
        WHERE DATE(start_time) BETWEEN $start_date AND $end_date
        
        UNION ALL
        
        SELECT 'DOCUMENT_AI' as service_type,
               COALESCE(SUM(credits_used), 0) as credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
        WHERE DATE(start_time) BETWEEN $start_date AND $end_date
        
        UNION ALL
        
        SELECT 'CORTEX_SEARCH_SERVING' as service_type,
               COALESCE(SUM(credits), 0) as credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
        WHERE DATE(start_time) BETWEEN $start_date AND $end_date
    ) services
)
SELECT 
    service_type,
    credits,
    percentage,
    CASE 
        WHEN percentage >= 50 THEN '🟩 PRIMARY'
        WHEN percentage >= 10 THEN '🟨 SIGNIFICANT'
        WHEN percentage >= 1 THEN '🟦 MODERATE'
        WHEN percentage > 0 THEN '🟪 MINIMAL'
        ELSE '⚫ NO_USAGE'
    END as usage_category
FROM service_percentages
ORDER BY credits DESC;

-- =============================================================================
-- Analysis Complete
-- =============================================================================
SELECT 
    'ANALYSIS COMPLETE' as status,
    'Review the comparison between AI_SERVICES total and individual services' as next_steps,
    'Pay attention to variance percentage and reconciliation status' as recommendations;

-- Test optimized time series query
-- This should consolidate multiple service queries into one

WITH all_time_series AS (
    -- Cortex Functions Usage
    SELECT 
        DATE_TRUNC('day', start_time) as period,
        'CORTEX_FUNCTIONS_USAGE' as service_type,
        SUM(COALESCE(token_credits, 0)) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
    WHERE start_time >= '2024-11-01'::date
      AND start_time < '2024-12-01'::date + INTERVAL '1 day'
    GROUP BY DATE_TRUNC('day', start_time)
    
    UNION ALL
    
    -- Cortex Analyst
    SELECT 
        DATE_TRUNC('day', start_time) as period,
        'CORTEX_ANALYST' as service_type,
        SUM(COALESCE(credits, 0)) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
    WHERE start_time >= '2024-11-01'::date
      AND start_time < '2024-12-01'::date + INTERVAL '1 day'
    GROUP BY DATE_TRUNC('day', start_time)
    
    UNION ALL
    
    -- Document AI
    SELECT 
        DATE_TRUNC('day', start_time) as period,
        'DOCUMENT_AI' as service_type,
        SUM(COALESCE(credits_used, 0)) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
    WHERE start_time >= '2024-11-01'::date
      AND start_time < '2024-12-01'::date + INTERVAL '1 day'
    GROUP BY DATE_TRUNC('day', start_time)
    
    UNION ALL
    
    -- Cortex Search Serving
    SELECT 
        DATE_TRUNC('day', start_time) as period,
        'CORTEX_SEARCH_SERVING' as service_type,
        SUM(COALESCE(credits, 0)) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
    WHERE start_time >= '2024-11-01'::date
      AND start_time < '2024-12-01'::date + INTERVAL '1 day'
    GROUP BY DATE_TRUNC('day', start_time)
    
    UNION ALL
    
    -- Cortex Fine Tuning
    SELECT 
        DATE_TRUNC('day', start_time) as period,
        'CORTEX_FINE_TUNING' as service_type,
        SUM(COALESCE(token_credits, 0)) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FINE_TUNING_USAGE_HISTORY
    WHERE start_time >= '2024-11-01'::date
      AND start_time < '2024-12-01'::date + INTERVAL '1 day'
    GROUP BY DATE_TRUNC('day', start_time)
)
SELECT 
    period,
    service_type,
    credits
FROM all_time_series
WHERE credits > 0  -- Only show periods with actual usage
ORDER BY period, service_type;

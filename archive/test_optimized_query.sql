-- Test the optimized reconciliation query
-- This should run as a single query instead of multiple sequential queries

WITH ai_baseline AS (
    SELECT COALESCE(SUM(credits_used), 0) as total_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
    WHERE start_time >= '2024-11-01'::date
      AND start_time < '2024-12-01'::date + INTERVAL '1 day'
      AND service_type = 'AI_SERVICES'
),
individual_services AS (
    SELECT 
        'CORTEX_FUNCTIONS_USAGE' as service,
        COALESCE(SUM(token_credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
    WHERE start_time >= '2024-11-01'::date
      AND start_time < '2024-12-01'::date + INTERVAL '1 day'
    
    UNION ALL
    
    SELECT 
        'CORTEX_ANALYST' as service,
        COALESCE(SUM(credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
    WHERE start_time >= '2024-11-01'::date
      AND start_time < '2024-12-01'::date + INTERVAL '1 day'
    
    UNION ALL
    
    SELECT 
        'DOCUMENT_AI' as service,
        COALESCE(SUM(credits_used), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
    WHERE start_time >= '2024-11-01'::date
      AND start_time < '2024-12-01'::date + INTERVAL '1 day'
    
    UNION ALL
    
    SELECT 
        'CORTEX_SEARCH_SERVING' as service,
        COALESCE(SUM(credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
    WHERE start_time >= '2024-11-01'::date
      AND start_time < '2024-12-01'::date + INTERVAL '1 day'
    
    UNION ALL
    
    SELECT 
        'CORTEX_FINE_TUNING' as service,
        COALESCE(SUM(token_credits), 0) as credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FINE_TUNING_USAGE_HISTORY
    WHERE start_time >= '2024-11-01'::date
      AND start_time < '2024-12-01'::date + INTERVAL '1 day'
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
        -- Use OBJECT_CONSTRUCT instead of OBJECT_AGG for better compatibility
        OBJECT_CONSTRUCT(
            'CORTEX_FUNCTIONS_USAGE', MAX(CASE WHEN st.service = 'CORTEX_FUNCTIONS_USAGE' THEN st.credits END),
            'CORTEX_ANALYST', MAX(CASE WHEN st.service = 'CORTEX_ANALYST' THEN st.credits END),
            'DOCUMENT_AI', MAX(CASE WHEN st.service = 'DOCUMENT_AI' THEN st.credits END),
            'CORTEX_SEARCH_SERVING', MAX(CASE WHEN st.service = 'CORTEX_SEARCH_SERVING' THEN st.credits END),
            'CORTEX_FINE_TUNING', MAX(CASE WHEN st.service = 'CORTEX_FINE_TUNING' THEN st.credits END)
        ) as service_breakdown
    FROM ai_baseline b
    CROSS JOIN service_totals st
    GROUP BY b.total_credits, st.total_individual
)
SELECT 
    ai_services_baseline,
    total_individual,
    service_breakdown,
    ((total_individual - ai_services_baseline) / NULLIF(ai_services_baseline, 0) * 100) as variance_pct,
    (total_individual / NULLIF(ai_services_baseline, 0) * 100) as coverage_pct
FROM summary;

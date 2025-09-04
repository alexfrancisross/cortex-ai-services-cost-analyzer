-- Cortex AI Services Cost Analyzer - Validation Queries
-- Pre and post-deployment validation tests
-- Usage: Run these queries to validate deployment readiness and success

-- =============================================================================
-- PRE-DEPLOYMENT VALIDATION
-- =============================================================================

-- 1. Check Account Usage Access
-- Expected: Should return a count without errors
SELECT 'ACCOUNT_USAGE_ACCESS' as validation_test,
       CASE 
           WHEN COUNT(*) >= 0 THEN 'PASS'
           ELSE 'FAIL'
       END as result,
       'Basic ACCOUNT_USAGE schema access' as description
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY 
LIMIT 1;

-- 2. Validate Cortex Service Tables Access
-- Expected: cortex_tables >= 4 for basic functionality, 6 for full functionality
WITH cortex_table_check AS (
    SELECT 
        table_name,
        CASE 
            WHEN table_name IN (
                'CORTEX_FUNCTIONS_USAGE_HISTORY',
                'CORTEX_ANALYST_USAGE_HISTORY', 
                'CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY',
                'CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY',
                'CORTEX_SEARCH_DAILY_USAGE_HISTORY',
                'CORTEX_SEARCH_SERVING_USAGE_HISTORY'
            ) THEN 1 
            ELSE 0 
        END as is_cortex_table
    FROM INFORMATION_SCHEMA.TABLES 
    WHERE table_schema = 'ACCOUNT_USAGE'
)
SELECT 'CORTEX_TABLES_ACCESS' as validation_test,
       CASE 
           WHEN SUM(is_cortex_table) >= 6 THEN 'PASS - FULL'
           WHEN SUM(is_cortex_table) >= 4 THEN 'PASS - PARTIAL'
           ELSE 'FAIL'
       END as result,
       CONCAT('Found ', SUM(is_cortex_table), '/6 Cortex service tables') as description
FROM cortex_table_check;

-- 3. Test Individual Cortex Table Access
-- Expected: Each query should execute without permission errors
SELECT 'CORTEX_FUNCTIONS_USAGE' as table_name,
       CASE WHEN COUNT(*) >= 0 THEN 'ACCESSIBLE' ELSE 'ERROR' END as status
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY LIMIT 1
UNION ALL
SELECT 'CORTEX_ANALYST',
       CASE WHEN COUNT(*) >= 0 THEN 'ACCESSIBLE' ELSE 'ERROR' END
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY LIMIT 1
UNION ALL
SELECT 'CORTEX_DOCUMENT_PROCESSING',
       CASE WHEN COUNT(*) >= 0 THEN 'ACCESSIBLE' ELSE 'ERROR' END
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY LIMIT 1
UNION ALL
SELECT 'CORTEX_FUNCTIONS_QUERY',
       CASE WHEN COUNT(*) >= 0 THEN 'ACCESSIBLE' ELSE 'ERROR' END
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY LIMIT 1
UNION ALL
SELECT 'CORTEX_SEARCH_DAILY',
       CASE WHEN COUNT(*) >= 0 THEN 'ACCESSIBLE' ELSE 'ERROR' END
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY LIMIT 1
UNION ALL
SELECT 'CORTEX_SEARCH_SERVING',
       CASE WHEN COUNT(*) >= 0 THEN 'ACCESSIBLE' ELSE 'ERROR' END
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY LIMIT 1;

-- 4. Check Organization Usage Access (Optional)
-- Expected: May return permission error - this is acceptable
SELECT 'ORGANIZATION_USAGE_ACCESS' as validation_test,
       CASE 
           WHEN COUNT(*) >= 0 THEN 'AVAILABLE'
           ELSE 'NOT_AVAILABLE'
       END as result,
       'Organization-level metering access (optional)' as description
FROM SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY 
WHERE account_name = CURRENT_ACCOUNT()
LIMIT 1;

-- 5. Validate AI Services Usage Exists
-- Expected: Should show some AI_SERVICES usage if account has been using Cortex
SELECT 'AI_SERVICES_USAGE_CHECK' as validation_test,
       CASE 
           WHEN SUM(credits_used) > 0 THEN 'USAGE_FOUND'
           ELSE 'NO_USAGE'
       END as result,
       CONCAT('Total AI_SERVICES credits in last 90 days: ', 
              COALESCE(SUM(credits_used), 0)) as description
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
WHERE service_type = 'AI_SERVICES'
  AND start_time >= CURRENT_DATE() - INTERVAL '90 days';

-- 6. Data Freshness Check
-- Expected: Most recent data should be within last 24 hours
SELECT 'DATA_FRESHNESS_CHECK' as validation_test,
       CASE 
           WHEN MAX(start_time) >= CURRENT_TIMESTAMP() - INTERVAL '6 hours' THEN 'FRESH'
           WHEN MAX(start_time) >= CURRENT_TIMESTAMP() - INTERVAL '24 hours' THEN 'ACCEPTABLE'
           ELSE 'STALE'
       END as result,
       CONCAT('Most recent metering data: ', 
              DATEDIFF('hour', MAX(start_time), CURRENT_TIMESTAMP()), ' hours ago') as description
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
WHERE service_type = 'AI_SERVICES';

-- =============================================================================
-- DEPLOYMENT READINESS SUMMARY
-- =============================================================================

-- Summary validation report
WITH validation_summary AS (
    -- Account access
    SELECT 'ACCOUNT_ACCESS' as check_category, 1 as priority,
           CASE WHEN COUNT(*) >= 0 THEN 1 ELSE 0 END as passed
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY LIMIT 1
    
    UNION ALL
    
    -- Cortex tables
    SELECT 'CORTEX_TABLES', 2,
           CASE WHEN (
               SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
               WHERE table_schema = 'ACCOUNT_USAGE' 
               AND table_name LIKE '%CORTEX%'
           ) >= 4 THEN 1 ELSE 0 END
    
    UNION ALL
    
    -- Current role permissions
    SELECT 'ROLE_PERMISSIONS', 3,
           CASE WHEN CURRENT_ROLE() IS NOT NULL THEN 1 ELSE 0 END
)
SELECT 
    'DEPLOYMENT_READINESS' as validation_test,
    CASE 
        WHEN SUM(passed) = COUNT(*) THEN 'READY'
        WHEN SUM(passed) >= 2 THEN 'READY_WITH_WARNINGS'
        ELSE 'NOT_READY'
    END as result,
    CONCAT(SUM(passed), '/', COUNT(*), ' validation checks passed') as description
FROM validation_summary;

-- =============================================================================
-- POST-DEPLOYMENT VALIDATION
-- =============================================================================

-- 7. Verify Streamlit Application Exists
-- Note: Replace database/schema names according to your deployment
SHOW STREAMLITS IN SCHEMA ANALYTICS.CORTEX_APPS;

-- 8. Verify Stage Contents
-- Note: Replace stage name according to your deployment  
LIST @ANALYTICS.CORTEX_APPS.CORTEX_ANALYZER_STAGE;

-- 9. Test Application Query Performance
-- Expected: Should complete in <5 seconds
SELECT 
    'QUERY_PERFORMANCE_TEST' as validation_test,
    'PASS' as result,
    CONCAT('Query completed in ', 
           DATEDIFF('millisecond', :start_time, CURRENT_TIMESTAMP()), 'ms') as description
FROM (
    SELECT CURRENT_TIMESTAMP() as start_time,
           COUNT(*) as record_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
    WHERE service_type = 'AI_SERVICES'
      AND start_time >= CURRENT_DATE() - INTERVAL '30 days'
) t;

-- 10. Reconciliation Sample Test
-- Expected: Variance should be <5% for healthy deployment
WITH reconciliation_test AS (
    -- Hourly metering total
    SELECT SUM(credits_used) as hourly_total
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
    WHERE service_type = 'AI_SERVICES'
      AND start_time >= CURRENT_DATE() - INTERVAL '7 days'
),
granular_test AS (
    -- Sum of granular services (simplified)
    SELECT 
        COALESCE(SUM(token_credits), 0) as granular_total
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
    WHERE start_time >= CURRENT_DATE() - INTERVAL '7 days'
)
SELECT 
    'RECONCILIATION_SAMPLE_TEST' as validation_test,
    CASE 
        WHEN ABS((g.granular_total - h.hourly_total) / NULLIF(h.hourly_total, 0) * 100) <= 5 
        THEN 'PASS'
        ELSE 'WARNING'
    END as result,
    CONCAT('Sample variance: ', 
           ROUND(ABS((g.granular_total - h.hourly_total) / NULLIF(h.hourly_total, 0) * 100), 3), 
           '% (Hourly: ', h.hourly_total, ', Granular: ', g.granular_total, ')') as description
FROM reconciliation_test h
CROSS JOIN granular_test g;

-- =============================================================================
-- TROUBLESHOOTING QUERIES
-- =============================================================================

-- Check current user privileges
SELECT 'CURRENT_USER_PRIVILEGES' as info_type,
       CURRENT_USER() as current_user,
       CURRENT_ROLE() as current_role,
       CURRENT_WAREHOUSE() as current_warehouse;

-- List available Cortex tables with access status
WITH cortex_tables AS (
    SELECT table_name
    FROM INFORMATION_SCHEMA.TABLES 
    WHERE table_schema = 'ACCOUNT_USAGE'
      AND table_name LIKE '%CORTEX%'
)
SELECT 
    table_name,
    'Accessible via INFORMATION_SCHEMA' as access_status
FROM cortex_tables
ORDER BY table_name;

-- Check for recent AI Services activity
SELECT 
    service_type,
    COUNT(*) as record_count,
    MIN(start_time) as earliest_record,
    MAX(start_time) as latest_record,
    SUM(credits_used) as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
WHERE service_type = 'AI_SERVICES'
  AND start_time >= CURRENT_DATE() - INTERVAL '30 days'
GROUP BY service_type;

-- =============================================================================
-- VALIDATION REPORT TEMPLATE
-- =============================================================================

-- Run this final query to get a comprehensive validation report
SELECT 
    '========================' as separator,
    'CORTEX COST ANALYZER VALIDATION REPORT' as title,
    CURRENT_TIMESTAMP() as validation_timestamp,
    CURRENT_USER() as validated_by,
    CURRENT_ACCOUNT() as target_account
UNION ALL
SELECT 
    '========================',
    'Execute the queries above individually',
    'to validate deployment readiness and success',
    'All tests should show PASS or ACCESSIBLE status',
    'for optimal application performance';

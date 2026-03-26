-- scripts/probe_views.sql
-- Run against each connection to test view existence + current reconciliation gap.
-- Views using start_time:
SELECT 'CORTEX_AI_FUNCTIONS_USAGE_HISTORY' AS view_name, COUNT(*) AS row_count, MAX(start_time) AS latest_row
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP());

-- CORTEX_AISQL uses usage_time (not start_time):
SELECT 'CORTEX_AISQL_USAGE_HISTORY' AS view_name, COUNT(*) AS row_count, MAX(usage_time) AS latest_row
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
WHERE usage_time >= DATEADD('day', -30, CURRENT_TIMESTAMP());

SELECT 'CORTEX_ANALYST_USAGE_HISTORY' AS view_name, COUNT(*) AS row_count, MAX(start_time) AS latest_row
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP());

SELECT 'CORTEX_SEARCH_SERVING_USAGE_HISTORY' AS view_name, COUNT(*) AS row_count, MAX(start_time) AS latest_row
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP());

SELECT 'CORTEX_FINE_TUNING_USAGE_HISTORY' AS view_name, COUNT(*) AS row_count, MAX(start_time) AS latest_row
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FINE_TUNING_USAGE_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP());

SELECT 'DOCUMENT_AI_USAGE_HISTORY' AS view_name, COUNT(*) AS row_count, MAX(start_time) AS latest_row
FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP());

SELECT 'CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY' AS view_name, COUNT(*) AS row_count, MAX(start_time) AS latest_row
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP());

SELECT 'CORTEX_AGENT_USAGE_HISTORY' AS view_name, COUNT(*) AS row_count, MAX(start_time) AS latest_row
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP());

SELECT 'SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY' AS view_name, COUNT(*) AS row_count, MAX(start_time) AS latest_row
FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP());

-- CORTEX_CODE_CLI uses usage_time (not start_time):
SELECT 'CORTEX_CODE_CLI_USAGE_HISTORY' AS view_name, COUNT(*) AS row_count, MAX(usage_time) AS latest_row
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY
WHERE usage_time >= DATEADD('day', -30, CURRENT_TIMESTAMP());

-- CORTEX_SEARCH_DAILY uses usage_date (DATE), not start_time:
SELECT 'CORTEX_SEARCH_DAILY_USAGE_HISTORY' AS view_name, COUNT(*) AS row_count, MAX(usage_date) AS latest_row
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
WHERE usage_date >= DATEADD('day', -30, CURRENT_DATE());

-- Reconciliation delta: METERING_HISTORY vs all granular views (pre-fix baseline)
SELECT
    mh.total_metering                                                        AS tier2_credits,
    gs.total_granular                                                        AS tier3_credits,
    (gs.total_granular - mh.total_metering)
        / NULLIF(mh.total_metering, 0) * 100                                AS variance_pct
FROM (
    SELECT COALESCE(SUM(credits_used), 0) AS total_metering
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
    WHERE service_type = 'AI_SERVICES'
      AND start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
) mh,
(
    SELECT
        COALESCE((SELECT SUM(credits)       FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())), 0)
      + COALESCE((SELECT SUM(token_credits) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY           WHERE usage_time  >= DATEADD('day', -30, CURRENT_TIMESTAMP())), 0)
      + COALESCE((SELECT SUM(credits)       FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY         WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())), 0)
      + COALESCE((SELECT SUM(credits)       FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY  WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())), 0)
      + COALESCE((SELECT SUM(token_credits) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FINE_TUNING_USAGE_HISTORY     WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())), 0)
      + COALESCE((SELECT SUM(credits)       FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY    WHERE usage_date  >= DATEADD('day', -30, CURRENT_DATE())),      0)
      + COALESCE((SELECT SUM(credits_used)  FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY            WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())), 0)
      + COALESCE((SELECT SUM(token_credits) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY           WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())), 0)
      + COALESCE((SELECT SUM(token_credits) FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())), 0)
    AS total_granular
) gs;

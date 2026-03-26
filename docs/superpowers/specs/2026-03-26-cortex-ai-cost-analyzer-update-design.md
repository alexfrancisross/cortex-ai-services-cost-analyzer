# Cortex AI Services Cost Analyzer — View Reconciliation Update

**Date:** 2026-03-26
**Status:** Approved for implementation

## Problem

`METERING_HISTORY` `AI_SERVICES` total no longer reconciles against the cumulative sum of all granular Cortex service views. Root cause: two views went GA on Feb 25, 2026 (`CORTEX_AGENT_USAGE_HISTORY`, `SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY`) whose credits flow into `AI_SERVICES` but have no corresponding tab or data layer entry in the app. Additionally, several views are deprecated or broken and still referenced.

Secondary issue: `streamlit_app.py` (~1000 lines, all queries inline) and `common/analytics/data_layer.py` have drifted into two parallel implementations with different view lists and no shared caching.

## Goal

1. Close the reconciliation gap by adding the two missing views.
2. Remove deprecated/broken view references.
3. Consolidate: `streamlit_app.py` drives entirely through `data_layer.py`; no inline SQL remains in the UI file.
4. Validate every view query against 5 Snowflake CLI connections before shipping.

## Architecture

### Before

```
streamlit_app.py   (standalone, ~1000 lines, all queries inline)
common/analytics/data_layer.py   (separate, references deprecated views)
common/analytics/reconciliation.py
```

### After

```
streamlit_app.py  →  UI only (fetch calls, charts, layout, ~400 lines)
                          ↓
common/analytics/data_layer.py  →  all SQL, session management, caching
                          ↓
common/analytics/reconciliation.py  →  tier-based variance math
```

`data_layer.py` is the single source of truth for view names, column mappings, and `@st.cache_data` TTLs. Caching currently defined inline in `streamlit_app.py` moves into `data_layer.py` methods so it is consistent regardless of caller.

## Phase 0: CLI Validation (before any code changes)

Run a probe script via `snow sql` across all 5 configured connections:
- `default` (sfseeurope-demo_aross, ACCOUNTADMIN)
- `aws_us` (sfseeurope-demo_aross_aws_us_west, ACCOUNTADMIN)
- `snowhouse` (SFCOGSOPS-SNOWHOUSE, SALES_ENGINEER)
- `travelodge` (JFGLBPJ-OP64174, ACCOUNTADMIN)
- `azure` (SFSEEUROPE-DEMO_AROSS_AZURE, ACCOUNTADMIN)

Probe queries per view:

```sql
-- View existence + recent data check
SELECT COUNT(*), MAX(start_time)
FROM SNOWFLAKE.ACCOUNT_USAGE.<VIEW_NAME>
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP());

-- Reconciliation delta check (run after adding Agent + SI)
SELECT
    mh.total_metering   AS tier2_credits,
    gs.total_granular   AS tier3_credits,
    (gs.total_granular - mh.total_metering) / NULLIF(mh.total_metering, 0) * 100 AS variance_pct
FROM (
    SELECT SUM(credits_used) AS total_metering
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
    WHERE service_type = 'AI_SERVICES'
      AND start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
) mh,
(
    SELECT SUM(credits) AS total_granular FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    SELECT SUM(token_credits) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    SELECT SUM(credits) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    SELECT SUM(credits) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    SELECT SUM(token_credits) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FINE_TUNING_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    SELECT SUM(credits) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
    WHERE usage_date >= DATEADD('day', -30, CURRENT_DATE())
    UNION ALL
    SELECT SUM(credits_used) FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    SELECT SUM(token_credits) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    SELECT SUM(token_credits) FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
) gs;
```

Probe results determine each view's `status` in the registry:
- Returns rows → `PRIMARY`
- Query succeeds but 0 rows → `PRIMARY` (view exists, just no usage)
- Query errors (view not found / no permission) → `FALLBACK` or `UNAVAILABLE`

## Phase 1: `data_layer.py` View Registry Update

### Remove

| View | Reason |
|------|--------|
| `CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY` | Deprecated Jan 2026, no new data |
| `CORTEX_FUNCTIONS_USAGE_HISTORY` | Deprecated in favour of `CORTEX_AISQL_USAGE_HISTORY` |

### Demote to graceful-fallback

| View | Reason |
|------|--------|
| `CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY` | Broken post-Nov 2025 billing event changes (confirmed internal Slack). Query it but display a warning banner; exclude from reconciliation sum until fixed. |

### Keep (confirmed active)

| View | Credit column | Notes |
|------|--------------|-------|
| `CORTEX_AI_FUNCTIONS_USAGE_HISTORY` | `CREDITS` | Preferred for AI Functions since Nov 2025 GA |
| `CORTEX_AISQL_USAGE_HISTORY` | `TOKEN_CREDITS` | Replaces FUNCTIONS + FUNCTIONS_QUERY views |
| `CORTEX_ANALYST_USAGE_HISTORY` | `CREDITS` | |
| `CORTEX_SEARCH_SERVING_USAGE_HISTORY` | `CREDITS` | |
| `CORTEX_FINE_TUNING_USAGE_HISTORY` | `TOKEN_CREDITS` | |
| `CORTEX_REST_API_USAGE_HISTORY` | none | Tokens only; billed in $ not credits since Nov 2025 |
| `CORTEX_SEARCH_DAILY_USAGE_HISTORY` | `credits` | Date column is `usage_date` not `start_time` |
| `DOCUMENT_AI_USAGE_HISTORY` | `CREDITS_USED` | |

### Add (reconciliation gap — GA Feb 25, 2026)

| View | Credit column | Grouping |
|------|--------------|---------|
| `CORTEX_AGENT_USAGE_HISTORY` | `TOKEN_CREDITS` | `AGENT_NAME` |
| `SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY` | `TOKEN_CREDITS` | `SNOWFLAKE_INTELLIGENCE_NAME` |

The `service_configs` dict gains a `status` field (`PRIMARY` / `FALLBACK` / `UNAVAILABLE`) set during a `probe_views()` call at startup. The reconciliation engine only sums views with `status == PRIMARY`.

## Phase 2: `reconciliation.py` Update

- Replace hardcoded `accessible_services >= 6` with `accessible_services >= len(primary_views)` where `primary_views` is the live list from `data_layer.py`.
- The 3-tier reconciliation targets remain the same:
  - Tier 1: `ORGANIZATION_USAGE.METERING_DAILY_HISTORY` (when accessible)
  - Tier 2: `ACCOUNT_USAGE.METERING_HISTORY` `AI_SERVICES` (account hourly baseline)
  - Tier 3: Sum of all `PRIMARY` granular views
- Variance thresholds unchanged (≤1% excellent, 1–2% good, 2–5% warning, >5% critical).
- `_generate_reconciliation_insights()` updated to name the specific views contributing to any remaining gap.

## Phase 3: `streamlit_app.py` Refactor

All inline `fetch_*` functions and `run_query()` are removed. The file imports `SnowflakeDataLoader` from `common.analytics.data_layer` and calls its public methods.

### AI & Cortex expander — tab changes

| Tab | View | Status |
|-----|------|--------|
| AI Functions | `CORTEX_AI_FUNCTIONS_USAGE_HISTORY` | Existing (updated) |
| Cortex Code | `CORTEX_CODE_CLI_USAGE_HISTORY` | Existing |
| REST API | `CORTEX_REST_API_USAGE_HISTORY` | Existing (tokens-only label) |
| AI SQL | `CORTEX_AISQL_USAGE_HISTORY` | Existing (updated) |
| Doc Processing | `CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY` | Existing (warning banner) |
| Cortex Analyst | `CORTEX_ANALYST_USAGE_HISTORY` | Existing |
| Cortex Search | `CORTEX_SEARCH_DAILY_USAGE_HISTORY` | Existing |
| Search Serving | `CORTEX_SEARCH_SERVING_USAGE_HISTORY` | Existing |
| **Cortex Agents** | `CORTEX_AGENT_USAGE_HISTORY` | **New** |
| **Snowflake Intelligence** | `SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY` | **New** |

### Reconciliation panel

A new top-level expander "AI Services Reconciliation" shows the 3-tier variance check using `ReconciliationEngine`. When Tier 2 vs. Tier 3 gap is ≤1% the panel shows green; >5% shows red with a per-service breakdown of unaccounted credits.

## Out of Scope

- `CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY` — not yet fully rolled out (as of 2026-03-26); Snowsight CoCo usage is currently in `CORTEX_AGENT_USAGE_HISTORY` where `AGENT_NAME IS NULL`. Will add once view is stable everywhere.
- `CORTEX_PROVISIONED_THROUGHPUT_USAGE_HISTORY` — exists in docs sidebar but usage is uncommon; add in a follow-up if probe shows data.
- UI styling, theming, or chart redesign.
- Changes to non-AI sections (warehouses, storage, SPCS, etc.).

## Files Changed

| File | Change |
|------|--------|
| `common/analytics/data_layer.py` | Update `service_configs`, add `probe_views()`, add methods for Agent + SI |
| `common/analytics/reconciliation.py` | Dynamic service count, updated insights |
| `streamlit_app.py` | Remove all inline SQL, drive through `data_layer.py`, add 2 new tabs, add reconciliation panel |
| `sql/cortex_credit_consumption_analysis.sql` | Update to reflect current view names |

## Validation Criteria

- `variance_pct` from the CLI reconciliation delta query is ≤5% on `default` and `aws_us` connections.
- All 5 connections return without error for every `PRIMARY` view.
- The reconciliation panel in the app shows `EXCELLENT` or `GOOD` status for the test period.

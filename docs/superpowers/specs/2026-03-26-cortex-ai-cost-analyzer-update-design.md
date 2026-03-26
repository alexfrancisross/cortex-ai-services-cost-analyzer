# Cortex AI Services Cost Analyzer — View Reconciliation Update

**Date:** 2026-03-26
**Status:** Approved for implementation

## Problem

`METERING_HISTORY` `AI_SERVICES` total no longer reconciles against the cumulative sum of all granular Cortex service views. Root cause: two views went GA on Feb 25, 2026 (`CORTEX_AGENT_USAGE_HISTORY`, `SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY`) whose credits flow into `AI_SERVICES` but have no corresponding tab or entry in `data_layer.py`'s service registry.

Secondary issue: `common/analytics/data_layer.py`'s `service_configs` dict references deprecated views (`CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY`) and is missing several current views (`CORTEX_AI_FUNCTIONS_USAGE_HISTORY`, `CORTEX_AISQL_USAGE_HISTORY`). The UI and data layer have drifted — the data layer's view list is stale even though `streamlit_app.py` already calls into it for rendering.

## Goal

1. Close the reconciliation gap by adding the two missing views to the service registry.
2. Audit and update `data_layer.py`'s `service_configs` — remove deprecated views, add active ones.
3. Update `reconciliation.py` to dynamically count services rather than hardcoding 6.
4. Validate every view query against 5 Snowflake CLI connections before shipping.

## Architecture

No structural change to the file layout. `streamlit_app.py` already drives through `data_layer.py`. The work is entirely in the data and reconciliation layers:

```
streamlit_app.py  →  UI only (no change to structure)
                          ↓
common/analytics/data_layer.py  →  service_configs audit + probe_views() + new service methods
                          ↓
common/analytics/reconciliation.py  →  dynamic service count, updated insights
```

`data_layer.py`'s `service_configs` becomes the single source of truth for which views are active. `reconciliation.py` reads this list dynamically rather than hardcoding a count of 6.

## Phase 0: CLI Validation (before any code changes)

Run a probe script via `snow sql` across all 5 configured connections:
- `default` (sfseeurope-demo_aross, ACCOUNTADMIN)
- `aws_us` (sfseeurope-demo_aross_aws_us_west, ACCOUNTADMIN)
- `snowhouse` (SFCOGSOPS-SNOWHOUSE, SALES_ENGINEER — may lack ACCOUNT_USAGE grants)
- `travelodge` (JFGLBPJ-OP64174, ACCOUNTADMIN)
- `azure` (SFSEEUROPE-DEMO_AROSS_AZURE, ACCOUNTADMIN)

**View existence probe** — run for each view in the registry. Note: `CORTEX_SEARCH_DAILY_USAGE_HISTORY` uses `usage_date` (DATE), not `start_time`, so its probe uses a different filter:

```sql
-- Standard probe (all views except CORTEX_SEARCH_DAILY_USAGE_HISTORY)
SELECT COUNT(*), MAX(start_time)
FROM SNOWFLAKE.ACCOUNT_USAGE.<VIEW_NAME>
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP());

-- CORTEX_SEARCH_DAILY_USAGE_HISTORY probe (date column is usage_date, not start_time)
SELECT COUNT(*), MAX(usage_date)
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
WHERE usage_date >= DATEADD('day', -30, CURRENT_DATE());
```

**Reconciliation delta check** — run after confirming probe results. `CORTEX_REST_API_USAGE_HISTORY` is intentionally excluded: REST API has been billed in USD (not credits) since Nov 2025, so it does not contribute to the `AI_SERVICES` credit total in `METERING_HISTORY`.

```sql
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
    -- AI Functions (new preferred view, CREDITS column)
    SELECT COALESCE(SUM(credits), 0) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    -- AI SQL (replaces CORTEX_FUNCTIONS_USAGE_HISTORY, TOKEN_CREDITS column)
    SELECT COALESCE(SUM(token_credits), 0) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AISQL_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    SELECT COALESCE(SUM(credits), 0) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    SELECT COALESCE(SUM(credits), 0) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    SELECT COALESCE(SUM(token_credits), 0) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FINE_TUNING_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    -- Search Daily uses usage_date (DATE), not start_time
    SELECT COALESCE(SUM(credits), 0) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
    WHERE usage_date >= DATEADD('day', -30, CURRENT_DATE())
    UNION ALL
    SELECT COALESCE(SUM(credits_used), 0) FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    -- NEW: Cortex Agents (TOKEN_CREDITS column)
    SELECT COALESCE(SUM(token_credits), 0) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    -- NEW: Snowflake Intelligence (TOKEN_CREDITS column)
    SELECT COALESCE(SUM(token_credits), 0) FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
) gs (total_granular);
```

Probe results determine each view's `status` in the registry:
- Query succeeds (rows or 0 rows) → `PRIMARY`
- Query errors (view not found / permission denied) → `FALLBACK` or `UNAVAILABLE`

`snowhouse` uses SALES_ENGINEER role and may not have `ACCOUNT_USAGE` grants; permission-denied errors on that connection downgrade a view to `FALLBACK` for that account only, not globally.

## Phase 1: `data_layer.py` View Registry Update

The `service_configs` dict before this change has 6 entries. After this change it has 9.

### Remove from `service_configs`

| Key | View | Reason |
|-----|------|--------|
| `CORTEX_FUNCTIONS_QUERY` | `CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY` | Deprecated Jan 2026, no new data |

### Demote to graceful-fallback in `service_configs`

| Key | View | Reason |
|-----|------|--------|
| `CORTEX_DOCUMENT_PROCESSING` | `CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY` | Broken post-Nov 2025 billing event type changes (internal Slack confirmed). Query it but display a warning banner; exclude from reconciliation sum until fixed. |

### Add to `service_configs` (views active but currently absent from the registry)

| Key | View | Credit column | Notes |
|-----|------|--------------|-------|
| `CORTEX_AI_FUNCTIONS` | `CORTEX_AI_FUNCTIONS_USAGE_HISTORY` | `CREDITS` | Preferred for AI Functions since Nov 2025 GA. Replaces `CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY` as the primary functions view. |
| `CORTEX_AISQL` | `CORTEX_AISQL_USAGE_HISTORY` | `TOKEN_CREDITS` | Replaces `CORTEX_FUNCTIONS_USAGE_HISTORY` and `CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY` |
| `CORTEX_AGENT` | `CORTEX_AGENT_USAGE_HISTORY` | `TOKEN_CREDITS` | GA Feb 25 2026. Group by `AGENT_NAME`. **Closes reconciliation gap.** |
| `SNOWFLAKE_INTELLIGENCE` | `SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY` | `TOKEN_CREDITS` | GA Feb 25 2026. Group by `SNOWFLAKE_INTELLIGENCE_NAME`. **Closes reconciliation gap.** |

### Keep in `service_configs` (no change to key or credit column)

| Key | View | Credit column | Notes |
|-----|------|--------------|-------|
| `CORTEX_ANALYST` | `CORTEX_ANALYST_USAGE_HISTORY` | `CREDITS` | |
| `CORTEX_SEARCH_SERVING` | `CORTEX_SEARCH_SERVING_USAGE_HISTORY` | `CREDITS` | |
| `CORTEX_FINE_TUNING` | `CORTEX_FINE_TUNING_USAGE_HISTORY` | `TOKEN_CREDITS` | |

### Not in `service_configs` (intentional — special handling)

| View | Reason |
|------|--------|
| `CORTEX_REST_API_USAGE_HISTORY` | Billed in USD (not credits) since Nov 2025. Tokens/requests shown in UI tab; excluded from credit reconciliation sum. |
| `CORTEX_SEARCH_DAILY_USAGE_HISTORY` | `credits` column, `usage_date` date column — handled separately due to different time column. |
| `DOCUMENT_AI_USAGE_HISTORY` | `CREDITS_USED` column — handled separately. |

### `probe_views()` function

Add a `probe_views()` method to `SnowflakeDataLoader`:
- Called once at app startup via `@st.cache_resource` (not `@st.cache_data`) so it is shared across sessions for the app's lifetime.
- Iterates over every entry in `service_configs` and runs the existence probe query.
- Sets `service_configs[key]['status']` to `PRIMARY`, `FALLBACK`, or `UNAVAILABLE` based on probe result.
- Returns the updated dict.
- The reconciliation engine reads `status` from this dict; only `PRIMARY` views are summed in Tier 3.

## Phase 2: `reconciliation.py` Update

Four hardcoded service-count references must be replaced dynamically:

| Location | Current | Replacement |
|----------|---------|-------------|
| `_determine_overall_health` line ~287 | `accessible_services >= 6` | `accessible_services >= len(primary_views)` |
| `_determine_overall_health` line ~289 | `accessible_services >= 4` | `accessible_services >= len(primary_views) * 0.67` (rounded) |
| `_generate_reconciliation_insights` line ~356 | `f"{accessible_services}/6"` | `f"{accessible_services}/{len(primary_views)}"` |
| `_generate_reconciliation_insights` line ~358 | `accessible_services == 6` | `accessible_services == len(primary_views)` |

Where `primary_views` is derived from `data_layer.service_configs` at call time:
```python
primary_views = [k for k, v in self.data_loader.service_configs.items()
                 if v.get('status') == 'PRIMARY']
```

Reconciliation tiers remain unchanged:
- Tier 1: `ORGANIZATION_USAGE.METERING_DAILY_HISTORY` `AI_SERVICES` (when accessible)
- Tier 2: `ACCOUNT_USAGE.METERING_HISTORY` `AI_SERVICES` (account hourly baseline)
- Tier 3: Sum of all `PRIMARY` views in `service_configs`

Variance thresholds unchanged (≤1% excellent, 1–2% good, 2–5% warning, >5% critical).

`_generate_reconciliation_insights()` updated to name specific views contributing to any remaining gap (e.g., if a new Cortex service begins billing under `AI_SERVICES` before a corresponding view is added).

## Phase 3: UI Changes (`streamlit_app.py`)

The file structure does not change. Two new tabs are added to the "AI & Cortex Costs" expander, and one existing tab gets a warning banner.

### AI & Cortex expander — tab changes

| Tab | View | Status |
|-----|------|--------|
| AI Functions | `CORTEX_AI_FUNCTIONS_USAGE_HISTORY` | Existing — update method call to new service key |
| Cortex Code | `CORTEX_CODE_CLI_USAGE_HISTORY` | **New** — not currently in data_layer or UI |
| REST API | `CORTEX_REST_API_USAGE_HISTORY` | Existing — update label to "tokens only (billed in USD)" |
| AI SQL | `CORTEX_AISQL_USAGE_HISTORY` | Existing — update method call to new service key |
| Doc Processing | `CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY` | Existing — add warning banner about data quality |
| Cortex Analyst | `CORTEX_ANALYST_USAGE_HISTORY` | Existing |
| Cortex Search | `CORTEX_SEARCH_DAILY_USAGE_HISTORY` | Existing |
| Search Serving | `CORTEX_SEARCH_SERVING_USAGE_HISTORY` | Existing |
| **Cortex Agents** | `CORTEX_AGENT_USAGE_HISTORY` | **New** |
| **Snowflake Intelligence** | `SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY` | **New** |

### Reconciliation panel

A new top-level expander "AI Services Reconciliation" surfaces the 3-tier variance check via `ReconciliationEngine`. Green when Tier 2 vs. Tier 3 gap ≤1%; red when >5% with a per-service breakdown identifying unaccounted credits.

## Out of Scope

- `CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY` — not yet fully rolled out as of 2026-03-26. Snowsight CoCo usage currently flows into `CORTEX_AGENT_USAGE_HISTORY` where `AGENT_NAME IS NULL`. Add the dedicated view in a follow-up once stable everywhere.
- `CORTEX_PROVISIONED_THROUGHPUT_USAGE_HISTORY` — add in a follow-up if probe shows data on any connection.
- UI styling, theming, or chart redesign.
- Changes to non-AI sections (warehouses, storage, SPCS, etc.).

## Files Changed

| File | Change |
|------|--------|
| `common/analytics/data_layer.py` | Audit `service_configs` (remove 1, add 4, demote 1), add `probe_views()`, add methods for `CORTEX_AGENT` and `SNOWFLAKE_INTELLIGENCE` |
| `common/analytics/reconciliation.py` | Replace 4 hardcoded service-count constants with dynamic `len(primary_views)` |
| `streamlit_app.py` | Add Cortex Agents and Snowflake Intelligence tabs, add Doc Processing warning banner, update REST API label, add reconciliation panel expander |
| `sql/cortex_credit_consumption_analysis.sql` | Update to reflect current view names and column mapping |

## Validation Criteria

- `variance_pct` from the CLI reconciliation delta query is ≤5% on `default` and `aws_us` connections (both ACCOUNTADMIN, expected to have full ACCOUNT_USAGE grants and AI service usage data).
- All 5 connections: every `PRIMARY` view probe either returns rows or returns 0 rows **without SQL error**. A `permission denied` error is acceptable for `snowhouse` (SALES_ENGINEER role) — that view is downgraded to `FALLBACK` for that account.
- `probe_views()` completes without raising an unhandled exception on any of the 5 connections.
- The reconciliation panel in the app shows `EXCELLENT` or `GOOD` status for the test period on the `default` account.
- `accessible_services` in reconciliation output equals the count of `PRIMARY` entries in `service_configs` (not hardcoded 6).

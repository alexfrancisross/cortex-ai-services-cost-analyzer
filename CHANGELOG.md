# Changelog

All notable changes to the Cortex AI Services Cost Analyzer are documented here.

---

## [Unreleased] — 2026-03-26

### Summary

Closes the `AI_SERVICES` reconciliation gap caused by two new Cortex views that went GA on Feb 25 2026 (`CORTEX_AGENT_USAGE_HISTORY`, `SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY`) but were absent from the data layer. Also audits and updates the full `service_configs` registry to remove deprecated views and align with current Snowflake `ACCOUNT_USAGE` schema.

### Added

- **`CORTEX_AGENT_USAGE_HISTORY` support** — new service registry entry, analysis method (`get_cortex_agent_analysis`), reconciliation CTE branch, and UI tab in Service Details. Groups by `AGENT_NAME`; null names are attributed as "Snowsight CoCo (unattributed)" pending `CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY` rollout.
- **`SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY` support** — new service registry entry, analysis method (`get_snowflake_intelligence_analysis`), reconciliation CTE branch, and UI tab in Service Details. Groups by `SNOWFLAKE_INTELLIGENCE_NAME`.
- **`CORTEX_AI_FUNCTIONS_USAGE_HISTORY` support** — replaces deprecated `CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY` as the primary AI functions view. Uses `CREDITS` column.
- **`CORTEX_AISQL_USAGE_HISTORY` support** — replaces deprecated `CORTEX_FUNCTIONS_USAGE_HISTORY`. Uses `TOKEN_CREDITS` column and `USAGE_TIME` time column (not `START_TIME`).
- **Cortex Code CLI tab** — new Service Details section calling `get_cortex_code_analysis` against `CORTEX_CODE_CLI_USAGE_HISTORY`.
- **`probe_views()` method** on `SnowflakeDataLoader` — probes every view in `service_configs` at startup; sets `status` to `PRIMARY`, `FALLBACK`, or `UNAVAILABLE`. Intended to be called once via `@st.cache_resource` before constructing `ReconciliationEngine`.
- **`primary_views` property** on `SnowflakeDataLoader` — returns list of service keys with `status == 'PRIMARY'`.
- **CLI probe scripts** — `scripts/probe_views.sql` and `scripts/run_probe.sh` for validating view existence across multiple Snowflake connections.
- **Unit tests** — `tests/test_data_layer.py` (23 tests) and `tests/test_reconciliation.py` (6 tests). Both use `sys.modules` stubs to run without a Snowflake environment.

### Changed

- **`service_configs` registry** updated from 6 entries to 9:
  - Removed: `CORTEX_FUNCTIONS_QUERY` (`CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY`, deprecated Jan 2026)
  - Added: `CORTEX_AI_FUNCTIONS`, `CORTEX_AISQL`, `CORTEX_AGENT`, `SNOWFLAKE_INTELLIGENCE`
  - Demoted to `FALLBACK`: `CORTEX_DOCUMENT_PROCESSING` (broken post-Nov 2025 billing event changes)
- **Reconciliation CTE** (`get_ai_services_reconciliation_optimized`) rewritten with 9 branches. `CORTEX_DOCUMENT_PROCESSING` hardcoded to `0` to exclude it from the reconciliation sum while still projecting it for visibility. `CORTEX_AISQL` branch uses `USAGE_TIME` in filter predicates.
- **`reconciliation.py` service-count constants** — four hardcoded `6` references replaced with `self._primary_view_count` (computed from `len(data_loader.primary_views)` at engine construction, fallback `6`). Display string, full-access threshold, partial-access threshold, and completeness check are all dynamic.
- **Reconciliation panel help text** updated to list all 8 credit-contributing views including the two new ones (marked ★ new).
- **Doc Processing warning banner** added to Service Details tab, noting data quality issue and reconciliation exclusion.
- **`get_model_token_analysis` and `get_specialized_functions_analysis`** updated to query `CORTEX_AISQL_USAGE_HISTORY` with `USAGE_TIME` column; all `START_TIME` references on this view corrected.
- **`get_available_services_optimized`** updated `TABLE_NAME IN (...)` list from 5 stale entries to 11 current views.
- **`sql/cortex_credit_consumption_analysis.sql`** — all `CORTEX_FUNCTIONS_USAGE_HISTORY` and `CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY` references replaced; `USAGE_TIME` used for `CORTEX_AISQL` branches; `CORTEX_AGENT` and `SNOWFLAKE_INTELLIGENCE` branches added to sections 1 (reconciliation), 3 (service breakdown), 4 (time series), and 5 (raw data exports 5f, 5g).

### Fixed

- Reconciliation gap of ~46% between `METERING_HISTORY` `AI_SERVICES` total and the granular service sum. `CORTEX_AGENT` (58.4 credits) and `SNOWFLAKE_INTELLIGENCE` (46.9 credits) were the confirmed missing contributors on the `default` account in the 30-day validation window.
- `CORTEX_AISQL_USAGE_HISTORY` probe and query failures caused by incorrect use of `START_TIME` column (correct column is `USAGE_TIME`).

### Known limitations

- Reconciliation variance on the `default` test account remains ~46% after the fix. The remaining gap is unexplained by any currently available `ACCOUNT_USAGE` view. Likely candidates: credits flowing through `METERING_HISTORY` with no corresponding granular view yet (e.g., provisioned throughput, Snowsight CoCo until `CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY` stabilizes). `CORTEX_PROVISIONED_THROUGHPUT_USAGE_HISTORY` showed 0 rows on the test accounts.
- `aws_us` connection validation blocked by IP allowlist restriction; this is an account configuration issue.
- `CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY` intentionally out of scope; Snowsight CoCo traffic currently flows into `CORTEX_AGENT_USAGE_HISTORY` where `AGENT_NAME IS NULL`.

---

## [1.0.0] — 2025-10-08

Initial release of the Cortex AI Services Cost Analyzer Streamlit-in-Snowflake app.

### Features

- 3-tier reconciliation: Organization usage → Account metering → Granular service views
- Model token and credit analysis with model-type classification
- Specialized function breakdown (TRANSLATE, CLASSIFY_TEXT, SENTIMENT, etc.)
- Service breakdown and utilization metrics
- Daily time series with per-function granularity
- Raw data export per service
- Multi-connection support via Snowflake CLI for cross-account validation
- Cortex Analyst, Document AI, Cortex Search Serving, Cortex Fine Tuning tabs

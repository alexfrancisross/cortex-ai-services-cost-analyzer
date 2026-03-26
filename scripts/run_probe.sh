#!/usr/bin/env bash
# scripts/run_probe.sh
# Usage: bash scripts/run_probe.sh
# Runs probe_views.sql against all configured Snowflake CLI connections.
CONNECTIONS=(default aws_us snowhouse travelodge azure)
SQL_FILE="scripts/probe_views.sql"

for conn in "${CONNECTIONS[@]}"; do
    echo ""
    echo "=============================="
    echo "Connection: $conn"
    echo "=============================="
    snow sql --connection "$conn" -f "$SQL_FILE" 2>&1 || echo "ERROR on $conn (may be permission-denied — expected for snowhouse)"
done

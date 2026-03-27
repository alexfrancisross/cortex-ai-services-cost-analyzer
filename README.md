# Cortex AI Services Cost Analyzer

[![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=for-the-badge&logo=snowflake&logoColor=white)](https://www.snowflake.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)

A cost analysis and reconciliation dashboard for **Snowflake Cortex AI Services**. Provides detailed insights into AI service consumption, billing reconciliation, and performance analytics.

![Demo](img/demo.gif)

## Prerequisites

- Snowflake account with Cortex AI Services enabled
- [Snowflake CLI](https://docs.snowflake.com/en/developer-guide/snowflake-cli/index) installed
- Role with `IMPORTED PRIVILEGES` on the `SNOWFLAKE` database

## Deploy to Snowflake

**1. Install Snowflake CLI**
```bash
pip install snowflake-cli-labs
```

**2. Configure a connection**
```bash
snow connection add
```

**3. Run setup SQL** (creates the database, schema, and stage)
```bash
snow sql -f setup.sql
```

**4. Deploy the app**
```bash
# First-time deployment
snow streamlit deploy cortex_cost_analyzer

# Update an existing deployment
snow streamlit deploy cortex_cost_analyzer --replace
```

**5. Open the app**

Navigate to **Snowsight > Data > Streamlit Apps** and open **CORTEX_AI_COST_ANALYZER**, or use the URL printed by the deploy command.

## Run Locally

```bash
conda env create -f environment.yml
conda activate cortex_cost_analyzer
streamlit run streamlit_app.py
```

Requires `~/.snowflake/config.toml` with a valid connection named `default`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Object already exists` on deploy | Add `--replace` flag |
| No data in dashboard | `ACCOUNT_USAGE` views have a 2–3 hour lag; try a wider date range |
| Permission denied | Run `GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE <YOUR_ROLE>` |
| Connection errors locally | Check `~/.snowflake/config.toml` and confirm your warehouse is running |

## Resources

- [Snowflake Cortex AI Docs](https://docs.snowflake.com/en/guides-overview-ai-features)
- [Snowflake CLI Docs](https://docs.snowflake.com/en/developer-guide/snowflake-cli/index)
- [Account Usage Views](https://docs.snowflake.com/en/sql-reference/account-usage)

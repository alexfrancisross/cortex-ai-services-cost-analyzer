#!/bin/bash
#
# Cortex AI Services Cost Analyzer - Deployment Script
# Automates deployment using Snowflake CLI
#
# Usage: 
#   ./scripts/deploy.sh [environment] [connection]
#   
# Examples:
#   ./scripts/deploy.sh dev
#   ./scripts/deploy.sh prod my-connection
#   ./scripts/deploy.sh test --validate-only
#

set -euo pipefail

# Configuration - Updated for official Snowflake monorepo structure
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${PROJECT_ROOT}/apps/cortex-cost-analyzer"
APP_NAME="cortex_cost_analyzer"
DEFAULT_CONNECTION="default"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
Cortex AI Services Cost Analyzer - Deployment Script

USAGE:
    ./scripts/deploy.sh [ENVIRONMENT] [OPTIONS]

ENVIRONMENTS:
    dev         Deploy to development environment
    test        Deploy to test environment  
    prod        Deploy to production environment

OPTIONS:
    --connection NAME    Use specific Snowflake connection (default: default)
    --validate-only     Only validate configuration, don't deploy
    --force             Force deployment even with warnings
    --help              Show this help message

EXAMPLES:
    ./scripts/deploy.sh dev
    ./scripts/deploy.sh prod --connection my-prod-conn
    ./scripts/deploy.sh test --validate-only
    ./scripts/deploy.sh prod --force

PREREQUISITES:
    - Snowflake CLI installed and configured
    - Appropriate privileges granted in target environment
    - Valid snowflake.yml configuration

EOF
}

# Validate prerequisites
validate_prerequisites() {
    log_info "Validating prerequisites..."
    
    # Check if snow CLI is installed
    if ! command -v snow &> /dev/null; then
        log_error "Snowflake CLI not found. Please install snowflake-cli-labs:"
        echo "  pip install snowflake-cli-labs"
        exit 1
    fi
    
    # Check if we're in the right directory (Snowflake monorepo structure)
    if [[ ! -f "$PROJECT_ROOT/snowflake.yml" ]]; then
        log_error "snowflake.yml not found in project root. Please check monorepo structure."
        exit 1
    fi
    
    # Validate project configuration
    log_info "Validating project configuration..."
    cd "$PROJECT_ROOT"
    
    if ! snow project validate; then
        log_error "Project validation failed. Please check snowflake.yml configuration."
        exit 1
    fi
    
    log_success "Prerequisites validated"
}

# Test connection
test_connection() {
    local connection="${1:-$DEFAULT_CONNECTION}"
    
    log_info "Testing connection: $connection"
    
    if ! snow connection test --connection "$connection"; then
        log_error "Connection test failed for: $connection"
        log_info "Please run: snow connection add"
        exit 1
    fi
    
    log_success "Connection test passed"
}

# Validate data access
validate_data_access() {
    local connection="${1:-$DEFAULT_CONNECTION}"
    
    log_info "Validating data access permissions..."
    
    # Test basic ACCOUNT_USAGE access
    if ! snow sql --connection "$connection" \
        -q "SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY LIMIT 1" \
        --quiet > /dev/null 2>&1; then
        log_error "Cannot access SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY"
        log_info "Required privilege: GRANT SELECT ON SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY TO ROLE <role>"
        exit 1
    fi
    
    # Test Cortex tables access
    local cortex_tables=(
        "CORTEX_FUNCTIONS_USAGE_HISTORY"
        "CORTEX_ANALYST_USAGE_HISTORY"
        "CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY"
        "CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY"
        "CORTEX_SEARCH_DAILY_USAGE_HISTORY"
        "CORTEX_SEARCH_SERVING_USAGE_HISTORY"
    )
    
    local accessible_tables=0
    for table in "${cortex_tables[@]}"; do
        if snow sql --connection "$connection" \
            -q "SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.$table LIMIT 1" \
            --quiet > /dev/null 2>&1; then
            ((accessible_tables++))
        else
            log_warning "Cannot access SNOWFLAKE.ACCOUNT_USAGE.$table"
        fi
    done
    
    if [[ $accessible_tables -lt 4 ]]; then
        log_error "Insufficient Cortex table access ($accessible_tables/6 accessible)"
        log_info "Minimum 4 tables required for basic functionality"
        exit 1
    fi
    
    log_success "Data access validated ($accessible_tables/6 Cortex tables accessible)"
}

# Deploy application
deploy_app() {
    local environment="$1"
    local connection="${2:-$DEFAULT_CONNECTION}"
    local validate_only="${3:-false}"
    local force="${4:-false}"
    
    log_info "Deploying Cortex Cost Analyzer to environment: $environment"
    
    cd "$PROJECT_ROOT"
    
    # Validate before deployment
    if ! snow streamlit validate --connection "$connection"; then
        log_error "Streamlit validation failed"
        exit 1
    fi
    
    if [[ "$validate_only" == "true" ]]; then
        log_success "Validation completed successfully"
        return 0
    fi
    
    # Check if app already exists
    local app_exists=false
    if snow streamlit list --connection "$connection" --env "$environment" | grep -q "$APP_NAME"; then
        app_exists=true
        log_warning "Application already exists in $environment environment"
        
        if [[ "$force" != "true" ]]; then
            read -p "Continue with replacement? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_info "Deployment cancelled"
                exit 0
            fi
        fi
    fi
    
    # Deploy the application
    log_info "Deploying application..."
    
    if snow streamlit deploy \
        --connection "$connection" \
        --env "$environment" \
        --replace; then
        log_success "Application deployed successfully"
    else
        log_error "Deployment failed"
        exit 1
    fi
    
    # Post-deployment validation
    log_info "Running post-deployment validation..."
    
    if snow streamlit describe "$APP_NAME" \
        --connection "$connection" \
        --env "$environment" > /dev/null; then
        log_success "Post-deployment validation passed"
    else
        log_warning "Post-deployment validation failed"
    fi
    
    # Display application URL
    log_success "Deployment completed!"
    log_info "Access your application in Snowsight: Apps > Streamlit > CORTEX_AI_COST_ANALYZER"
}

# Grant access to users
grant_access() {
    local environment="$1"
    local connection="${2:-$DEFAULT_CONNECTION}"
    local role="${3:-ANALYST_ROLE}"
    
    log_info "Granting access to role: $role"
    
    # Get app identifier based on environment
    local app_db app_schema app_name
    case "$environment" in
        "dev")
            app_db="ANALYTICS_DEV"
            app_schema="CORTEX_APPS_DEV"
            app_name="CORTEX_AI_COST_ANALYZER_DEV"
            ;;
        "test")
            app_db="ANALYTICS_TEST"
            app_schema="CORTEX_APPS_TEST"
            app_name="CORTEX_AI_COST_ANALYZER_TEST"
            ;;
        "prod")
            app_db="ANALYTICS"
            app_schema="CORTEX_APPS"
            app_name="CORTEX_AI_COST_ANALYZER"
            ;;
        *)
            log_error "Unknown environment: $environment"
            exit 1
            ;;
    esac
    
    # Grant usage on streamlit
    if snow sql --connection "$connection" \
        -q "GRANT USAGE ON STREAMLIT $app_db.$app_schema.$app_name TO ROLE $role" \
        --quiet; then
        log_success "Access granted to role: $role"
    else
        log_warning "Failed to grant access to role: $role"
    fi
}

# Main execution
main() {
    local environment=""
    local connection="$DEFAULT_CONNECTION"
    local validate_only=false
    local force=false
    local grant_role=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            dev|test|prod)
                environment="$1"
                shift
                ;;
            --connection)
                connection="$2"
                shift 2
                ;;
            --validate-only)
                validate_only=true
                shift
                ;;
            --force)
                force=true
                shift
                ;;
            --grant-to)
                grant_role="$2"
                shift 2
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Validate required arguments
    if [[ -z "$environment" ]]; then
        log_error "Environment is required"
        show_help
        exit 1
    fi
    
    # Execute deployment steps
    log_info "Starting deployment process..."
    log_info "Environment: $environment"
    log_info "Connection: $connection"
    log_info "Validate Only: $validate_only"
    
    validate_prerequisites
    test_connection "$connection"
    validate_data_access "$connection"
    deploy_app "$environment" "$connection" "$validate_only" "$force"
    
    # Grant access if requested
    if [[ -n "$grant_role" ]]; then
        grant_access "$environment" "$connection" "$grant_role"
    fi
    
    log_success "Deployment process completed successfully!"
    
    # Show next steps
    cat << EOF

🎉 Deployment Summary:
   Environment: $environment
   Application: Cortex AI Services Cost Analyzer
   Status: Ready for use

📱 Access Instructions:
   1. Open Snowsight in your browser
   2. Navigate to: Apps > Streamlit
   3. Click on: CORTEX_AI_COST_ANALYZER$([ "$environment" != "prod" ] && echo "_${environment^^}")

🔍 Next Steps:
   - Verify application loads correctly
   - Check reconciliation accuracy (<1% variance expected)
   - Grant access to additional users if needed:
     ./scripts/deploy.sh $environment --grant-to ROLE_NAME

EOF
}

# Execute main function
main "$@"

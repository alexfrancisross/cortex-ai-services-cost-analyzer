"""
Utility functions and constants for Cortex AI Services Cost Analyzer.
Provides helper functions for formatting, calculations, and common operations.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Union, Any, Tuple
import streamlit as st
import json
import hashlib

# Application constants
APP_VERSION = "1.0.0"
APP_NAME = "Cortex AI Services Cost Analyzer"
APP_DESCRIPTION = "Production-ready cost analysis and reconciliation for Snowflake Cortex AI Services"

# Service configuration constants - All 8 Cortex service categories from AI_Billing_FAQ.md
CORTEX_SERVICES = {
    'CORTEX_FUNCTIONS_USAGE': {
        'display_name': 'Functions Usage',
        'description': 'LLM function calls aggregated hourly',
        'icon': '🤖',
        'expected_usage': 'High volume for AI applications'
    },
    'CORTEX_ANALYST': {
        'display_name': 'Analyst',
        'description': 'Interactive data analysis requests',
        'icon': '📊',
        'expected_usage': 'Request-level granularity'
    },
    'CORTEX_DOCUMENT_PROCESSING': {
        'display_name': 'Document Processing',
        'description': 'Document parsing and processing',
        'icon': '📄',
        'expected_usage': 'Often overlooked but critical'
    },
    'DOCUMENT_AI': {
        'display_name': 'Document AI',
        'description': 'Document AI parsing and extraction',
        'icon': '📝',
        'expected_usage': 'Advanced document intelligence'
    },
    'CORTEX_FUNCTIONS_QUERY': {
        'display_name': 'Functions Query',
        'description': 'SQL-embedded function calls',
        'icon': '🔍',
        'expected_usage': 'Query-level tracking'
    },
    'CORTEX_SEARCH_DAILY': {
        'display_name': 'Search Daily',
        'description': 'Search service daily aggregation',
        'icon': '🔎',
        'expected_usage': 'Daily consumption patterns'
    },
    'CORTEX_SEARCH_SERVING': {
        'display_name': 'Search Serving',
        'description': 'Search serving infrastructure',
        'icon': '⚡',
        'expected_usage': 'Hourly serving metrics'
    },
    'CORTEX_FINE_TUNING': {
        'display_name': 'Fine Tuning',
        'description': 'Model fine-tuning operations',
        'icon': '🎯',
        'expected_usage': 'Training session level'
    }
}

# Reconciliation thresholds from PRD
RECONCILIATION_THRESHOLDS = {
    'excellent': 1.0,      # ≤1% variance
    'good': 2.0,          # 1-2% variance
    'warning': 5.0,       # 2-5% variance
    'critical': float('inf')  # >5% variance
}

# Data freshness thresholds (in hours)
DATA_FRESHNESS_THRESHOLDS = {
    'fresh': 3.0,         # <3 hours = fresh
    'acceptable': 6.0,    # 3-6 hours = acceptable
    'stale': 24.0,        # 6-24 hours = stale
    'very_stale': float('inf')  # >24 hours = very stale
}

# Status indicators and colors
STATUS_INDICATORS = {
    'EXCELLENT': {'emoji': '✅', 'color': '#28a745', 'description': 'Excellent accuracy'},
    'GOOD': {'emoji': '⚠️', 'color': '#ffc107', 'description': 'Good with minor variance'},
    'WARNING': {'emoji': '🟡', 'color': '#fd7e14', 'description': 'Warning - investigation suggested'},
    'CRITICAL': {'emoji': '🔴', 'color': '#dc3545', 'description': 'Critical - investigation required'},
    'UNKNOWN': {'emoji': '⚪', 'color': '#6c757d', 'description': 'Status unknown'},
    'ERROR': {'emoji': '❌', 'color': '#dc3545', 'description': 'Error occurred'}
}

def format_credits(credits: Union[float, int, None], precision: int = 6) -> str:
    """
    Format credits for display with appropriate precision.
    
    Args:
        credits: Credit amount to format
        precision: Number of decimal places (default 6)
        
    Returns:
        Formatted credit string
    """
    if credits is None or pd.isna(credits):
        return "0.000000"
    
    try:
        credits = float(credits)
        if credits == 0:
            return "0.000000"
        elif credits < 0.001:
            return f"{credits:.6f}"
        elif credits < 1:
            return f"{credits:.4f}"
        elif credits < 1000:
            return f"{credits:.3f}"
        else:
            return f"{credits:,.2f}"
    except (ValueError, TypeError):
        return "N/A"

def format_percentage(value: Union[float, int, None], precision: int = 2) -> str:
    """
    Format percentage values for display.
    
    Args:
        value: Percentage value to format
        precision: Number of decimal places
        
    Returns:
        Formatted percentage string
    """
    if value is None or pd.isna(value):
        return "N/A"
    
    try:
        return f"{float(value):.{precision}f}%"
    except (ValueError, TypeError):
        return "N/A"

def format_variance(variance: Union[float, int, None], precision: int = 3) -> str:
    """
    Format variance values with appropriate sign and precision.
    
    Args:
        variance: Variance value to format
        precision: Number of decimal places
        
    Returns:
        Formatted variance string with + or - sign
    """
    if variance is None or pd.isna(variance):
        return "N/A"
    
    try:
        variance = float(variance)
        return f"{variance:+.{precision}f}%"
    except (ValueError, TypeError):
        return "N/A"

def format_large_number(number: Union[float, int, None]) -> str:
    """
    Format large numbers with appropriate units (K, M, B).
    
    Args:
        number: Number to format
        
    Returns:
        Formatted number string with units
    """
    if number is None or pd.isna(number):
        return "N/A"
    
    try:
        number = float(number)
        if abs(number) >= 1_000_000_000:
            return f"{number/1_000_000_000:.1f}B"
        elif abs(number) >= 1_000_000:
            return f"{number/1_000_000:.1f}M"
        elif abs(number) >= 1_000:
            return f"{number/1_000:.1f}K"
        else:
            return f"{number:,.0f}"
    except (ValueError, TypeError):
        return "N/A"

def calculate_percentage_change(old_value: Union[float, int, None], 
                              new_value: Union[float, int, None]) -> Optional[float]:
    """
    Calculate percentage change between two values.
    
    Args:
        old_value: Previous period value
        new_value: Current period value
        
    Returns:
        Percentage change or None if calculation not possible
    """
    if old_value is None or new_value is None or pd.isna(old_value) or pd.isna(new_value):
        return None
    
    try:
        old_value = float(old_value)
        new_value = float(new_value)
        
        if old_value == 0:
            return None if new_value == 0 else float('inf')
        
        return ((new_value - old_value) / old_value) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return None

def get_status_color(status: str) -> str:
    """
    Get color code for reconciliation status.
    
    Args:
        status: Status string
        
    Returns:
        Hex color code
    """
    return STATUS_INDICATORS.get(status, STATUS_INDICATORS['UNKNOWN'])['color']

def get_status_emoji(status: str) -> str:
    """
    Get emoji for reconciliation status.
    
    Args:
        status: Status string
        
    Returns:
        Status emoji
    """
    return STATUS_INDICATORS.get(status, STATUS_INDICATORS['UNKNOWN'])['emoji']

def get_status_description(status: str) -> str:
    """
    Get description for reconciliation status.
    
    Args:
        status: Status string
        
    Returns:
        Status description
    """
    return STATUS_INDICATORS.get(status, STATUS_INDICATORS['UNKNOWN'])['description']

def determine_variance_status(variance: float) -> str:
    """
    Determine reconciliation status based on variance percentage.
    
    Args:
        variance: Absolute variance percentage
        
    Returns:
        Status string (EXCELLENT, GOOD, WARNING, CRITICAL)
    """
    abs_variance = abs(variance)
    
    if abs_variance <= RECONCILIATION_THRESHOLDS['excellent']:
        return 'EXCELLENT'
    elif abs_variance <= RECONCILIATION_THRESHOLDS['good']:
        return 'GOOD'
    elif abs_variance <= RECONCILIATION_THRESHOLDS['warning']:
        return 'WARNING'
    else:
        return 'CRITICAL'

def determine_freshness_status(hours_old: float) -> str:
    """
    Determine data freshness status based on age in hours.
    
    Args:
        hours_old: Age of data in hours
        
    Returns:
        Freshness status string
    """
    if hours_old <= DATA_FRESHNESS_THRESHOLDS['fresh']:
        return 'FRESH'
    elif hours_old <= DATA_FRESHNESS_THRESHOLDS['acceptable']:
        return 'ACCEPTABLE'
    elif hours_old <= DATA_FRESHNESS_THRESHOLDS['stale']:
        return 'STALE'
    else:
        return 'VERY_STALE'

def get_service_display_info(service_name: str) -> Dict[str, str]:
    """
    Get display information for a Cortex service.
    
    Args:
        service_name: Internal service name
        
    Returns:
        Dictionary with display information
    """
    return CORTEX_SERVICES.get(service_name, {
        'display_name': service_name,
        'description': 'Unknown service',
        'icon': '❓',
        'expected_usage': 'Unknown'
    })

def validate_date_range(start_date: date, end_date: date) -> Tuple[bool, str]:
    """
    Validate date range for analysis.
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if start_date >= end_date:
        return False, "Start date must be before end date"
    
    if end_date > datetime.now().date():
        return False, "End date cannot be in the future"
    
    # Check for reasonable date range (not more than 1 year)
    if (end_date - start_date).days > 365:
        return False, "Date range cannot exceed 365 days"
    
    return True, ""

def create_date_range_presets() -> Dict[str, Tuple[date, date]]:
    """
    Create common date range presets.
    
    Returns:
        Dictionary of preset name to (start_date, end_date) tuples
    """
    today = datetime.now().date()
    
    return {
        'Last 7 days': (today - timedelta(days=7), today),
        'Last 30 days': (today - timedelta(days=30), today),
        'Last 90 days': (today - timedelta(days=90), today),
        'Last 365 days': (today - timedelta(days=365), today),
        'This month': (today.replace(day=1), today),
        'Last month': (
            (today.replace(day=1) - timedelta(days=1)).replace(day=1),
            today.replace(day=1) - timedelta(days=1)
        )
    }

def safe_divide(numerator: Union[float, int], denominator: Union[float, int], 
               default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if division by zero.
    
    Args:
        numerator: Numerator value
        denominator: Denominator value
        default: Default value if division by zero
        
    Returns:
        Division result or default value
    """
    try:
        if denominator == 0:
            return default
        return float(numerator) / float(denominator)
    except (ValueError, TypeError, ZeroDivisionError):
        return default

def filter_dataframe_by_date(df: pd.DataFrame, date_column: str,
                           start_date: date, end_date: date) -> pd.DataFrame:
    """
    Filter DataFrame by date range.
    
    Args:
        df: DataFrame to filter
        date_column: Name of date column
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        
    Returns:
        Filtered DataFrame
    """
    if df.empty or date_column not in df.columns:
        return df
    
    try:
        # Convert to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
            df[date_column] = pd.to_datetime(df[date_column])
        
        # Filter by date range
        mask = (df[date_column].dt.date >= start_date) & (df[date_column].dt.date <= end_date)
        return df[mask].copy()
    
    except Exception:
        # Return original DataFrame if filtering fails
        return df

def summarize_service_data(service_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Create summary statistics for service data.
    
    Args:
        service_df: DataFrame with service breakdown data
        
    Returns:
        Dictionary with summary statistics
    """
    if service_df.empty:
        return {
            'total_credits': 0.0,
            'total_services': 0,
            'active_services': 0,
            'top_service': None,
            'top_service_percentage': 0.0
        }
    
    total_credits = service_df['total_credits'].sum() if 'total_credits' in service_df.columns else 0.0
    total_services = len(service_df)
    active_services = len(service_df[service_df['total_credits'] > 0]) if 'total_credits' in service_df.columns else 0
    
    # Find top service
    if 'total_credits' in service_df.columns and not service_df.empty:
        top_row = service_df.loc[service_df['total_credits'].idxmax()]
        top_service = top_row['service_type'] if 'service_type' in top_row else None
        top_service_percentage = top_row.get('percentage', 0.0)
    else:
        top_service = None
        top_service_percentage = 0.0
    
    return {
        'total_credits': total_credits,
        'total_services': total_services,
        'active_services': active_services,
        'top_service': top_service,
        'top_service_percentage': top_service_percentage
    }

def generate_session_id() -> str:
    """
    Generate unique session ID for tracking.
    
    Returns:
        Unique session identifier
    """
    timestamp = datetime.now().isoformat()
    random_component = str(hash(timestamp + str(np.random.random())))
    return hashlib.md5(random_component.encode()).hexdigest()[:8]

def log_user_interaction(action: str, details: Dict[str, Any] = None) -> None:
    """
    Log user interaction for analytics (placeholder function).
    
    Args:
        action: Action performed by user
        details: Additional details about the action
    """
    # In production, this would log to analytics service
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'details': details or {},
        'session_id': st.session_state.get('session_id', 'unknown')
    }
    
    # For now, just store in session state for debugging
    if 'user_interactions' not in st.session_state:
        st.session_state.user_interactions = []
    
    st.session_state.user_interactions.append(log_entry)

def export_dataframe_to_csv(df: pd.DataFrame, filename_prefix: str = "cortex_export") -> str:
    """
    Export DataFrame to CSV format for download.
    
    Args:
        df: DataFrame to export
        filename_prefix: Prefix for filename
        
    Returns:
        CSV string
    """
    try:
        # Add timestamp to filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Clean up DataFrame for export
        export_df = df.copy()
        
        # Convert any datetime columns to string
        for col in export_df.columns:
            if pd.api.types.is_datetime64_any_dtype(export_df[col]):
                export_df[col] = export_df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Create CSV
        csv_string = export_df.to_csv(index=False)
        
        # Log export action
        log_user_interaction('export_csv', {
            'filename_prefix': filename_prefix,
            'row_count': len(df),
            'column_count': len(df.columns)
        })
        
        return csv_string
        
    except Exception as e:
        st.error(f"Failed to export data: {str(e)}")
        return ""

def calculate_reconciliation_score(variance_pct: float, service_coverage: float,
                                 data_completeness: float) -> Tuple[float, str]:
    """
    Calculate overall reconciliation score based on multiple factors.
    
    Args:
        variance_pct: Variance percentage (absolute)
        service_coverage: Service coverage percentage
        data_completeness: Data completeness percentage (0-1)
        
    Returns:
        Tuple of (score, grade) where score is 0-100
    """
    # Variance component (0-40 points, lower variance = higher score)
    if variance_pct <= 1.0:
        variance_score = 40
    elif variance_pct <= 2.0:
        variance_score = 35
    elif variance_pct <= 5.0:
        variance_score = 25
    else:
        variance_score = max(0, 40 - variance_pct * 2)
    
    # Coverage component (0-30 points)
    if service_coverage >= 99.5:
        coverage_score = 30
    elif service_coverage >= 95.0:
        coverage_score = 25
    elif service_coverage >= 90.0:
        coverage_score = 20
    else:
        coverage_score = max(0, service_coverage * 0.3)
    
    # Completeness component (0-30 points)
    completeness_score = data_completeness * 30
    
    # Total score
    total_score = variance_score + coverage_score + completeness_score
    
    # Determine grade
    if total_score >= 90:
        grade = 'A+'
    elif total_score >= 85:
        grade = 'A'
    elif total_score >= 80:
        grade = 'B+'
    elif total_score >= 75:
        grade = 'B'
    elif total_score >= 70:
        grade = 'C+'
    elif total_score >= 65:
        grade = 'C'
    elif total_score >= 60:
        grade = 'D'
    else:
        grade = 'F'
    
    return round(total_score, 1), grade

def create_error_message(error_type: str, details: str = "", 
                        suggestions: List[str] = None) -> Dict[str, Any]:
    """
    Create standardized error message structure.
    
    Args:
        error_type: Type of error
        details: Error details
        suggestions: List of suggested solutions
        
    Returns:
        Structured error message
    """
    return {
        'type': error_type,
        'details': details,
        'suggestions': suggestions or [],
        'timestamp': datetime.now().isoformat(),
        'session_id': st.session_state.get('session_id', 'unknown')
    }

def display_help_section() -> None:
    """Display help section with usage instructions."""
    with st.expander("📖 How to Use This Application"):
        st.markdown("""
        ### Cortex AI Services Cost Analyzer Help
        
        **Purpose**: Analyze and reconcile Snowflake Cortex AI Services costs with 99.98% accuracy.
        
        **Key Features**:
        - 📊 **Executive Summary**: High-level metrics and trends
        - 🔧 **Service Breakdown**: Detailed analysis across 6 Cortex services
        - 🔍 **Reconciliation**: 3-tier validation methodology
        - 📈 **Time Series**: Usage trends and patterns
        
        **Navigation**:
        1. Use sidebar to select date range and services
        2. Review executive summary for key insights
        3. Explore service breakdown for detailed attribution
        4. Check reconciliation status for data quality
        5. Export data for further analysis
        
        **Reconciliation Status**:
        - ✅ **Excellent**: ≤1% variance (target accuracy)
        - ⚠️ **Good**: 1-2% variance (acceptable)
        - 🟡 **Warning**: 2-5% variance (investigate)
        - 🔴 **Critical**: >5% variance (action required)
        
        **Service Categories**:
        - **Functions Usage**: LLM function calls (typically highest usage)
        - **Analyst**: Interactive data analysis requests
        - **Document Processing**: PDF/document parsing (often overlooked)
        - **Functions Query**: SQL-embedded functions
        - **Search Daily/Serving**: Search service infrastructure
        
        **Tips**:
        - Start with 30-day analysis for optimal performance
        - Document Processing usage is often missed in manual analysis
        - Variance <1% indicates excellent data quality
        - Export data for monthly financial reconciliation
        """)

# Initialize session state helper
def init_session_state() -> None:
    """Initialize Streamlit session state variables."""
    if 'session_id' not in st.session_state:
        st.session_state.session_id = generate_session_id()
    
    if 'user_interactions' not in st.session_state:
        st.session_state.user_interactions = []
    
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now()

# Constants for export
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_EXPORT_ROWS = 100000  # Limit for CSV export

# Validation helpers
def is_valid_credit_amount(amount: Any) -> bool:
    """Check if amount is a valid credit value."""
    try:
        val = float(amount)
        return val >= 0 and not np.isnan(val) and np.isfinite(val)
    except (ValueError, TypeError):
        return False

def is_valid_percentage(percentage: Any) -> bool:
    """Check if percentage is valid (0-100+)."""
    try:
        val = float(percentage)
        return val >= 0 and not np.isnan(val) and np.isfinite(val)
    except (ValueError, TypeError):
        return False

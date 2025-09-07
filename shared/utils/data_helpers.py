"""
Essential utility functions for Cortex AI Services Cost Analyzer.
Cleaned version with only functions used by the application.
"""

import pandas as pd
from typing import Union

# Status configuration for reconciliation states
STATUS_CONFIG = {
    'EXCELLENT': {'emoji': '🟢', 'color': '#28a745', 'description': 'Excellent reconciliation'},
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

def get_status_color(status: str) -> str:
    """
    Get color code for reconciliation status.
    
    Args:
        status: Status string (EXCELLENT, GOOD, WARNING, CRITICAL, etc.)
        
    Returns:
        Hex color code
    """
    return STATUS_CONFIG.get(status.upper(), STATUS_CONFIG['UNKNOWN'])['color']

def calculate_percentage_change(old_value: Union[float, int, None], 
                              new_value: Union[float, int, None]) -> Union[float, None]:
    """
    Calculate percentage change between two values.
    
    Args:
        old_value: Original value
        new_value: New value
        
    Returns:
        Percentage change or None if calculation not possible
    """
    if old_value is None or new_value is None:
        return None
    
    try:
        old_value = float(old_value)
        new_value = float(new_value)
        
        if old_value == 0:
            return 100.0 if new_value != 0 else 0.0
        
        return ((new_value - old_value) / old_value) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return None

"""Utility functions for CFL Commute integration."""

from datetime import datetime
from typing import Optional


def format_time(time_str: Optional[str]) -> str:
    """Format time from HH:MM:SS to HH:MM.

    Args:
        time_str: Time string in HH:MM:SS format (or HH:MM)

    Returns:
        Time string in HH:MM format, or empty string if input is empty
    """
    if not time_str:
        return ""

    try:
        dt = datetime.strptime(time_str, "%H:%M:%S")
        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return time_str[:5] if len(time_str) >= 5 else time_str

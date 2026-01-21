"""
Utility functions for PDF Compressor application.
"""

import re
from typing import Optional
from pathlib import Path


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to remove invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for all operating systems
    """
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)

    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip('. ')

    # Limit length to 255 characters (common filesystem limit)
    if len(sanitized) > 255:
        name, ext = Path(sanitized).stem, Path(sanitized).suffix
        max_name_length = 255 - len(ext)
        sanitized = name[:max_name_length] + ext

    return sanitized or 'unnamed_file'


def validate_pdf_file(file_data: bytes) -> bool:
    """
    Validate if file data represents a valid PDF.

    Args:
        file_data: File data as bytes

    Returns:
        True if valid PDF, False otherwise
    """
    if not file_data:
        return False

    # Check PDF header (should start with %PDF-)
    pdf_header = file_data[:8]
    return pdf_header.startswith(b'%PDF-')


def get_compression_recommendation(file_size: int) -> str:
    """
    Get recommended compression level based on file size.

    Args:
        file_size: File size in bytes

    Returns:
        Recommended compression level
    """
    mb_size = file_size / (1024 * 1024)

    if mb_size < 5:
        return "medium"
    elif mb_size < 20:
        return "high"
    else:
        return "maximum"


def calculate_total_size(files_list: list) -> int:
    """
    Calculate total size of multiple files.

    Args:
        files_list: List of file objects with 'size' attribute

    Returns:
        Total size in bytes
    """
    return sum(getattr(file, 'size', 0) for file in files_list)


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"

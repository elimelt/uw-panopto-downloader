"""File utilities for Panopto Downloader."""

import os
import re
import shutil
from pathlib import Path
from typing import List, Optional

from .logging import get_logger

logger = get_logger(__name__)


def clean_filename(filename: str) -> str:
    """Clean a string to make it suitable for use as a filename.
    
    Args:
        filename: The original filename
        
    Returns:
        str: The cleaned filename
    """
    # Replace invalid characters with underscore
    cleaned = re.sub(r'[\\/*?:"<>|]', '_', filename)
    # Remove extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def ensure_directory(directory: str) -> bool:
    """Ensure a directory exists, creating it if necessary.
    
    Args:
        directory: Path to the directory
        
    Returns:
        bool: Whether directory exists or was created
    """
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {directory}: {e}")
        return False


def check_ffmpeg_installed() -> bool:
    """Check if FFmpeg is installed and available.
    
    Returns:
        bool: Whether FFmpeg is installed
    """
    import subprocess
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_available_space(directory: str) -> Optional[int]:
    """Get available disk space in bytes for a directory.
    
    Args:
        directory: Path to check
        
    Returns:
        int: Available space in bytes, or None if error
    """
    try:
        if os.name == 'nt':  # Windows
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(directory), None, None, ctypes.pointer(free_bytes))
            return free_bytes.value
        else:  # Unix/Linux/macOS
            stats = os.statvfs(directory)
            return stats.f_frsize * stats.f_bavail
    except Exception as e:
        logger.error(f"Failed to get disk space for {directory}: {e}")
        return None


def get_file_size(file_path: str) -> Optional[int]:
    """Get file size in bytes.
    
    Args:
        file_path: Path to the file
        
    Returns:
        int: File size in bytes, or None if file doesn't exist
    """
    try:
        return os.path.getsize(file_path)
    except (FileNotFoundError, OSError):
        return None


def format_size(size_bytes: int) -> str:
    """Format file size in a human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        str: Formatted size string
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
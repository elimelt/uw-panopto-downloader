"""Network utilities for Panopto Downloader."""

import os
import time
import urllib.parse
from typing import Dict, Any, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .logging import get_logger

logger = get_logger(__name__)


def create_session(retries: int = 3, backoff_factor: float = 0.3) -> requests.Session:
    """Create a requests session with automatic retries.
    
    Args:
        retries: Number of retries
        backoff_factor: Backoff factor between retries
        
    Returns:
        requests.Session: Configured session
    """
    session = requests.Session()
    
    # Configure automatic retries with exponential backoff
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def download_file(url: str, output_path: str, session: Optional[requests.Session] = None,
                 chunk_size: int = 8192, timeout: int = 30) -> Tuple[bool, Optional[str]]:
    """Download a file with progress tracking.
    
    Args:
        url: URL to download
        output_path: Path to save the file
        session: Optional requests session to use
        chunk_size: Download chunk size
        timeout: Connection timeout in seconds
        
    Returns:
        tuple: (success, error_message)
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # Use provided session or create a new one
    if session is None:
        session = create_session()
    
    try:
        # Start the request
        response = session.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
        
        # Get file size if available
        total_size = int(response.headers.get('content-length', 0))
        
        # Download the file
        with open(output_path, 'wb') as f:
            start_time = time.time()
            downloaded = 0
            
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Calculate progress and speed
                    elapsed = time.time() - start_time
                    if elapsed > 0:
                        speed = downloaded / elapsed
                        
                        if total_size > 0:
                            progress = downloaded / total_size * 100
                            logger.debug(f"Progress: {progress:.1f}% ({format_size(downloaded)}/{format_size(total_size)}) "
                                       f"at {format_size(speed)}/s")
                        else:
                            logger.debug(f"Downloaded {format_size(downloaded)} at {format_size(speed)}/s")
        
        return True, None
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Download failed: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def parse_url(url: str) -> Dict[str, Any]:
    """Parse a URL into its components.
    
    Args:
        url: URL to parse
        
    Returns:
        dict: URL components
    """
    parsed = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(parsed.query))
    
    return {
        'scheme': parsed.scheme,
        'netloc': parsed.netloc,
        'path': parsed.path,
        'params': parsed.params,
        'query': query,
        'fragment': parsed.fragment,
        'base_url': f"{parsed.scheme}://{parsed.netloc}",
    }


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
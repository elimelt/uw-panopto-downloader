"""Core functionality for downloading Panopto videos."""

import concurrent.futures
import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from ..utils.file import get_file_size
from ..utils.logging import get_logger
from .browser import BrowserSession
from .config import config

logger = get_logger(__name__)


class PanoptoDownloader:
    """Main downloader class for Panopto videos."""

    def __init__(self, browser_session: BrowserSession, max_workers: Optional[int] = None):
        """Initialize the downloader.

        Args:
            browser_session: The browser session to use
            max_workers: Maximum number of concurrent downloads
        """
        self.browser = browser_session
        self.max_workers = max_workers or config.max_workers

    def get_video_id(self, url: str) -> Optional[str]:
        """Extract the video ID from a Panopto URL.

        Args:
            url: The Panopto video URL

        Returns:
            str: The video ID or None if not found
        """
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        video_id = query_params.get("id", [None])[0] or query_params.get("Id", [None])[0]

        if not video_id:
            logger.error(f"Could not extract video ID from URL: {url}")

        return video_id

    def get_delivery_info(self, video_id: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Request the delivery info for a video ID.

        Args:
            video_id: The Panopto video ID

        Returns:
            tuple: (stream_url, additional_streams)
        """
        if not self.browser.base_url:
            logger.error("Base URL not set. Make sure to log in first.")
            return None, []

        logger.info(f"Requesting delivery info for video ID: {video_id}")

        url = f"{self.browser.base_url}/Panopto/Pages/Viewer/DeliveryInfo.aspx"
        data = {"deliveryId": video_id, "isEmbed": "true", "responseType": "json"}

        try:
            response = self.browser.session.post(url, data=data)
            response.raise_for_status()
            data = response.json()

            if data.get("ErrorCode"):
                error_msg = data.get("ErrorMessage", "Unknown error")
                logger.error(f"Error requesting delivery info: {error_msg}")
                return None, []

            stream_url = data.get("Delivery", {}).get("PodcastStreams", [{}])[0].get("StreamUrl")
            additional_streams = data.get("Delivery", {}).get("Streams", [])

            additional_streams = [s for s in additional_streams if s.get("StreamUrl") != stream_url]

            if not stream_url:
                logger.error("Stream URL not found in delivery info")

                for stream in additional_streams:
                    if stream.get("StreamUrl"):
                        stream_url = stream.get("StreamUrl")
                        break

            return stream_url, additional_streams
        except Exception as e:
            logger.error(f"Error requesting delivery info: {e}")
            return None, []

    def download_m3u8(self, m3u8_url: str, output_path: str, max_retries: int = 3) -> bool:
        """Download a video from an m3u8 URL using FFmpeg.

        Args:
            m3u8_url: The m3u8 URL to download
            output_path: The output file path
            max_retries: Maximum number of retry attempts

        Returns:
            bool: Whether download was successful
        """
        try:

            try:
                subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.error(
                    "FFmpeg is not installed. Please install FFmpeg to download HLS streams."
                )
                return False

            cmd = [
                "ffmpeg",
                "-i",
                m3u8_url,
                "-c",
                "copy",
                "-bsf:a",
                "aac_adtstoasc",
                output_path,
                "-y",
            ]

            retries = 0
            while retries < max_retries:
                logger.info(f"Downloading to {output_path}")
                result = subprocess.run(cmd, capture_output=True, check=False)

                if result.returncode == 0:
                    logger.info(f"Successfully downloaded {output_path}")
                    return True

                retries += 1
                logger.warning(f"Download failed, retrying ({retries}/{max_retries})...")
                time.sleep(2)

            logger.error(f"Failed to download after {max_retries} attempts")
            return False
        except Exception as e:
            logger.error(f"Error downloading m3u8: {e}")
            return False

    def download_direct(
        self, url: str, output_path: str, chunk_size: int = 8192, max_retries: int = 3
    ) -> bool:
        """Download a direct video link.

        Args:
            url: The direct video URL
            output_path: The output file path
            chunk_size: The download chunk size
            max_retries: Maximum number of retry attempts

        Returns:
            bool: Whether download was successful
        """
        retries = 0
        while retries < max_retries:
            try:
                logger.info(f"Downloading to {output_path}")
                response = self.browser.session.get(url, stream=True)
                response.raise_for_status()

                int(response.headers.get("content-length", 0))
                downloaded = 0

                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                logger.info(f"Successfully downloaded {output_path}")
                return True

            except Exception as e:
                retries += 1
                logger.warning(f"Download failed ({e}), retrying ({retries}/{max_retries})...")
                time.sleep(2)

        logger.error(f"Failed to download after {max_retries} attempts")
        return False

    def download_video(
        self, video_info: Tuple[str, str], download_dir: str
    ) -> Tuple[bool, str, Optional[str], int]:
        """Download a single video.

        Args:
            video_info: Tuple of (url, title)
            download_dir: The directory to save the video to

        Returns:
            tuple: (success, video_path, video_id, file_size)
        """
        url, title = video_info
        video_id = self.get_video_id(url)

        if not video_id:
            return (False, "", None, 0)

        stream_url, _ = self.get_delivery_info(video_id)

        if not stream_url:
            logger.error(f"Could not get stream URL for {title}")
            return (False, "", video_id, 0)

        logger.info(f"Got stream URL for {title}: {stream_url}")

        file_ext = ".mp4"

        os.makedirs(download_dir, exist_ok=True)

        output_path = os.path.join(download_dir, f"{title}{file_ext}")

        if os.path.exists(output_path):
            logger.info(f"File already exists: {output_path}")
            file_size = get_file_size(output_path) or 0
            return (True, output_path, video_id, file_size)

        success = False
        if stream_url.endswith(".m3u8"):
            success = self.download_m3u8(stream_url, output_path)
        else:
            success = self.download_direct(stream_url, output_path)

        file_size = 0
        if success:
            file_size = get_file_size(output_path) or 0

        return (success, output_path if success else "", video_id, file_size)

    def download_videos(
        self, video_list: List[Tuple[str, str]], download_dir: str
    ) -> Tuple[int, int]:
        """Download multiple videos in parallel.

        Args:
            video_list: List of (url, title) tuples
            download_dir: The directory to save videos to

        Returns:
            tuple: (successful, failed) counts
        """
        successful = 0
        failed = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_video = {
                executor.submit(self.download_video, video, download_dir): video
                for video in video_list
            }

            for future in concurrent.futures.as_completed(future_to_video):
                video = future_to_video[future]
                try:
                    result = future.result()
                    if result[0]:  # success flag
                        successful += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Error processing {video[1]}: {e}")
                    failed += 1

        logger.info(f"Processing complete. Successful: {successful}, Failed: {failed}")
        return successful, failed

"""Core functionality for converting videos to audio."""

import glob
import multiprocessing
import os
import subprocess
from typing import List, Optional, Tuple

from ..utils.logging import get_logger
from .config import config

logger = get_logger(__name__)


class VideoConverter:
    """Handles conversion of video files to audio formats."""

    def __init__(self, bitrate: Optional[str] = None, threads: Optional[int] = None):
        """Initialize the converter.

        Args:
            bitrate: Audio bitrate for conversion
            threads: Number of FFmpeg threads to use
        """
        self.bitrate = bitrate or config.audio_bitrate
        self.threads = threads if threads is not None else config.ffmpeg_threads

    def find_video_files(self, directory: str, extension: str = "mp4") -> List[str]:
        """Find all video files of a specific extension in a directory.

        Args:
            directory: The directory to search in
            extension: The file extension to search for

        Returns:
            list: List of file paths
        """
        pattern = os.path.join(directory, "**", f"*.{extension}")
        return glob.glob(pattern, recursive=True)

    def convert_file(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        bitrate: Optional[str] = None,
        threads: Optional[int] = None,
    ) -> bool:
        """Convert a single video file to audio.

        Args:
            video_path: Path to the video file
            output_path: Path to save the audio file
            bitrate: Audio bitrate
            threads: Number of FFmpeg threads to use

        Returns:
            bool: Whether conversion was successful
        """
        # Use instance defaults if not specified
        bitrate = bitrate or self.bitrate
        threads = threads if threads is not None else self.threads

        # Generate output path if not provided
        if not output_path:
            output_path = os.path.splitext(video_path)[0] + ".mp3"

        # Skip if output file already exists
        if os.path.exists(output_path):
            logger.info(f"Skipping existing file: {output_path}")
            return True

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # Set thread count
        if threads <= 0:
            threads = multiprocessing.cpu_count()

        # Check if FFmpeg is installed
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.error("FFmpeg is not installed. Please install FFmpeg for audio conversion.")
            return False

        # Run FFmpeg command
        cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-threads",
            str(threads),
            "-vn",  # No video
            "-b:a",
            bitrate,  # Audio bitrate
            "-c:a",
            "libmp3lame",  # MP3 codec
            "-map_metadata",
            "0",  # Copy metadata
            "-stats",  # Show progress
            "-y",  # Overwrite output
            output_path,
        ]

        logger.info(
            f"Converting: {os.path.basename(video_path)} -> {os.path.basename(output_path)}"
        )

        try:
            subprocess.run(cmd, check=True)
            logger.info(f"Successfully converted {output_path}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error converting {video_path}: {e}")
            return False

    def convert_directory(
        self,
        input_dir: str,
        output_dir: Optional[str] = None,
        bitrate: Optional[str] = None,
        threads: Optional[int] = None,
    ) -> Tuple[int, int]:
        """Process all video files in a directory and convert to audio.

        Args:
            input_dir: Directory containing video files
            output_dir: Directory to save audio files to
            bitrate: Audio bitrate
            threads: Number of FFmpeg threads to use

        Returns:
            tuple: (successful, failed) counts
        """
        # Use instance defaults if not specified
        bitrate = bitrate or self.bitrate
        threads = threads if threads is not None else self.threads

        # Find all video files
        video_files = self.find_video_files(input_dir)
        if not video_files:
            logger.info(f"No video files found in {input_dir}")
            return 0, 0

        logger.info(f"Found {len(video_files)} video files to convert")

        # Process each file
        successful = 0
        failed = 0

        for i, video_path in enumerate(video_files, 1):
            try:
                # Determine output path
                if output_dir:
                    rel_path = os.path.relpath(video_path, input_dir)
                    output_path = os.path.join(output_dir, os.path.splitext(rel_path)[0] + ".mp3")
                else:
                    output_path = os.path.splitext(video_path)[0] + ".mp3"

                # Convert the file
                logger.info(f"Processing {i}/{len(video_files)}: {os.path.basename(video_path)}")
                if self.convert_file(video_path, output_path, bitrate, threads):
                    successful += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"Unexpected error processing {video_path}: {e}")
                failed += 1

        logger.info(f"Conversion completed: {successful} successful, {failed} failed")
        return successful, failed

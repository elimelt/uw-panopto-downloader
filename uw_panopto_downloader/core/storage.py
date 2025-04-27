"""Storage management for UW Panopto Downloader."""

import os
import shutil
from pathlib import Path
from typing import Optional, Tuple

from ..utils.file import clean_filename, ensure_directory, get_file_size
from ..utils.logging import get_logger

logger = get_logger(__name__)


class StorageManager:
    """Manages file storage with symlinks for UW Panopto Downloader."""

    def __init__(self, storage_dir: Optional[str] = None):
        """Initialize the storage manager.

        Args:
            storage_dir: Directory to store content (defaults to ~/.uw-panopto-downloader/content)
        """
        base_dir = storage_dir or os.path.join(Path.home(), ".uw-panopto-downloader")
        self.content_dir = os.path.join(base_dir, "content")

        # create subdirectories for different content types
        self.video_dir = os.path.join(self.content_dir, "videos")
        self.audio_dir = os.path.join(self.content_dir, "audio")
        self.transcript_dir = os.path.join(self.content_dir, "transcripts")

        ensure_directory(self.content_dir)
        ensure_directory(self.video_dir)
        ensure_directory(self.audio_dir)
        ensure_directory(self.transcript_dir)

    def store_video(self, source_path: str, title: str) -> Tuple[str, int]:
        """Store a video file and create a symlink.

        Args:
            source_path: Path to the source video file
            title: Video title for naming

        Returns:
            tuple: (stored_path, file_size)
        """
        if not os.path.exists(source_path):
            logger.error(f"Source file does not exist: {source_path}")
            return ("", 0)

        clean_title = clean_filename(title)
        ext = os.path.splitext(source_path)[1].lower()

        # generate a unique filename
        target_filename = f"{clean_title}{ext}"
        target_path = os.path.join(self.video_dir, target_filename)

        # if file with same name exists, add a number
        counter = 1
        while os.path.exists(target_path):
            target_filename = f"{clean_title}_{counter}{ext}"
            target_path = os.path.join(self.video_dir, target_filename)
            counter += 1

        try:
            # copy file (RIP your Disk Space 😅)
            shutil.copy2(source_path, target_path)
            file_size = get_file_size(target_path) or 0

            logger.info(f"Stored video: {target_path}")
            return (target_path, file_size)
        except Exception as e:
            logger.error(f"Error storing video: {e}")
            return ("", 0)

    def store_audio(self, source_path: str, title: str) -> str:
        """Store an audio file and create a symlink.

        Args:
            source_path: Path to the source audio file
            title: Audio title for naming

        Returns:
            str: Path to the stored audio file
        """
        if not os.path.exists(source_path):
            logger.error(f"Source file does not exist: {source_path}")
            return ""

        clean_title = clean_filename(title)
        ext = os.path.splitext(source_path)[1].lower()

        target_filename = f"{clean_title}{ext}"
        target_path = os.path.join(self.audio_dir, target_filename)

        counter = 1
        while os.path.exists(target_path):
            target_filename = f"{clean_title}_{counter}{ext}"
            target_path = os.path.join(self.audio_dir, target_filename)
            counter += 1

        try:
            shutil.copy2(source_path, target_path)

            logger.info(f"Stored audio: {target_path}")
            return target_path
        except Exception as e:
            logger.error(f"Error storing audio: {e}")
            return ""

    def store_transcript(self, source_path: str, title: str) -> Tuple[str, str]:
        """Store a transcript file and create a symlink.

        Args:
            source_path: Path to the source transcript file
            title: Transcript title for naming

        Returns:
            tuple: (stored_path, content)
        """
        if not os.path.exists(source_path):
            logger.error(f"Source file does not exist: {source_path}")
            return ("", "")

        clean_title = clean_filename(title)
        ext = os.path.splitext(source_path)[1].lower()

        target_filename = f"{clean_title}{ext}"
        target_path = os.path.join(self.transcript_dir, target_filename)

        counter = 1
        while os.path.exists(target_path):
            target_filename = f"{clean_title}_{counter}{ext}"
            target_path = os.path.join(self.transcript_dir, target_filename)
            counter += 1

        try:
            shutil.copy2(source_path, target_path)

            content = ""
            with open(target_path, encoding="utf-8") as f:
                content = f.read()

            logger.info(f"Stored transcript: {target_path}")
            return (target_path, content)
        except Exception as e:
            logger.error(f"Error storing transcript: {e}")
            return ("", "")

    def create_symlink(self, real_path: str, link_path: str) -> bool:
        """Create a symbolic link.

        Args:
            real_path: Path to the real file
            link_path: Path where the symlink should be created

        Returns:
            bool: Whether creation was successful
        """
        try:
            ensure_directory(os.path.dirname(link_path))

            if os.path.islink(link_path):
                os.unlink(link_path)

            os.symlink(real_path, link_path)
            logger.info(f"Created symlink: {link_path} -> {real_path}")
            return True
        except FileExistsError:
            logger.warning(f"Already performed copy, skipping symlink creation: {link_path}")
            return False
        except Exception as e:
            logger.error(f"Error creating symlink: {e}")
            return False

    def delete_file(self, file_path: str) -> bool:
        """Delete a file from storage.

        Args:
            file_path: Path to the file to delete

        Returns:
            bool: Whether deletion was successful
        """
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"File does not exist: {file_path}")
            return True  # consider it a success if file doesn't exist

        try:
            os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False


# singleton storage manager instance
storage = StorageManager()

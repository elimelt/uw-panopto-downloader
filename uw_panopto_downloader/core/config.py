"""Configuration management for Panopto Downloader."""

import json
from pathlib import Path
from typing import Any, ClassVar, Dict


class Config:
    """Configuration manager for Panopto Downloader."""

    DEFAULT_CONFIG: ClassVar = {
        "download_dir": "downloads",
        "max_workers": 3,
        "headless": False,
        "audio_bitrate": "192k",
        "ffmpeg_threads": 0,
    }

    def __init__(self):
        """Initialize with default configuration."""
        self.config_dir = Path.home() / ".uw-panopto-downloader"
        self.config_file = self.config_dir / "config.json"
        self.settings = self.DEFAULT_CONFIG.copy()
        self._load()

    def _load(self) -> None:
        """Load configuration from file."""
        if not self.config_file.exists():
            self._save()
            return

        try:
            with open(self.config_file) as f:
                loaded_config = json.load(f)
                self.settings.update(loaded_config)
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to load config file: {e}")

    def _save(self) -> None:
        """Save configuration to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.settings, f, indent=2)
        except OSError as e:
            print(f"Warning: Failed to save config file: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and save."""
        self.settings[key] = value
        self._save()

    def update(self, settings: Dict[str, Any]) -> None:
        """Update multiple configuration values and save."""
        self.settings.update(settings)
        self._save()

    @property
    def download_dir(self) -> str:
        """Get the download directory."""
        return self.settings["download_dir"]

    @download_dir.setter
    def download_dir(self, value: str) -> None:
        """Set the download directory."""
        self.settings["download_dir"] = value
        self._save()

    @property
    def max_workers(self) -> int:
        """Get the maximum number of concurrent workers."""
        return self.settings["max_workers"]

    @max_workers.setter
    def max_workers(self, value: int) -> None:
        """Set the maximum number of concurrent workers."""
        self.settings["max_workers"] = value
        self._save()

    @property
    def headless(self) -> bool:
        """Get the headless browser setting."""
        return self.settings["headless"]

    @headless.setter
    def headless(self, value: bool) -> None:
        """Set the headless browser setting."""
        self.settings["headless"] = value
        self._save()

    @property
    def audio_bitrate(self) -> str:
        """Get the audio bitrate for conversion."""
        return self.settings["audio_bitrate"]

    @audio_bitrate.setter
    def audio_bitrate(self, value: str) -> None:
        """Set the audio bitrate for conversion."""
        self.settings["audio_bitrate"] = value
        self._save()

    @property
    def ffmpeg_threads(self) -> int:
        """Get the number of threads for FFmpeg."""
        return self.settings["ffmpeg_threads"]

    @ffmpeg_threads.setter
    def ffmpeg_threads(self, value: int) -> None:
        """Set the number of threads for FFmpeg."""
        self.settings["ffmpeg_threads"] = value
        self._save()


config = Config()

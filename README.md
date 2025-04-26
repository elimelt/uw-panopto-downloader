# UW Panopto Downloader

A Python tool for downloading videos from UW Panopto and optionally converting them to audio format.

## Features

- Interactive browser-based login to access your Panopto content
- Extract video links from Panopto course pages
- Concurrent downloading of multiple videos
- Video to audio conversion (MP4 to MP3)
- User-friendly command line interface with rich formatting
- Configurable settings saved between sessions

## Installation

```bash
# From PyPI
pip install uw-panopto-downloader

# From source
git clone https://github.com/elimelt/uw-panopto-downloader.git
cd uw-panopto-downloader
pip install -e .
```

## Requirements

- Python 3.11 or higher
- FFmpeg (for video downloads and conversion)
- Chrome or Chromium browser (for Selenium)

## Usage

### Command Line Interface

The package provides a command-line tool `uwpd` with several subcommands:

```bash
# Show help
uwpd --help

# Download videos
uwpd download [OPTIONS]

# Convert videos to audio
uwpd convert [INPUT] [OPTIONS]

# View or update configuration
uwpd config [OPTIONS]

# Show version
uwpd version
```

### Download Command

```bash
# Start an interactive download session
uwpd download

# Specify a starting URL
uwpd download --url "https://panopto.uw.edu/your-course-page"

# Set output directory
uwpd download --output "path/to/downloads"

# Set number of concurrent downloads
uwpd download --workers 5

# Run in headless mode (no browser window)
uwpd download --headless
```

### Convert Command

```bash
# Convert a single video
uwpd convert video.mp4

# Convert with output path
uwpd convert video.mp4 --output audio.mp3

# Convert a directory of videos
uwpd convert videos_dir/ --output audio_dir/

# Set audio bitrate
uwpd convert video.mp4 --bitrate 320k

# Set number of FFmpeg threads
uwpd convert video.mp4 --threads 4
```

### Config Command

```bash
# Show current configuration
uwpd config --show

# Update configuration
uwpd config --download-dir "path/to/downloads" --max-workers 4
```

## Python API

You can also use the package programmatically:

```python
from uw_panopto_downloader.core import BrowserSession, PanoptoDownloader, VideoConverter

# Initialize a browser session
browser = BrowserSession(headless=False)
browser.manual_login("https://panopto.uw.edu/your-course-page")

# Download videos
downloader = PanoptoDownloader(browser, max_workers=3)
video_links = browser.extract_links()
downloader.download_videos(video_links, "downloads")

# Convert videos to audio
converter = VideoConverter(bitrate="192k")
converter.convert_directory("downloads", "audio")
```

## Configuration

The configuration is stored in `~/.uw-panopto-downloader/config.json` and includes:

- `download_dir`: Default download directory
- `max_workers`: Maximum number of concurrent downloads
- `headless`: Whether to run the browser in headless mode
- `audio_bitrate`: Default audio bitrate for conversion
- `ffmpeg_threads`: Default number of FFmpeg threads

## License

This project is licensed under the MIT License - see the LICENSE file for details.
# UW Panopto Downloader

A Python library and CLI tool for downloading and processing videos from University of Washington's Panopto. Use at your own risk!

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)

## Overview

Tired of taking classes and forgetting everything the next quarter? Tired of having to rewatch the same lecture over and over again only for a few key points? Scared of graduating and losing access to all this institutional knowledge? UW Panopto Downloader might be just what you're looking for!

### Key Features

- **Video Downloads**: Log in to Panopto and batch download videos from course pages
- **Audio Conversion**: Convert videos to audio format for efficient storage and mobile listening
- **Transcription**: Generate accurate transcripts with timestamps either locally using OpenAI's Whisper or Google Cloud Speech-to-Text
- **Metadata Management**: Organize videos with tags, notes, and searchable transcripts
- **Store Locally**: Keep all your videos, audio, and transcripts in a structured format on your local machine with a SQLite database for metadata indexing

## Installation

```bash
pip install uw-panopto-downloader
```

### Requirements

- Python 3.12 (exactly 3.12 if you want any hope of using the Whisper model)
- FFmpeg installed on your system
- Google Cloud credentials (for transcription features)

## Quick Start

### Downloading Videos

```bash
uwpd download --url "https://uw.hosted.panopto.com/Panopto/Pages/Sessions/List.aspx#folderID=..."
```

### Converting Videos to Audio

```bash
uwpd convert path/to/videos
```

### Transcribing Audio with Google Cloud

```bash
uwpd cloud-transcribe path/to/audio.mp3 --language en-US
```

### Transcribing Audio with Local Whisper Model

```bash
uwpd transcribe path/to/audio.mp3
```

### Searching Transcripts

```bash
uwpd db search "neural networks" --transcript
```

## Command Reference

The CLI is organized into the following main commands:

### Core Commands

| Command | Description |
|---------|-------------|
| `download` | Download videos from UW Panopto |
| `convert` | Convert video files to audio format |
| `cloud-transcribe` | Transcribe audio files using Google Cloud Speech-to-Text |
| `transcribe` | Transcribe audio files using local Whisper model |
| `config` | View or update configuration |
| `version` | Show the current version |

### Database Commands

| Command | Description |
|---------|-------------|
| `db list` | List videos in the database |
| `db search` | Search videos in the database |
| `db info` | Display detailed information about a video |
| `db tag` | Add or remove a tag for a video |
| `db tags` | List all available tags with usage count |
| `db delete` | Delete a video from the database |
| `db note` | Add or update a note for a video |
| `db stats` | Show database statistics |
| `db migrate` | Migrate existing files to the database |

## Detailed Usage

### Downloading Videos

```bash
uwpd download --url "https://uw.hosted.panopto.com/Panopto/Pages/Sessions/List.aspx#folderID=..." \
              --output ~/Videos/CSE142 \
              --workers 3 \
              --headless
```

This command will:
1. Open a browser window for you to log in
2. After login, automatically extract available videos
3. Prompt confirmation before downloading
4. Use 3 concurrent downloads for speed
5. Store metadata in the local database

### Google Cloud Speech-to-Text Transcription

```bash
uwpd cloud-transcribe ~/Videos/lecture.mp3 \
                     --output ~/Transcripts/lecture.txt \
                     --language en-US \
                     --credentials path/to/google-credentials.json
```

Features:
- Automatically splits long audio into chunks separated by silence for better accuracy
- Produces timestamped transcripts for easy reference
- Stores transcripts in searchable database

## Configuration

Configuration is stored in `~/.uw-panopto-downloader/config.json`. You can update it using:

```bash
uwpd config --download-dir ~/Videos \
            --max-workers 4 \
            --headless True \
            --audio-bitrate 192k
```

## Storage Management

The tool uses a structured storage approach:
- Content is stored in `~/.uw-panopto-downloader/content/`
- Subdirectories for videos, audio, and transcripts
- Symlinks created to original locations when desired
- SQLite database tracks metadata at `~/.uw-panopto-downloader/metadata.db`

## Google Cloud Integration

This project leverages Google Cloud Speech-to-Text for high-quality transcription.

For optimal transcription quality, the tool:
1. Automatically converts audio to mono
2. Splits audio at natural silence points
3. Uses word-level time offsets for timestamps
4. Assembles chunks into a cohesive transcript

## Development

To contribute to this project:

```bash
git clone https://github.com/elimelt/uw-panopto-downloader.git
cd uw-panopto-downloader
pip install -e ".[dev]"
```

### Bumping Version

Use the provided script to bump the version before pushing changes/merging PRs (only for maintainers):

```bash
./bump-version.sh patch  # or minor or major
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Created by Elijah Melton (elimelt@uw.edu)
- Submitted for SWECCathon 2025!
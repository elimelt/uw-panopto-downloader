"""Main entry point for the UW Panopto Downloader CLI application."""

from importlib import metadata
from typing import Optional

import typer
from rich.console import Console

from ..core.config import config
from .convert import convert_command
from .download import download_command
from .gcp import cloud_transcribe_command
from .utils import check_dependencies, print_header, print_info, print_warning

app = typer.Typer(
    name="uwpd",
    help="Download and convert videos from UW Panopto",
    add_completion=False,
)

console = Console()


@app.callback()
def callback() -> None:
    """UW Panopto Downloader - A tool for downloading and converting Panopto videos."""

    check_dependencies()


@app.command("download", help="Download videos from UW Panopto")
def download(
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Starting URL for download"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
    workers: Optional[int] = typer.Option(
        None, "--workers", "-w", help="Number of concurrent downloads"
    ),
    headless: Optional[bool] = typer.Option(
        None, "--headless", help="Run browser in headless mode"
    ),
) -> None:
    """Download videos from UW Panopto."""
    download_command(url, output, workers, headless)


@app.command("convert", help="Convert video files to audio format")
def convert(
    input_path: str = typer.Argument(..., help="Input video file or directory"),
    output_path: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output directory or file"
    ),
    bitrate: Optional[str] = typer.Option(
        None, "--bitrate", "-b", help="Audio bitrate (e.g. 192k)"
    ),
    threads: Optional[int] = typer.Option(
        None, "--threads", "-t", help="Number of FFmpeg threads (0=auto)"
    ),
) -> None:
    """Convert video files to audio format."""
    convert_command(input_path, output_path, bitrate, threads)


@app.command("transcribe", help="Transcribe audio files to text")
def transcribe(
    input_path: str = typer.Argument(..., help="Input audio file"),
    output_path: Optional[str] = typer.Option(
        "transcript.txt", "--output", "-o", help="Output text file"
    ),
    model: Optional[str] = typer.Option(
        "turbo", "--model", "-m", help="Whisper model name (e.g. tiny, base, small, medium, large)"
    ),
) -> None:
    """Transcribe audio files to text."""
    from ..core.transcriber import transcribe_command

    transcribe_command(input_path, output_path, model)


@app.command("config", help="View or update configuration")
def config_command(
    download_dir: Optional[str] = typer.Option(
        None, "--download-dir", help="Set default download directory"
    ),
    max_workers: Optional[int] = typer.Option(
        None, "--max-workers", help="Set default number of concurrent downloads"
    ),
    headless: Optional[bool] = typer.Option(
        None, "--headless", help="Set default headless browser mode"
    ),
    audio_bitrate: Optional[str] = typer.Option(
        None, "--audio-bitrate", help="Set default audio bitrate"
    ),
    ffmpeg_threads: Optional[int] = typer.Option(
        None, "--ffmpeg-threads", help="Set default FFmpeg threads"
    ),
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
) -> None:
    """View or update configuration."""

    if download_dir is not None:
        config.download_dir = download_dir
    if max_workers is not None:
        config.max_workers = max_workers
    if headless is not None:
        config.headless = headless
    if audio_bitrate is not None:
        config.audio_bitrate = audio_bitrate
    if ffmpeg_threads is not None:
        config.ffmpeg_threads = ffmpeg_threads

    if show or all(
        param is None
        for param in [download_dir, max_workers, headless, audio_bitrate, ffmpeg_threads]
    ):
        print_header("Current Configuration")
        print_info(f"Download directory: {config.download_dir}")
        print_info(f"Max concurrent downloads: {config.max_workers}")
        print_info(f"Headless browser mode: {config.headless}")
        print_info(f"Audio bitrate: {config.audio_bitrate}")
        print_info(f"FFmpeg threads: {config.ffmpeg_threads}")

        print_info(f"Config file: {config.config_file}")


@app.command("cloud-transcribe", help="Transcribe audio files using Google Cloud Speech-to-Text")
def cloud_transcribe(
    input_path: str = typer.Argument(..., help="Input audio file or directory"),
    output_path: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file or directory for transcriptions"
    ),
    language_code: str = typer.Option(
        "en-US", "--language", "-l", help="Language code (e.g., en-US, fr-FR)"
    ),
    credentials_path: Optional[str] = typer.Option(
        None, "--credentials", "-c", help="Path to GCP credentials JSON file"
    ),
) -> None:
    """Transcribe audio files using Google Cloud Speech-to-Text."""
    cloud_transcribe_command(input_path, output_path, language_code, credentials_path)


@app.command("version")
def version():
    """Show the current version of UW Panopto Downloader."""
    try:
        version = metadata.version("uw-panopto-downloader")
        print_header(f"UW Panopto Downloader v{version}")
    except metadata.PackageNotFoundError:
        print_warning("Version information not available (running in development mode)")


if __name__ == "__main__":
    app()

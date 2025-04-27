"""Main entry point for the UW Panopto Downloader CLI application."""

from importlib import metadata
from typing import Optional

import typer
from rich.console import Console

from ..core.config import config
from .convert import convert_command
from .download import download_command
from .gcp import cloud_transcribe_command
from .query import (
    add_note_command,
    delete_video_command,
    list_tags_command,
    list_videos_command,
    migrate_command,
    search_videos_command,
    stats_command,
    tag_video_command,
    video_info_command,
)
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
    store: bool = typer.Option(
        True, "--store/--no-store", help="Store in database and create symlinks"
    ),
) -> None:
    """Download videos from UW Panopto."""
    download_command(url, output, workers, headless, store)


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
    store: bool = typer.Option(
        True, "--store/--no-store", help="Store in database and create symlinks"
    ),
) -> None:
    """Convert video files to audio format."""
    convert_command(input_path, output_path, bitrate, threads, store)


@app.command("transcribe", help="Transcribe audio files to text")
def transcribe(
    input_path: str = typer.Argument(..., help="Input audio file"),
    output_path: Optional[str] = typer.Option(
        "transcript.txt", "--output", "-o", help="Output text file"
    ),
    model: Optional[str] = typer.Option(
        "turbo", "--model", "-m", help="Whisper model name (e.g. tiny, base, small, medium, large)"
    ),
    store: bool = typer.Option(
        True, "--store/--no-store", help="Store in database and create symlinks"
    ),
) -> None:
    """Transcribe audio files to text."""
    from ..core.transcriber import transcribe_command

    transcribe_command(input_path, output_path, model, store=store)


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
    store: bool = typer.Option(
        True, "--store/--no-store", help="Store in database and create symlinks"
    ),
) -> None:
    """Transcribe audio files using Google Cloud Speech-to-Text."""
    cloud_transcribe_command(input_path, output_path, language_code, credentials_path, store)


@app.command("version")
def version():
    """Show the current version of UW Panopto Downloader."""
    try:
        version = metadata.version("uw-panopto-downloader")
        print_header(f"UW Panopto Downloader v{version}")
    except metadata.PackageNotFoundError:
        print_warning("Version information not available (running in development mode)")


db_app = typer.Typer(help="Database management commands")
app.add_typer(db_app, name="db")


@db_app.command("list", help="List videos in the database")
def list_videos(
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of videos to list"),
    offset: int = typer.Option(0, "--offset", "-o", help="Offset for pagination"),
    all_videos: bool = typer.Option(False, "--all", "-a", help="List all videos"),
    order_by: str = typer.Option(
        "date_added", "--order", "-r", help="Field to order by (date_added, title, size, duration)"
    ),
    asc: bool = typer.Option(False, "--asc", help="Sort in ascending order"),
):
    """List videos in the database."""
    list_videos_command(limit, offset, all_videos, order_by, asc)


@db_app.command("search", help="Search videos in the database")
def search_videos(
    query: str = typer.Argument(..., help="Search query"),
    transcript: bool = typer.Option(False, "--transcript", "-t", help="Search in transcripts"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of results to show"),
    context_lines: int = typer.Option(
        1, "--context", "-c", help="Number of context lines to show for each result"
    ),
):
    """Search videos in the database."""
    search_videos_command(query, transcript, limit, context_lines)


@db_app.command("info", help="Display detailed information about a video")
def video_info(
    video_id: int = typer.Argument(..., help="Video ID"),
):
    """Display detailed information about a video."""
    video_info_command(video_id)


@db_app.command("tag", help="Add or remove a tag for a video")
def tag_video(
    video_id: int = typer.Argument(..., help="Video ID"),
    tag_name: str = typer.Argument(..., help="Tag name"),
    remove: bool = typer.Option(
        False, "--remove", "-r", help="Remove the tag instead of adding it"
    ),
):
    """Add or remove a tag for a video."""
    tag_video_command(video_id, tag_name, remove)


@db_app.command("tags", help="List all available tags with usage count")
def list_tags():
    """List all available tags with usage count."""
    list_tags_command()


@db_app.command("delete", help="Delete a video from the database")
def delete_video(
    video_id: int = typer.Argument(..., help="Video ID"),
    files: bool = typer.Option(False, "--files", "-f", help="Also delete associated files"),
):
    """Delete a video from the database."""
    delete_video_command(video_id, files)


@db_app.command("note", help="Add or update a note for a video")
def add_note(
    video_id: int = typer.Argument(..., help="Video ID"),
    note: str = typer.Argument(..., help="Note to add"),
):
    """Add or update a note for a video."""
    add_note_command(video_id, note)


@db_app.command("stats", help="Show database statistics")
def stats():
    """Show database statistics."""
    stats_command()


@db_app.command("migrate", help="Migrate existing files to the database")
def migrate(
    video_dir: str = typer.Argument(..., help="Video directory to migrate"),
    audio_dir: Optional[str] = typer.Option(
        None, "--audio", "-a", help="Audio directory to migrate"
    ),
    transcript_dir: Optional[str] = typer.Option(
        None, "--transcript", "-t", help="Transcript directory to migrate"
    ),
):
    """Migrate existing files to the database."""
    migrate_command(video_dir, audio_dir, transcript_dir)


if __name__ == "__main__":
    app()

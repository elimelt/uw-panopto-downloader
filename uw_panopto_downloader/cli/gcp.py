"""Cloud transcription command for the CLI interface."""

import os
import time
from typing import Optional

import typer
from rich.console import Console

from ..core.config import config
from ..core.database import db
from ..core.gcp_transcriber import GCPTranscriber
from ..core.storage import storage
from ..utils.file import ensure_directory
from ..utils.logging import get_logger
from .utils import (
    confirm_action,
    create_progress_bar,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
)

logger = get_logger(__name__)
console = Console()


def cloud_transcribe_command(  # noqa: PLR0915
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
    store: bool = True,
) -> None:
    """Transcribe audio files using Google Cloud Speech-to-Text.

    Large files are automatically split into chunks based on silence detection for better accuracy.
    """

    if not os.path.exists(input_path):
        print_error(f"Input path does not exist: {input_path}")
        return

    credentials_config = config.get("gcp_credentials", credentials_path)
    config.set("gcp_credentials", credentials_config)

    print_header("Google Cloud Speech-to-Text Transcriber")
    print_info(f"Input: {input_path}")
    print_info(f"Output: {output_path or 'Same as input with .txt extension'}")
    print_info(f"Language: {language_code}")
    print_info(f"Credentials: {credentials_path or 'Using application default credentials'}")
    print_info("Note: Audio files will be automatically:")
    print_info("  - Converted to mono if stereo")
    print_info("  - Split into chunks ≤ 45 seconds based on silence detection")
    print_info("  - Transcribed with word time offsets")

    if store:
        print_info("Database storage: Enabled")
        if not db.connect():
            print_warning(
                "Failed to connect to database. Files will be transcribed but not indexed."
            )
            store = False
    else:
        print_info("Database storage: Disabled")

    if not confirm_action("Proceed with transcription?"):
        print_info("Transcription cancelled")
        return

    transcriber = GCPTranscriber(credentials_path)

    start_time = time.time()

    if os.path.isdir(input_path):

        if not output_path:
            output_path = os.path.join(os.path.dirname(input_path), "transcripts")

        ensure_directory(output_path)

        print_info(f"Searching for audio files in {input_path}...")

        audio_files = []
        for root, _, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith((".mp3", ".wav", ".flac", ".ogg", ".mp4")):
                    audio_files.append(os.path.join(root, file))

        if not audio_files:
            print_warning(f"No audio files found in {input_path}")
            return

        print_info(f"Found {len(audio_files)} audio files to transcribe")

        if not confirm_action("Proceed with transcription?"):
            print_info("Transcription cancelled")
            return

        with create_progress_bar() as progress:
            task = progress.add_task("[cyan]Transcribing audio...", total=len(audio_files))
            successful, failed = [], []

            for i, audio_path in enumerate(audio_files):
                try:
                    rel_path = os.path.relpath(audio_path, input_path)
                    file_output = os.path.join(output_path, os.path.splitext(rel_path)[0] + ".txt")

                    ensure_directory(os.path.dirname(file_output))

                    chunk_task = progress.add_task(
                        f"[green]Processing {os.path.basename(audio_path)}...",
                        total=100,
                        visible=True,
                    )

                    def update_chunk_progress(percent_complete):
                        nonlocal chunk_task
                        chunk_task = chunk_task or 0
                        progress.update(chunk_task, completed=percent_complete)

                    result = transcriber.transcribe(
                        audio_path,
                        file_output,
                        language_code,
                        progress_callback=update_chunk_progress,
                    )

                    progress.update(chunk_task, visible=False)

                    if not result.startswith("ERROR:"):
                        successful.append(audio_path)
                    else:
                        failed.append(audio_path)

                except Exception as e:
                    logger.error(f"Error transcribing {audio_path}: {e}")
                    failed.append(audio_path)

                progress.update(task, completed=i + 1)

        elapsed_time = time.time() - start_time
        print_header("Transcription Results")
        print_success(f"Successfully transcribed: {len(successful)}")
        if failed:
            print_warning(f"Failed: {len(failed)}")
            for failure in failed[:5]:
                print_error(f"  - {os.path.basename(failure)}")
            if len(failed) > 5:
                print_warning(f"  ... and {len(failed) - 5} more")

        print_info(f"Time elapsed: {elapsed_time:.2f} seconds")
        print_info(f"Transcriptions saved to: {output_path}")

    else:

        if not input_path.lower().endswith((".mp3", ".wav", ".flac", ".ogg", ".mp4")):
            print_warning(f"Input file does not appear to be an audio file: {input_path}")
            if not confirm_action("Continue anyway?", default=False):
                return

        if not output_path:
            output_path = os.path.splitext(input_path)[0] + ".txt"
        elif os.path.isdir(output_path):
            output_path = os.path.join(
                output_path, os.path.basename(os.path.splitext(input_path)[0]) + ".txt"
            )

        ensure_directory(os.path.dirname(output_path))

        print_info(
            f"Transcribing {os.path.basename(input_path)} to {os.path.basename(output_path)}..."
        )
        print_info("This may take a while for large files as they will be split into chunks...")

        with console.status(
            "[bold blue]Transcribing... (this may take a while)[/bold blue]"
        ) as status:
            try:
                def update_progress(percent_complete):
                    status.update(
                        f"[bold blue]Transcribing... {percent_complete:.1f}% complete[/bold blue]"
                    )

                result = transcriber.transcribe(
                    input_path, output_path, language_code, progress_callback=update_progress
                )
                success = not result.startswith("ERROR:")
            except Exception as e:
                logger.error(f"Error transcribing {input_path}: {e}")
                success = False

        elapsed_time = time.time() - start_time

        if success:
            print_success(f"Transcription completed successfully in {elapsed_time:.2f} seconds")
            print_info(f"Transcription saved to: {output_path}")

            if store:
                title = os.path.splitext(os.path.basename(input_path))[0]

                stored_path, transcript_content = storage.store_transcript(output_path, title)

                if stored_path:
                    storage.create_symlink(stored_path, output_path)

                    if db.connect():
                        try:
                            videos = db.search_videos(title)

                            if videos:
                                video_id = videos[0]["id"]
                                db.update_video(video_id, {"transcript_path": stored_path})

                                db.add_transcript(video_id, transcript_content)
                                print_info(f"Updated database entry for: {title}")
                            else:
                                video_id = db.add_video(title=title, transcript_path=stored_path)

                                db.add_transcript(video_id, transcript_content)
                                print_info(f"Added to database: {title} (ID: {video_id})")
                        finally:
                            db.close()
        else:
            print_error(f"Transcription failed after {elapsed_time:.2f} seconds")

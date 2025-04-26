"""Convert command for the CLI interface."""

import os
import time
from typing import Optional

import typer
from rich.console import Console

from ..core.converter import VideoConverter
from ..core.config import config
from ..utils.file import check_ffmpeg_installed, ensure_directory
from ..utils.logging import get_logger
from .utils import (
    print_header, print_info, print_success, print_warning, print_error,
    confirm_action, create_progress_bar
)

logger = get_logger(__name__)
console = Console()


def convert_command(
    input_path: str = typer.Argument(..., help="Input video file or directory"),
    output_path: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory or file"),
    bitrate: Optional[str] = typer.Option(None, "--bitrate", "-b", help="Audio bitrate (e.g. 192k)"),
    threads: Optional[int] = typer.Option(None, "--threads", "-t", help="Number of FFmpeg threads (0=auto)")
) -> None:
    """Convert video files to audio format."""
    # Check if FFmpeg is installed
    if not check_ffmpeg_installed():
        print_error("FFmpeg is not installed. Please install FFmpeg to convert videos.")
        print_info("You can download FFmpeg from: https://ffmpeg.org/download.html")
        return

    # Set defaults from config if not provided
    if bitrate is None:
        bitrate = config.audio_bitrate
    if threads is None:
        threads = config.ffmpeg_threads

    # Save settings to config
    config.audio_bitrate = bitrate
    config.ffmpeg_threads = threads

    # Display conversion information
    print_header("UW Panopto Video to Audio Converter")
    print_info(f"Input: {input_path}")
    print_info(f"Output: {output_path or 'Same as input with .mp3 extension'}")
    print_info(f"Audio bitrate: {bitrate}")
    print_info(f"FFmpeg threads: {threads}")

    # Initialize converter
    converter = VideoConverter(bitrate=bitrate, threads=threads)

    # Check if input exists
    if not os.path.exists(input_path):
        print_error(f"Input path does not exist: {input_path}")
        return

    # Process based on whether input is a file or directory
    start_time = time.time()

    if os.path.isdir(input_path):
        # Input is a directory
        if output_path and not os.path.exists(output_path):
            ensure_directory(output_path)

        # Find and convert videos
        video_files = converter.find_video_files(input_path)
        
        if not video_files:
            print_warning(f"No video files found in {input_path}")
            return
            
        print_info(f"Found {len(video_files)} video files to convert")
        
        if not confirm_action("Proceed with conversion?"):
            print_info("Conversion cancelled")
            return
            
        # Track progress
        with create_progress_bar() as progress:
            task = progress.add_task(f"[cyan]Converting videos...", total=len(video_files))
            successful, failed = 0, 0
            
            for i, video_path in enumerate(video_files):
                try:
                    # Determine output path
                    if output_path:
                        rel_path = os.path.relpath(video_path, input_path)
                        file_output = os.path.join(output_path, os.path.splitext(rel_path)[0] + ".mp3")
                    else:
                        file_output = os.path.splitext(video_path)[0] + ".mp3"
                        
                    # Convert the file
                    result = converter.convert_file(video_path, file_output, bitrate, threads)
                    
                    if result:
                        successful += 1
                    else:
                        failed += 1
                        
                except Exception as e:
                    logger.error(f"Error converting {video_path}: {e}")
                    failed += 1
                    
                # Update progress
                progress.update(task, completed=i+1)
                
        # Display results
        elapsed_time = time.time() - start_time
        print_header("Conversion Results")
        print_success(f"Successfully converted: {successful}")
        print_warning(f"Failed: {failed}")
        print_info(f"Time elapsed: {elapsed_time:.2f} seconds")
        
    else:
        # Input is a single file
        if not input_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            print_warning(f"Input file does not appear to be a video: {input_path}")
            if not confirm_action("Continue anyway?", default=False):
                return
                
        # Determine output path for a single file
        if not output_path:
            file_output = os.path.splitext(input_path)[0] + ".mp3"
        elif os.path.isdir(output_path):
            file_output = os.path.join(output_path, os.path.basename(os.path.splitext(input_path)[0]) + ".mp3")
        else:
            file_output = output_path
            
        # Ensure output directory exists
        ensure_directory(os.path.dirname(file_output))
        
        # Convert the file
        print_info(f"Converting {os.path.basename(input_path)} to {os.path.basename(file_output)}...")
        
        with console.status("[bold blue]Converting...[/bold blue]") as status:
            result = converter.convert_file(input_path, file_output, bitrate, threads)
            
        elapsed_time = time.time() - start_time
        
        if result:
            print_success(f"Conversion completed successfully in {elapsed_time:.2f} seconds")
        else:
            print_error(f"Conversion failed after {elapsed_time:.2f} seconds")
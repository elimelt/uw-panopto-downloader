"""Download command for the CLI interface."""

import time
from typing import Optional

import typer
from rich.console import Console

from ..core.browser import BrowserSession
from ..core.config import config
from ..core.downloader import PanoptoDownloader
from ..utils.file import ensure_directory
from ..utils.logging import get_logger
from .utils import (
    check_disk_space,
    confirm_action,
    create_progress_bar,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
    prompt_input,
)

logger = get_logger(__name__)
console = Console()


def download_command(
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Starting URL for download"),
    output: str = typer.Option(None, "--output", "-o", help="Output directory"),
    workers: Optional[int] = typer.Option(
        None, "--workers", "-w", help="Number of concurrent downloads"
    ),
    headless: Optional[bool] = typer.Option(
        None, "--headless", help="Run browser in headless mode"
    ),
) -> None:
    """Download videos from UW Panopto."""
    # Set defaults from config if not provided
    if output is None:
        output = config.download_dir
    if workers is None:
        workers = config.max_workers
    if headless is None:
        headless = config.headless

    # Save to config for future use
    config.download_dir = output
    config.max_workers = workers
    config.headless = headless

    # Check disk space
    if not check_disk_space(output):
        if not confirm_action("Continue despite low disk space?", default=False):
            print_info("Download cancelled")
            return

    # Display download information
    print_header("UW Panopto Downloader")
    print_info(f"Output directory: {output}")
    print_info(f"Concurrent downloads: {workers}")

    # Ensure output directory exists
    ensure_directory(output)

    # Initialize browser session
    browser = BrowserSession(headless=headless)
    downloader = PanoptoDownloader(browser, max_workers=workers)

    # Get starting URL if not provided
    if not url:
        url = prompt_input("Enter the Panopto URL to start with: ")

    # Interactive login
    try:
        print_info("Opening browser for login...")
        if not browser.manual_login(url):
            print_error("Failed to set up browser session")
            return

        download_loop(browser, downloader, output)

    except KeyboardInterrupt:
        print_warning("\nProcess interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print_error(f"An error occurred: {e}")
    finally:
        browser.close()
        print_success("\nBrowser session closed. Goodbye!")


def download_loop(browser: BrowserSession, downloader: PanoptoDownloader, output_dir: str) -> None:
    """Main download loop for multiple jobs.

    Args:
        browser: The browser session
        downloader: The downloader instance
        output_dir: Default output directory
    """
    while True:
        # Extract links from current page
        with console.status("[bold blue]Extracting video links...[/bold blue]"):
            video_links = browser.extract_links()

        if not video_links:
            print_warning("No video links found on the current page.")
            if not confirm_action("Would you like to navigate to another page?"):
                break

            new_url = prompt_input("Enter the URL to navigate to: ")
            if not browser.navigate_to(new_url):
                print_error("Failed to navigate to new URL")
                break
            continue

        print_success(f"Found {len(video_links)} videos.")

        # Show sample links
        console.print("\n[bold]Sample videos:[/bold]")
        for i, (_, title) in enumerate(video_links[:3], 1):
            console.print(f"  {i}. {title}")

        if len(video_links) > 3:
            console.print(f"  ... and {len(video_links) - 3} more")

        if not confirm_action("\nProceed with download?"):
            print_info("Download canceled")
        else:
            # Ask for output directory for this job
            job_output_dir = prompt_input(
                f"Enter output directory for this job (default: {output_dir}): ", default=output_dir
            )

            # Process and download videos
            print_header(f"Downloading {len(video_links)} videos to {job_output_dir}...")

            with create_progress_bar() as progress:
                task = progress.add_task("[cyan]Downloading videos...", total=len(video_links))

                # Track progress in a separate thread
                start_time = time.time()
                successful, failed = 0, 0

                # Set up download monitoring
                def update_progress(success: bool, task_id) -> None:
                    nonlocal successful, failed
                    if success:
                        successful += 1
                    else:
                        failed += 1
                    progress.update(task, completed=successful + failed)  # noqa: B023

                # Download videos and update progress
                for video_info in video_links:
                    result = downloader.download_video(video_info, job_output_dir)
                    update_progress(result, task)

            elapsed_time = time.time() - start_time

            print_header("Download Results")
            print_success(f"Successfully downloaded: {successful}")
            print_warning(f"Failed: {failed}")
            print_info(f"Time elapsed: {elapsed_time:.2f} seconds")

        # Ask if user wants to navigate to another page
        if not confirm_action("\nWould you like to navigate to another page?"):
            break

        new_url = prompt_input("Enter the URL to navigate to: ")
        if not browser.navigate_to(new_url):
            print_error("Failed to navigate to new URL")
            break

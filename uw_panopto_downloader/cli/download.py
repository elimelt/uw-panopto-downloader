"""Download command for the CLI interface."""

import os
import time
from typing import Optional, Tuple

import typer
from rich.console import Console

from ..core.browser import BrowserSession
from ..core.config import config
from ..core.database import db
from ..core.downloader import PanoptoDownloader
from ..core.storage import storage
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
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
    workers: Optional[int] = typer.Option(
        None, "--workers", "-w", help="Number of concurrent downloads"
    ),
    headless: Optional[bool] = typer.Option(
        None, "--headless", help="Run browser in headless mode"
    ),
    store: bool = True,
) -> None:
    """Download videos from UW Panopto."""

    if output is None:
        output = config.download_dir
    if workers is None:
        workers = config.max_workers
    if headless is None:
        headless = config.headless

    config.download_dir = output
    config.max_workers = workers
    config.headless = headless

    if not check_disk_space(output):
        if not confirm_action("Continue despite low disk space?", default=False):
            print_info("Download cancelled")
            return

    print_header("UW Panopto Downloader")
    print_info(f"Output directory: {output}")
    print_info(f"Concurrent downloads: {workers}")

    if store:
        print_info("Database storage: Enabled")
        if not db.connect():
            print_warning(
                "Failed to connect to database. Videos will be downloaded but not indexed."
            )
            store = False
    else:
        print_info("Database storage: Disabled")

    ensure_directory(output)

    browser = BrowserSession(headless=headless)
    downloader = PanoptoDownloader(browser, max_workers=workers)

    if not url:
        url = prompt_input("Enter the Panopto URL to start with: ")

    try:
        print_info("Opening browser for login...")
        if not browser.manual_login(url):
            print_error("Failed to set up browser session")
            return

        download_loop(browser, downloader, output, store)

    except KeyboardInterrupt:
        print_warning("\nProcess interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print_error(f"An error occurred: {e}")
    finally:
        if store:
            db.close()
        browser.close()
        print_success("\nBrowser session closed. Goodbye!")


def download_loop(  # noqa: PLR0915
    browser: BrowserSession, downloader: PanoptoDownloader, output_dir: str, store: bool = True
) -> None:
    """Main download loop for multiple jobs.

    Args:
        browser: The browser session
        downloader: The downloader instance
        output_dir: Default output directory
        store: Whether to store in database
    """
    while True:

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

        console.print("\n[bold]Sample videos:[/bold]")
        for i, (_, title) in enumerate(video_links[:3], 1):
            console.print(f"  {i}. {title}")

        if len(video_links) > 3:
            console.print(f"  ... and {len(video_links) - 3} more")

        if not confirm_action("\nProceed with download?"):
            print_info("Download canceled")
        else:

            job_output_dir = prompt_input(
                f"Enter output directory for this job (default: {output_dir}): ", default=output_dir
            )

            print_header(f"Downloading {len(video_links)} videos to {job_output_dir}...")

            with create_progress_bar() as progress:
                task = progress.add_task("[cyan]Downloading videos...", total=len(video_links))

                start_time = time.time()
                successful, failed = 0, 0

                def handle_download_result(
                    url, result: Tuple[bool, str, Optional[str], int]
                ) -> None:
                    nonlocal successful, failed, job_output_dir
                    success, video_path, video_id, file_size = result

                    if success:
                        successful += 1

                        if store and video_path:
                            title = os.path.splitext(os.path.basename(video_path))[0]
                            job_output_dir = job_output_dir or config.download_dir
                            if job_output_dir != storage.video_dir:
                                # store in content directory with symlink
                                stored_path, stored_size = storage.store_video(video_path, title)

                                if stored_path:
                                    storage.create_symlink(stored_path, video_path)

                                    db.add_video(
                                        title=title,
                                        url=url,
                                        video_id=video_id,
                                        video_path=stored_path,
                                        size=stored_size,
                                    )
                            else:
                                # already in content directory
                                # just add to db
                                db.add_video(
                                    title=title,
                                    url=url,
                                    video_id=video_id,
                                    video_path=video_path,
                                    size=file_size,
                                )
                    else:
                        failed += 1

                    progress.update(task, completed=successful + failed)  # noqa: B023

                for video_info in video_links:
                    result = downloader.download_video(video_info, job_output_dir)
                    handle_download_result(video_info[0], result)

            elapsed_time = time.time() - start_time

            print_header("Download Results")
            print_success(f"Successfully downloaded: {successful}")
            print_warning(f"Failed: {failed}")
            print_info(f"Time elapsed: {elapsed_time:.2f} seconds")

        if not confirm_action("\nWould you like to navigate to another page?"):
            break

        new_url = prompt_input("Enter the URL to navigate to: ")
        if not browser.navigate_to(new_url):
            print_error("Failed to navigate to new URL")
            break

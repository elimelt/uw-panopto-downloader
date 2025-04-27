"""Utility functions for the CLI interface."""

from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ..utils.file import check_ffmpeg_installed, format_size, get_available_space
from ..utils.logging import get_logger

logger = get_logger(__name__)
console = Console()


def print_header(text: str) -> None:
    """Print a styled header.

    Args:
        text: Header text
    """
    console.print()
    console.print(Panel(text, style="bold blue"))
    console.print()


def print_info(text: str) -> None:
    """Print styled info text.

    Args:
        text: Info text
    """
    console.print(f"[blue]i[/blue] {text}")


def print_success(text: str) -> None:
    """Print styled success text.

    Args:
        text: Success text
    """
    console.print(f"[green]✅[/green] {text}")


def print_warning(text: str) -> None:
    """Print styled warning text.

    Args:
        text: Warning text
    """
    console.print(f"[yellow]⚠️[/yellow] {text}")


def print_error(text: str) -> None:
    """Print styled error text.

    Args:
        text: Error text
    """
    console.print(f"[red]❌[/red] {text}")


def confirm_action(prompt: str = "Do you want to proceed?", default: bool = True) -> bool:
    """Prompt for user confirmation.

    Args:
        prompt: Prompt text
        default: Default response

    Returns:
        bool: User response
    """
    return Confirm.ask(prompt, default=default)


def prompt_input(prompt: str, default: Optional[str] = None) -> str:
    """Prompt for user input with optional default.

    Args:
        prompt: Prompt text
        default: Default value

    Returns:
        str: User input
    """
    return Prompt.ask(prompt, default=default or "")


def create_progress_bar() -> Progress:
    """Create a styled progress bar.

    Returns:
        Progress: Rich progress bar
    """
    return Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def display_file_list(files: List[Dict[str, Any]], title: str = "Files") -> None:
    """Display a list of files in a table.

    Args:
        files: List of file info dictionaries
        title: Table title
    """
    table = Table(title=title)
    table.add_column("#", style="dim")
    table.add_column("Filename", style="blue")
    table.add_column("Size", style="green", justify="right")

    for i, file_info in enumerate(files, 1):
        size = format_size(file_info.get("size", 0)) if file_info.get("size") else "Unknown"
        table.add_row(str(i), file_info["name"], size)

    console.print(table)


def check_dependencies() -> bool:
    """Check if all required dependencies are installed.

    Returns:
        bool: Whether all dependencies are satisfied
    """
    all_ok = True

    if not check_ffmpeg_installed():
        print_warning(
            "FFmpeg is not installed. Video downloads and conversions may not work correctly."
        )
        print_info("You can install FFmpeg from: https://ffmpeg.org/download.html")
        all_ok = False

    return all_ok


def check_disk_space(directory: str, required_mb: int = 500) -> bool:
    """Check if there's sufficient disk space.

    Args:
        directory: Directory to check
        required_mb: Required space in MB

    Returns:
        bool: Whether there's sufficient space
    """
    required_bytes = required_mb * 1024 * 1024
    available = get_available_space(directory)

    if available is None:
        print_warning(f"Could not determine available disk space for {directory}")
        return True

    if available < required_bytes:
        print_warning(
            f"Low disk space: {format_size(available)} available, recommended at least "
            f"{format_size(required_bytes)}"
        )
        return False

    return True

"""Command line interface for UW Panopto Downloader."""

from .app import app
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
from .utils import (
    check_dependencies,
    check_disk_space,
    confirm_action,
    create_progress_bar,
    display_file_list,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
    prompt_input,
)

__all__ = [
    "add_note_command",
    "app",
    "check_dependencies",
    "check_disk_space",
    "cloud_transcribe_command",
    "confirm_action",
    "convert_command",
    "create_progress_bar",
    "delete_video_command",
    "display_file_list",
    "download_command",
    "list_tags_command",
    "list_videos_command",
    "migrate_command",
    "print_error",
    "print_header",
    "print_info",
    "print_success",
    "print_warning",
    "prompt_input",
    "search_videos_command",
    "stats_command",
    "tag_video_command",
    "video_info_command",
]

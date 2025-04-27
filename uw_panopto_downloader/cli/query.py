"""Query command for the CLI interface."""

import os
import re
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ..core.database import db
from ..core.storage import storage
from ..utils.file import format_size
from ..utils.logging import get_logger
from .utils import (
    confirm_action,
    format_link,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
)

logger = get_logger(__name__)
console = Console()


def format_date(timestamp: int) -> str:
    """Format timestamp as a readable date.

    Args:
        timestamp: Unix timestamp

    Returns:
        str: Formatted date string
    """

    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def list_videos_command(
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of videos to list"),
    offset: int = typer.Option(0, "--offset", "-o", help="Offset for pagination"),
    all_videos: bool = typer.Option(False, "--all", "-a", help="List all videos"),
    order_by: str = typer.Option(
        "date_added", "--order", "-r", help="Field to order by (date_added, title, size, duration)"
    ),
    asc: bool = typer.Option(False, "--asc", help="Sort in ascending order"),
) -> None:
    """List videos in the database."""
    print_header("UW Panopto Video Library")

    if not db.connect():
        print_error("Failed to connect to database")
        return

    try:
        final_limit = None if all_videos else limit
        videos = db.get_all_videos(
            limit=final_limit, offset=offset, order_by=order_by, desc=not asc
        )

        if not videos:
            print_info("No videos found in the database.")
            return

        table = Table(title=f"Videos ({len(videos)} shown)")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="green")
        table.add_column("Added", style="blue")
        table.add_column("Size", style="magenta", justify="right")
        table.add_column("Video", style="yellow", justify="center")
        table.add_column("Audio", style="yellow", justify="center")
        table.add_column("Transcript", style="yellow", justify="center")

        for video in videos:
            row = [
                str(video["id"]),
                video["title"],
                format_date(video["date_added"]),
                format_size(video["size"] or 0),
                "✓" if video["video_path"] else "",
                "✓" if video["audio_path"] else "",
                "✓" if video["transcript_path"] else "",
            ]
            table.add_row(*row)

        console.print(table)

        # Show pagination info if not showing all
        if not all_videos:
            stats = db.get_stats()
            total = stats.get("total_videos", 0)

            if total > (offset + limit):
                print_info(f"Showing {offset+1}-{min(offset+limit, total)} of {total} videos")
                print_info(f"Use --offset {offset+limit} to see the next page")

    finally:
        db.close()


def search_videos_command( # noqa: PLR0915
    query: str = typer.Argument(..., help="Search query"),
    transcript: bool = typer.Option(True, "--transcript", "-t", help="Search in transcripts"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of results to show"),
    context_lines: int = typer.Option(
        1, "--context", "-c", help="Number of context lines to show around matches"
    ),
) -> None:
    """Search videos in the database with transcript snippets."""
    print_header(f"Search Results: {query}")

    if not db.connect():
        print_error("Failed to connect to database")
        return

    try:
        results = []
        if transcript:
            # Search in transcripts and collect matches with context
            search_results = db.search_transcripts(query, limit=limit)

            for video in search_results:
                # Load the transcript content
                if video.get("transcript_path") and os.path.exists(video.get("transcript_path")):
                    with open(video.get("transcript_path"), encoding="utf-8") as f:
                        transcript_text = f.read()

                    # find matches in transcript
                    matches = []
                    lines = transcript_text.split("\n")

                    for i, line in enumerate(lines):
                        if query.lower() in line.lower():
                            # extract timestamp if available

                            timestamp_match = re.search(r"\[(\d+\.\d+)\s*-\s*\d+\.\d+\]", line)
                            seconds = 0
                            timestamp_text = ""

                            if timestamp_match:
                                timestamp_text = timestamp_match.group(0)
                                try:
                                    seconds = float(timestamp_match.group(1))
                                except (ValueError, IndexError):
                                    pass

                            # get context lines
                            start_idx = max(0, i - context_lines)
                            end_idx = min(len(lines), i + context_lines + 1)
                            context = lines[start_idx:end_idx]

                            # create URL with timestamp
                            direct_url = ""
                            if video.get("url") and seconds > 0:
                                # format URL with timestamp for Panopto
                                video_url = video.get("url", "")
                                if "panopto.com" in video_url or "hosted.panopto" in video_url:
                                    direct_url = f"{video_url}&start={seconds}"
                                else:
                                    direct_url = f"{video_url}?t={int(seconds)}"

                            matches.append(
                                {
                                    "timestamp_text": timestamp_text,
                                    "seconds": seconds,
                                    "context": context,
                                    "line_number": i,
                                    "direct_url": direct_url,
                                    "line": line.replace(timestamp_text, "").strip(),
                                }
                            )

                    # add matches to result
                    video["matches"] = matches

                    if matches:
                        results.append(video)
        else:
            results = db.search_videos(query, limit=limit)

        if not results:
            print_info(f"No videos found matching '{query}'.")
            return

        table = Table(title=f"Search Results: {len(results)} videos found", show_lines=True)
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Match", style="yellow", overflow="fold")
        table.add_column("Direct Link", style="blue", overflow="fold")

        for video in results:
            if transcript and video.get("matches"):
                for match in video["matches"][:20]:
                    # format snippet
                    snippet = match["line"]

                    row = [
                        str(video["id"]),
                        video["title"],
                        f"{match['timestamp_text']} {snippet}",
                        (
                            format_link(match["direct_url"], match["timestamp_text"])
                            if match["direct_url"]
                            else "N/A"
                        ),
                    ]
                    table.add_row(*row)

                if len(video["matches"]) > 3:
                    table.add_row(
                        str(video["id"]),
                        video["title"],
                        f"...and {len(video['matches']) - 3} more matches",
                        "",
                    )
            else:
                # metadata only result
                row = [
                    str(video["id"]),
                    video["title"],
                    "Matched in metadata",
                    video.get("url", "N/A"),
                ]
                table.add_row(*row)

        console.print(table)

        # detailed results for transcript matches
        if transcript:
            for video in results:
                if video.get("matches"):
                    console.print()
                    console.print(
                        f"[bold cyan]Video ID {video['id']}:[/] [green]{video['title']}[/]"
                    )

                    for i, match in enumerate(video["matches"]):
                        if i >= 5:
                            console.print(
                                f"[italic]...and {len(video['matches']) - 5} more matches[/italic]"
                            )
                            break

                        console.print()
                        if match["direct_url"]:
                            console.print(
                                f"[bold]{match['timestamp_text']}[/] [link={match['direct_url']}]"
                                "View...[/link]"
                            )
                        else:
                            console.print(f"[bold]{match['timestamp_text']}[/]")

                        for line in match["context"]:
                            if query.lower() in line.lower():
                                # highlight match
                                start = line.lower().find(query.lower())
                                end = start + len(query)

                                highlighted = (
                                    line[:start]
                                    + f"[bold red]{line[start:end]}[/bold red]"
                                    + line[end:]
                                )
                                console.print(highlighted)
                            else:
                                console.print(line)

    finally:
        db.close()


def video_info_command(
    video_id: int = typer.Argument(..., help="Video ID"),
) -> None:
    """Display detailed information about a video."""
    if not db.connect():
        print_error("Failed to connect to database")
        return

    try:
        video = db.get_video(video_id)

        if not video:
            print_error(f"Video with ID {video_id} not found")
            return

        tags = db.get_video_tags(video_id)

        print_header(f"Video Information: {video['title']}")

        console.print("[bold]Basic Information[/bold]")
        console.print(f"ID: {video['id']}")
        console.print(f"Title: {video['title']}")
        console.print(f"Added: {format_date(video['date_added'])}")
        console.print(f"Size: {format_size(video['size'] or 0)}")

        if video["course"]:
            console.print(f"Course: {video['course']}")

        if video["instructor"]:
            console.print(f"Instructor: {video['instructor']}")

        if video["url"]:
            console.print(f"Original URL: {video['url']}")

        console.print()
        console.print("[bold]Files[/bold]")

        if video["video_path"]:
            console.print(f"Video: {video['video_path']}")
        else:
            console.print("Video: [italic]Not available[/italic]")

        if video["audio_path"]:
            console.print(f"Audio: {video['audio_path']}")
        else:
            console.print("Audio: [italic]Not available[/italic]")

        if video["transcript_path"]:
            console.print(f"Transcript: {video['transcript_path']}")
        else:
            console.print("Transcript: [italic]Not available[/italic]")

        if tags:
            console.print()
            console.print("[bold]Tags[/bold]")
            console.print(", ".join(tags))

        if video["notes"]:
            console.print()
            console.print("[bold]Notes[/bold]")
            console.print(video["notes"])

    finally:
        db.close()


def tag_video_command(
    video_id: int = typer.Argument(..., help="Video ID"),
    tag_name: str = typer.Argument(..., help="Tag name"),
    remove: bool = typer.Option(
        False, "--remove", "-r", help="Remove the tag instead of adding it"
    ),
) -> None:
    """Add or remove a tag for a video."""
    if not db.connect():
        print_error("Failed to connect to database")
        return

    try:
        video = db.get_video(video_id)

        if not video:
            print_error(f"Video with ID {video_id} not found")
            return

        if remove:
            if db.remove_video_tag(video_id, tag_name):
                print_success(f"Tag '{tag_name}' removed from video: {video['title']}")
            else:
                print_error(f"Failed to remove tag '{tag_name}' from video")
        elif db.add_video_tag(video_id, tag_name):
            print_success(f"Tag '{tag_name}' added to video: {video['title']}")
        else:
            print_error(f"Failed to add tag '{tag_name}' to video")

    finally:
        db.close()


def list_tags_command() -> None:
    """List all available tags with usage count."""
    if not db.connect():
        print_error("Failed to connect to database")
        return

    try:
        tags = db.get_all_tags()

        if not tags:
            print_info("No tags found in the database.")
            return

        table = Table(title="Tags")
        table.add_column("Tag", style="green")
        table.add_column("Videos", style="cyan", justify="right")

        for tag in tags:
            table.add_row(tag["name"], str(tag["count"]))

        console.print(table)

    finally:
        db.close()


def delete_video_command(
    video_id: int = typer.Argument(..., help="Video ID"),
    files: bool = typer.Option(False, "--files", "-f", help="Also delete associated files"),
) -> None:
    """Delete a video from the database."""
    if not db.connect():
        print_error("Failed to connect to database")
        return

    try:
        video = db.get_video(video_id)

        if not video:
            print_error(f"Video with ID {video_id} not found")
            return

        print_warning(f"About to delete video: {video['title']}")
        if files:
            print_warning("Associated files will also be deleted")

        if not confirm_action("Are you sure you want to delete this video?", default=False):
            print_info("Deletion cancelled")
            return

        if files:

            # delete associated files
            if video["video_path"]:
                storage.delete_file(video["video_path"])

            if video["audio_path"]:
                storage.delete_file(video["audio_path"])

            if video["transcript_path"]:
                storage.delete_file(video["transcript_path"])

        # delete from database
        if db.delete_video(video_id):
            print_success(f"Video '{video['title']}' deleted from database")
        else:
            print_error("Failed to delete video from database")

    finally:
        db.close()


def add_note_command(
    video_id: int = typer.Argument(..., help="Video ID"),
    note: str = typer.Argument(..., help="Note to add"),
) -> None:
    """Add or update a note for a video."""
    if not db.connect():
        print_error("Failed to connect to database")
        return

    try:
        video = db.get_video(video_id)

        if not video:
            print_error(f"Video with ID {video_id} not found")
            return

        if db.update_video(video_id, {"notes": note}):
            print_success(f"Note added to video: {video['title']}")
        else:
            print_error("Failed to add note to video")

    finally:
        db.close()


def stats_command() -> None:
    """Show database statistics."""
    if not db.connect():
        print_error("Failed to connect to database")
        return

    try:
        stats = db.get_stats()

        if not stats:
            print_error("Failed to retrieve statistics")
            return

        print_header("UW Panopto Downloader Statistics")

        console.print(f"Total videos: {stats.get('total_videos', 0)}")
        console.print(f"Total storage: {format_size(stats.get('total_size', 0))}")
        console.print(f"Videos with audio: {stats.get('videos_with_audio', 0)}")
        console.print(f"Videos with transcripts: {stats.get('videos_with_transcript', 0)}")
        console.print(f"Total tags: {stats.get('total_tags', 0)}")

    finally:
        db.close()


def migrate_command(  # noqa: PLR0915
    video_dir: str = typer.Argument(..., help="Video directory to migrate"),
    audio_dir: Optional[str] = typer.Option(
        None, "--audio", "-a", help="Audio directory to migrate"
    ),
    transcript_dir: Optional[str] = typer.Option(
        None, "--transcript", "-t", help="Transcript directory to migrate"
    ),
) -> None:
    """Migrate existing files to the database."""

    print_header("Migrating Files to Database")

    if not os.path.exists(video_dir):
        print_error(f"Video directory does not exist: {video_dir}")
        return

    if audio_dir and not os.path.exists(audio_dir):
        print_error(f"Audio directory does not exist: {audio_dir}")
        return

    if transcript_dir and not os.path.exists(transcript_dir):
        print_error(f"Transcript directory does not exist: {transcript_dir}")
        return

    print_info(f"Scanning video directory: {video_dir}")
    video_files = []
    for root, _, files in os.walk(video_dir):
        for file in files:
            if file.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
                video_files.append(os.path.join(root, file))

    if not video_files:
        print_warning("No video files found")
        return

    print_info(f"Found {len(video_files)} video files")

    if not confirm_action("Proceed with migration?"):
        print_info("Migration cancelled")
        return

    if not db.connect():
        print_error("Failed to connect to database")
        return

    try:
        migrated = 0
        failed = 0

        for video_path in video_files:
            filename = os.path.basename(video_path)
            title = os.path.splitext(filename)[0]

            print_info(f"Processing: {title}")

            # check if matching audio file exists
            audio_path = None
            if audio_dir:
                possible_audio = os.path.join(audio_dir, f"{title}.mp3")
                if os.path.exists(possible_audio):
                    audio_path = possible_audio

            # check if matching transcript file exists
            transcript_path = None
            transcript_content = ""
            if transcript_dir:
                possible_transcript = os.path.join(transcript_dir, f"{title}.txt")
                if os.path.exists(possible_transcript):
                    transcript_path = possible_transcript
                    try:
                        with open(transcript_path, encoding="utf-8") as f:
                            transcript_content = f.read()
                    except Exception as e:
                        logger.error(f"Error reading transcript: {e}")

            # store files
            stored_video_path, file_size = storage.store_video(video_path, title)

            if not stored_video_path:
                print_error(f"Failed to store video: {title}")
                failed += 1
                continue

            stored_audio_path = ""
            if audio_path:
                stored_audio_path = storage.store_audio(audio_path, title)

            stored_transcript_path = ""
            if transcript_path:
                stored_transcript_path, transcript_content = storage.store_transcript(
                    transcript_path, title
                )

            # add to database
            video_id = db.add_video(
                title=title,
                video_path=stored_video_path,
                audio_path=stored_audio_path,
                transcript_path=stored_transcript_path,
                size=file_size,
            )

            if video_id > 0:
                print_success(f"Added to database: {title} (ID: {video_id})")

                # add transcript for searching
                if transcript_content:
                    db.add_transcript(video_id, transcript_content)

                migrated += 1
            else:
                print_error(f"Failed to add to database: {title}")
                failed += 1

        print_header("Migration Results")
        print_success(f"Successfully migrated: {migrated}")
        print_warning(f"Failed: {failed}")

    finally:
        db.close()

"""SQLite database module for UW Panopto Downloader."""

import os
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

from ..utils.logging import get_logger

logger = get_logger(__name__)


class Database:
    """SQLite database manager for storing video metadata."""

    def __init__(self, db_dir: Optional[str] = None):
        """Initialize the database.

        Args:
            db_dir: Directory to store the database (defaults to ~/.uw-panopto-downloader)
        """
        self.db_dir = db_dir or os.path.join(Path.home(), ".uw-panopto-downloader")
        os.makedirs(self.db_dir, exist_ok=True)

        self.db_path = os.path.join(self.db_dir, "metadata.db")
        self.conn = None
        self.cursor = None

    def connect(self) -> bool:
        """Connect to the SQLite database.

        Returns:
            bool: Whether connection was successful
        """
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            self._initialize_tables()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}")
            return False

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def _initialize_tables(self) -> None:
        """Initialize database tables if they don't exist."""
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT,
            video_id TEXT,
            date_added INTEGER NOT NULL,
            video_path TEXT,
            audio_path TEXT,
            transcript_path TEXT,
            duration INTEGER,
            size INTEGER,
            course TEXT,
            instructor TEXT,
            notes TEXT
        )
        """
        )

        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
        """
        )

        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS video_tags (
            video_id INTEGER,
            tag_id INTEGER,
            PRIMARY KEY (video_id, tag_id),
            FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
        )
        """
        )

        # full-text search index for transcripts
        self.cursor.execute(
            """
        CREATE VIRTUAL TABLE IF NOT EXISTS transcript_search USING fts5(
            video_id, content
        )
        """
        )

        self.conn.commit()

    def add_video(
        self,
        title: str,
        url: Optional[str] = None,
        video_id: Optional[str] = None,
        video_path: Optional[str] = None,
        audio_path: Optional[str] = None,
        transcript_path: Optional[str] = None,
        duration: Optional[int] = None,
        size: Optional[int] = None,
        course: Optional[str] = None,
        instructor: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Add a video to the database.

        Args:
            title: Video title
            url: Original Panopto URL
            video_id: Panopto video ID
            video_path: Path to the video file
            audio_path: Path to the audio file
            transcript_path: Path to the transcript file
            duration: Video duration in seconds
            size: File size in bytes
            course: Course name
            instructor: Instructor name
            notes: Additional notes

        Returns:
            int: Database ID of the added video
        """
        try:
            self.cursor.execute(
                """
            INSERT INTO videos (
                title, url, video_id, date_added, video_path, audio_path,
                transcript_path, duration, size, course, instructor, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    title,
                    url,
                    video_id,
                    int(time.time()),
                    video_path,
                    audio_path,
                    transcript_path,
                    duration,
                    size,
                    course,
                    instructor,
                    notes,
                ),
            )

            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error adding video to database: {e}")
            return -1

    def update_video(self, video_id: int, updates: Dict[str, Union[str, int, None]]) -> bool:
        """Update video metadata.

        Args:
            video_id: Database ID of the video
            updates: Dictionary of fields to update

        Returns:
            bool: Whether update was successful
        """
        valid_fields = {
            "title",
            "url",
            "video_id",
            "video_path",
            "audio_path",
            "transcript_path",
            "duration",
            "size",
            "course",
            "instructor",
            "notes",
        }

        # filter invalid fields
        valid_updates = {k: v for k, v in updates.items() if k in valid_fields}

        if not valid_updates:
            logger.warning("No valid fields to update")
            return False

        try:
            set_clause = ", ".join([f"{field} = ?" for field in valid_updates.keys()])
            values = list(valid_updates.values())
            values.append(video_id)

            self.cursor.execute(
                f"""
            UPDATE videos SET {set_clause} WHERE id = ?
            """,
                values,
            )

            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error updating video: {e}")
            return False

    def get_video(self, video_id: int) -> Optional[Dict]:
        """Get video metadata by ID.

        Args:
            video_id: Database ID of the video

        Returns:
            dict: Video metadata or None if not found
        """
        try:
            self.cursor.execute(
                """
            SELECT * FROM videos WHERE id = ?
            """,
                (video_id,),
            )

            row = self.cursor.fetchone()
            if row:
                return dict(row)
            return None
        except sqlite3.Error as e:
            logger.error(f"Error getting video: {e}")
            return None

    def get_all_videos(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: str = "date_added",
        desc: bool = True,
    ) -> List[Dict]:
        """Get all videos with optional pagination.

        Args:
            limit: Maximum number of videos to return
            offset: Offset for pagination
            order_by: Field to order by
            desc: Whether to sort in descending order

        Returns:
            list: List of video metadata dictionaries
        """
        try:
            # validate order_by field
            valid_order_fields = {"id", "title", "date_added", "duration", "size"}

            if order_by not in valid_order_fields:
                order_by = "date_added"

            direction = "DESC" if desc else "ASC"

            query = f"""
            SELECT * FROM videos ORDER BY {order_by} {direction}
            """

            if limit is not None:
                query += f" LIMIT {limit} OFFSET {offset}"

            self.cursor.execute(query)

            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error getting videos: {e}")
            return []

    def search_videos(self, query: str, limit: Optional[int] = None) -> List[Dict]:
        """Search videos by title and metadata.

        Args:
            query: Search query
            limit: Maximum number of results to return

        Returns:
            list: List of matching video metadata dictionaries
        """
        try:
            search_terms = f"%{query}%"

            sql = """
            SELECT * FROM videos
            WHERE title LIKE ? OR course LIKE ? OR instructor LIKE ? OR notes LIKE ?
            ORDER BY date_added DESC
            """

            if limit is not None:
                sql += f" LIMIT {limit}"

            self.cursor.execute(sql, (search_terms, search_terms, search_terms, search_terms))

            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error searching videos: {e}")
            return []

    def delete_video(self, video_id: int) -> bool:
        """Delete a video from the database.

        Args:
            video_id: Database ID of the video

        Returns:
            bool: Whether deletion was successful
        """
        try:
            # first, delete from transcript search index
            self.cursor.execute(
                """
            DELETE FROM transcript_search WHERE video_id = ?
            """,
                (video_id,),
            )

            # then delete the video
            self.cursor.execute(
                """
            DELETE FROM videos WHERE id = ?
            """,
                (video_id,),
            )

            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error deleting video: {e}")
            return False

    def add_tag(self, name: str) -> int:
        """Add a tag to the database.

        Args:
            name: Tag name

        Returns:
            int: Tag ID
        """
        try:
            # insert tag if it doesn't exist
            self.cursor.execute(
                """
            INSERT OR IGNORE INTO tags (name) VALUES (?)
            """,
                (name,),
            )

            self.conn.commit()

            # get the tag ID
            self.cursor.execute(
                """
            SELECT id FROM tags WHERE name = ?
            """,
                (name,),
            )

            row = self.cursor.fetchone()
            return row["id"] if row else -1
        except sqlite3.Error as e:
            logger.error(f"Error adding tag: {e}")
            return -1

    def add_video_tag(self, video_id: int, tag_name: str) -> bool:
        """Add a tag to a video.

        Args:
            video_id: Database ID of the video
            tag_name: Tag name

        Returns:
            bool: Whether operation was successful
        """
        try:
            tag_id = self.add_tag(tag_name)

            if tag_id == -1:
                return False

            self.cursor.execute(
                """
            INSERT OR IGNORE INTO video_tags (video_id, tag_id) VALUES (?, ?)
            """,
                (video_id, tag_id),
            )

            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error adding video tag: {e}")
            return False

    def get_video_tags(self, video_id: int) -> List[str]:
        """Get tags for a video.

        Args:
            video_id: Database ID of the video

        Returns:
            list: List of tag names
        """
        try:
            self.cursor.execute(
                """
            SELECT t.name FROM tags t
            JOIN video_tags vt ON t.id = vt.tag_id
            WHERE vt.video_id = ?
            ORDER BY t.name
            """,
                (video_id,),
            )

            rows = self.cursor.fetchall()
            return [row["name"] for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error getting video tags: {e}")
            return []

    def remove_video_tag(self, video_id: int, tag_name: str) -> bool:
        """Remove a tag from a video.

        Args:
            video_id: Database ID of the video
            tag_name: Tag name

        Returns:
            bool: Whether operation was successful
        """
        try:
            self.cursor.execute(
                """
            DELETE FROM video_tags
            WHERE video_id = ? AND tag_id = (
                SELECT id FROM tags WHERE name = ?
            )
            """,
                (video_id, tag_name),
            )

            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error removing video tag: {e}")
            return False

    def get_all_tags(self) -> List[Dict]:
        """Get all tags with usage count.

        Returns:
            list: List of tag dictionaries with name and count
        """
        try:
            self.cursor.execute(
                """
            SELECT t.name, COUNT(vt.video_id) as count
            FROM tags t
            LEFT JOIN video_tags vt ON t.id = vt.tag_id
            GROUP BY t.id
            ORDER BY t.name
            """
            )

            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error getting tags: {e}")
            return []

    def add_transcript(self, video_id: int, content: str) -> bool:
        """Add transcript content for full-text search.

        Args:
            video_id: Database ID of the video
            content: Transcript content

        Returns:
            bool: Whether operation was successful
        """
        try:
            # delete any existing transcript for this video
            self.cursor.execute(
                """
            DELETE FROM transcript_search WHERE video_id = ?
            """,
                (video_id,),
            )

            # add new transcript content
            self.cursor.execute(
                """
            INSERT INTO transcript_search (video_id, content) VALUES (?, ?)
            """,
                (video_id, content),
            )

            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error adding transcript: {e}")
            return False

    def search_transcripts(self, query: str, limit: Optional[int] = None) -> List[Dict]:
        """Search video transcripts.

        Args:
            query: Search query
            limit: Maximum number of results to return

        Returns:
            list: List of matching video metadata dictionaries
        """
        try:
            sql = """
            SELECT v.* FROM videos v
            JOIN transcript_search ts ON v.id = ts.video_id
            WHERE ts.content MATCH ?
            ORDER BY v.date_added DESC
            """

            if limit is not None:
                sql += f" LIMIT {limit}"

            self.cursor.execute(sql, (query,))

            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error searching transcripts: {e}")
            return []

    def get_stats(self) -> Dict:
        """Get database statistics.

        Returns:
            dict: Statistics dictionary
        """
        try:
            stats = {}

            # total videos
            self.cursor.execute("SELECT COUNT(*) as count FROM videos")
            stats["total_videos"] = self.cursor.fetchone()["count"]

            # total storage used
            self.cursor.execute("SELECT SUM(size) as total_size FROM videos")
            stats["total_size"] = self.cursor.fetchone()["total_size"] or 0

            # videos with audio
            self.cursor.execute("SELECT COUNT(*) as count FROM videos WHERE audio_path IS NOT NULL")
            stats["videos_with_audio"] = self.cursor.fetchone()["count"]

            # videos with transcripts
            self.cursor.execute(
                "SELECT COUNT(*) as count FROM videos WHERE transcript_path IS NOT NULL"
            )
            stats["videos_with_transcript"] = self.cursor.fetchone()["count"]

            # total tags
            self.cursor.execute("SELECT COUNT(*) as count FROM tags")
            stats["total_tags"] = self.cursor.fetchone()["count"]

            return stats
        except sqlite3.Error as e:
            logger.error(f"Error getting stats: {e}")
            return {}


# singleton database instance
db = Database()

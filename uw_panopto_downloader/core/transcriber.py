import os
from typing import Optional

from .database import db
from .storage import storage


def _check_whisper_installed():
    """Check if the Whisper ASR model is installed."""
    try:
        import torch  # noqa: F401
        import whisper  # noqa: F401

        return True
    except ImportError:
        return False


class Transcriber:
    def __init__(self, model_name: str):
        if not _check_whisper_installed():
            raise ImportError("Whisper not installed... no transcription will be done")
        import torch
        import whisper

        torch.set_num_threads(1)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {device}")
        self.model = whisper.load_model(model_name).to(device)
        self.model_name = model_name

    def transcribe(self, audio_path: str, output_path: Optional[str] = None):
        """Transcribe audio using Whisper ASR model.

        Args:
            audio_path: Path to the audio file
            output_path: Path to save the transcription (optional)

        Returns:
            str: Transcription text (including timestamps)
        """
        result = self.model.transcribe(
            audio_path, language="en", temperature=0.0, word_timestamps=True
        )
        text_with_timestamps = result["segments"]

        transcription = ""
        for segment in text_with_timestamps:
            start_time = segment["start"]
            end_time = segment["end"]
            text = segment["text"].strip()
            if text:
                transcription += f"[{start_time:.2f} - {end_time:.2f}] {text}\n"
        if output_path:
            with open(output_path, "w") as f:
                f.write(transcription)

        return transcription


def transcribe_directory(
    input_dir: str,
    output_dir: Optional[str] = None,
    model: Optional[str] = "base",
    store: bool = True,
) -> None:
    """Transcribe all audio files in a directory to text with timestamps."""
    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"Input directory {input_dir} does not exist")

    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    transcriber = Transcriber(model)

    if store:
        db.connect()

    try:
        for filename in os.listdir(input_dir):
            if filename.endswith(".wav") or filename.endswith(".mp3"):
                input_path = os.path.join(input_dir, filename)
                output_path = (
                    os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.txt")
                    if output_dir
                    else None
                )

                transcription = transcriber.transcribe(input_path, output_path)
                print(f"Transcription saved to {output_path}")
                print(f"Transcription content:\n{transcription[:100]}...")

                if store and output_path:
                    title = os.path.splitext(filename)[0]

                    # store transcript
                    stored_path, transcript_content = storage.store_transcript(output_path, title)

                    if stored_path:
                        # create symlink back to oginal location
                        storage.create_symlink(stored_path, output_path)

                        # try to find the video/audio in the database first by title
                        videos = db.search_videos(title)

                        if videos:
                            # update existing record
                            video_id = videos[0]["id"]
                            db.update_video(video_id, {"transcript_path": stored_path})

                            # transcript for searching
                            db.add_transcript(video_id, transcript_content)
                            print(f"Updated database entry for: {title}")
                        else:
                            # add new entry if not found
                            video_id = db.add_video(
                                title=title,
                                transcript_path=stored_path
                            )

                            db.add_transcript(video_id, transcript_content)
                            print(f"Added to database: {title} (ID: {video_id})")
    finally:
        if store:
            db.close()


def transcribe_command(
    input_path: str,
    output_path: Optional[str] = None,
    model: Optional[str] = "base",
    store: bool = True,
) -> None:
    """Transcribe audio files to text with timestamps."""

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file {input_path} does not exist")

    if os.path.isdir(input_path):
        transcribe_directory(input_path, output_path, model, store)
        return

    if not output_path:
        output_path = os.path.splitext(input_path)[0] + ".txt"

    transcriber = Transcriber(model)
    transcription = transcriber.transcribe(input_path, output_path)
    print(f"Transcription saved to {output_path}")
    print(f"Transcription content:\n{transcription[:100]}...")

    if store:
        db.connect()

        try:
            title = os.path.splitext(os.path.basename(input_path))[0]

            stored_path, transcript_content = storage.store_transcript(output_path, title)

            if stored_path:
                storage.create_symlink(stored_path, output_path)

                videos = db.search_videos(title)

                if videos:
                    video_id = videos[0]["id"]
                    db.update_video(video_id, {"transcript_path": stored_path})

                    db.add_transcript(video_id, transcript_content)
                    print(f"Updated database entry for: {title}")
                else:
                    video_id = db.add_video(
                        title=title,
                        transcript_path=stored_path
                    )

                    db.add_transcript(video_id, transcript_content)
                    print(f"Added to database: {title} (ID: {video_id})")
        finally:
            db.close()

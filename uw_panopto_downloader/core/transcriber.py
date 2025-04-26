from typing import Optional


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
) -> None:
    """Transcribe all audio files in a directory to text with timestamps."""
    import os

    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"Input directory {input_dir} does not exist")

    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    transcriber = Transcriber(model)
    for filename in os.listdir(input_dir):
        if filename.endswith(".wav") or filename.endswith(".mp3"):
            input_path = os.path.join(input_dir, filename)
            output_path = (
                os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.txt")
                if output_dir
                else None
            )
            transcriber.transcribe(input_path, output_path)

def transcribe_command(
    input_path: str,
    output_path: Optional[str] = None,
    model: Optional[str] = "base",
) -> None:
    """Transcribe audio files to text with timestamps."""

    import os

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file {input_path} does not exist")
    # check if input_path is a directory
    if os.path.isdir(input_path):
        transcribe_directory(input_path, output_path, model)
        return

    transcriber = Transcriber(model)
    transcriber.transcribe(input_path, output_path)

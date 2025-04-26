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


def transcribe_command(
    input_path: str,
    output_path: Optional[str] = None,
    model: Optional[str] = "base",
) -> None:
    """Transcribe audio files to text with timestamps."""
    transcriber = Transcriber(model)
    transcription = transcriber.transcribe(input_path, output_path)
    print(transcription)

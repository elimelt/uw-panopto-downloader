"""Google Cloud Speech-to-Text transcriber for UW Panopto Downloader."""

import os
import tempfile
from typing import List, Optional, Tuple

from google.cloud import speech
from pydub import AudioSegment
from pydub.silence import split_on_silence

from ..utils.logging import get_logger

logger = get_logger(__name__)

MAX_CHUNK_SIZE_MS = 45 * 1000


class GCPTranscriber:
    """Class for transcribing audio files using Google Cloud Speech-to-Text with chunking."""

    def __init__(self, credentials_path: Optional[str] = None):
        """Initialize the GCP transcriber.

        Args:
            credentials_path: Path to the GCP credentials JSON file
        """
        self.credentials_path = credentials_path

        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

    def initialize_client(self) -> speech.SpeechClient:
        """Initialize and return a Speech client.

        Returns:
            speech.SpeechClient: The Speech client
        """
        try:
            return speech.SpeechClient()
        except Exception as e:
            logger.error(f"Failed to initialize Speech client: {e}")
            raise

    def _detect_encoding_and_sample_rate(
        self, audio_path: str
    ) -> Tuple[speech.RecognitionConfig.AudioEncoding, int]:
        """Detect the encoding and sample rate based on the audio file extension.

        Args:
            audio_path: Path to the audio file

        Returns:
            tuple: (encoding, sample_rate_hertz)
        """

        encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16
        sample_rate_hertz = 16000

        if audio_path.lower().endswith(".flac"):
            encoding = speech.RecognitionConfig.AudioEncoding.FLAC
        elif audio_path.lower().endswith(".wav"):
            encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16

            sample_rate_hertz = 44100
        elif audio_path.lower().endswith(".mp3"):
            encoding = speech.RecognitionConfig.AudioEncoding.MP3

            sample_rate_hertz = 44100
        elif audio_path.lower().endswith(".ogg"):
            encoding = speech.RecognitionConfig.AudioEncoding.OGG_OPUS

        return encoding, sample_rate_hertz

    def _transcribe_audio_chunk(
        self, chunk: AudioSegment, chunk_path: str, language_code: str = "en-US"
    ) -> str:
        """Transcribe a small audio chunk using Google Cloud Speech-to-Text.

        Args:
            chunk: The audio chunk to transcribe
            chunk_path: Path where the chunk should be saved
            language_code: Language code for transcription

        Returns:
            str: The transcribed text
        """

        if chunk.channels > 1:
            chunk = chunk.set_channels(1)

        chunk.export(chunk_path, format="wav")

        client = self.initialize_client()

        with open(chunk_path, "rb") as audio_file:
            content = audio_file.read()

        audio = speech.RecognitionAudio(content=content)

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=chunk.frame_rate,
            language_code=language_code,
            enable_word_time_offsets=True,
            enable_automatic_punctuation=True,
            audio_channel_count=1,
        )

        try:

            response = client.recognize(config=config, audio=audio)

            transcript = ""
            words_with_timestamps = []

            for result in response.results:
                alternative = result.alternatives[0]
                transcript += alternative.transcript + " "

                if hasattr(alternative, "words"):
                    for word_info in alternative.words:
                        word = word_info.word
                        start_time = word_info.start_time.total_seconds()
                        end_time = word_info.end_time.total_seconds()
                        words_with_timestamps.append(
                            {"word": word, "start_time": start_time, "end_time": end_time}
                        )

            return transcript.strip(), words_with_timestamps

        except Exception as e:
            logger.error(f"Error transcribing chunk {chunk_path}: {e}")
            return "", []

    def transcribe(  # noqa: PLR0915
        self,
        audio_path: str,
        output_path: Optional[str] = None,
        language_code: str = "en-US",
        progress_callback: Optional[callable] = None,
    ) -> str:
        """Transcribe audio with word time offsets by splitting into chunks.

        Args:
            audio_path: Path to the audio file
            output_path: Path to save the transcription (optional)
            language_code: Language code for transcription
            progress_update: Optional callback for progress updates

        Returns:
            str: Transcription text (including timestamps)
        """
        try:

            logger.info(f"Loading audio file: {audio_path}")
            audio = AudioSegment.from_file(audio_path)

            if audio.channels > 1:
                logger.info(f"Converting {audio.channels} channels to mono")
                audio = audio.set_channels(1)

            temp_dir = tempfile.mkdtemp()
            logger.info(f"Created temporary directory: {temp_dir}")

            logger.info("Splitting audio on silence...")
            audio_chunks = split_on_silence(
                audio, min_silence_len=700, silence_thresh=audio.dBFS - 14, keep_silence=500
            )

            if not audio_chunks:
                logger.warning("No chunks were created. Using fixed interval chunking instead.")

                chunk_length_ms = 30 * 1000
                audio_chunks = [
                    audio[i : i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)
                ]

            processed_chunks = []
            for chunk in audio_chunks:
                if len(chunk) > MAX_CHUNK_SIZE_MS:
                    logger.info(
                        f"Splitting large chunk of {len(chunk)/1000:.1f}s into smaller pieces"
                    )

                    sub_chunks = [
                        chunk[i : i + MAX_CHUNK_SIZE_MS]
                        for i in range(0, len(chunk), MAX_CHUNK_SIZE_MS)
                    ]
                    processed_chunks.extend(sub_chunks)
                else:
                    processed_chunks.append(chunk)

            audio_chunks = processed_chunks

            logger.info(f"Split audio into {len(audio_chunks)} chunks")

            transcription = ""
            all_words_with_time = []
            offset = 0

            for i, chunk in enumerate(audio_chunks):
                logger.info(f"Processing chunk {i+1}/{len(audio_chunks)}")
                if progress_callback:
                    percent_complete = (i + 1) / len(audio_chunks) * 100
                    progress_callback(percent_complete)

                chunk_path = os.path.join(temp_dir, f"chunk_{i}.wav")

                chunk_text, words_with_time = self._transcribe_audio_chunk(
                    chunk, chunk_path, language_code
                )

                for word_info in words_with_time:
                    word_info["start_time"] += offset
                    word_info["end_time"] += offset
                    all_words_with_time.append(word_info)

                offset += len(chunk) / 1000.0

                if chunk_text:
                    transcription += chunk_text + " "

            import shutil

            shutil.rmtree(temp_dir)

            formatted_transcription = ""

            segments = []
            current_segment = {"words": [], "start_time": None, "end_time": None, "text": ""}

            for word_info in all_words_with_time:
                word = word_info["word"]

                if current_segment["start_time"] is None:
                    current_segment["start_time"] = word_info["start_time"]

                current_segment["end_time"] = word_info["end_time"]

                current_segment["words"].append(word_info)
                current_segment["text"] += word + " "

                if word.endswith((".", "!", "?", ":", ";")):
                    segments.append(current_segment)
                    current_segment = {
                        "words": [],
                        "start_time": None,
                        "end_time": None,
                        "text": "",
                    }

            if current_segment["words"]:
                segments.append(current_segment)

            for segment in segments:
                start_time = segment["start_time"]
                end_time = segment["end_time"]
                text = segment["text"].strip()

                if start_time is not None and end_time is not None and text:
                    formatted_transcription += f"[{start_time:.2f} - {end_time:.2f}] {text}\n"

            if output_path:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(formatted_transcription)
                logger.info(f"Transcription saved to {output_path}")

            return formatted_transcription

        except Exception as e:
            error_msg = f"Error transcribing {audio_path}: {e}"
            logger.error(error_msg)
            if output_path:

                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(f"ERROR: {error_msg}")
            return f"ERROR: {error_msg}"

    def transcribe_batch(
        self, input_dir: str, output_dir: str, language_code: str = "en-US"
    ) -> Tuple[List[str], List[str]]:
        """Transcribe all audio files in a directory.

        Args:
            input_dir: Directory containing audio files
            output_dir: Directory to save transcriptions
            language_code: The language code to use

        Returns:
            tuple: (successful_files, failed_files)
        """
        if not os.path.isdir(input_dir):
            logger.error(f"Input directory does not exist: {input_dir}")
            return [], [f"Directory not found: {input_dir}"]

        os.makedirs(output_dir, exist_ok=True)

        audio_files = []
        for root, _, files in os.walk(input_dir):
            for file in files:
                if file.lower().endswith((".mp3", ".wav", ".flac", ".ogg")):
                    audio_files.append(os.path.join(root, file))

        if not audio_files:
            logger.warning(f"No audio files found in {input_dir}")
            return [], []

        successful = []
        failed = []

        for audio_path in audio_files:
            try:

                rel_path = os.path.relpath(audio_path, input_dir)
                output_path = os.path.join(output_dir, os.path.splitext(rel_path)[0] + ".txt")

                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                logger.info(f"Transcribing {audio_path}")
                result = self.transcribe(audio_path, output_path, language_code)

                if result.startswith("ERROR:"):
                    failed.append(audio_path)
                else:
                    successful.append(audio_path)
                    logger.info(f"Successfully transcribed {audio_path}")

            except Exception as e:
                logger.error(f"Failed to transcribe {audio_path}: {e}")
                failed.append(audio_path)

        return successful, failed


def transcribe_command(
    input_path: str,
    output_path: Optional[str] = None,
    model: Optional[str] = None,
    language_code: str = "en-US",
    credentials_path: Optional[str] = None,
) -> None:
    """Transcribe audio files to text with timestamps using Google Cloud Speech-to-Text.

    Args:
        input_path: Path to the audio file or directory
        output_path: Path to save the transcription (default: input_path with .txt extension)
        model: Not used for GCP (kept for API compatibility with Whisper)
        language_code: The language code to use (default: "en-US")
        credentials_path: Path to GCP credentials JSON file (optional)
    """
    transcriber = GCPTranscriber(credentials_path)

    if os.path.isdir(input_path):

        if not output_path:
            output_path = os.path.join(os.path.dirname(input_path), "transcripts")

        successful, failed = transcriber.transcribe_batch(input_path, output_path, language_code)

        logger.info(f"Transcription completed: {len(successful)} successful, {len(failed)} failed")
        if failed:
            logger.info(f"Failed files: {', '.join(os.path.basename(f) for f in failed)}")
    else:

        if not output_path:
            output_path = os.path.splitext(input_path)[0] + ".txt"

        transcriber.transcribe(input_path, output_path, language_code)
        logger.info(f"Transcription completed and saved to {output_path}")

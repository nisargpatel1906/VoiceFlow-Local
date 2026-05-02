"""
VoiceFlow Local - Whisper Transcriber Module

Transcribes audio files to text using faster-whisper with GPU acceleration.
"""

import os
import sys
import time
import config


class WhisperTranscriber:
    """
    Transcribes audio files using faster-whisper.

    Loads the model once at startup for fast subsequent transcriptions.
    Uses CUDA GPU acceleration when available, falls back to CPU otherwise.
    """

    def __init__(self):
        """
        Initialize the Whisper transcriber.

        Loads the model from config.MODEL_SIZE.
        First run downloads the model to ./models/ automatically.
        """
        self.model = None
        self.model_size = config.MODEL_SIZE
        if sys.platform == "darwin":
            self.device = "cpu"
            self.compute_type = "int8"
        else:
            self.device = config.DEVICE
            self.compute_type = config.COMPUTE_TYPE
        self._model_loaded = False

    def _load_model(self):
        """
        Load the Whisper model with GPU acceleration.

        Falls back to CPU if CUDA is not available.
        """
        if self._model_loaded:
            return

        print(f"[INFO] Loading Whisper model '{self.model_size}'...")
        start = time.time()

        try:
            from faster_whisper import WhisperModel

            # If CUDA is requested but unavailable, switch to CPU before model init.
            if self.device == 'cuda':
                try:
                    import torch
                    if not torch.cuda.is_available():
                        print("[WARNING] CUDA requested but not available; using CPU mode.")
                        self.device = 'cpu'
                        self.compute_type = 'int8'
                except Exception:
                    print("[WARNING] Could not verify CUDA availability; using CPU mode.")
                    self.device = 'cpu'
                    self.compute_type = 'int8'

            # Try CUDA first
            if self.device == 'cuda':
                try:
                    self.model = WhisperModel(
                        self.model_size,
                        device=self.device,
                        compute_type=self.compute_type,
                        download_root=config.MODEL_DIR
                    )
                    print(f"[OK] Model loaded on CUDA ({self.compute_type}) in {time.time() - start:.1f}s")

                except RuntimeError as e:
                    if "CUDA" in str(e) or "can't load CUDA" in str(e):
                        # Fall back to CPU
                        print(f"[WARNING] CUDA not available: {e}")
                        print("[INFO] Falling back to CPU mode...")
                        self.device = 'cpu'
                        self.compute_type = 'int8'
                        self.model = WhisperModel(
                            self.model_size,
                            device='cpu',
                            compute_type='int8',
                            download_root=config.MODEL_DIR
                        )
                        print(f"[OK] Model loaded on CPU (int8) in {time.time() - start:.1f}s")
                    else:
                        raise
            else:
                # CPU mode from config
                self.model = WhisperModel(
                    self.model_size,
                    device='cpu',
                    compute_type='int8',
                    download_root=config.MODEL_DIR
                )
                print(f"[OK] Model loaded on CPU (int8) in {time.time() - start:.1f}s")

            self._model_loaded = True

        except ImportError:
            print("[ERROR] faster-whisper not installed. Run: pip install faster-whisper")
            raise
        except Exception as e:
            print(f"[ERROR] Failed to load model: {e}")
            raise

    def transcribe(self, audio_file_path):
        """
        Transcribe an audio file to text.

        Args:
            audio_file_path: Path to a WAV audio file.

        Returns:
            str: Cleaned transcription text.
        """
        if not os.path.exists(audio_file_path):
            print(f"[ERROR] Audio file not found: {audio_file_path}")
            return ""

        # Load model if not already loaded
        self._load_model()

        print(f"[INFO] Transcribing {os.path.basename(audio_file_path)}...")
        start = time.time()

        # Transcribe with optimized settings
        transcribe_kwargs = {
            'beam_size': getattr(config, 'BEAM_SIZE', 5),
            'vad_filter': True,
            'condition_on_previous_text': False,
            'without_timestamps': True,
        }
        if getattr(config, 'TRANSLATE_TO_ENGLISH', False):
            transcribe_kwargs['task'] = 'translate'
            transcribe_kwargs['language'] = None
        else:
            transcribe_kwargs['language'] = config.LANGUAGE

        segments, _ = self.model.transcribe(audio_file_path, **transcribe_kwargs)

        # Join all segments into one string
        text = ' '.join(segment.text for segment in segments)

        # Clean up whitespace
        text = text.strip()

        elapsed = time.time() - start
        print(f"[OK] Transcription complete in {elapsed:.1f}s")

        return text


# =============================================================================
# TEST: Transcribe a WAV file passed as command-line argument
# =============================================================================
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python transcriber.py <path_to_wav_file>")
        print("Example: python transcriber.py temp_recording.wav")
        sys.exit(1)

    wav_file = sys.argv[1]

    if not os.path.exists(wav_file):
        print(f"[ERROR] File not found: {wav_file}")
        sys.exit(1)

    transcriber = WhisperTranscriber()
    result = transcriber.transcribe(wav_file)

    print()
    print("=" * 50)
    print("TRANSCRIPTION RESULT:")
    print("=" * 50)
    print(result)

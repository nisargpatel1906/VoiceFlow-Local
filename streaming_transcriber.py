"""
VoiceFlow Local - Streaming Whisper transcriber.

Consumes chunk WAV files from a queue, transcribes them on a background thread,
and forwards partial/final transcript updates through Qt signals.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
from typing import Callable, Optional

from PyQt6.QtCore import QObject, Qt, pyqtSignal

import config as default_config
from cleaner import TextCleaner
from streaming_recorder import StreamingRecorder


class StreamingTranscriber(QObject):
    partial_ready = pyqtSignal(str)
    final_ready = pyqtSignal(str)
    error_ready = pyqtSignal(str)

    def __init__(self, config_module=None):
        super().__init__()
        self.config = config_module or default_config
        self.model = None
        self.model_size = self.config.MODEL_SIZE
        if sys.platform == "win32":
            self.device = "cuda"
            self.compute_type = "float16"
        elif sys.platform == "darwin":
            self.device = "cpu"
            self.compute_type = "int8"
        else:
            self.device = getattr(self.config, "DEVICE", "cpu")
            self.compute_type = getattr(self.config, "COMPUTE_TYPE", "int8")
        self.beam_size = 3
        self.vad_filter = True
        self.running_transcript = ""
        self.detected_language = getattr(self.config, "LANGUAGE", None)
        self._model_loaded = False
        self._consumer_thread: Optional[threading.Thread] = None
        self._cleanup_helper = StreamingRecorder()
        self.cleaner = TextCleaner()

        self._load_model()

    def start(
        self,
        chunk_queue: "queue.Queue[Optional[str]]",
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
    ):
        self.reset()
        self._reset_signal(self.partial_ready, on_partial)
        self._reset_signal(self.final_ready, on_final)
        self._consumer_thread = threading.Thread(
            target=self._consume_queue,
            args=(chunk_queue,),
            daemon=True,
            name="StreamingTranscriber",
        )
        self._consumer_thread.start()

    def transcribe_chunk(self, wav_path) -> str:
        if not os.path.exists(wav_path):
            return ""

        transcribe_kwargs = {
            "beam_size": self.beam_size,
            "vad_filter": self.vad_filter,
            "condition_on_previous_text": False,
            "without_timestamps": True,
        }
        if self.detected_language:
            transcribe_kwargs["language"] = self.detected_language

        try:
            segments, info = self.model.transcribe(wav_path, **transcribe_kwargs)
        except ValueError as exc:
            if "empty sequence" in str(exc).lower():
                return ""
            raise

        if not self.detected_language:
            detected = getattr(info, "language", None)
            if detected:
                self.detected_language = detected

        chunk_text = " ".join(segment.text for segment in segments).strip()
        if self.cleaner.is_duplicate_of_previous(chunk_text, self.running_transcript):
            return ""
        return chunk_text

    def reset(self):
        self.running_transcript = ""
        self.detected_language = getattr(self.config, "LANGUAGE", None)

    def _consume_queue(self, chunk_queue: "queue.Queue[Optional[str]]"):
        while True:
            chunk_path = chunk_queue.get()
            if chunk_path is None:
                self.final_ready.emit(self.running_transcript.strip())
                break

            finish_after_chunk = False
            stale_paths = []
            while True:
                try:
                    queued_item = chunk_queue.get_nowait()
                except queue.Empty:
                    break

                if queued_item is None:
                    finish_after_chunk = True
                    break

                stale_paths.append(chunk_path)
                chunk_path = queued_item

            for stale_path in stale_paths:
                self._cleanup_helper.cleanup(stale_path)

            try:
                try:
                    partial_text = self.transcribe_chunk(chunk_path)
                except Exception as exc:
                    print(f"[ERROR] Streaming chunk transcription failed: {exc}")
                    self.error_ready.emit(str(exc))
                    partial_text = ""
                if partial_text:
                    if self.running_transcript:
                        self.running_transcript = f"{self.running_transcript} {partial_text}".strip()
                    else:
                        self.running_transcript = partial_text
                    self.partial_ready.emit(self.running_transcript)
            finally:
                self._cleanup_helper.cleanup(chunk_path)

            if finish_after_chunk:
                self.final_ready.emit(self.running_transcript.strip())
                break

    def _reset_signal(self, signal, callback: Callable[[str], None]):
        try:
            signal.disconnect()
        except TypeError:
            pass
        signal.connect(callback, Qt.ConnectionType.QueuedConnection)

    def _load_model(self):
        if self._model_loaded:
            return

        print(f"[INFO] Loading streaming Whisper model '{self.model_size}'...")
        start = time.time()

        try:
            from faster_whisper import WhisperModel

            if self.device == "cuda":
                try:
                    import torch

                    if not torch.cuda.is_available():
                        print("[WARNING] CUDA unavailable for streaming mode; falling back to CPU int8.")
                        self.device = "cpu"
                        self.compute_type = "int8"
                except Exception:
                    print("[WARNING] CUDA check failed; falling back to CPU int8.")
                    self.device = "cpu"
                    self.compute_type = "int8"

            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=self.config.MODEL_DIR,
            )
            self._model_loaded = True
            print(
                f"[OK] Streaming model loaded on {self.device} "
                f"({self.compute_type}) in {time.time() - start:.1f}s"
            )
        except Exception as exc:
            print(f"[ERROR] Failed to load streaming Whisper model: {exc}")
            raise

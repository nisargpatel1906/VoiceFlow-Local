"""
VoiceFlow Local - Streaming audio recorder.

Captures microphone audio in fixed-size chunks and writes each chunk to a
temporary WAV file for live transcription pipelines.
"""

from __future__ import annotations

import audioop
import os
import queue
import sys
import tempfile
import threading
import wave
from typing import Optional

import pyaudio


class StreamingRecorder:
    SAMPLE_RATE = 16000
    CHANNELS = 1
    FORMAT = pyaudio.paInt16
    SAMPLE_WIDTH = 2
    CHUNK_DURATION_MS = 500 if sys.platform == "win32" else 2500 if sys.platform == "darwin" else 500
    SNAPSHOT_WINDOW_MS = 2000 if sys.platform == "win32" else 5000 if sys.platform == "darwin" else 2000
    ROLLING_BUFFER_SECONDS = 30
    SILENCE_RMS_THRESHOLD = 280

    def __init__(self):
        self.frames_per_chunk = int(self.SAMPLE_RATE * self.CHUNK_DURATION_MS / 1000)
        self.audio: Optional[pyaudio.PyAudio] = None
        self.stream = None
        self.chunk_queue: Optional["queue.Queue[Optional[str]]"] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._buffer_lock = threading.Lock()
        self._rolling_buffer = bytearray()
        self._max_buffer_bytes = self.ROLLING_BUFFER_SECONDS * self.SAMPLE_RATE * self.SAMPLE_WIDTH
        self._sentinel_sent = False
        self._sentinel_lock = threading.Lock()
        self._last_error: Optional[str] = None
        self._snapshot_window_bytes = int(self.SAMPLE_RATE * self.SAMPLE_WIDTH * self.SNAPSHOT_WINDOW_MS / 1000)
        self._silence_threshold_ms = 0
        self._silence_elapsed_ms = 0
        self._silence_callback = None
        self._silence_triggered = False

    def start(
        self,
        chunk_queue: "queue.Queue[Optional[str]]",
        on_silence_timeout=None,
        silence_threshold_sec: Optional[int] = None,
    ):
        if self._thread and self._thread.is_alive():
            return

        self.chunk_queue = chunk_queue
        self._silence_callback = on_silence_timeout
        self._silence_threshold_ms = max(0, int((silence_threshold_sec or 0) * 1000))
        self._silence_elapsed_ms = 0
        self._silence_triggered = False
        self._stop_event.clear()
        self._last_error = None
        self._sentinel_sent = False
        with self._buffer_lock:
            self._rolling_buffer.clear()

        self._open_stream()
        self._thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="StreamingRecorder",
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._close_stream()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        self._emit_sentinel()

    def get_rolling_buffer(self) -> bytes:
        with self._buffer_lock:
            return bytes(self._rolling_buffer)

    def cleanup(self, path):
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    def _open_stream(self):
        try:
            self.audio = pyaudio.PyAudio()
            default_device = self.audio.get_default_input_device_info()
            if not default_device:
                raise OSError("No microphone found.")

            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.SAMPLE_RATE,
                input=True,
                frames_per_buffer=self.frames_per_chunk,
                start=False,
            )
            self.stream.start_stream()
        except Exception as exc:
            self._close_stream()
            message = (
                "Failed to start streaming microphone capture. "
                "Check that a microphone is connected and allowed in system settings. "
                f"Details: {exc}"
            )
            self._last_error = message
            raise RuntimeError(message) from exc

    def _capture_loop(self):
        try:
            while not self._stop_event.is_set():
                try:
                    chunk = self.stream.read(self.frames_per_chunk, exception_on_overflow=False)
                except Exception as exc:
                    if self._stop_event.is_set():
                        break
                    self._last_error = f"PyAudio streaming read failed: {exc}"
                    print(f"[ERROR] {self._last_error}")
                    break

                self._append_to_rolling_buffer(chunk)
                self._update_silence_state(chunk)
                wav_path = tempfile.mktemp(suffix=".wav")

                try:
                    snapshot = self._current_snapshot()
                    self._write_chunk_wav(wav_path, snapshot)
                    if self.chunk_queue is not None:
                        self._put_chunk_path(wav_path)
                except Exception as exc:
                    self._last_error = f"Failed to write streaming chunk WAV: {exc}"
                    print(f"[ERROR] {self._last_error}")
                    self.cleanup(wav_path)
                    break
                if self._silence_triggered:
                    break
        finally:
            self._close_stream()
            self._emit_sentinel()

    def _append_to_rolling_buffer(self, chunk: bytes):
        with self._buffer_lock:
            self._rolling_buffer.extend(chunk)
            if len(self._rolling_buffer) > self._max_buffer_bytes:
                overflow = len(self._rolling_buffer) - self._max_buffer_bytes
                del self._rolling_buffer[:overflow]

    def _current_snapshot(self) -> bytes:
        with self._buffer_lock:
            if len(self._rolling_buffer) <= self._snapshot_window_bytes:
                return bytes(self._rolling_buffer)
            return bytes(self._rolling_buffer[-self._snapshot_window_bytes :])

    def _update_silence_state(self, chunk: bytes):
        if self._silence_threshold_ms <= 0 or self._silence_triggered:
            return

        rms = audioop.rms(chunk, self.SAMPLE_WIDTH) if chunk else 0
        if rms <= self.SILENCE_RMS_THRESHOLD:
            self._silence_elapsed_ms += self.CHUNK_DURATION_MS
        else:
            self._silence_elapsed_ms = 0

        if self._silence_elapsed_ms < self._silence_threshold_ms:
            return

        self._silence_triggered = True
        self._stop_event.set()
        if self._silence_callback:
            try:
                self._silence_callback()
            except Exception:
                pass

    def _put_chunk_path(self, wav_path: str):
        if self.chunk_queue is None:
            return

        try:
            self.chunk_queue.put_nowait(wav_path)
            return
        except queue.Full:
            pass

        try:
            dropped = self.chunk_queue.get_nowait()
        except queue.Empty:
            dropped = None

        if isinstance(dropped, str):
            self.cleanup(dropped)

        self.chunk_queue.put_nowait(wav_path)

    def _write_chunk_wav(self, path: str, audio_bytes: bytes):
        with wave.open(path, "wb") as wav_file:
            wav_file.setnchannels(self.CHANNELS)
            wav_file.setsampwidth(self.SAMPLE_WIDTH)
            wav_file.setframerate(self.SAMPLE_RATE)
            wav_file.writeframes(audio_bytes)

    def _emit_sentinel(self):
        with self._sentinel_lock:
            if self._sentinel_sent:
                return
            self._sentinel_sent = True

        if self.chunk_queue is not None:
            while True:
                try:
                    self.chunk_queue.put_nowait(None)
                    break
                except queue.Full:
                    try:
                        dropped = self.chunk_queue.get_nowait()
                    except queue.Empty:
                        break
                    if isinstance(dropped, str):
                        self.cleanup(dropped)

    def _close_stream(self):
        if self.stream is not None:
            try:
                self.stream.stop_stream()
            except Exception:
                pass
            try:
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        if self.audio is not None:
            try:
                self.audio.terminate()
            except Exception:
                pass
            self.audio = None

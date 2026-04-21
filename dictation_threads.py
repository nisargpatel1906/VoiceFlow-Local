"""
VoiceFlow Local - QThread workers for recording and transcription.

Audio capture and Whisper work run outside the Qt UI thread. faster-whisper 1.0.3
does not provide a direct stream=True API, so partial text is produced by
transcribing periodic recording snapshots and replacing them with the final
transcript after release.
"""

from __future__ import annotations

import os
import queue
import json
import subprocess
import sys
import tempfile
import time
import wave

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
CHUNK_SIZE = 1024
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKER_SCRIPT = os.path.join(BASE_DIR, "whisper_worker.py")


class AudioCaptureThread(QThread):
    level_changed = pyqtSignal(float)
    snapshot_ready = pyqtSignal(bytes, float)
    audio_finished = pyqtSignal(bytes, float)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def stop(self):
        self._running = False

    def run(self):  # noqa: D401 - Qt thread entrypoint
        audio = None
        stream = None
        frames = []
        start = time.time()
        last_snapshot = start
        capture_error = None

        try:
            import pyaudio

            audio = pyaudio.PyAudio()
            audio.get_default_input_device_info()
            stream = audio.open(
                format=audio.get_format_from_width(SAMPLE_WIDTH),
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )

            while self._running:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)

                audio_array = np.frombuffer(data, dtype=np.int16)
                peak = int(np.max(np.abs(audio_array))) if audio_array.size else 0
                self.level_changed.emit(min(1.0, peak / 18000.0))

                now = time.time()
                if now - last_snapshot >= 0.3:
                    duration = now - start
                    self.snapshot_ready.emit(b"".join(frames), duration)
                    last_snapshot = now

        except Exception as exc:
            capture_error = f"Mic error: {exc}"
            self.error.emit(capture_error)
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if audio is not None:
                try:
                    audio.terminate()
                except Exception:
                    pass

            duration = max(0.0, time.time() - start)
            if frames:
                self.audio_finished.emit(b"".join(frames), duration)
            elif capture_error is None:
                self.error.emit("Mic produced no audio frames. Check input device and permissions.")


class StreamingWhisperThread(QThread):
    partial_ready = pyqtSignal(str)
    final_ready = pyqtSignal(str, float)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: "queue.Queue[tuple[bytes, float, bool]]" = queue.Queue(maxsize=4)
        self._running = True

    def submit_audio(self, audio_bytes: bytes, duration_sec: float, final: bool = False):
        if not audio_bytes:
            return

        if self._queue.full():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
        self._queue.put((audio_bytes, duration_sec, final))

    def stop(self):
        self._running = False

    def run(self):  # noqa: D401 - Qt thread entrypoint
        last_partial = 0.0

        while self._running:
            try:
                audio_bytes, duration_sec, final = self._queue.get(timeout=0.15)
            except queue.Empty:
                continue

            # Drain stale snapshots so Whisper always sees the newest audio.
            while True:
                try:
                    next_audio, next_duration, next_final = self._queue.get_nowait()
                    audio_bytes, duration_sec = next_audio, next_duration
                    final = final or next_final
                except queue.Empty:
                    break

            if not final and (duration_sec < 0.8 or time.time() - last_partial < 1.0):
                continue

            wav_path = self._write_temp_wav(audio_bytes)
            try:
                text = self._transcribe_in_subprocess(wav_path).strip()
                if final:
                    self.final_ready.emit(text, duration_sec)
                    break
                if text:
                    self.partial_ready.emit(text)
                    last_partial = time.time()
            except Exception as exc:
                self.error.emit(f"Transcription error: {exc}")
                if final:
                    break
            finally:
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

    def _write_temp_wav(self, audio_bytes: bytes) -> str:
        temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        path = temp.name
        temp.close()
        with wave.open(path, "wb") as wav:
            wav.setnchannels(CHANNELS)
            wav.setsampwidth(SAMPLE_WIDTH)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(audio_bytes)
        return path

    def _transcribe_in_subprocess(self, wav_path: str) -> str:
        result = self._run_worker(wav_path, force_cpu=False)
        if result.returncode != 0:
            result = self._run_worker(wav_path, force_cpu=True)

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(stderr[-800:] or f"Whisper worker exited with code {result.returncode}")

        lines = [line for line in (result.stdout or "").splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("Whisper worker returned no output")

        payload = json.loads(lines[-1])
        if not payload.get("ok"):
            raise RuntimeError(payload.get("error", "Whisper worker failed"))
        return payload.get("text", "")

    def _run_worker(self, wav_path: str, force_cpu: bool):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        if force_cpu:
            env["VOICEFLOW_FORCE_CPU"] = "1"

        return subprocess.run(
            [sys.executable, WORKER_SCRIPT, wav_path],
            cwd=BASE_DIR,
            env=env,
            text=True,
            capture_output=True,
            timeout=240,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

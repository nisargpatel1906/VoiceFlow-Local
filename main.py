"""
VoiceFlow Local - Windows dictation app.

 PyQt6 tray popup UI + global Ctrl+Space push-to-talk dictation.
"""

from __future__ import annotations

import argparse
import ctypes
import importlib
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

if sys.platform == "win32":
    from ctypes import wintypes

# We MUST import torch / faster_whisper before PyQt6 or we encounter a silent failure
# down the line when starting a streaming dictation thread with CUDA enabled.
try:
    import torch
    import faster_whisper
except ImportError:
    pass

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

import config
from cleaner import TextCleaner
from dictation_threads import StreamingWhisperThread
from gui.settings_window import SettingsWindow
from hotkey import HotkeyManager
from injector import TextInjector
from signals import TranscriptionSignals
from streaming_recorder import StreamingRecorder
from streaming_transcriber import StreamingTranscriber
from voiceflow_ui import TrayController, VoiceFlowWindow, copy_to_clipboard, make_history_entry


def setup_logging(debug_mode: bool = False):
    log_level = logging.DEBUG if debug_mode else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("voiceflow.log", encoding="utf-8"),
            logging.StreamHandler() if debug_mode else logging.NullHandler(),
        ],
    )
    return logging.getLogger(__name__)


def app_logo_icon() -> QIcon:
    logo_path = Path(__file__).resolve().with_name("logo.png")
    if logo_path.exists():
        return QIcon(str(logo_path))
    return QIcon()


class JsonlHistory:
    def __init__(self, path: str, limit: int = 50):
        self.path = path
        self.limit = limit
        self.entries: List[Dict] = []
        self.load()

    def load(self):
        self.entries = []
        if not os.path.exists(self.path):
            return

        with open(self.path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entry.setdefault("chars", len(entry.get("text", "")))
                entry.setdefault("duration_sec", 0)
                entry["time_label"] = self._time_label(entry)
                self.entries.append(entry)

        self.entries = self.entries[-self.limit :]

    def add(self, entry: Dict):
        self.entries.append(entry)
        self.entries = self.entries[-self.limit :]
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({k: v for k, v in entry.items() if k != "time_label"}, ensure_ascii=False) + "\n")

    def clear(self):
        self.entries = []
        with open(self.path, "w", encoding="utf-8"):
            pass

    def _time_label(self, entry: Dict) -> str:
        raw = f"{entry.get('date', '')} {entry.get('time', '')}".strip()
        try:
            created = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
            return created.strftime("%Y-%m-%d, %I:%M %p").replace(" 0", " ")
        except ValueError:
            return entry.get("date", entry.get("time", ""))


class VoiceFlowApp(QObject):
    hotkey_pressed = pyqtSignal()
    hotkey_released = pyqtSignal()
    quit_requested = pyqtSignal()
    silence_timeout = pyqtSignal()
    final_audio_ready = pyqtSignal(str, float)
    final_audio_failed = pyqtSignal(str)

    def __init__(self, debug_mode: bool = False):
        super().__init__()
        self.logger = setup_logging(debug_mode)

        self.qt_app = QApplication.instance() or QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.qt_app.setWindowIcon(app_logo_icon())

        self.window = VoiceFlowWindow()
        self.settings_window = None
        self.tray = TrayController(self.window, self.quit)
        self.cleaner = TextCleaner()
        self.injector = TextInjector()
        self.history = JsonlHistory(config.LOG_FILE, config.HISTORY_LIMIT)
        self.transcription_signals = TranscriptionSignals()
        self.stream_recorder = StreamingRecorder()
        self.stream_transcriber: StreamingTranscriber | None = None
        self._stream_transcriber_signature = None
        self._ensure_stream_transcriber()
        self.chunk_queue: "queue.Queue[str | None]" = queue.Queue(maxsize=3)
        self.recording_started_at = 0.0
        self.pending_final_audio: bytes | None = None
        self.pending_final_duration = 0.0
        self._sound_path = Path(__file__).resolve().with_name("sound.mp3")
        self._enter_sound_path = Path(__file__).resolve().with_name("enter.mp3")
        self._quit_sound_path = Path(__file__).resolve().with_name("quite.mp3")
        self._sound_lock = threading.Lock()
        self._mci_alias = "voiceflow_sound"

        self.window.set_history(self.history.entries)
        self.window.copy_requested.connect(self._copy_text)
        self.window.clear_history_requested.connect(self._clear_history)
        self.window.settings_requested.connect(self._show_settings)
        self.window.history_selected.connect(self._load_history_entry)
        self.transcription_signals.partial_result.connect(self.window.update_live_text)
        self.transcription_signals.final_result.connect(self._on_final_received)

        self.hotkey_pressed.connect(self._start_recording)
        self.hotkey_released.connect(self._stop_recording)
        self.quit_requested.connect(self.quit)
        self.silence_timeout.connect(self._finish_recording)
        self.final_audio_ready.connect(self._on_final_text)
        self.final_audio_failed.connect(self._on_worker_error)
        self.hotkey = HotkeyManager(
            on_press_callback=lambda: self.hotkey_pressed.emit(),
            on_release_callback=lambda: self.hotkey_released.emit(),
            on_quit_callback=lambda: self.quit_requested.emit(),
        )

        self.transcriber_thread: StreamingWhisperThread | None = None
        self.is_recording = False
        self.is_processing = False

    def start(self):
        self.logger.info("Starting VoiceFlow Local UI")
        self.hotkey.start()
        self.window.set_state("idle")
        self.tray.set_state("idle")
        self.tray.notify(f"Ready. Hold {config.HOTKEY} to dictate")
        self._play_app_sound(self._enter_sound_path if self._enter_sound_path.exists() else self._sound_path)
        return self.qt_app.exec()

    @pyqtSlot()
    def _start_recording(self):
        if self.is_processing:
            return
        if self.is_recording:
            if getattr(config, "TOGGLE_MODE", False):
                self._finish_recording()
            return

        self.logger.info("Hotkey pressed")
        self._ensure_stream_transcriber()
        self.is_recording = True
        self.is_processing = False
        self.recording_started_at = time.time()
        self.pending_final_audio = None
        self.pending_final_duration = 0.0
        self.chunk_queue = queue.Queue(maxsize=3)
        self.stream_transcriber.reset()
        self.window.update_live_text("")
        self.window.set_hotkey_active(True)
        self.window.set_state("recording")
        self.window.show_live_badge()
        self.tray.show_floating(hide_window=False)
        self.tray.set_state("recording")

        try:
            on_partial, on_final = self.get_streaming_callbacks()
            self.stream_transcriber.start(self.chunk_queue, on_partial=on_partial, on_final=on_final)
            self.stream_recorder.start(
                self.chunk_queue,
                on_silence_timeout=lambda: self.silence_timeout.emit(),
                silence_threshold_sec=getattr(config, "SILENCE_THRESHOLD_SEC", 0),
            )
        except Exception as exc:
            try:
                self.stream_recorder.stop()
            except Exception:
                pass
            self._on_worker_error(f"Streaming start error: {exc}")
            self._reset_idle()

    @pyqtSlot()
    def _stop_recording(self):
        if not self.is_recording:
            return
        if getattr(config, "TOGGLE_MODE", False):
            return
        self._finish_recording()

    def _finish_recording(self):
        if not self.is_recording:
            return

        self.logger.info("Hotkey released")
        self.is_recording = False
        self.is_processing = True
        self.window.set_hotkey_active(False)
        self.window.set_state("processing")
        self.tray.set_state("processing")
        self.stream_recorder.stop()
        self.pending_final_audio = self.stream_recorder.get_rolling_buffer()
        self.pending_final_duration = max(0.0, time.time() - self.recording_started_at) if self.recording_started_at else 0.0

    @pyqtSlot(bytes, float)
    def _submit_partial_audio(self, audio_bytes: bytes, duration_sec: float):
        # Live Whisper snapshots were disabled because faster-whisper native
        # inference could overlap the release/finalize path and crash on some
        # Windows GPU setups. Final transcription still runs off the UI thread.
        return

    @pyqtSlot(bytes, float)
    def _submit_final_audio(self, audio_bytes: bytes, duration_sec: float):
        if not audio_bytes:
            self._on_worker_error("No audio captured")
            self._reset_idle()
            return
        def _worker():
            try:
                text = self.stream_transcriber.transcribe_final_audio(audio_bytes)
                self.final_audio_ready.emit(text, duration_sec)
            except Exception as exc:
                self.final_audio_failed.emit(f"Final transcription error: {exc}")

        threading.Thread(target=_worker, daemon=True, name="VoiceFlowFinalTranscribe").start()

    @pyqtSlot(str)
    def _on_partial_text(self, text: str):
        self.window.update_live_text(text)

    @pyqtSlot(str, float)
    def _on_final_text(self, raw_text: str, duration_sec: float):
        self._finalize_transcript(raw_text, duration_sec)

    @pyqtSlot(str)
    def _on_final_received(self, raw_text: str):
        if self.pending_final_audio:
            final_audio = self.pending_final_audio
            duration_sec = self.pending_final_duration
            self.pending_final_audio = None
            self.pending_final_duration = 0.0
            self._submit_final_audio(final_audio, duration_sec)
            return

        duration_sec = max(0.0, time.time() - self.recording_started_at) if self.recording_started_at else 0.0
        self._finalize_transcript(raw_text, duration_sec)

    @pyqtSlot(str)
    def _on_streaming_error(self, message: str):
        self.logger.warning(f"Streaming chunk skipped: {message}")

    @pyqtSlot(str)
    def _on_worker_error(self, message: str):
        self.logger.error(message)
        self.is_recording = False
        self.is_processing = False
        self.window.set_hotkey_active(False)
        self.window.hide_live_badge()
        self.window.set_state("idle")
        self.tray.set_state("error")
        self.tray.notify(message[:80], duration=6000)
        QTimer.singleShot(1800, lambda: self.tray.set_state("idle"))

    def _reset_idle(self):
        self.is_recording = False
        self.is_processing = False
        self.pending_final_audio = None
        self.pending_final_duration = 0.0
        self.window.set_hotkey_active(False)
        self.window.hide_live_badge()
        self.window.set_state("idle")
        self.tray.set_state("idle")

    def _finalize_transcript(self, raw_text: str, duration_sec: float):
        self.is_processing = False

        clean_text = self.cleaner.clean(raw_text)
        if not clean_text:
            self._on_worker_error("Transcription returned empty text")
            self._reset_idle()
            return

        self.window.hide_live_badge()
        self.window.update_live_text(clean_text)

        if clean_text != "DELETE_LAST":
            entry = make_history_entry(clean_text, duration_sec)
            if getattr(config, "AUTO_SAVE", True):
                self.history.add(entry)
                self.window.add_history_entry(entry)
            self._inject_text_async(clean_text)
            self.tray.notify(clean_text[:60] + ("..." if len(clean_text) > 60 else ""))
            self._play_app_sound()

        self._reset_idle()

    def _play_app_sound(self, sound_path: Path | None = None):
        def _worker():
            try:
                if sys.platform == "win32":
                    self._play_windows_mp3(sound_path or self._sound_path)
                elif sys.platform == "darwin":
                    self._play_macos_sound(sound_path or self._sound_path)
                else:
                    QApplication.beep()
            except Exception as exc:
                self.logger.debug(f"App sound failed: {exc}")

        threading.Thread(target=_worker, daemon=True, name="VoiceFlowAppSound").start()

    def _play_windows_mp3(self, sound_path: Path):
        if not sound_path.exists():
            return

        mci_send_string = ctypes.windll.winmm.mciSendStringW
        mci_send_string.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.UINT, wintypes.HANDLE]
        mci_send_string.restype = wintypes.UINT

        def _send(command: str):
            error_code = mci_send_string(command, None, 0, None)
            if error_code:
                raise RuntimeError(f"MCI command failed ({error_code}): {command}")

        with self._sound_lock:
            try:
                mci_send_string(f"close {self._mci_alias}", None, 0, None)
            except Exception:
                pass
            sound_file = str(sound_path).replace('"', '""')
            _send(f'open "{sound_file}" type mpegvideo alias {self._mci_alias}')
            _send(f"play {self._mci_alias} from 0")

    def _play_macos_sound(self, sound_path: Path):
        if not sound_path.exists():
            return
        subprocess.Popen(
            ["afplay", str(sound_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def get_streaming_callbacks(self):
        return (
            lambda text: self.transcription_signals.partial_result.emit(text),
            lambda text: self.transcription_signals.final_result.emit(text),
        )

    def _clear_transcriber_thread(self, thread):
        if self.transcriber_thread is thread:
            self.transcriber_thread = None

    def _inject_text_async(self, text: str):
        # Keep focus on the previous app and keep Qt responsive while pyautogui pastes.
        self.tray.show_floating()
        thread = threading.Thread(target=self.injector.inject_at_cursor, args=(text,), daemon=True)
        thread.start()

    @pyqtSlot(str)
    def _copy_text(self, text: str):
        copy_to_clipboard(text)
        self.tray.notify("Copied")

    @pyqtSlot()
    def _clear_history(self):
        self.history.clear()
        self.window.set_history([])
        self.window.update_live_text("")
        self.tray.notify("History cleared")

    @pyqtSlot()
    def _show_settings(self):
        if self.settings_window is None:
            self.settings_window = SettingsWindow()
            self.settings_window.settings_changed.connect(self._reload_settings)
            self.settings_window.window_hidden.connect(self.hotkey.resume_hotkey)
            self.settings_window.return_to_floating.connect(self._return_to_floating)

        self.hotkey.pause_hotkey()
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    @pyqtSlot()
    def _return_to_floating(self):
        if self.settings_window:
            self.settings_window.hide()
        self.tray.show_floating()

    @pyqtSlot()
    def _reload_settings(self):
        importlib.reload(config)
        self.cleaner = TextCleaner()
        if self._transcriber_signature() != self._stream_transcriber_signature:
            self.stream_transcriber = None
            self._stream_transcriber_signature = None
        self.history.path = config.LOG_FILE
        self.history.limit = config.HISTORY_LIMIT
        self.history.load()
        self.window.set_history(self.history.entries)
        if self.hotkey.hotkey != config.HOTKEY:
            self.hotkey.update_hotkey(config.HOTKEY)
            self.window.refresh_hotkey_display()
        self.hotkey.update_quit_hotkey(getattr(config, "QUIT_HOTKEY", "ctrl+q"))
        self.tray.notify("Settings saved")

    def _transcriber_signature(self):
        return (
            getattr(config, "MODEL_SIZE", None),
            getattr(config, "DEVICE", None),
            getattr(config, "COMPUTE_TYPE", None),
            getattr(config, "LANGUAGE", None),
            getattr(config, "TRANSLATE_TO_ENGLISH", None),
            getattr(config, "BEAM_SIZE", None),
            getattr(config, "MODEL_DIR", None),
        )

    def _ensure_stream_transcriber(self):
        signature = self._transcriber_signature()
        if self.stream_transcriber is not None and self._stream_transcriber_signature == signature:
            return
        self.stream_transcriber = StreamingTranscriber(config)
        self.stream_transcriber.error_ready.connect(self._on_streaming_error)
        self._stream_transcriber_signature = signature

    @pyqtSlot(dict)
    def _load_history_entry(self, entry: Dict):
        self.window.update_live_text(entry.get("text", ""))

    def quit(self):
        self._play_app_sound(self._quit_sound_path if self._quit_sound_path.exists() else self._sound_path)
        self.qt_app.processEvents()
        time.sleep(0.12)
        self.hotkey.stop()
        self.stream_recorder.stop()
        if self.transcriber_thread and self.transcriber_thread.isRunning():
            self.transcriber_thread.stop()
        self.tray.tray_icon.hide()
        self.tray.floating.hide()
        if self.settings_window:
            self.settings_window.hide()
        self.qt_app.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VoiceFlow Local")
    parser.add_argument("--debug", action="store_true", help="Enable console debug logging")
    args = parser.parse_args()

    app = VoiceFlowApp(debug_mode=args.debug)
    try:
        sys.exit(app.start())
    except KeyboardInterrupt:
        app.quit()

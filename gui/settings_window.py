"""
VoiceFlow Local - Settings window.

Frameless PyQt6 settings panel that reads/writes config.py and emits
settings_changed after a successful save.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QKeyEvent, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

import config


BG = "#0f0f13"
SURFACE = "#16161e"
BORDER = "#2a2a3a"
TEXT = "#ECEFF1"
MUTED = "#8c93a1"
ACCENT = "#4A90D9"
PRIMARY = "#1565C0"
SUCCESS = "#2E7D32"


DEFAULT_CONFIG: Dict[str, Any] = {
    "HOTKEY": "ctrl+space",
    "TOGGLE_MODE": False,
    "MODEL_SIZE": "medium",
    "DEVICE": "cuda",
    "COMPUTE_TYPE": "float16",
    "LANGUAGE": "en",
    "LANGUAGE_CHOICE": "english",
    "BEAM_SIZE": 5,
    "PRELOAD_MODEL_ON_START": False,
    "REMOVE_FILLERS": True,
    "FILLER_WORDS": ["um", "uh", "like", "you know", "basically", "actually", "literally", "right", "so", "well"],
    "FIX_SELF_CORRECTIONS": True,
    "AUTO_CAPITALIZE": True,
    "ENABLE_VOICE_COMMANDS": True,
    "HISTORY_LIMIT": 50,
    "AUTO_SAVE": True,
    "LOG_FORMAT": "JSON lines",
    "START_WITH_WINDOWS": False,
    "SHOW_NOTIFICATIONS": True,
    "SILENCE_THRESHOLD_SEC": 3,
    "DEBUG_MODE": False,
}

LANGUAGE_TO_CODE = {
    "auto detect": None,
    "english": "en",
    "hindi": "hi",
    "hinglish": "en",
    "gujarati": "gu",
}

CODE_TO_LANGUAGE = {
    None: "auto detect",
    "en": "english",
    "hi": "hindi",
    "gu": "gujarati",
}


def ui_font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont("Segoe UI", size)
    font.setWeight(weight)
    return font


def cfg(name: str) -> Any:
    return getattr(config, name, DEFAULT_CONFIG[name])


def format_hotkey(value: str) -> str:
    parts = [part.strip() for part in value.replace("-", "+").split("+") if part.strip()]
    names = {
        "ctrl": "Ctrl",
        "control": "Ctrl",
        "alt": "Alt",
        "shift": "Shift",
        "windows": "Win",
        "win": "Win",
        "space": "Space",
    }
    return " + ".join(names.get(part.lower(), part.upper() if len(part) == 1 else part.title()) for part in parts)


def normalize_hotkey(display_value: str) -> str:
    return display_value.lower().replace(" ", "")


def detect_cuda_label() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return f"CUDA - {torch.cuda.get_device_name(0)}"
    except Exception:
        pass
    return "CUDA - RTX 3050"


def startup_command() -> str:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else Path(sys.executable)
    main_py = Path(__file__).resolve().parents[1] / "main.py"
    return f'"{exe}" "{main_py}"'


def set_startup_enabled(enabled: bool):
    if sys.platform != "win32":
        return

    import winreg

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, "VoiceFlow Local", 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, "VoiceFlow Local")
            except FileNotFoundError:
                pass


class Toggle(QCheckBox):
    def __init__(self, checked: bool = False):
        super().__init__()
        self.setChecked(checked)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(44, 24)
        self.setStyleSheet(
            f"""
            QCheckBox::indicator {{
                width: 44px;
                height: 24px;
                border-radius: 12px;
                background: #20202a;
                border: 1px solid #545463;
            }}
            QCheckBox::indicator:checked {{
                background: {PRIMARY};
                border: 1px solid {ACCENT};
            }}
            """
        )

    def paintEvent(self, event):  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QColor(PRIMARY if self.isChecked() else "#20202a")
        painter.setBrush(track)
        painter.setPen(QPen(QColor(ACCENT if self.isChecked() else "#545463"), 1))
        painter.drawRoundedRect(0, 0, 44, 24, 12, 12)
        knob_x = 23 if self.isChecked() else 3
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(knob_x, 3, 18, 18)


class HotkeyRecorder(QPushButton):
    changed = pyqtSignal(str)

    def __init__(self, value: str):
        super().__init__(format_hotkey(value))
        self.hotkey = value
        self.recording = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumWidth(120)
        self._style(False)
        self.clicked.connect(self._start_capture)

    def _style(self, active: bool):
        border = ACCENT if active else BORDER
        self.setStyleSheet(
            f"QPushButton {{ background: {BG}; color: {ACCENT}; border: 1px solid {border}; border-radius: 7px; padding: 7px 12px; font-weight: 700; }}"
        )

    def _start_capture(self):
        self.recording = True
        self.setText("press keys...")
        self._style(True)
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent):  # noqa: N802 - Qt override
        if not self.recording:
            return super().keyPressEvent(event)

        key = event.key()
        if key in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
            Qt.Key.Key_unknown,
        ):
            return

        parts: List[str] = []
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("windows")

        key_name = self._key_name(key, event.text())
        if key_name:
            parts.append(key_name)

        if parts:
            self.hotkey = "+".join(parts)
            self.setText(format_hotkey(self.hotkey))
            self.changed.emit(self.hotkey)
        self.recording = False
        self._style(False)

    def _key_name(self, key: int, text: str) -> str:
        if key == Qt.Key.Key_Space:
            return "space"
        if key == Qt.Key.Key_Return:
            return "enter"
        if key == Qt.Key.Key_Tab:
            return "tab"
        if key == Qt.Key.Key_Escape:
            return "esc"
        if text and text.strip():
            return text.lower()
        name = Qt.Key(key).name.replace("Key_", "").lower()
        return name


class Chip(QPushButton):
    removed = pyqtSignal(str)

    def __init__(self, word: str):
        super().__init__(f"{word}  x")
        self.word = word
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clicked.connect(lambda: self.removed.emit(self.word))
        self.setStyleSheet(
            f"QPushButton {{ background: #202033; color: #aab2c0; border: 1px solid {BORDER}; border-radius: 5px; padding: 5px 8px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; color: {TEXT}; }}"
        )


class SectionCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setStyleSheet(f"QFrame {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 10, 14, 12)
        self.layout.setSpacing(0)

        label = QLabel(title)
        label.setFont(ui_font(8, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {MUTED}; letter-spacing: 2px; border: none; background: transparent;")
        self.layout.addWidget(label)

    def row(self, title: str, subtitle: str = "", control: Optional[QWidget] = None):
        wrap = QFrame()
        wrap.setStyleSheet(f"QFrame {{ border: none; border-top: 1px solid {BORDER}; border-radius: 0; background: transparent; }}")
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 12, 0, 10)
        row.setSpacing(12)

        labels = QVBoxLayout()
        labels.setContentsMargins(0, 0, 0, 0)
        labels.setSpacing(3)
        title_label = QLabel(title)
        title_label.setFont(ui_font(10, QFont.Weight.DemiBold))
        title_label.setStyleSheet(f"color: {TEXT}; border: none; background: transparent;")
        labels.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setFont(ui_font(8))
            subtitle_label.setStyleSheet(f"color: {MUTED}; border: none; background: transparent;")
            labels.addWidget(subtitle_label)
        row.addLayout(labels, 1)
        if control:
            row.addWidget(control)
        self.layout.addWidget(wrap)
        return wrap


class SettingsWindow(QWidget):
    settings_changed = pyqtSignal()
    window_hidden = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(480, 680)
        self.setWindowTitle("VoiceFlow Local Settings")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._drag_pos: Optional[QPoint] = None
        self.filler_words = list(cfg("FILLER_WORDS"))

        self._build()
        self._load_values()

    def _build(self):
        self.setStyleSheet(self._stylesheet())
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        titlebar = QFrame()
        titlebar.setObjectName("Titlebar")
        titlebar.setFixedHeight(58)
        title_layout = QHBoxLayout(titlebar)
        title_layout.setContentsMargins(18, 0, 18, 0)
        title_layout.setSpacing(10)

        icon = QFrame()
        icon.setFixedSize(32, 28)
        icon.setStyleSheet(f"background: {SURFACE}; border: 1px solid #545463; border-radius: 7px;")
        title = QLabel("settings")
        title.setFont(ui_font(12, QFont.Weight.Bold))
        version = QLabel("v1.0.0")
        version.setStyleSheet("background: #202033; color: #757b89; border-radius: 5px; padding: 3px 8px;")
        close_btn = QPushButton("x")
        close_btn.setFixedSize(26, 26)
        close_btn.clicked.connect(self.hide)

        title_layout.addWidget(icon)
        title_layout.addWidget(title)
        title_layout.addStretch()
        title_layout.addWidget(version)
        title_layout.addWidget(close_btn)
        root.addWidget(titlebar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("Scroll")
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(18, 18, 18, 18)
        self.content_layout.setSpacing(12)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self._build_hotkey()
        self._build_model()
        self._build_cleanup()
        self._build_save_log()
        self._build_behaviour()
        self._build_stats()
        self.content_layout.addStretch()

        bottom = QFrame()
        bottom.setObjectName("BottomBar")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(18, 12, 18, 14)
        bottom_layout.setSpacing(10)
        reset = QPushButton("reset")
        reset.clicked.connect(self.reset_defaults)
        self.save_btn = QPushButton("save settings")
        self.save_btn.setObjectName("SaveButton")
        self.save_btn.clicked.connect(self.save_settings)
        bottom_layout.addWidget(reset)
        bottom_layout.addWidget(self.save_btn, 1)
        root.addWidget(bottom)

    def _build_hotkey(self):
        card = SectionCard("HOTKEY")
        self.hotkey_field = HotkeyRecorder(cfg("HOTKEY"))
        card.row("push-to-talk hotkey", "hold to record, release to transcribe", self.hotkey_field)
        self.toggle_mode = Toggle(bool(cfg("TOGGLE_MODE")))
        card.row("toggle mode", "tap once to start, tap again to stop", self.toggle_mode)
        self.content_layout.addWidget(card)

    def _build_model(self):
        card = SectionCard("AI MODEL")
        self.model_size = self.combo(["tiny", "base", "medium", "large-v3"])
        card.row("whisper model", "larger = more accurate, slower", self.model_size)

        device_wrap = QWidget()
        device_layout = QHBoxLayout(device_wrap)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_layout.setSpacing(8)
        self.device_badge = QLabel(detect_cuda_label())
        self.device_badge.setStyleSheet(f"background: #143d18; color: #69d36f; border-radius: 5px; padding: 5px 8px; font-weight: 700;")
        self.compute_type = self.combo(["float16", "float32", "int8"])
        device_layout.addWidget(self.device_badge)
        device_layout.addWidget(self.compute_type)
        card.row("device", "GPU detected: RTX 3050", device_wrap)

        self.language = self.combo(["auto detect", "english", "hindi", "hinglish", "gujarati"])
        card.row("language", "auto-detect or fix to one language", self.language)

        self.beam_size, self.beam_value = self.slider(1, 10)
        card.row("beam size", "higher = more accurate, slower", self._slider_control(self.beam_size, self.beam_value))
        self.content_layout.addWidget(card)

    def _build_cleanup(self):
        card = SectionCard("TEXT CLEANUP")
        self.remove_fillers = Toggle(bool(cfg("REMOVE_FILLERS")))
        card.row("remove filler words", "removes um, uh, like, you know...", self.remove_fillers)

        self.chips_wrap = QWidget()
        self.chips = QGridLayout(self.chips_wrap)
        self.chips.setContentsMargins(0, 8, 0, 8)
        self.chips.setHorizontalSpacing(6)
        self.chips.setVerticalSpacing(6)
        card.layout.addWidget(self.chips_wrap)
        self._render_chips()

        self.fix_self_corrections = Toggle(bool(cfg("FIX_SELF_CORRECTIONS")))
        card.row("fix self-corrections", '"5pm no wait 6pm" -> "6pm"', self.fix_self_corrections)
        self.auto_capitalize = Toggle(bool(cfg("AUTO_CAPITALIZE")))
        card.row("auto-capitalize", "capitalize first letter of output", self.auto_capitalize)
        self.voice_commands = Toggle(bool(cfg("ENABLE_VOICE_COMMANDS")))
        card.row("voice commands", '"new line", "comma", "delete that"', self.voice_commands)
        self.content_layout.addWidget(card)

    def _build_save_log(self):
        card = SectionCard("SAVE LOG")
        self.auto_save = Toggle(bool(cfg("AUTO_SAVE")))
        card.row("auto-save transcriptions", "saves every dictation with date + time", self.auto_save)

        path_wrap = QWidget()
        path_layout = QHBoxLayout(path_wrap)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(8)
        self.log_path = QLabel(str(getattr(config, "LOG_FILE", os.path.join(config.BASE_DIR, "voiceflow_log.txt"))))
        self.log_path.setMinimumWidth(220)
        self.log_path.setStyleSheet(f"background: {BG}; color: {ACCENT}; border: 1px solid {BORDER}; border-radius: 5px; padding: 7px;")
        change = QPushButton("change")
        change.clicked.connect(self.change_log_path)
        path_layout.addWidget(self.log_path, 1)
        path_layout.addWidget(change)
        card.row("log file location", "", path_wrap)

        self.log_format = self.combo(["JSON lines", "plain text", "CSV"])
        card.row("log format", "", self.log_format)

        self.history_limit, self.history_value = self.slider(10, 200)
        card.row("history limit", "entries kept in sidebar", self._slider_control(self.history_limit, self.history_value))
        self.content_layout.addWidget(card)

    def _build_behaviour(self):
        card = SectionCard("BEHAVIOUR")
        self.start_with_windows = Toggle(bool(cfg("START_WITH_WINDOWS")))
        card.row("start with Windows", "launch automatically on boot", self.start_with_windows)
        self.show_notifications = Toggle(bool(cfg("SHOW_NOTIFICATIONS")))
        card.row("show notification on paste", "brief toast after each dictation", self.show_notifications)
        self.silence_threshold, self.silence_value = self.slider(1, 10, suffix="s")
        card.row("silence threshold", "stop recording after x seconds quiet", self._slider_control(self.silence_threshold, self.silence_value))
        self.debug_mode = Toggle(bool(cfg("DEBUG_MODE")))
        card.row("debug mode", "log all events to voiceflow.log", self.debug_mode)
        self.content_layout.addWidget(card)

    def _build_stats(self):
        card = SectionCard("STATS")
        stats = self._read_stats()
        grid = QGridLayout()
        grid.setContentsMargins(0, 12, 0, 0)
        grid.setHorizontalSpacing(0)
        labels = [
            (str(stats["total_dictations"]), "total dictations"),
            (f"{stats['avg_latency']:.1f}s", "avg latency"),
            (f"{stats['total_words']:,}", "words spoken"),
        ]
        for col, (value, label) in enumerate(labels):
            box = QFrame()
            box.setStyleSheet(f"QFrame {{ background: transparent; border-left: {'none' if col == 0 else '1px solid ' + BORDER}; border-radius: 0; }}")
            layout = QVBoxLayout(box)
            layout.setContentsMargins(12, 8, 12, 8)
            value_label = QLabel(value)
            value_label.setFont(ui_font(15, QFont.Weight.Bold))
            caption = QLabel(label)
            caption.setFont(ui_font(8))
            caption.setStyleSheet(f"color: {MUTED};")
            layout.addWidget(value_label)
            layout.addWidget(caption)
            grid.addWidget(box, 0, col)
        card.layout.addLayout(grid)
        self.content_layout.addWidget(card)

    def combo(self, options: List[str]) -> QComboBox:
        combo = QComboBox()
        combo.addItems(options)
        combo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        return combo

    def slider(self, minimum: int, maximum: int, suffix: str = ""):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setFixedWidth(130)
        value = QLabel()
        value.setMinimumWidth(28)
        value.setStyleSheet(f"color: {ACCENT};")
        slider.valueChanged.connect(lambda current: value.setText(f"{current}{suffix}"))
        return slider, value

    def _slider_control(self, slider: QSlider, value: QLabel) -> QWidget:
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(slider)
        layout.addWidget(value)
        return wrap

    def _render_chips(self):
        while self.chips.count():
            item = self.chips.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for index, word in enumerate(self.filler_words):
            chip = Chip(word)
            chip.removed.connect(self._remove_filler)
            self.chips.addWidget(chip, index // 4, index % 4)

        add = QPushButton("+ add word")
        add.clicked.connect(self._add_filler)
        add.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add.setStyleSheet(f"background: transparent; color: {TEXT}; border: 1px solid #545463; border-radius: 6px; padding: 6px 12px;")
        index = len(self.filler_words)
        self.chips.addWidget(add, index // 4, index % 4)

    def _remove_filler(self, word: str):
        self.filler_words = [item for item in self.filler_words if item != word]
        self._render_chips()

    def _add_filler(self):
        word, ok = QInputDialog.getText(self, "Add filler word", "Word or phrase:")
        word = word.strip()
        if ok and word and word not in self.filler_words:
            self.filler_words.append(word)
            self._render_chips()

    def _load_values(self):
        self.model_size.setCurrentText(str(cfg("MODEL_SIZE")))
        self.compute_type.setCurrentText(str(cfg("COMPUTE_TYPE")))
        language_choice = getattr(config, "LANGUAGE_CHOICE", CODE_TO_LANGUAGE.get(getattr(config, "LANGUAGE", "en"), "english"))
        self.language.setCurrentText(language_choice)
        self.beam_size.setValue(int(cfg("BEAM_SIZE")))
        self.history_limit.setValue(int(cfg("HISTORY_LIMIT")))
        self.silence_threshold.setValue(int(cfg("SILENCE_THRESHOLD_SEC")))
        self.log_format.setCurrentText(str(cfg("LOG_FORMAT")))

    def current_values(self) -> Dict[str, Any]:
        language_choice = self.language.currentText()
        log_file = self.log_path.text()
        return {
            "HOTKEY": self.hotkey_field.hotkey,
            "TOGGLE_MODE": self.toggle_mode.isChecked(),
            "MODEL_SIZE": self.model_size.currentText(),
            "DEVICE": "cuda",
            "COMPUTE_TYPE": self.compute_type.currentText(),
            "LANGUAGE": LANGUAGE_TO_CODE[language_choice],
            "LANGUAGE_CHOICE": language_choice,
            "BEAM_SIZE": self.beam_size.value(),
            "PRELOAD_MODEL_ON_START": bool(cfg("PRELOAD_MODEL_ON_START")),
            "REMOVE_FILLERS": self.remove_fillers.isChecked(),
            "FILLER_WORDS": self.filler_words,
            "FIX_SELF_CORRECTIONS": self.fix_self_corrections.isChecked(),
            "AUTO_CAPITALIZE": self.auto_capitalize.isChecked(),
            "ENABLE_VOICE_COMMANDS": self.voice_commands.isChecked(),
            "HISTORY_LIMIT": self.history_limit.value(),
            "AUTO_SAVE": self.auto_save.isChecked(),
            "LOG_FILE": log_file,
            "LOG_FORMAT": self.log_format.currentText(),
            "START_WITH_WINDOWS": self.start_with_windows.isChecked(),
            "SHOW_NOTIFICATIONS": self.show_notifications.isChecked(),
            "SILENCE_THRESHOLD_SEC": self.silence_threshold.value(),
            "DEBUG_MODE": self.debug_mode.isChecked(),
        }

    def change_log_path(self):
        path, _ = QFileDialog.getSaveFileName(self, "Choose log file", self.log_path.text(), "Text files (*.txt);;All files (*.*)")
        if path:
            self.log_path.setText(path)

    def reset_defaults(self):
        self.apply_values(DEFAULT_CONFIG | {"LOG_FILE": os.path.join(config.BASE_DIR, "voiceflow_log.txt")})
        self.save_settings()

    def apply_values(self, values: Dict[str, Any]):
        self.hotkey_field.hotkey = values["HOTKEY"]
        self.hotkey_field.setText(format_hotkey(values["HOTKEY"]))
        self.toggle_mode.setChecked(values["TOGGLE_MODE"])
        self.model_size.setCurrentText(values["MODEL_SIZE"])
        self.compute_type.setCurrentText(values["COMPUTE_TYPE"])
        self.language.setCurrentText(values["LANGUAGE_CHOICE"])
        self.beam_size.setValue(values["BEAM_SIZE"])
        self.remove_fillers.setChecked(values["REMOVE_FILLERS"])
        self.filler_words = list(values["FILLER_WORDS"])
        self._render_chips()
        self.fix_self_corrections.setChecked(values["FIX_SELF_CORRECTIONS"])
        self.auto_capitalize.setChecked(values["AUTO_CAPITALIZE"])
        self.voice_commands.setChecked(values["ENABLE_VOICE_COMMANDS"])
        self.auto_save.setChecked(values["AUTO_SAVE"])
        self.log_path.setText(values["LOG_FILE"])
        self.log_format.setCurrentText(values["LOG_FORMAT"])
        self.history_limit.setValue(values["HISTORY_LIMIT"])
        self.start_with_windows.setChecked(values["START_WITH_WINDOWS"])
        self.show_notifications.setChecked(values["SHOW_NOTIFICATIONS"])
        self.silence_threshold.setValue(values["SILENCE_THRESHOLD_SEC"])
        self.debug_mode.setChecked(values["DEBUG_MODE"])

    def save_settings(self):
        values = self.current_values()
        write_config(values)
        try:
            set_startup_enabled(values["START_WITH_WINDOWS"])
        except Exception:
            pass
        importlib.reload(config)
        self.settings_changed.emit()
        self._flash_saved()

    def _flash_saved(self):
        self.save_btn.setText("saved")
        self.save_btn.setStyleSheet(f"background: {SUCCESS}; color: white; border-radius: 8px; padding: 10px; font-weight: 700;")
        QTimer.singleShot(1100, self._restore_save_button)

    def _restore_save_button(self):
        self.save_btn.setText("save settings")
        self.save_btn.setStyleSheet("")

    def _read_stats(self) -> Dict[str, float]:
        entries: List[Dict[str, Any]] = []
        history_path = Path(config.BASE_DIR) / "history.json"
        if history_path.exists():
            try:
                entries = json.loads(history_path.read_text(encoding="utf-8"))
            except Exception:
                entries = []

        if not entries:
            log_path = Path(getattr(config, "LOG_FILE", os.path.join(config.BASE_DIR, "voiceflow_log.txt")))
            if log_path.exists():
                for line in log_path.read_text(encoding="utf-8").splitlines():
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass

        total = len(entries)
        words = sum(len(str(item.get("text", "")).split()) for item in entries)
        latencies = [float(item.get("duration_sec", 0)) for item in entries if item.get("duration_sec")]
        avg = sum(latencies) / len(latencies) if latencies else 0.0
        return {"total_dictations": total, "avg_latency": avg, "total_words": words}

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 58:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt override
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt override
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def hideEvent(self, event):  # noqa: N802 - Qt override
        self.window_hidden.emit()
        super().hideEvent(event)

    def _stylesheet(self) -> str:
        return f"""
        QWidget {{
            background: {BG};
            color: {TEXT};
            font-family: Segoe UI;
        }}
        QFrame#Titlebar {{
            background: {SURFACE};
            border-bottom: 1px solid {BORDER};
        }}
        QFrame#BottomBar {{
            background: {BG};
            border-top: 1px solid {BORDER};
        }}
        QScrollArea#Scroll {{
            border: none;
            background: {BG};
        }}
        QScrollBar:vertical {{
            background: {BG};
            width: 6px;
        }}
        QScrollBar::handle:vertical {{
            background: #3a3a4a;
            border-radius: 3px;
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QPushButton {{
            background: transparent;
            color: {TEXT};
            border: 1px solid #545463;
            border-radius: 8px;
            padding: 8px 14px;
            font-weight: 700;
        }}
        QPushButton:hover {{
            border-color: {ACCENT};
        }}
        QPushButton#SaveButton {{
            background: transparent;
            border-color: #545463;
        }}
        QComboBox {{
            background: #282a27;
            color: {TEXT};
            border: 1px solid #4d504b;
            border-radius: 7px;
            padding: 8px 12px;
            min-width: 132px;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox QAbstractItemView {{
            background: {SURFACE};
            color: {TEXT};
            selection-background-color: {PRIMARY};
            border: 1px solid {BORDER};
        }}
        QSlider::groove:horizontal {{
            height: 4px;
            background: #333348;
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            width: 16px;
            height: 16px;
            margin: -6px 0;
            border-radius: 8px;
            background: {ACCENT};
            border: 2px solid {PRIMARY};
        }}
        """


def literal(value: Any) -> str:
    if isinstance(value, str):
        return repr(value)
    if value is None:
        return "None"
    return repr(value)


def write_config(values: Dict[str, Any]):
    base_dir_line = "BASE_DIR = os.path.dirname(os.path.abspath(__file__))"
    log_file = values["LOG_FILE"]
    default_log = os.path.join(config.BASE_DIR, "voiceflow_log.txt")
    if os.path.normcase(os.path.abspath(log_file)) == os.path.normcase(os.path.abspath(default_log)):
        log_value = "os.path.join(BASE_DIR, 'voiceflow_log.txt')"
    else:
        log_value = literal(log_file)

    content = f'''"""
VoiceFlow Local - Configuration Settings

Generated by the settings window.
"""

import os

# Hotkey
HOTKEY = {literal(values["HOTKEY"])}
TOGGLE_MODE = {literal(values["TOGGLE_MODE"])}

# Whisper model
MODEL_SIZE = {literal(values["MODEL_SIZE"])}
DEVICE = {literal(values["DEVICE"])}
COMPUTE_TYPE = {literal(values["COMPUTE_TYPE"])}
LANGUAGE = {literal(values["LANGUAGE"])}
LANGUAGE_CHOICE = {literal(values["LANGUAGE_CHOICE"])}
BEAM_SIZE = {literal(values["BEAM_SIZE"])}
PRELOAD_MODEL_ON_START = {literal(values["PRELOAD_MODEL_ON_START"])}

# Text cleanup
REMOVE_FILLERS = {literal(values["REMOVE_FILLERS"])}
FILLER_WORDS = {literal(values["FILLER_WORDS"])}
FIX_SELF_CORRECTIONS = {literal(values["FIX_SELF_CORRECTIONS"])}
AUTO_CAPITALIZE = {literal(values["AUTO_CAPITALIZE"])}
ENABLE_VOICE_COMMANDS = {literal(values["ENABLE_VOICE_COMMANDS"])}

# Storage
HISTORY_LIMIT = {literal(values["HISTORY_LIMIT"])}
AUTO_SAVE = {literal(values["AUTO_SAVE"])}
LOG_FORMAT = {literal(values["LOG_FORMAT"])}
{base_dir_line}
MODEL_DIR = os.path.join(BASE_DIR, 'models')
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
LOG_FILE = {log_value}

# Behaviour
START_WITH_WINDOWS = {literal(values["START_WITH_WINDOWS"])}
SHOW_NOTIFICATIONS = {literal(values["SHOW_NOTIFICATIONS"])}
SILENCE_THRESHOLD_SEC = {literal(values["SILENCE_THRESHOLD_SEC"])}
DEBUG_MODE = {literal(values["DEBUG_MODE"])}
'''
    Path(config.BASE_DIR, "config.py").write_text(content, encoding="utf-8")

"""
VoiceFlow Local - compact tray popup UI.
"""

from __future__ import annotations

import ctypes
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pyperclip
from PyQt6.QtCore import QByteArray, QEasingCurve, QEvent, QPoint, QPropertyAnimation, QRectF, QSize, Qt, QTimer, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSystemTrayIcon, QTextEdit, QToolButton, QVBoxLayout, QWidget

import config

if sys.platform == "win32":
    HWND_TOPMOST = -1
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
    SWP_NOOWNERZORDER = 0x0200
    SWP_NOSENDCHANGING = 0x0400


BG = "#0d0d12"
SURFACE = "#17171f"
SURFACE_2 = "#1c1c26"
BORDER = "#262636"
TEXT = "#f1f3f7"
MUTED = "#8f95a3"
ACCENT = "#8bbcff"
PRIMARY = "#1768c7"
RECORDING = "#ffaaa8"
RECORDING_DEEP = "#7c2b2e"
PROCESSING = "#f6b84a"
SUCCESS = "#2edc88"
NAVY = "#1b1d35"


MIC_SVG = """
<svg width="40" height="40" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M24 8C20.7 8 18 10.7 18 14V24C18 27.3 20.7 30 24 30C27.3 30 30 27.3 30 24V14C30 10.7 27.3 8 24 8Z" stroke="white" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M13 23V24C13 30.1 17.9 35 24 35C30.1 35 35 30.1 35 24V23" stroke="white" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M24 35V41" stroke="white" stroke-width="3.5" stroke-linecap="round"/>
</svg>
""".strip()


def app_font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont("Segoe UI", size)
    font.setWeight(weight)
    return font


def app_logo_icon() -> QIcon:
    logo_path = Path(__file__).resolve().with_name("logo.png")
    if logo_path.exists():
        return QIcon(str(logo_path))
    return QIcon()


def format_hotkey_text(value: str) -> str:
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


class LogoMark(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(24, 24)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(NAVY))
        painter.drawRoundedRect(self.rect(), 5, 5)
        painter.setBrush(QColor("#dce9ff"))
        for x, height in zip([6, 11, 16], [12, 17, 10]):
            painter.drawRoundedRect(QRectF(x, (24 - height) / 2, 3, height), 1.5, 1.5)


class StatusPill(QFrame):
    def __init__(self):
        super().__init__()
        self.dot = QLabel()
        self.dot.setFixedSize(6, 6)
        self.label = QLabel("ready")
        self.label.setFont(app_font(7, QFont.Weight.Bold))
        self.label.setStyleSheet(f"color: {MUTED}; background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 4, 7, 4)
        layout.setSpacing(5)
        layout.addWidget(self.dot)
        layout.addWidget(self.label)
        self._pulse = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.set_state("ready")

    def set_state(self, state: str):
        self.state = state
        labels = {"ready": "ready", "recording": "RECORDING", "processing": "processing"}
        colors = {"ready": SUCCESS, "recording": RECORDING, "processing": PROCESSING}
        self.label.setText(labels.get(state, state))
        pill_bg = "#191c1e" if state != "recording" else "#2a171b"
        pill_border = "#22382e" if state == "ready" else ("#5e2b33" if state == "recording" else "#4d3b1f")
        self.setStyleSheet(f"QFrame {{ background: {pill_bg}; border: 1px solid {pill_border}; border-radius: 9px; }}")
        self._set_dot(colors.get(state, SUCCESS), 1.0)
        if state == "recording":
            self._timer.start(450)
        else:
            self._timer.stop()

    def _set_dot(self, color: str, opacity: float):
        c = QColor(color)
        c.setAlphaF(opacity)
        self.dot.setStyleSheet(f"background: rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha()}); border-radius: 3px;")

    def _tick(self):
        self._pulse = not self._pulse
        self._set_dot(RECORDING, 1.0 if self._pulse else 0.45)


class KeyBadge(QLabel):
    def __init__(self, text: str):
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(18)
        self.setMinimumWidth(36 if len(text) >= 4 else 28)
        self.setFont(app_font(7, QFont.Weight.Bold))
        self.set_active(False)

    def set_active(self, active: bool):
        bg = "#32415b" if active else "#222634"
        color = "#dbe8ff" if active else "#c1c7d1"
        self.setStyleSheet(f"background: {bg}; color: {color}; border: 1px solid #303646; border-radius: 3px; padding: 1px 5px;")


class HotkeyDisplay(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)
        self.badges = []
        self._update_badges()

    def _update_badges(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self.badges = []
        hotkey_parts = config.HOTKEY.replace("-", "+").split("+")
        for part in hotkey_parts:
            badge = KeyBadge(format_hotkey_text(part))
            self.badges.append(badge)
            self.layout.addWidget(badge)

    def set_active(self, active: bool):
        for badge in self.badges:
            badge.set_active(active)


class MicButton(QToolButton):
    def __init__(self):
        super().__init__()
        self.setFixedSize(104, 92)
        self.refresh_hotkey_text()
        self.state = "ready"
        self._radius = 32.0
        self._svg = QSvgRenderer(QByteArray(MIC_SVG.encode("utf-8")))
        self._anim = QPropertyAnimation(self, b"pulseRadius", self)
        self._anim.setStartValue(32.0)
        self._anim.setEndValue(45.0)
        self._anim.setDuration(850)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)

    def get_pulse_radius(self):
        return self._radius

    def set_pulse_radius(self, value):
        self._radius = value
        self.update()

    pulseRadius = pyqtProperty(float, fget=get_pulse_radius, fset=set_pulse_radius)

    def set_state(self, state: str):
        self.state = state
        if state == "recording":
            self._anim.start()
        else:
            self._anim.stop()
            self._radius = 32.0
        self.update()

    def refresh_hotkey_text(self):
        self.setToolTip(f"Hold {format_hotkey_text(config.HOTKEY)} to start")

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.rect().center()
        if self.state == "recording":
            pulse = QColor(RECORDING)
            pulse.setAlpha(58)
            painter.setBrush(pulse)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, int(self._radius), int(self._radius))
        fill = QColor(RECORDING if self.state == "recording" else PRIMARY)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawEllipse(center, 30, 30)
        self._svg.render(painter, QRectF(center.x() - 15, center.y() - 17, 30, 30))


class WaveformWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(70, 34)
        self.mode = "idle"
        self.level = 0.2
        self.phase = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def set_recording(self, recording: bool):
        self.mode = "recording" if recording else "idle"
        if recording:
            self.timer.start(80)
        else:
            self.timer.stop()
            self.level = 0.18
        self.update()

    def set_mode(self, mode: str):
        self.mode = mode
        if mode in ("recording", "processing"):
            self.timer.start(80)
        else:
            self.timer.stop()
            self.level = 0.18
        self.update()

    def set_level(self, level: float):
        self.level = max(0.12, min(level, 1.0))
        self.update()

    def _tick(self):
        self.phase = (self.phase + 1) % 10
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if self.mode == "recording":
            color = QColor("#9bc8ff")
        elif self.mode == "processing":
            color = QColor("#f6b84a")
        else:
            color = QColor("#6f91bd")
        painter.setBrush(color)
        base = [0.35, 0.65, 0.95, 0.55, 0.8, 0.42, 0.6]
        for index, scale in enumerate(base):
            if self.mode == "recording":
                extra = 0.25 if (index + self.phase) % 4 == 0 else 0
            elif self.mode == "processing":
                extra = 0.15 if (index + self.phase) % 3 == 0 else 0
            else:
                extra = 0
            height = 6 + (self.height() - 9) * min(1, self.level * scale + extra)
            x = 7 + index * 9
            y = (self.height() - height) / 2
            painter.drawRoundedRect(QRectF(x, y, 4, height), 2, 2)


class FloatingBar(QWidget):
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.state = "idle"
        self.level = 0.2
        self.phase = 0
        self.hovered = False
        self._anchor_center_x: Optional[int] = None
        self._anchor_bottom: Optional[int] = None
        self._repositioning = False
        self._position_lock = QTimer(self)
        self._position_lock.setInterval(40)
        self._position_lock.timeout.connect(self._enforce_anchor)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        if sys.platform != "win32":
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(24)
            shadow.setOffset(0, 4)
            shadow.setColor(QColor(0, 0, 0, 165))
            self.setGraphicsEffect(shadow)
        self._apply_size()

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseDoubleClickEvent(event)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        self._set_anchor(screen)
        # Defer first positioning until the native window is visible to avoid
        # a one-time startup jump on Windows.
        QTimer.singleShot(0, self._move_to_anchor)
        self._position_lock.start()

    def hideEvent(self, event):  # noqa: N802
        self._position_lock.stop()
        super().hideEvent(event)

    def moveEvent(self, event):  # noqa: N802
        super().moveEvent(event)
        if not self._repositioning:
            QTimer.singleShot(0, self._enforce_anchor)

    def enterEvent(self, event):  # noqa: N802
        self.hovered = True
        self._apply_size()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self.hovered = False
        self._apply_size()
        self.update()
        super().leaveEvent(event)

    def set_state(self, state: str):
        self.state = state
        if state == "recording":
            self.timer.start(90)
        else:
            self.timer.stop()
            self.phase = 0
        self._apply_size()
        self.update()

    def set_level(self, level: float):
        self.level = max(0.1, min(level, 1.0))
        self.update()

    def _tick(self):
        self.phase = (self.phase + 1) % 12
        self.update()

    def show_center_top(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self._set_anchor(screen)
        was_visible = self.isVisible()
        self.show()
        self.raise_()
        if was_visible:
            self._move_to_anchor()

    def _apply_size(self):
        if self.state == "idle" and self.hovered:
            self.setFixedSize(324, 90)
        elif self.state == "idle":
            self.setFixedSize(116, 30)
        else:
            self.setFixedSize(128, 42)

        if self._anchor_center_x is not None and self._anchor_bottom is not None:
            self._move_to_anchor()

    def _set_anchor(self, screen):
        self._anchor_center_x = screen.left() + screen.width() // 2
        self._anchor_bottom = screen.bottom()

    def _move_to_anchor(self):
        target = self._anchor_point()
        if target is None:
            return
        if self.pos() == target:
            return
        self._repositioning = True
        try:
            self.move(target)
        finally:
            self._repositioning = False

    def _enforce_anchor(self):
        if not self.isVisible() or self._anchor_center_x is None or self._anchor_bottom is None:
            return
        self._move_to_anchor()

    def _anchor_point(self) -> Optional[QPoint]:
        if self._anchor_center_x is None or self._anchor_bottom is None:
            return None
        x = self._anchor_center_x - self.width() // 2
        y = self._anchor_bottom - self.height() + 1
        return QPoint(x, y)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.state == "idle" and not self.hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 28))
            painter.drawRoundedRect(QRectF(31, 8, 54, 13), 6.5, 6.5)
            painter.setBrush(QColor(42, 42, 42, 170))
            painter.drawRoundedRect(QRectF(37, 11, 42, 7), 3.5, 3.5)
            painter.setPen(QPen(QColor(255, 255, 255, 62), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(31, 8, 54, 13), 6.5, 6.5)
        elif self.state == "idle":
            glass = QColor(10, 10, 12, 184)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 22))
            painter.drawRoundedRect(QRectF(4, 0, 316, 60), 27, 27)
            painter.setBrush(glass)
            painter.setPen(QPen(QColor(255, 255, 255, 34), 1))
            painter.drawRoundedRect(QRectF(10, 4, 304, 52), 24, 24)
            painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
            painter.drawRoundedRect(QRectF(12, 6, 300, 48), 22, 22)
            painter.setPen(QPen(QColor(255, 255, 255, 128), 1))
            painter.setBrush(QColor(8, 8, 9, 158))
            painter.drawRoundedRect(QRectF(108, 66, 108, 20), 10, 10)
            self._draw_dots(painter, 143, 75, QColor(185, 185, 190))

            painter.setFont(app_font(10, QFont.Weight.Medium))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(32, 2, 78, 54), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "Click or hold")
            painter.setPen(QColor("#ff9be7"))
            painter.setFont(app_font(10, QFont.Weight.Bold))
            hotkey_display = format_hotkey_text(config.HOTKEY)
            painter.drawText(QRectF(112, 2, 88, 54), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, hotkey_display)
            painter.setPen(QColor("#ffffff"))
            painter.setFont(app_font(10, QFont.Weight.Medium))
            painter.drawText(QRectF(196, 2, 86, 54), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "to dictate")
        elif self.state == "recording":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 22))
            painter.drawRoundedRect(QRectF(5, 6, 118, 30), 15, 15)
            painter.setBrush(QColor(18, 10, 11, 172))
            painter.setPen(QPen(QColor(255, 255, 255, 44), 1))
            painter.drawRoundedRect(QRectF(8, 8, 112, 26), 13, 13)
            self._draw_wave(painter, x_offset=36, y_center=21)
        elif self.state == "processing":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 22))
            painter.drawRoundedRect(QRectF(5, 6, 118, 30), 15, 15)
            painter.setBrush(QColor(12, 10, 5, 172))
            painter.setPen(QPen(QColor(255, 255, 255, 44), 1))
            painter.drawRoundedRect(QRectF(8, 8, 112, 26), 13, 13)
            self._draw_dots(painter, 46, 20, QColor(PROCESSING))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#050506"))
            painter.drawRoundedRect(QRectF(68, 36, 66, 8), 4, 4)

    def _draw_dots(self, painter: QPainter, x: int, y: int, color: QColor):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        for index in range(10):
            painter.drawEllipse(x + index * 4, y, 2, 2)

    def _draw_wave(self, painter: QPainter, x_offset: int = 32, y_center: int = 23):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#9bc8ff"))
        base = [0.35, 0.65, 0.95, 0.55, 0.8, 0.42, 0.6]
        for index, scale in enumerate(base):
            extra = 0.25 if (index + self.phase) % 4 == 0 else 0
            height = 5 + 17 * min(1, self.level * scale + extra)
            x = x_offset + index * 8
            y = y_center - height / 2
            painter.drawRoundedRect(QRectF(x, y, 4, height), 2, 2)


class LiveTextBox(QFrame):
    copy_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._text = ""
        self.setStyleSheet(f"QFrame {{ background: {BG}; border: none; }}")
        self.live_badge = QLabel("LIVE")
        self.live_badge.setFont(app_font(7, QFont.Weight.Bold))
        self.live_badge.setStyleSheet(f"color: {RECORDING}; background: transparent;")
        self.live_badge.hide()

        self.editor = QTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setAcceptRichText(False)
        self.editor.setPlaceholderText("Speak to type")
        self.editor.setFixedHeight(60)
        self.editor.setFont(app_font(9))
        self.editor.setStyleSheet(
            f"QTextEdit {{ background: #0c0c12; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 5px; padding: 9px; }}"
            f"QTextEdit:!focus {{ color: {TEXT}; }}"
        )

        self.char_count = QLabel("0 chars")
        self.char_count.setFont(app_font(7, QFont.Weight.Bold))
        self.char_count.setStyleSheet(f"color: {MUTED}; background: transparent;")
        self.copy_button = QPushButton("Copy")
        self.copy_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.copy_button.setFont(app_font(8, QFont.Weight.Bold))
        self.copy_button.clicked.connect(lambda: self.copy_requested.emit(self._text))
        self.copy_button.setStyleSheet(f"border: none; color: {ACCENT}; padding: 0; background: transparent;")

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addStretch()
        top.addWidget(self.live_badge)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 4, 0, 0)
        bottom.addWidget(self.char_count)
        bottom.addStretch()
        bottom.addWidget(self.copy_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(top)
        layout.addWidget(self.editor)
        layout.addLayout(bottom)

    def set_live(self, live: bool):
        self.live_badge.setVisible(live)

    def set_text(self, text: str):
        self._text = text or ""
        self.editor.setPlainText(self._text)
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        self.char_count.setText(f"{len(self._text)} chars")

    def text(self):
        return self._text


class HistoryEntry(QFrame):
    selected = pyqtSignal(dict)
    copy_requested = pyqtSignal(str)

    def __init__(self, entry: Dict):
        super().__init__()
        self.entry = entry
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setObjectName("HistoryEntry")
        self.setStyleSheet(
            "QFrame#HistoryEntry { background: #ffffff; border: 1px solid #e9e5dc; border-radius: 10px; }"
            "QFrame#HistoryEntry:hover { border-color: #d8ccb8; background: #fffdf8; }"
        )
        preview = entry.get("text", "")
        if len(preview) > 48:
            preview = preview[:45] + "..."
        text_label = QLabel(preview)
        text_label.setWordWrap(True)
        text_label.setFont(app_font(11, QFont.Weight.DemiBold))
        text_label.setStyleSheet("color: #232323; background: transparent;")
        meta = QLabel(f"{entry.get('time_label', '')}    {entry.get('chars', 0)} chars    saved")
        meta.setFont(app_font(8, QFont.Weight.DemiBold))
        meta.setStyleSheet("color: #77746d; background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        layout.addWidget(text_label)
        layout.addWidget(meta)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.entry)
        super().mousePressEvent(event)


class VoiceFlowWindow(QWidget):
    copy_requested = pyqtSignal(str)
    clear_history_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    history_selected = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setFixedSize(1180, 720)
        self.setWindowTitle("VoiceFlow Local")
        self.setWindowIcon(app_logo_icon())
        self.setWindowFlags(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setStyleSheet("background: #f7f5ef; color: #222222;")
        self.current_state = "idle"
        self.status = StatusPill()
        self.hotkey = HotkeyDisplay()
        self.mic = MicButton()
        self.waveform = WaveformWidget()
        self.live_box = LiveTextBox()
        self.history_list = QVBoxLayout()
        self.history_list.setContentsMargins(0, 0, 0, 0)
        self.history_list.setSpacing(7)
        self.history_list.addStretch()
        self.greeting_row = None
        self.live_box.copy_requested.connect(self.copy_requested)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        shell = QHBoxLayout()
        shell.setContentsMargins(36, 34, 36, 30)
        shell.setSpacing(28)
        root.addLayout(shell, 1)

        main = QVBoxLayout()
        main.setSpacing(20)
        shell.addLayout(main, 1)

        greeting_row = QHBoxLayout()
        self.greeting_row = greeting_row
        greeting = QLabel("Hey Nisarg, get back into the flow with")
        greeting.setFont(app_font(17, QFont.Weight.Bold))
        greeting.setStyleSheet("color: #151515; background: transparent;")
        greeting_row.addWidget(greeting)
        self._populate_greeting_hotkey()
        greeting_row.addStretch()
        main.addLayout(greeting_row)

        top_cards = QHBoxLayout()
        top_cards.setSpacing(18)
        control_card = QFrame()
        control_card.setFixedHeight(220)
        control_card.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #e8e2d8; border-radius: 16px; }")
        control_layout = QHBoxLayout(control_card)
        control_layout.setContentsMargins(24, 20, 24, 20)
        control_layout.setSpacing(20)
        mic_area = QVBoxLayout()
        title = QLabel("Dictation control")
        title.setFont(app_font(20, QFont.Weight.Bold))
        title.setStyleSheet("color: #191919; background: transparent;")
        subtitle = QLabel("Hold the hotkey, speak naturally, and VoiceFlow pastes the final text into your active app.")
        subtitle.setWordWrap(True)
        subtitle.setFont(app_font(10))
        subtitle.setStyleSheet("color: #65615a; background: transparent;")
        mic_area.addWidget(title)
        mic_area.addWidget(subtitle)
        mic_area.addStretch()
        mic_area.addWidget(self.live_box)
        self.live_box.editor.setStyleSheet("QTextEdit { background: #fbfaf7; color: #222222; border: 1px solid #ece5d8; border-radius: 8px; padding: 12px; }")
        self.live_box.char_count.setStyleSheet("color: #78736c; background: transparent;")
        self.live_box.copy_button.setStyleSheet("border: none; color: #6c4a1d; padding: 0; background: transparent;")
        control_layout.addLayout(mic_area, 1)
        meter = QVBoxLayout()
        meter.addStretch()
        meter.addWidget(self.mic, alignment=Qt.AlignmentFlag.AlignCenter)
        meter.addWidget(self.waveform, alignment=Qt.AlignmentFlag.AlignCenter)
        meter.addStretch()
        control_layout.addLayout(meter)
        top_cards.addWidget(control_card, 1)

        stats_card = QFrame()
        stats_card.setFixedSize(220, 220)
        stats_card.setStyleSheet("QFrame { background: #f0ede5; border: 1px solid #e4ddd0; border-radius: 16px; }")
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(24, 20, 24, 20)
        for value, label in (("15", "total words"), ("85", "wpm today"), ("1", "day streak")):
            stat = QLabel(f"<span style='font-size:28px; color:#191919;'>{value}</span> <span style='font-size:13px; color:#333333;'>{label}</span>")
            stat.setStyleSheet("background: transparent;")
            stats_layout.addWidget(stat)
        stats_layout.addStretch()
        top_cards.addWidget(stats_card)
        main.addLayout(top_cards)

        history_header = QHBoxLayout()
        today = QLabel("TODAY")
        today.setFont(app_font(10, QFont.Weight.Bold))
        today.setStyleSheet("color: #7b7770; background: transparent; letter-spacing: 1px;")
        clear = QPushButton("Clear all")
        clear.clicked.connect(self.clear_history_requested)
        clear.setStyleSheet("QPushButton { border: none; color: #7b5b2e; background: transparent; font-weight: 700; }")
        history_header.addWidget(today)
        history_header.addStretch()
        history_header.addWidget(clear)
        main.addLayout(history_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: #f7f5ef; }"
            "QScrollBar:vertical { background: #f7f5ef; width: 6px; }"
            "QScrollBar::handle:vertical { background: #d8d0c4; border-radius: 3px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        container = QWidget()
        container.setStyleSheet("background: #f7f5ef;")
        container.setLayout(self.history_list)
        scroll.setWidget(container)
        main.addWidget(scroll, 1)

        side = QVBoxLayout()
        side.setSpacing(16)
        shell.addLayout(side)
        scratch = QFrame()
        scratch.setFixedWidth(260)
        scratch.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #e8e2d8; border-radius: 16px; }")
        scratch_layout = QVBoxLayout(scratch)
        scratch_layout.setContentsMargins(18, 18, 18, 18)
        scratch_title = QLabel("Scratchpad")
        scratch_title.setFont(app_font(15, QFont.Weight.Bold))
        scratch_text = QTextEdit()
        scratch_text.setPlaceholderText("Quick notes while dictating...")
        scratch_text.setFixedHeight(150)
        scratch_text.setStyleSheet("QTextEdit { background: #fbfaf7; color: #222222; border: 1px solid #ece5d8; border-radius: 8px; padding: 10px; }")
        scratch_layout.addWidget(scratch_title)
        scratch_layout.addWidget(scratch_text)
        side.addWidget(scratch)

        quick = QFrame()
        quick.setFixedWidth(260)
        quick.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #e8e2d8; border-radius: 16px; }")
        quick_layout = QVBoxLayout(quick)
        quick_layout.setContentsMargins(18, 18, 18, 18)
        quick_title = QLabel("Quick actions")
        quick_title.setFont(app_font(15, QFont.Weight.Bold))
        settings = QPushButton("Open settings")
        settings.clicked.connect(self.settings_requested)
        copy_last = QPushButton("Copy current text")
        copy_last.clicked.connect(lambda: self.copy_requested.emit(self.live_box.text()))
        for button in (settings, copy_last):
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            button.setStyleSheet("QPushButton { background: #191919; color: #ffffff; border: none; border-radius: 8px; padding: 10px 12px; font-weight: 700; text-align: left; } QPushButton:hover { background: #2a2a2a; }")
        quick_layout.addWidget(quick_title)
        quick_layout.addWidget(settings)
        quick_layout.addWidget(copy_last)
        side.addWidget(quick)
        side.addStretch()

    def set_state(self, state: str):
        self.current_state = state
        ui_state = "ready" if state == "idle" else state
        self.status.set_state(ui_state)
        self.mic.set_state(ui_state)
        self.waveform.set_mode(ui_state)

    def set_hotkey_active(self, active: bool):
        self.hotkey.set_active(active)

    def refresh_hotkey_display(self):
        self.hotkey._update_badges()
        self.mic.refresh_hotkey_text()
        self._populate_greeting_hotkey()
        self.update()

    def _populate_greeting_hotkey(self):
        if self.greeting_row is None:
            return
        while self.greeting_row.count() > 1:
            item = self.greeting_row.takeAt(1)
            if item and item.widget():
                item.widget().deleteLater()

        hotkey_parts = [part.strip() for part in config.HOTKEY.replace("-", "+").split("+") if part.strip()]
        for index, part in enumerate(hotkey_parts):
            chip = QLabel(format_hotkey_text(part))
            chip.setFont(app_font(13, QFont.Weight.Bold))
            chip.setStyleSheet("background: #ffae43; color: #17120a; border: 1px solid #a65f12; border-radius: 5px; padding: 6px 9px;")
            self.greeting_row.addWidget(chip)
            if index < len(hotkey_parts) - 1:
                plus = QLabel("+")
                plus.setFont(app_font(16, QFont.Weight.Bold))
                plus.setStyleSheet("color: #151515; background: transparent;")
                self.greeting_row.addWidget(plus)
        self.greeting_row.addStretch()

    def update_level(self, level: float):
        self.waveform.set_level(level)

    def update_live_text(self, text: str):
        self.live_box.set_text(text)

    def show_live_badge(self):
        self.live_box.set_live(True)

    def hide_live_badge(self):
        self.live_box.set_live(False)

    def add_history_entry(self, entry: Dict):
        widget = HistoryEntry(entry)
        widget.selected.connect(self.history_selected)
        self.history_list.insertWidget(0, widget)
        while self.history_list.count() > 51:
            item = self.history_list.takeAt(50)
            if item and item.widget():
                item.widget().deleteLater()

    def set_history(self, entries: List[Dict]):
        while self.history_list.count() > 1:
            item = self.history_list.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        newest_first = list(reversed(entries))[:50]
        for entry in newest_first:
            widget = HistoryEntry(entry)
            widget.selected.connect(self.history_selected)
            self.history_list.insertWidget(self.history_list.count() - 1, widget)

    def show_near_tray(self, activate: bool = False):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.left() + (screen.width() - self.width()) // 2
        y = screen.top() + (screen.height() - self.height()) // 2
        self.move(QPoint(max(screen.left(), x), max(screen.top(), y)))
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, not activate)
        self.show()
        self.raise_()
        if activate:
            self.activateWindow()

    def changeEvent(self, event):  # noqa: N802
        if event.type() == QEvent.Type.ActivationChange and self.isVisible() and not self.isActiveWindow() and self.current_state == "idle":
            self.hide()
        super().changeEvent(event)


class TrayController:
    def __init__(self, window: VoiceFlowWindow, on_quit: Callable[[], None]):
        self.window = window
        self.on_quit = on_quit
        self.floating = FloatingBar()
        self.floating.clicked.connect(self.show_full_window)
        self.tray_icon = QSystemTrayIcon()
        self._logo_icon = app_logo_icon()
        self.tray_icon.setIcon(self._icon("idle"))
        self.tray_icon.setToolTip("VoiceFlow Local - Ready")
        self.tray_icon.activated.connect(self._activated)
        self.tray_icon.show()
        self.floating.show_center_top()

    def _activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.window.isVisible():
                self.show_floating()
            else:
                self.show_full_window()

    def set_state(self, state: str):
        self.tray_icon.setIcon(self._icon(state))
        self.floating.set_state(state)

    def set_level(self, level: float):
        self.floating.set_level(level)

    def show_full_window(self):
        self.window.show_near_tray(activate=True)
        self.floating.show_center_top()

    def show_floating(self, hide_window: bool = True):
        if hide_window:
            self.window.hide()
        self.floating.show_center_top()

    def notify(self, message: str, duration: int = 3000):
        self.tray_icon.showMessage("VoiceFlow", message, QSystemTrayIcon.MessageIcon.Information, duration)

    def _icon(self, state: str) -> QIcon:
        if not self._logo_icon.isNull():
            return self._logo_icon
        color = {"idle": PRIMARY, "recording": RECORDING_DEEP, "processing": PROCESSING, "error": "#b71c1c"}.get(state, PRIMARY)
        pixmap = QPixmap(QSize(32, 32))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(4, 4, 24, 24, 6, 6)
        painter.setBrush(QColor("#dce9ff"))
        painter.drawRoundedRect(11, 9, 3, 14, 1.5, 1.5)
        painter.drawRoundedRect(18, 9, 3, 14, 1.5, 1.5)
        painter.end()
        return QIcon(pixmap)


def copy_to_clipboard(text: str):
    if text:
        pyperclip.copy(text)


def make_history_entry(text: str, duration_sec: float, created_at: Optional[datetime] = None) -> Dict:
    created_at = created_at or datetime.now()
    return {
        "text": text,
        "date": created_at.strftime("%Y-%m-%d"),
        "time": created_at.strftime("%H:%M:%S"),
        "time_label": created_at.strftime("%Y-%m-%d, %I:%M %p").replace(" 0", " "),
        "chars": len(text),
        "duration_sec": round(duration_sec, 2),
    }

"""
VoiceFlow Local - PyQt6 popup UI.

Contains the tray popup window and all custom widgets for the dark VoiceFlow UI.
The window is intentionally compact and non-activating so the user's last text
field remains the paste target after dictation finishes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, List, Optional

import pyperclip
from PyQt6.QtCore import QByteArray, QEasingCurve, QEvent, QPoint, QPropertyAnimation, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSystemTrayIcon,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


BG = "#0f0f13"
SURFACE = "#16161e"
BORDER = "#2a2a3a"
TEXT = "#ECEFF1"
MUTED = "#8c93a1"
ACCENT = "#4A90D9"
PRIMARY = "#1565C0"
RECORDING = "#E53935"
PROCESSING = "#F9A825"
SUCCESS = "#2E7D32"
NAVY = "#1A1A2E"


MIC_SVG = """
<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M24 7C20.6863 7 18 9.68629 18 13V24C18 27.3137 20.6863 30 24 30C27.3137 30 30 27.3137 30 24V13C30 9.68629 27.3137 7 24 7Z" stroke="white" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M13 22V24C13 30.0751 17.9249 35 24 35C30.0751 35 35 30.0751 35 24V22" stroke="white" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M24 35V42" stroke="white" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M18 42H30" stroke="white" stroke-width="3.5" stroke-linecap="round"/>
</svg>
""".strip()


def app_font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont("Segoe UI", size)
    font.setWeight(weight)
    return font


class LogoMark(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(42, 42)

    def paintEvent(self, event):  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(NAVY))
        painter.drawRoundedRect(self.rect(), 10, 10)

        bar_width = 4
        heights = [16, 24, 32, 24, 16]
        start_x = 8
        for index, height in enumerate(heights):
            x = start_x + index * 7
            y = (self.height() - height) / 2
            painter.setBrush(QColor("#ffffff"))
            painter.drawRoundedRect(QRectF(x, y, bar_width, height), 2, 2)


class StatusPill(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.state = "ready"
        self.dot = QLabel()
        self.label = QLabel("ready")
        self.dot.setFixedSize(8, 8)
        self.label.setFont(app_font(10))
        self.label.setStyleSheet(f"color: {MUTED};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(7)
        layout.addWidget(self.dot)
        layout.addWidget(self.label)

        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._toggle_pulse)
        self._pulse_on = False
        self.set_state("ready")

    def set_state(self, state: str):
        self.state = state
        labels = {"ready": "ready", "recording": "recording", "processing": "processing"}
        colors = {"ready": SUCCESS, "recording": RECORDING, "processing": PROCESSING}
        self.label.setText(labels.get(state, state))
        self._set_dot(colors.get(state, SUCCESS))
        self.setStyleSheet(
            f"QFrame {{ background: #1b1b2a; border: 1px solid #30304a; border-radius: 14px; }}"
        )
        if state == "recording":
            self._pulse_timer.start(450)
        else:
            self._pulse_timer.stop()
            self._pulse_on = False

    def _set_dot(self, color: str, opacity: float = 1.0):
        qcolor = QColor(color)
        qcolor.setAlphaF(opacity)
        self.dot.setStyleSheet(f"background: rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {qcolor.alpha()}); border-radius: 4px;")

    def _toggle_pulse(self):
        self._pulse_on = not self._pulse_on
        self._set_dot(RECORDING, 1.0 if self._pulse_on else 0.45)


class KeyBadge(QLabel):
    def __init__(self, text: str, parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(30)
        self.setMinimumWidth(64 if text == "Space" else 54)
        self.setFont(app_font(10, QFont.Weight.DemiBold))
        self.set_active(False)

    def set_active(self, active: bool):
        bg = "#1b2d4a" if active else "#1b1b28"
        border = ACCENT if active else "#3a3a56"
        color = TEXT if active else "#a8afbd"
        self.setStyleSheet(
            f"QLabel {{ background: {bg}; color: {color}; border: 1px solid {border}; border-radius: 7px; padding: 4px 10px; }}"
        )


class HotkeyDisplay(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ctrl = KeyBadge("Ctrl")
        self.space = KeyBadge("Space")
        plus = QLabel("+")
        plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plus.setFont(app_font(10, QFont.Weight.Bold))
        plus.setStyleSheet(f"color: {MUTED};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        layout.addWidget(self.ctrl)
        layout.addWidget(plus)
        layout.addWidget(self.space)

    def set_active(self, active: bool):
        self.ctrl.set_active(active)
        self.space.set_active(active)


class MicButton(QToolButton):
    clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(112, 112)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip("Hold Ctrl+Space to start")
        self.state = "ready"
        self._pulse_radius = 42.0
        self._svg = QSvgRenderer(QByteArray(MIC_SVG.encode("utf-8")))
        self._pulse = QPropertyAnimation(self, b"pulseRadius", self)
        self._pulse.setStartValue(42.0)
        self._pulse.setEndValue(54.0)
        self._pulse.setDuration(850)
        self._pulse.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse.setLoopCount(-1)

    def get_pulse_radius(self) -> float:
        return self._pulse_radius

    def set_pulse_radius(self, value: float):
        self._pulse_radius = value
        self.update()

    pulseRadius = property(get_pulse_radius, set_pulse_radius)

    def set_state(self, state: str):
        self.state = state
        if state == "recording":
            self._pulse.start()
        else:
            self._pulse.stop()
            self._pulse_radius = 42.0
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.rect().center()

        if self.state == "recording":
            pulse = QColor(RECORDING)
            pulse.setAlpha(70)
            painter.setBrush(pulse)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, int(self._pulse_radius), int(self._pulse_radius))

        fill = QColor(RECORDING if self.state == "recording" else PRIMARY)
        painter.setBrush(fill)
        painter.setPen(QPen(QColor("#2b5ca2" if self.state != "recording" else "#ff7774"), 2))
        painter.drawEllipse(center, 40, 40)

        self._svg.render(painter, QRectF(center.x() - 20, center.y() - 22, 40, 40))


class WaveformWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(92, 42)
        self.level = 0.15
        self.recording = False
        self.phase = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_recording(self, recording: bool):
        self.recording = recording
        if recording:
            self._timer.start(90)
        else:
            self._timer.stop()
            self.level = 0.12
        self.update()

    def set_level(self, level: float):
        self.level = max(0.08, min(1.0, level))
        self.update()

    def _tick(self):
        self.phase = (self.phase + 1) % 14
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        color = QColor(ACCENT)
        color.setAlpha(220 if self.recording else 90)
        painter.setBrush(color)

        base = [0.35, 0.55, 0.78, 1.0, 0.78, 0.55, 0.35]
        width = 6
        gap = 7
        start_x = (self.width() - (7 * width + 6 * gap)) / 2
        for i, scale in enumerate(base):
            wobble = 0.25 if self.recording and (i + self.phase) % 3 == 0 else 0
            height = 8 + (self.height() - 10) * min(1.0, self.level * scale + wobble)
            x = start_x + i * (width + gap)
            y = (self.height() - height) / 2
            painter.drawRoundedRect(QRectF(x, y, width, height), 3, 3)


class LiveTextBox(QFrame):
    copy_requested = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._text = ""
        self.live_badge = QLabel("● LIVE")
        self.live_badge.setFont(app_font(8, QFont.Weight.Bold))
        self.live_badge.setStyleSheet(
            f"background: rgba(229,57,53,0.15); color: {RECORDING}; border: 1px solid rgba(229,57,53,0.35); border-radius: 8px; padding: 2px 7px;"
        )
        self.live_badge.hide()

        self.editor = QTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setAcceptRichText(False)
        self.editor.setFont(app_font(11))
        self.editor.setPlaceholderText("")
        self.editor.setStyleSheet(
            f"QTextEdit {{ background: {BG}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 8px; padding: 10px; selection-background-color: {PRIMARY}; }}"
        )
        self.editor.setFixedHeight(96)

        self.copy_button = QPushButton("copy")
        self.copy_button.setFont(app_font(10, QFont.Weight.DemiBold))
        self.copy_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.copy_button.clicked.connect(lambda: self.copy_requested.emit(self._text))
        self.copy_button.setStyleSheet(
            f"QPushButton {{ color: {TEXT}; background: transparent; border: 1px solid #545463; border-radius: 7px; padding: 7px 16px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; color: white; }}"
        )
        self.char_count = QLabel("0 chars")
        self.char_count.setFont(app_font(9))
        self.char_count.setStyleSheet(f"color: {MUTED};")

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addStretch()
        top.addWidget(self.live_badge)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addWidget(self.copy_button)
        bottom.addStretch()
        bottom.addWidget(self.char_count)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
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

    def text(self) -> str:
        return self._text


class HistoryEntry(QFrame):
    selected = pyqtSignal(dict)
    copy_requested = pyqtSignal(str)

    def __init__(self, entry: Dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setObjectName("HistoryEntry")
        self.setStyleSheet(
            f"QFrame#HistoryEntry {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; }}"
            f"QFrame#HistoryEntry:hover {{ border-color: {ACCENT}; }}"
        )

        preview = entry.get("text", "")
        if len(preview) > 62:
            preview = preview[:59] + "..."

        text_label = QLabel(preview)
        text_label.setFont(app_font(10, QFont.Weight.DemiBold))
        text_label.setWordWrap(True)
        text_label.setStyleSheet(f"color: {TEXT};")

        meta = QLabel(f"{entry.get('time_label', '')}  ·  {entry.get('chars', 0)} chars  ·  ✓ saved")
        meta.setFont(app_font(8))
        meta.setStyleSheet(f"color: {MUTED};")

        self.copy_button = QPushButton("copy")
        self.copy_button.setFixedWidth(54)
        self.copy_button.hide()
        self.copy_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.copy_button.clicked.connect(lambda: self.copy_requested.emit(entry.get("text", "")))
        self.copy_button.setStyleSheet(
            f"QPushButton {{ background: #1d2a40; color: {TEXT}; border: 1px solid {ACCENT}; border-radius: 6px; padding: 4px; }}"
        )

        labels = QVBoxLayout()
        labels.setContentsMargins(0, 0, 0, 0)
        labels.setSpacing(4)
        labels.addWidget(text_label)
        labels.addWidget(meta)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 9, 10, 9)
        row.setSpacing(8)
        row.addLayout(labels, 1)
        row.addWidget(self.copy_button)

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.entry)
        super().mousePressEvent(event)

    def enterEvent(self, event):  # noqa: N802 - Qt override
        self.copy_button.show()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - Qt override
        self.copy_button.hide()
        super().leaveEvent(event)


class VoiceFlowWindow(QWidget):
    copy_requested = pyqtSignal(str)
    clear_history_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    history_selected = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setFixedSize(320, 580)
        self.setWindowTitle("VoiceFlow Local")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setStyleSheet(f"background: {BG}; color: {TEXT};")
        self.current_state = "idle"

        self.status = StatusPill()
        self.hotkey = HotkeyDisplay()
        self.mic = MicButton()
        self.waveform = WaveformWidget()
        self.live_box = LiveTextBox()
        self.history_list = QVBoxLayout()
        self.history_list.setContentsMargins(0, 0, 0, 0)
        self.history_list.setSpacing(6)
        self.history_list.addStretch()

        self.live_box.copy_requested.connect(self.copy_requested)

        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        logo = LogoMark()
        wordmark = QLabel('<span style="font-weight:700; color:#ECEFF1;">VoiceFlow</span> <span style="color:#4A90D9;">Local</span>')
        wordmark.setFont(app_font(14, QFont.Weight.DemiBold))
        top.addWidget(logo)
        top.addWidget(wordmark)
        top.addStretch()
        top.addWidget(self.status)
        root.addLayout(top)

        panel = QFrame()
        panel.setStyleSheet(f"QFrame {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 12, 14, 12)
        panel_layout.setSpacing(10)

        hotkey_row = QHBoxLayout()
        hotkey_label = QLabel("HOTKEY")
        hotkey_label.setFont(app_font(9, QFont.Weight.DemiBold))
        hotkey_label.setStyleSheet(f"color: {MUTED};")
        hotkey_row.addWidget(hotkey_label)
        hotkey_row.addStretch()
        hotkey_row.addWidget(self.hotkey)
        panel_layout.addLayout(hotkey_row)

        panel_layout.addSpacing(2)
        mic_row = QHBoxLayout()
        mic_row.addStretch()
        mic_row.addWidget(self.mic)
        mic_row.addStretch()
        panel_layout.addLayout(mic_row)

        hint = QLabel('<span style="color:#7f8591;">Hold </span><span style="color:#4A90D9; font-weight:700;">Ctrl + Space</span><span style="color:#7f8591;"> to dictate</span>')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setFont(app_font(9))
        panel_layout.addWidget(hint)

        wave_row = QHBoxLayout()
        wave_row.addStretch()
        wave_row.addWidget(self.waveform)
        wave_row.addStretch()
        panel_layout.addLayout(wave_row)

        panel_layout.addWidget(self.live_box)
        root.addWidget(panel)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {BORDER};")
        root.addWidget(divider)

        history_header = QHBoxLayout()
        label = QLabel("HISTORY")
        label.setFont(app_font(10, QFont.Weight.DemiBold))
        label.setStyleSheet(f"color: {MUTED};")
        clear = QPushButton("clear all")
        clear.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        clear.clicked.connect(self.clear_history_requested)
        clear.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {TEXT}; border: 1px solid #4a4a56; border-radius: 7px; padding: 5px 12px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; }}"
        )
        history_header.addWidget(label)
        history_header.addStretch()
        history_header.addWidget(clear)
        root.addLayout(history_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG}; }}"
            f"QScrollBar:vertical {{ background: {BG}; width: 5px; }}"
            f"QScrollBar::handle:vertical {{ background: #39394c; border-radius: 2px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        history_container = QWidget()
        history_container.setStyleSheet(f"background: {BG};")
        history_container.setLayout(self.history_list)
        scroll.setWidget(history_container)
        root.addWidget(scroll, 1)

        bottom = QHBoxLayout()
        autosave = QLabel(f'<span style="color:{SUCCESS};">●</span> <span style="color:{MUTED};">auto-saving to voiceflow_log.txt</span>')
        autosave.setFont(app_font(9))
        settings = QPushButton("settings ↗")
        settings.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        settings.clicked.connect(self.settings_requested)
        settings.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {TEXT}; border: 1px solid #545463; border-radius: 8px; padding: 7px 13px; font-weight: 700; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; }}"
        )
        bottom.addWidget(autosave)
        bottom.addStretch()
        bottom.addWidget(settings)
        root.addLayout(bottom)

    def set_state(self, state: str):
        self.current_state = state
        ui_state = "ready" if state == "idle" else state
        self.status.set_state(ui_state)
        self.mic.set_state(ui_state)
        self.waveform.set_recording(ui_state == "recording")
        self.live_box.set_live(ui_state == "recording")

    def set_hotkey_active(self, active: bool):
        self.hotkey.set_active(active)

    def update_level(self, level: float):
        self.waveform.set_level(level)

    def update_live_text(self, text: str):
        self.live_box.set_text(text)

    def add_history_entry(self, entry: Dict):
        widget = HistoryEntry(entry)
        widget.selected.connect(self.history_selected)
        widget.copy_requested.connect(self.copy_requested)
        self.history_list.insertWidget(0, widget)
        while self.history_list.count() > 51:  # 50 entries plus stretch
            item = self.history_list.takeAt(50)
            if item and item.widget():
                item.widget().deleteLater()

    def set_history(self, entries: List[Dict]):
        while self.history_list.count() > 1:
            item = self.history_list.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        for entry in reversed(entries[:50]):
            self.add_history_entry(entry)

    def show_near_tray(self, activate: bool = False):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - 18
        y = screen.bottom() - self.height() - 18
        self.move(QPoint(max(screen.left(), x), max(screen.top(), y)))
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, not activate)
        self.show()
        self.raise_()
        if activate:
            self.activateWindow()

    def changeEvent(self, event):  # noqa: N802 - Qt override
        if (
            event.type() == QEvent.Type.ActivationChange
            and self.isVisible()
            and not self.isActiveWindow()
            and self.current_state == "idle"
        ):
            self.hide()
        super().changeEvent(event)


class TrayController:
    def __init__(self, window: VoiceFlowWindow, on_quit: Callable[[], None]):
        self.window = window
        self.on_quit = on_quit
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(self._icon("idle"))
        self.tray_icon.setToolTip("VoiceFlow Local - Ready")
        self.tray_icon.activated.connect(self._activated)
        self.tray_icon.show()

    def _activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.window.isVisible():
                self.window.hide()
            else:
                self.window.show_near_tray(activate=True)

    def set_state(self, state: str):
        self.tray_icon.setIcon(self._icon(state))
        tips = {
            "idle": "VoiceFlow Local - Ready",
            "recording": "VoiceFlow Local - Recording",
            "processing": "VoiceFlow Local - Transcribing",
            "error": "VoiceFlow Local - Error",
        }
        self.tray_icon.setToolTip(tips.get(state, "VoiceFlow Local"))

    def notify(self, message: str, duration: int = 3000):
        self.tray_icon.showMessage("VoiceFlow", message, QSystemTrayIcon.MessageIcon.Information, duration)

    def _icon(self, state: str) -> QIcon:
        colors = {
            "idle": QColor(ACCENT),
            "recording": QColor(RECORDING),
            "processing": QColor(PROCESSING),
            "error": QColor("#B71C1C"),
        }
        pixmap = QPixmap(QSize(32, 32))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(colors.get(state, QColor(ACCENT)))
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawEllipse(5, 5, 22, 22)
        if state == "recording":
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(13, 13, 6, 6)
        elif state == "processing":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#ffffff"), 3))
            painter.drawArc(8, 8, 16, 16, 0, 270 * 16)
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
        "time_label": created_at.strftime("Today, %I:%M %p").replace(" 0", " "),
        "chars": len(text),
        "duration_sec": round(duration_sec, 2),
    }

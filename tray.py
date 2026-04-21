"""
VoiceFlow Local - System Tray UI Module

Provides a system tray icon with context menu for the voice dictation app.
Uses PyQt6 for native Windows system tray integration.
"""

import os
import sys
from PyQt6.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
)
from PyQt6.QtGui import QAction, QIcon, QPainter, QColor, QBrush, QPen
from PyQt6.QtCore import Qt, QCoreApplication
import config


class SystemTray:
    """
    System tray icon with context menu for VoiceFlow Local.

    States:
    - idle: Gray icon, waiting for hotkey
    - recording: Red icon, actively recording
    - processing: Yellow icon, transcribing audio
    - error: Red X icon, error occurred
    """

    # State definitions
    STATE_IDLE = 'idle'
    STATE_RECORDING = 'recording'
    STATE_PROCESSING = 'processing'
    STATE_ERROR = 'error'

    def __init__(self, on_quit_callback=None, on_toggle_history=None, on_show_settings=None):
        """
        Initialize the system tray.

        Args:
            on_quit_callback: Function to call when user selects Quit.
            on_toggle_history: Function to call when user clicks tray icon.
            on_show_settings: Function to call when user selects Settings.
        """
        self.app = None
        self.tray_icon = None
        self.tray_menu = None
        self.current_state = self.STATE_IDLE

        self.on_quit_callback = on_quit_callback
        self.on_toggle_history = on_toggle_history
        self.on_show_settings = on_show_settings

        self._icon_cache = {}  # Cache generated icons

    def _generate_icon(self, state):
        """
        Generate a 32x32 PNG icon programmatically for the given state.

        Uses QPainter to draw a simple colored circle with state indicator.

        Args:
            state: One of 'idle', 'recording', 'processing', 'error'.

        Returns:
            QIcon: Generated icon.
        """
        if state in self._icon_cache:
            return self._icon_cache[state]

        from PyQt6.QtGui import QPixmap, QPainter, QBrush, QPen, QColor

        # Create 32x32 pixmap
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Brand colors per VoiceFlow Local guidelines (Section 3.2, 8.1)
        colors = {
            self.STATE_IDLE: QColor(74, 144, 217, 200),     # #4A90D9 Sky Blue
            self.STATE_RECORDING: QColor(229, 57, 53, 220), # #E53935 Signal Red
            self.STATE_PROCESSING: QColor(249, 168, 37, 220), # #F9A825 Amber
            self.STATE_ERROR: QColor(183, 28, 28, 220),     # #B71C1C Alert Red
        }

        # Draw main circle
        color = colors.get(state, colors[self.STATE_IDLE])
        brush = QBrush(color)
        pen = QPen(QColor(255, 255, 255, 100), 2)
        painter.setBrush(brush)
        painter.setPen(pen)
        painter.drawEllipse(4, 4, 24, 24)

        # Add state-specific indicator
        if state == self.STATE_RECORDING:
            # Recording dot in center
            painter.setBrush(QColor(255, 255, 255, 255))
            painter.drawEllipse(12, 12, 8, 8)
        elif state == self.STATE_PROCESSING:
            # Processing ring
            painter.setPen(QPen(QColor(255, 255, 255, 200), 3))
            painter.drawArc(6, 6, 20, 20, 0, 270 * 16)  # Incomplete circle
        elif state == self.STATE_ERROR:
            # Error X
            painter.setPen(QPen(QColor(255, 255, 255, 255), 3))
            painter.drawLine(10, 10, 22, 22)
            painter.drawLine(22, 10, 10, 22)

        painter.end()

        # Create icon from pixmap
        icon = QIcon(pixmap)
        self._icon_cache[state] = icon
        return icon

    def _create_menu(self):
        """
        Create the context menu for the tray icon.

        Returns:
            QMenu: The context menu.
        """
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #444444;
            }
            QMenu::separator {
                height: 1px;
                background: #444444;
                margin: 4px 8px;
            }
        """)

        # Show History action
        history_action = QAction("Show History", menu)
        history_action.triggered.connect(self._on_history_triggered)
        menu.addAction(history_action)

        menu.addSeparator()

        # Settings action
        settings_action = QAction("Settings", menu)
        settings_action.triggered.connect(self._on_settings_triggered)
        menu.addAction(settings_action)

        menu.addSeparator()

        # Start with Windows toggle (placeholder)
        self.start_with_windows_action = QAction("Start with Windows", menu)
        self.start_with_windows_action.setCheckable(True)
        self.start_with_windows_action.setChecked(False)
        # TODO: Implement actual Windows startup integration
        menu.addAction(self.start_with_windows_action)

        menu.addSeparator()

        # Quit action
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._on_quit_triggered)
        menu.addAction(quit_action)

        return menu

    def _on_history_triggered(self):
        """Handle Show History menu action."""
        print("[TRAY] Show History requested")
        if self.on_toggle_history:
            self.on_toggle_history()

    def _on_settings_triggered(self):
        """Handle Settings menu action."""
        print("[TRAY] Settings requested")
        if self.on_show_settings:
            self.on_show_settings()

    def _on_quit_triggered(self):
        """Handle Quit menu action."""
        print("[TRAY] Quit requested")
        if self.on_quit_callback:
            self.on_quit_callback()

    def show(self):
        """
        Show the system tray icon.

        Creates the QApplication if not already created.
        """
        # Check if QApplication exists
        if QApplication.instance() is None:
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()

        # Tray-only app: keep running even with no visible windows.
        self.app.setQuitOnLastWindowClosed(False)

        # Create tray icon
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(self._generate_icon(self.STATE_IDLE))
        self.tray_icon.setToolTip("VoiceFlow Local — Ready")

        # Create and set menu
        self.tray_menu = self._create_menu()
        self.tray_icon.setContextMenu(self.tray_menu)

        # Connect activated signal (left-click)
        self.tray_icon.activated.connect(self._on_tray_activated)

        # Show the icon
        self.tray_icon.show()

        print("[OK] System tray icon displayed")

    def _on_tray_activated(self, reason):
        """
        Handle tray icon activation (left-click).

        Args:
            reason: The activation reason (QSystemTrayIcon.ActivationReason).
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Left-click
            print("[TRAY] Left-click on tray icon")
            if self.on_toggle_history:
                self.on_toggle_history()

    def set_state(self, state):
        """
        Update the tray icon state.

        Args:
            state: One of 'idle', 'recording', 'processing', 'error'.
        """
        if state not in [self.STATE_IDLE, self.STATE_RECORDING,
                         self.STATE_PROCESSING, self.STATE_ERROR]:
            print(f"[WARNING] Unknown state: {state}")
            return

        old_state = self.current_state
        self.current_state = state

        if self.tray_icon:
            self.tray_icon.setIcon(self._generate_icon(state))

            # Update tooltip with state (brand format: em dash, concise)
            tooltips = {
                self.STATE_IDLE: "VoiceFlow Local — Ready",
                self.STATE_RECORDING: "VoiceFlow Local — Recording...",
                self.STATE_PROCESSING: "VoiceFlow Local — Transcribing...",
                self.STATE_ERROR: "VoiceFlow Local — Error",
            }
            self.tray_icon.setToolTip(tooltips.get(state, "VoiceFlow Local"))

        print(f"[TRAY] State changed: {old_state} -> {state}")

    def show_notification(self, title, message, duration=3000):
        """
        Show a notification bubble.

        Args:
            title: Notification title.
            message: Notification message body.
            duration: How long to show (ms), default 3000ms.
        """
        if self.tray_icon:
            # Prefix with "VoiceFlow" per brand guidelines (Section 8.2)
            display_title = "VoiceFlow"
            self.tray_icon.showMessage(display_title, message,
                                       QSystemTrayIcon.MessageIcon.Information,
                                       duration)
            print(f"[NOTIFY] {display_title}: {message[:50]}...")

    def show_transcription_complete(self, text):
        """
        Show notification when transcription is complete.

        Args:
            text: The transcribed text (shows first 60 chars per brand guidelines).
        """
        # Brand guidelines Section 8.2: show first 60 characters
        preview = text[:60] + "..." if len(text) > 60 else text
        self.show_notification("Transcribed", preview)

    def run(self):
        """
        Run the Qt event loop.

        Blocks until quit() is called.
        """
        if self.app:
            return self.app.exec()
        return 0

    def quit(self):
        """
        Quit the application and hide the tray icon.
        """
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon = None

        if self.app:
            self.app.quit()


# =============================================================================
# TEST: Show tray icon and cycle through states
# =============================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("SystemTray Test")
    print("=" * 60)
    print()
    print("The tray icon will appear. Right-click for menu.")
    print("Cycle through states every 3 seconds...")
    print()

    import time

    def on_quit():
        print("Quit requested")
        tray.quit()

    tray = SystemTray(on_quit_callback=on_quit)
    tray.show()

    # Cycle through states for testing
    states = [
        SystemTray.STATE_IDLE,
        SystemTray.STATE_RECORDING,
        SystemTray.STATE_PROCESSING,
        SystemTray.STATE_IDLE,
    ]

    for state in states:
        time.sleep(2)
        tray.set_state(state)

    # Show test notification
    time.sleep(1)
    tray.show_transcription_complete("This is a test transcription. It shows the first 50 characters of the result...")

    print()
    print("Test complete! Close the tray icon to exit.")
    tray.run()

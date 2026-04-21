"""
VoiceFlow Local - suppressing global hotkey listener.

The configured hotkey is intercepted globally while VoiceFlow is running so the
foreground app does not receive it. Other keys pass through normally.
"""

import threading
import time

import keyboard

import config


class HotkeyManager:
    """
    Global push-to-talk hotkey manager.

    Uses keyboard.add_hotkey(..., suppress=True) so the configured hotkey is
    blocked from every other app while VoiceFlow is active. Release is detected
    by polling the current key state, avoiding duplicate suppressed
    registrations.
    """

    def __init__(self, on_press_callback=None, on_release_callback=None):
        self.hotkey = config.HOTKEY
        self.on_press_callback = on_press_callback
        self.on_release_callback = on_release_callback

        self._is_listening = False
        self._is_pressed = False
        self._is_paused = False
        self._listener_thread = None
        self._stop_event = threading.Event()
        self._press_handle = None

    def _check_conflicts(self):
        warnings = []
        hotkey_lower = self.hotkey.lower()
        system_shortcuts = {
            "windows": "Windows key alone is reserved by Windows",
            "windows+e": "Opens File Explorer",
            "windows+d": "Shows desktop",
            "windows+l": "Locks computer",
            "windows+r": "Opens Run dialog",
            "windows+tab": "Opens Task View",
            "alt+tab": "Switches applications",
            "ctrl+alt+del": "Opens security screen",
            "alt+f4": "Closes active window",
            "ctrl+c": "Copy shortcut",
            "ctrl+v": "Paste shortcut",
            "ctrl+x": "Cut shortcut",
        }
        if hotkey_lower in system_shortcuts:
            warnings.append(f"Conflict warning: '{self.hotkey}' - {system_shortcuts[hotkey_lower]}")
        if hotkey_lower in ["ctrl", "alt", "shift", "windows"]:
            warnings.append(f"Warning: Single modifier key '{self.hotkey}' may not work reliably")
        return warnings

    def _register_hotkey(self):
        self._unregister_hotkey()
        self._press_handle = keyboard.add_hotkey(
            self.hotkey,
            self._on_press,
            suppress=True,
            trigger_on_release=False,
        )

    def _unregister_hotkey(self):
        if self._press_handle is not None:
            try:
                keyboard.remove_hotkey(self._press_handle)
            except Exception:
                pass
        self._press_handle = None

    def _on_press(self):
        if self._is_paused or self._is_pressed:
            return
        self._is_pressed = True
        print(f"[HOTKEY] PRESSED and suppressed ({self.hotkey})")
        if self.on_press_callback:
            try:
                self.on_press_callback()
            except Exception as exc:
                print(f"[ERROR] on_press callback failed: {exc}")

    def _on_release(self):
        if self._is_paused or not self._is_pressed:
            return
        self._is_pressed = False
        print(f"[HOTKEY] RELEASED and suppressed ({self.hotkey})")
        if self.on_release_callback:
            try:
                self.on_release_callback()
            except Exception as exc:
                print(f"[ERROR] on_release callback failed: {exc}")

    def _listener_loop(self):
        print(f"[INFO] Starting suppressing hotkey listener for: {self.hotkey}")
        for warning in self._check_conflicts():
            print(f"[WARNING] {warning}")

        try:
            self._register_hotkey()
            print(f"[OK] Hotkey '{self.hotkey}' active with suppress=True")
            while not self._stop_event.is_set():
                if self._is_pressed and not keyboard.is_pressed(self.hotkey):
                    self._on_release()
                time.sleep(0.1)
        except Exception as exc:
            print(f"[ERROR] Failed to register suppressing hotkey: {exc}")
            print(f"[INFO] Run start.bat as Administrator if {self.hotkey} is not blocked on Windows 11.")
        finally:
            self._unregister_hotkey()
            self._is_pressed = False

    def start(self):
        if self._is_listening:
            print("[WARNING] Hotkey listener already running")
            return

        self._stop_event.clear()
        self._is_paused = False
        self._is_listening = True
        self._listener_thread = threading.Thread(
            target=self._listener_loop,
            daemon=True,
            name="SuppressingHotkeyListener",
        )
        self._listener_thread.start()

    def stop(self):
        if not self._is_listening:
            return

        print("[INFO] Stopping hotkey listener...")
        self._stop_event.set()
        self._unregister_hotkey()
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass

        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=2.0)

        self._is_listening = False
        self._is_pressed = False
        self._is_paused = False
        print(f"[OK] Hotkey listener stopped and {self.hotkey} restored")

    def pause_hotkey(self):
        """Temporarily disable callbacks while keeping normal typing possible."""
        if self._is_paused:
            return
        self._is_paused = True
        self._is_pressed = False
        self._unregister_hotkey()
        print("[INFO] Hotkey paused")

    def resume_hotkey(self):
        """Resume suppression/callbacks after a temporary pause."""
        if not self._is_paused:
            return
        self._is_paused = False
        if self._is_listening:
            self._register_hotkey()
        print("[INFO] Hotkey resumed")

    def update_hotkey(self, new_hotkey):
        if new_hotkey == self.hotkey:
            return True

        self.hotkey = new_hotkey
        print(f"[INFO] Hotkey updated to: {new_hotkey}")
        for warning in self._check_conflicts():
            print(f"[WARNING] {warning}")

        if self._is_listening and not self._is_paused:
            self._register_hotkey()
        return True

    def is_listening(self):
        return self._is_listening

    def is_pressed(self):
        return self._is_pressed


if __name__ == "__main__":
    print("=" * 60)
    print("HotkeyManager Test")
    print("=" * 60)
    print(f"Testing with hotkey: {config.HOTKEY}")
    print("Run as Administrator if suppression does not work.")

    def on_test_press():
        print(">>> PRESSED")

    def on_test_release():
        print(">>> RELEASED")

    manager = HotkeyManager(on_test_press, on_test_release)
    manager.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.stop()

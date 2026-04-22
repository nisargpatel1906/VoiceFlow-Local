"""
VoiceFlow Local - global hotkey listener.

Windows keeps the existing suppressed keyboard hook path.
macOS uses pynput for global key detection without key suppression.
"""

import sys
import threading
import time

import config

if sys.platform == "darwin":
    try:
        from pynput import keyboard as pynput_keyboard
        _PYNPUT_IMPORT_ERROR = None
    except Exception as exc:
        pynput_keyboard = None
        _PYNPUT_IMPORT_ERROR = exc
else:
    import keyboard


class HotkeyManager:
    """
    Global push-to-talk hotkey manager.

    Uses keyboard.add_hotkey(..., suppress=True) so the configured hotkey is
    blocked from every other app while VoiceFlow is active. Release is detected
    by polling the current key state, avoiding duplicate suppressed
    registrations.
    """

    def __init__(self, on_press_callback=None, on_release_callback=None, on_quit_callback=None):
        self.hotkey = config.HOTKEY
        self.quit_hotkey = getattr(config, "QUIT_HOTKEY", "ctrl+q")
        self.on_press_callback = on_press_callback
        self.on_release_callback = on_release_callback
        self.on_quit_callback = on_quit_callback

        self._is_listening = False
        self._is_pressed = False
        self._is_paused = False
        self._listener_thread = None
        self._stop_event = threading.Event()
        self._press_handle = None
        self._quit_handle = None
        self._listener = None
        self._pressed_keys = set()
        self._quit_fired = False
        self._hotkey_tokens = self._parse_hotkey(self.hotkey)
        self._quit_hotkey_tokens = self._parse_hotkey(self.quit_hotkey)

    def _check_conflicts(self, hotkey_value=None):
        warnings = []
        hotkey_lower = (hotkey_value or self.hotkey).lower()
        if sys.platform == "darwin":
            system_shortcuts = {
                "command+space": "Opens Spotlight",
                "ctrl+space": "Often switches input source",
                "command+tab": "Switches applications",
                "command+q": "Quits the active app",
                "command+c": "Copy shortcut",
                "command+v": "Paste shortcut",
                "command+x": "Cut shortcut",
            }
        else:
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
            warnings.append(f"Conflict warning: '{hotkey_value or self.hotkey}' - {system_shortcuts[hotkey_lower]}")
        modifier_only = ["ctrl", "alt", "shift", "windows", "command"]
        if hotkey_lower in modifier_only:
            warnings.append(f"Warning: Single modifier key '{hotkey_value or self.hotkey}' may not work reliably")
        return warnings

    def _register_hotkey(self):
        self._unregister_hotkey()
        self._hotkey_tokens = self._parse_hotkey(self.hotkey)
        self._quit_hotkey_tokens = self._parse_hotkey(self.quit_hotkey)
        if sys.platform == "darwin":
            if pynput_keyboard is None:
                raise RuntimeError(
                    f"macOS hotkeys require pynput. Install requirements first. ({_PYNPUT_IMPORT_ERROR})"
                )
            self._listener = pynput_keyboard.Listener(
                on_press=self._on_native_press,
                on_release=self._on_native_release,
            )
            self._listener.start()
            return

        self._press_handle = keyboard.add_hotkey(
            self.hotkey,
            self._on_press,
            suppress=True,
            trigger_on_release=False,
        )
        self._quit_handle = keyboard.add_hotkey(
            self.quit_hotkey,
            self._on_quit,
            suppress=True,
            trigger_on_release=False,
        )

    def _unregister_hotkey(self):
        if sys.platform == "darwin":
            listener = self._listener
            self._listener = None
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    pass
            self._pressed_keys.clear()
            self._quit_fired = False
            return

        if self._press_handle is not None:
            try:
                keyboard.remove_hotkey(self._press_handle)
            except Exception:
                pass
        self._press_handle = None
        if self._quit_handle is not None:
            try:
                keyboard.remove_hotkey(self._quit_handle)
            except Exception:
                pass
        self._quit_handle = None

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

    def _on_quit(self):
        if self._is_paused:
            return
        print(f"[HOTKEY] QUIT and suppressed ({self.quit_hotkey})")
        if self.on_quit_callback:
            try:
                self.on_quit_callback()
            except Exception as exc:
                print(f"[ERROR] on_quit callback failed: {exc}")

    def _listener_loop(self):
        if sys.platform == "darwin":
            print(f"[INFO] Starting macOS hotkey listener for: {self.hotkey}")
        else:
            print(f"[INFO] Starting suppressing hotkey listener for: {self.hotkey}")
        for warning in self._check_conflicts():
            print(f"[WARNING] {warning}")
        for warning in self._check_conflicts(self.quit_hotkey):
            print(f"[WARNING] Quit {warning}")

        try:
            self._register_hotkey()
            if sys.platform == "darwin":
                print(f"[OK] Hotkey '{self.hotkey}' active on macOS")
                print(f"[OK] Quit hotkey '{self.quit_hotkey}' active on macOS")
            else:
                print(f"[OK] Hotkey '{self.hotkey}' active with suppress=True")
                print(f"[OK] Quit hotkey '{self.quit_hotkey}' active with suppress=True")
            while not self._stop_event.is_set():
                if sys.platform != "darwin" and self._is_pressed and not keyboard.is_pressed(self.hotkey):
                    self._on_release()
                time.sleep(0.1)
        except Exception as exc:
            if sys.platform == "darwin":
                print(f"[ERROR] Failed to register macOS hotkey listener: {exc}")
                print("[INFO] Grant Accessibility permissions to the terminal/app on macOS.")
            else:
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
        if sys.platform != "darwin":
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
        if sys.platform == "darwin":
            self._pressed_keys.clear()
            self._quit_fired = False
        else:
            self._unregister_hotkey()
        print("[INFO] Hotkey paused")

    def resume_hotkey(self):
        """Resume suppression/callbacks after a temporary pause."""
        if not self._is_paused:
            return
        self._is_paused = False
        if self._is_listening and sys.platform != "darwin":
            self._register_hotkey()
        print("[INFO] Hotkey resumed")

    def update_hotkey(self, new_hotkey):
        if new_hotkey == self.hotkey:
            return True

        self.hotkey = new_hotkey
        self._hotkey_tokens = self._parse_hotkey(new_hotkey)
        print(f"[INFO] Hotkey updated to: {new_hotkey}")
        for warning in self._check_conflicts():
            print(f"[WARNING] {warning}")

        if self._is_listening and not self._is_paused:
            self._register_hotkey()
        return True

    def update_quit_hotkey(self, new_hotkey):
        if new_hotkey == self.quit_hotkey:
            return True

        self.quit_hotkey = new_hotkey
        self._quit_hotkey_tokens = self._parse_hotkey(new_hotkey)
        print(f"[INFO] Quit hotkey updated to: {new_hotkey}")
        for warning in self._check_conflicts(self.quit_hotkey):
            print(f"[WARNING] Quit {warning}")

        if self._is_listening and not self._is_paused:
            self._register_hotkey()
        return True

    def is_listening(self):
        return self._is_listening

    def is_pressed(self):
        return self._is_pressed

    def _parse_hotkey(self, hotkey_value):
        aliases = {
            "control": "ctrl",
            "win": "windows",
            "cmd": "windows",
            "command": "windows",
            "meta": "windows",
            "option": "alt",
            "return": "enter",
        }
        tokens = []
        for part in hotkey_value.replace("-", "+").split("+"):
            token = part.strip().lower()
            if not token:
                continue
            tokens.append(aliases.get(token, token))
        return set(tokens)

    def _normalize_pynput_key(self, key):
        if key in (pynput_keyboard.Key.ctrl, pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r):
            return "ctrl"
        if key in (pynput_keyboard.Key.alt, pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r, pynput_keyboard.Key.alt_gr):
            return "alt"
        if key in (pynput_keyboard.Key.shift, pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r):
            return "shift"
        if key in (
            pynput_keyboard.Key.cmd,
            getattr(pynput_keyboard.Key, "cmd_l", None),
            getattr(pynput_keyboard.Key, "cmd_r", None),
        ):
            return "windows"
        if key == pynput_keyboard.Key.space:
            return "space"
        if key == pynput_keyboard.Key.enter:
            return "enter"
        if key == pynput_keyboard.Key.tab:
            return "tab"
        if key == pynput_keyboard.Key.esc:
            return "esc"
        if hasattr(key, "char") and key.char:
            return key.char.lower()
        return None

    def _on_native_press(self, key):
        if self._is_paused:
            return
        token = self._normalize_pynput_key(key)
        if not token:
            return
        self._pressed_keys.add(token)

        if self._quit_hotkey_tokens and self._quit_hotkey_tokens.issubset(self._pressed_keys):
            if not self._quit_fired:
                self._quit_fired = True
                self._on_quit()
            return

        if self._hotkey_tokens and self._hotkey_tokens.issubset(self._pressed_keys) and not self._is_pressed:
            self._on_press()

    def _on_native_release(self, key):
        token = self._normalize_pynput_key(key)
        if token:
            self._pressed_keys.discard(token)

        if self._quit_fired and not self._quit_hotkey_tokens.issubset(self._pressed_keys):
            self._quit_fired = False

        if self._is_pressed and not self._hotkey_tokens.issubset(self._pressed_keys):
            self._on_release()


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

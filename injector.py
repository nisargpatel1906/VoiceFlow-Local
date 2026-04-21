"""
VoiceFlow Local - Text Injector Module

Injects transcribed text into the currently focused Windows application.
Uses clipboard + Ctrl+V as primary method, pyautogui.write() as fallback.
"""

import time
import threading
import pyperclip
import pyautogui
import config


class TextInjector:
    """
    Injects text into the active Windows application.

    Uses a two-tier strategy:
    1. Clipboard + Ctrl+V (works in 99% of apps)
    2. pyautogui.write() character-by-character (fallback)
    """

    # Timing constants (in seconds)
    CLIPBOARD_SET_DELAY = 0.1      # 100ms wait after setting clipboard
    HOTKEY_RELEASE_DELAY = 0.2     # 200ms wait before injection
    CLIPBOARD_RESTORE_DELAY = 2.0  # 2 seconds before restoring clipboard
    KEY_INTERVAL = 0.01            # 10ms between characters for fallback

    def __init__(self):
        """Initialize the text injector."""
        # Configure pyautogui for faster typing
        pyautogui.PAUSE = self.KEY_INTERVAL
        pyautogui.FAILSAFE = False  # Disable fail-safe for injection

    def _save_clipboard(self):
        """
        Save the current clipboard content.

        Returns:
            str: Current clipboard content, or None if empty/error.
        """
        try:
            content = pyperclip.paste()
            return content if content else None
        except Exception as e:
            print(f"[DEBUG] Could not save clipboard: {e}")
            return None

    def _set_clipboard(self, text):
        """
        Set text to clipboard.

        Args:
            text: Text to copy to clipboard.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            pyperclip.copy(text)
            # Wait for clipboard to be set
            time.sleep(self.CLIPBOARD_SET_DELAY)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to set clipboard: {e}")
            return False

    def _restore_clipboard(self, original_content):
        """
        Restore the original clipboard content.

        Args:
            original_content: The content to restore (or None to clear).
        """
        try:
            if original_content is not None:
                pyperclip.copy(original_content)
                print(f"[DEBUG] Clipboard restored")
            else:
                # Clear clipboard if there was no original content
                pyperclip.copy('')
                print(f"[DEBUG] Clipboard cleared")
        except Exception as e:
            print(f"[DEBUG] Could not restore clipboard: {e}")

    def _inject_with_paste(self, text):
        """
        Inject text using Ctrl+V paste method.

        Args:
            text: Text to inject.

        Returns:
            bool: True if successful, False otherwise.
        """
        print("[DEBUG] Attempting clipboard paste method...")

        try:
            # Simulate Ctrl+V
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)  # Small delay to ensure paste completes
            print("[OK] Clipboard paste successful")
            return True
        except Exception as e:
            print(f"[DEBUG] Paste method failed: {e}")
            return False

    def _inject_with_typing(self, text):
        """
        Inject text by typing character-by-character (fallback).

        Args:
            text: Text to inject.

        Returns:
            bool: True if successful, False otherwise.
        """
        print("[DEBUG] Attempting typing fallback method...")

        try:
            # Type each character with small delay
            for char in text:
                pyautogui.write(char, interval=0)  # interval=0 uses PAUSE
            print("[OK] Typing fallback successful")
            return True
        except Exception as e:
            print(f"[DEBUG] Typing method failed: {e}")
            return False

    def inject_at_cursor(self, text):
        """
        Inject text at the current cursor position.

        This is the main public method. It:
        1. Waits for hotkey release (200ms)
        2. Saves original clipboard
        3. Sets new clipboard content
        4. Tries Ctrl+V paste (primary)
        5. Falls back to character-by-character typing
        6. Schedules clipboard restore after 2 seconds

        Args:
            text: The text to inject.

        Returns:
            bool: True if injection was successful, False otherwise.
        """
        if not text:
            print("[WARNING] No text to inject")
            return False

        print(f"[INFO] Injecting {len(text)} characters...")

        # Step 1: Wait for hotkey release
        time.sleep(self.HOTKEY_RELEASE_DELAY)

        # Step 2: Save original clipboard
        original_clipboard = self._save_clipboard()
        print(f"[DEBUG] Original clipboard saved ({len(original_clipboard or '')} chars)")

        # Step 3: Set new clipboard content
        if not self._set_clipboard(text):
            print("[ERROR] Could not set clipboard, trying typing fallback...")
            return self._inject_with_typing(text)

        # Step 4: Try primary method (Ctrl+V)
        if self._inject_with_paste(text):
            # Schedule clipboard restore in background
            self._schedule_clipboard_restore(original_clipboard)
            return True

        # Step 5: Fallback to typing
        print("[INFO] Paste failed, falling back to typing...")
        if self._inject_with_typing(text):
            # Still restore clipboard since we set it
            self._schedule_clipboard_restore(original_clipboard)
            return True

        # Step 6: Both methods failed
        print("[ERROR] Both injection methods failed. Text remains in clipboard.")
        # Don't restore clipboard yet - user may want to manually paste
        return False

    def _schedule_clipboard_restore(self, original_content):
        """
        Schedule clipboard restoration after a delay.

        Args:
            original_content: The content to restore.
        """
        def restore_later():
            time.sleep(self.CLIPBOARD_RESTORE_DELAY)
            self._restore_clipboard(original_content)

        # Run in background thread so we don't block
        thread = threading.Thread(target=restore_later, daemon=True)
        thread.start()


# =============================================================================
# TEST: Inject test text (run with caution - will inject into active window)
# =============================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("TextInjector Test")
    print("=" * 60)
    print()
    print("WARNING: This will inject text into your currently active window!")
    print("Click on a text field (Notepad, Word, browser, etc.) in 5 seconds...")
    print()

    # Countdown
    for i in range(5, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    print()
    print("Injecting test text...")

    injector = TextInjector()
    test_text = "Hello! This is a test from VoiceFlow Local."

    success = injector.inject_at_cursor(test_text)

    print()
    if success:
        print("[OK] Injection successful!")
    else:
        print("[ERROR] Injection failed.")

    print()
    print("Clipboard will be restored in 2 seconds...")
    time.sleep(3)
    print("Test complete!")

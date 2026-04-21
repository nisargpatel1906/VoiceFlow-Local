"""
VoiceFlow Local - Audio Recorder Module

Handles microphone recording for voice dictation.
Captures audio via pyaudio and saves as 16kHz mono WAV files.
"""

import os
import wave
import tempfile
import threading
import pyaudio
import config


class AudioRecorder:
    """
    Records audio from the default microphone.

    Supports push-to-talk recording with audio level feedback.
    Audio is saved as 16kHz mono WAV format for Whisper processing.
    """

    # Audio format constants
    SAMPLE_RATE = 16000      # 16kHz - Whisper's expected sample rate
    CHANNELS = 1             # Mono
    SAMPLE_WIDTH = 2         # 16-bit audio
    CHUNK_SIZE = 1024        # Buffer size for reading audio

    def __init__(self):
        """Initialize the audio recorder."""
        self.audio = None
        self.stream = None
        self.is_recording = False
        self.audio_data = []
        self._temp_file_path = None
        self._peak_volume = 0
        self._error = None

    def _init_audio(self):
        """
        Initialize PyAudio instance and open microphone stream.

        Raises:
            OSError: If no microphone is found or permission is denied.
        """
        try:
            self.audio = pyaudio.PyAudio()

            # Find and open default input device (microphone)
            default_device = self.audio.get_default_input_device_info()
            if not default_device:
                raise OSError("No microphone found. Please connect a microphone and try again.")

            self.stream = self.audio.open(
                format=self.audio.get_format_from_width(self.SAMPLE_WIDTH),
                channels=self.CHANNELS,
                rate=self.SAMPLE_RATE,
                input=True,
                frames_per_buffer=self.CHUNK_SIZE
            )
        except OSError as e:
            if "Invalid device" in str(e) or "Unanticipated host error" in str(e):
                raise OSError(
                    "No microphone found or access denied.\n"
                    "Please check: (1) Microphone is connected, "
                    "(2) Microphone permissions are granted in Windows settings."
                ) from e
            raise
        except Exception as e:
            raise OSError(f"Failed to initialize audio: {e}") from e

    def start_recording(self):
        """
        Start recording audio from the microphone.

        Captures audio chunks until stop_recording() is called.
        Prints peak volume level to console during recording.
        """
        if self.is_recording:
            return

        try:
            self._init_audio()
        except OSError as e:
            self._error = str(e)
            print(f"[ERROR] {e}")
            return

        self.is_recording = True
        self.audio_data = []
        self._peak_volume = 0

        print("[REC] Recording... (audio levels below)")

        # Read audio chunks while recording
        while self.is_recording:
            try:
                data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
                self.audio_data.append(data)

                # Calculate and display audio level (peak amplitude)
                import numpy as np
                audio_array = np.frombuffer(data, dtype=np.int16)
                peak = np.max(np.abs(audio_array))
                self._peak_volume = max(self._peak_volume, peak)

                # Visual feedback: bar based on volume (0-32767 range for 16-bit)
                level_pct = (peak / 32767) * 100
                bar_len = int(level_pct / 5)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                print(f"\r  Level: [{bar}] {level_pct:5.1f}%  ", end="", flush=True)

            except OSError as e:
                if "Input overflowed" in str(e):
                    # Buffer overflow - skip this chunk
                    continue
                print(f"\n[ERROR] Audio read error: {e}")
                break

        print()  # Newline after recording stops
        print(f"  Peak volume: {self._peak_volume}")

    def stop_recording(self):
        """Stop recording and close the audio stream."""
        self.is_recording = False

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        if self.audio:
            self.audio.terminate()
            self.audio = None

    def get_audio_file(self):
        """
        Save recorded audio to a temporary WAV file.

        Returns:
            str: Path to the temporary WAV file, or None if no audio was recorded.
        """
        if not self.audio_data:
            print("[WARNING] No audio data to save.")
            return None

        # Create temp file for WAV output
        temp_file = tempfile.NamedTemporaryFile(
            suffix='.wav',
            delete=False
        )
        self._temp_file_path = temp_file.name
        temp_file.close()

        # Write WAV file
        try:
            with wave.open(self._temp_file_path, 'wb') as wf:
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(2)  # 16-bit = 2 bytes
                wf.setframerate(self.SAMPLE_RATE)
                wf.writeframes(b''.join(self.audio_data))

            print(f"[OK] Audio saved to: {self._temp_file_path}")
            return self._temp_file_path

        except Exception as e:
            print(f"[ERROR] Failed to save audio: {e}")
            return None

    def cleanup(self):
        """Delete the temporary WAV file after processing."""
        if self._temp_file_path and os.path.exists(self._temp_file_path):
            try:
                os.remove(self._temp_file_path)
                print(f"[CLEANUP] Deleted temp file: {self._temp_file_path}")
                self._temp_file_path = None
            except OSError as e:
                print(f"[WARNING] Failed to delete temp file: {e}")

    def get_error(self):
        """Return the last error message, or None if no error."""
        return self._error


# =============================================================================
# TEST: Record for 3 seconds and print file path
# =============================================================================
if __name__ == '__main__':
    import time

    print("=" * 50)
    print("AudioRecorder Test - Recording for 3 seconds...")
    print("=" * 50)
    print()

    recorder = AudioRecorder()

    # Start recording
    recorder.start_recording()

    # Wait 3 seconds
    time.sleep(3)

    # Stop recording
    recorder.stop_recording()

    # Get the audio file path
    file_path = recorder.get_audio_file()

    if file_path:
        print()
        print(f"Recorded file: {file_path}")
        print("Test complete!")
    else:
        print("Test failed - no audio file created.")
        if recorder.get_error():
            print(f"Error: {recorder.get_error()}")

    # Cleanup
    recorder.cleanup()

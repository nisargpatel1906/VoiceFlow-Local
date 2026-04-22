<p align="center">
  <img src="logo.png" width="150" alt="VoiceFlow Local Logo">
</p>

# VoiceFlow Local (v2.5)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows/)

**VoiceFlow Local** is a high-performance, privacy-focused voice dictation application for Windows. Version 2.5 introduces a complete architectural overhaul, moving from batch processing to **Real-time Streaming Dictation**. Powered by OpenAI's Whisper (via `faster-whisper`), it allows you to dictate text anywhere on your system with zero cloud dependency.

---

## New in Version 2.5

- **Real-time Streaming**: See your words appear as you speak with a new low-latency streaming engine.
- **Voice Commands**: Control formatting with commands like "new line", "period", "comma", and "delete that".
- **Intelligent Text Cleaning**: Advanced algorithms automatically remove filler words ("um", "uh"), fix self-corrections ("no wait..."), and deduplicate speech artifacts.
- **Flexible Dictation**: Support for both "Push-to-Talk" and "Toggle" modes.
- **Translation Support**: Live translation from any language to English.

---

## Core Features

- **Lightning Fast**: Optimized CTranslate2 inference using `faster-whisper`.
- **Privacy First**: 100% local processing. Your audio never leaves your machine.
- **Direct Injection**: Transcribed text is automatically typed at your cursor position in any application.
- **Customizable Models**: Choose between `tiny`, `base`, `small`, `medium`, and `large-v3` based on your hardware.
- **Enhanced History**: Search and manage your session history with character counts and duration tracking.
- **Modern UI**: Sleek dark-mode interface with real-time waveform visualization and live text feedback.

---

## Architecture

VoiceFlow Local 2.5 utilizes a sophisticated multi-threaded system:
- **StreamingRecorder**: High-performance audio capture with chunked buffering.
- **StreamingTranscriber**: Asynchronous Whisper inference for non-blocking UI updates.
- **TextCleaner**: Multi-stage processing pipeline for polished, human-like text output.
- **PyQt6 Interface**: Hardware-accelerated GUI for system tray and settings management.

---

## Getting Started

### Prerequisites

- **OS**: Windows 10/11
- **Python**: 3.10 recommended (the installer targets `py -3.10`)
- **GPU**: NVIDIA GPU with CUDA support is highly recommended for the streaming engine.

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/nisargpatel1906/VoiceFlow-Local.git
   cd voiceflow-local
   ```

2. **Run the Installer**:
   Double-click `install.bat`. This will set up the virtual environment, install dependencies, and download the default model.

---

## Usage Guide

1. **Launch**: Run `start.bat`. A microphone icon will appear in your System Tray.
2. **Setup Focus**: Click into any text field (VS Code, Browser, Word, etc.).
3. **Dictate**: Press and hold **`Ctrl + Space`** (default).
   - The tray icon turns **red**.
   - A **live overlay** shows your text appearing in real-time.
4. **Voice Commands**: While speaking, use commands like:
   - "Comma", "Period", "Question Mark" for punctuation.
   - "New line" or "New paragraph" for structure.
   - "Delete that" to instantly cancel the current phrase.
5. **Release**: Let go of the hotkey. The final, polished text is injected at your cursor.

---

## Voice Commands Reference

| Command | Action |
|---------|--------|
| `period` / `full stop` | Inserts `.` |
| `comma` | Inserts `,` |
| `new line` | Inserts a line break |
| `new paragraph` | Inserts two line breaks |
| `delete that` | Cancels the current transcription |
| `question mark` | Inserts `?` |

---

## Configuration

Settings can be adjusted via the **Settings Window** or in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `HOTKEY` | `ctrl+space` | Trigger for dictation. |
| `MODEL_SIZE`| `medium` | Whisper model accuracy level. |
| `TOGGLE_MODE`| `False` | Switch between push-to-talk and toggle behavior. |
| `REMOVE_FILLERS`| `True` | Strips "um", "uh", "like" from output. |
| `AUTO_CAPITALIZE`| `True` | Automatically formats sentence starts. |
| `TRANSLATE` | `False` | Translates incoming speech to English. |

---

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any features or bug fixes.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/NewFeature`)
3. Commit your Changes (`git commit -m 'Add NewFeature'`)
4. Push to the Branch (`git push origin feature/NewFeature`)
5. Open a Pull Request

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

---

## Author

**Nisarg Patel**
- GitHub: [@nisargpatel1906](https://github.com/nisargpatel1906)

*Revolutionizing local dictation*


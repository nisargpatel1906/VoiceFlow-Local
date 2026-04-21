<p align="center">
  <img src="logo.png" width="150" alt="VoiceFlow Local Logo">
</p>

# VoiceFlow Local

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows/)

**VoiceFlow Local** is a high-performance, privacy-focused voice dictation application for Windows. Powered by OpenAI's Whisper (via `faster-whisper`), it allows you to dictate text anywhere on your system with a simple hotkey, performing all transcription locally on your GPU/CPU.

---

## Features

- **Lightning Fast**: Uses `faster-whisper` for optimized CTranslate2 inference.
- **Privacy First**: No cloud APIs. Your voice never leaves your machine.
- **Push-to-Talk**: Global hotkey (`Ctrl + Space` by default) for seamless dictation.
- **Direct Injection**: Transcribed text is automatically typed at your cursor or copied to the clipboard.
- **Customizable**: Adjustable model sizes (tiny to large-v3), filler word removal, and more.
- **History**: Keep track of your previous dictations with a built-in session history.
- **Sleek UI**: Minimalist system tray integration with real-time audio level visualization.

---

## Architecture

VoicesFlow Local is built with a robust, multi-threaded architecture:
- **PyQt6**: Manages the system tray, UI windows, and event loop.
- **Faster-Whisper**: High-efficiency ASR (Automatic Speech Recognition).
- **PyAudio**: Low-latency audio capture.
- **PyAutoGUI**: Handles simulated keyboard input for text injection.

---

## Getting Started

### Prerequisites

- **OS**: Windows 10/11
- **Python**: 3.10 recommended (the installer specifically looks for `py -3.10`)
- **GPU (Optional)**: NVIDIA GPU with CUDA support is highly recommended for real-time performance.

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/nisargpatel1906/VoiceFlow-Local.git
   cd voiceflow-local
   ```

2. **Run the Installer**:
   Double-click `install.bat`. This will:
   - Create a Python virtual environment (`venv`).
   - Install all required dependencies from `requirements.txt`.
   - Download the default Whisper model to the `models/` directory.

### Running the App

Double-click `start.bat` to launch the application.
- You will see a microphone icon in your system tray.
- Hold **`Ctrl + Space`** to record.
- Release to transcribe and inject the text.

---

## Configuration

Settings can be managed via the UI or by editing `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `HOTKEY` | `ctrl+space` | Global key combination to trigger recording. |
| `MODEL_SIZE`| `medium` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v3`). |
| `DEVICE` | `cuda` | `cuda` for GPU or `cpu` for CPU-only mode. |
| `COMPUTE_TYPE`| `float16` | Quantization type for inference (e.g., `int8`, `float16`). |
| `REMOVE_FILLERS`| `True` | Automatically strips words like "um", "uh", "like". |

---

## Contributing

Contributions are welcome! If you have suggestions for new features or find bugs, please open an issue or submit a pull request.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

---

## Author

**Nisarg Patel**
- GitHub: [@nisargpatel1906](https://github.com/nisargpatel1906)

*Made with support for faster, easier dictation.*

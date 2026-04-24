<p align="center">
  <img src="logo.png" width="140" alt="VoiceFlow Local logo">
</p>

# VoiceFlow Local

Local voice dictation with a floating UI, live preview, final paste-on-release, history, and a settings panel. The app is built with PyQt6 and runs fully on-device with Whisper via `faster-whisper`.

## What it does

- Global dictation hotkey: `Ctrl+Space`
- Global quit hotkey: `Ctrl+Q`
- Floating bottom bar plus full desktop window
- Live transcription preview while you speak
- Final higher-accuracy transcription on release
- Direct paste into the last focused app
- Local history in `voiceflow_log.txt`
- Text cleanup:
  - filler removal
  - self-correction cleanup
  - auto-capitalization
  - voice commands
- Optional translate-to-English mode

## Current platform support

### Windows

Windows is the primary path.

- Global hotkeys use `keyboard`
- Text injection uses `Ctrl+V`
- `faster-whisper` uses CUDA when available
- One-click launcher: `start.bat`
- Installer: `install.bat`

### macOS

macOS support uses the same codebase, but not the same acceleration path.

- Global hotkeys use `pynput`
- Text injection uses `Cmd+V`
- One-click launchers:
  - `start_mac.command`
  - `start.command`
- `faster-whisper` runs on **CPU/int8** on macOS in this project

Important: this codebase does **not** use CUDA on Mac.

Reason:
- PyTorch supports `mps` on Apple Silicon
- but this app uses `faster-whisper`, which runs on CTranslate2
- CTranslate2 prebuilt GPU support is NVIDIA-only, so the practical path here is CPU on Mac

## Requirements

### Common

- Python 3.10+
- microphone access
- internet on first model download

### Windows

- Windows 10 or 11
- Python Launcher available as `py`
- NVIDIA GPU recommended for best live performance

### macOS

- macOS with Python 3.10+
- Accessibility permission for the terminal or app runner
- microphone permission

## Install

### 1. Clone the repository

```bash
git clone https://github.com/nisargpatel1906/VoiceFlow-Local.git
cd VoiceFlow-Local
```

### 2. Install Dependencies

#### Windows install

That script:
- creates `venv`
- installs dependencies
- downloads the default Whisper model

#### macOS install

There is no separate Mac installer script in the repo yet. Use a normal venv setup:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
chmod +x start.command start_mac.command
```

If you want the model downloaded before first launch:

```bash
python -c "import config; from faster_whisper import WhisperModel; WhisperModel(config.MODEL_SIZE, download_root='models')"
```

## Run

### Windows

```bat
start.bat
```

This launches the app hidden in the background with the floating UI.

### macOS

Use either:

```bash
./start_mac.command
```

or:

```bash
./start.command
```

## First-run OS permissions

### Windows

- Microphone access must be enabled
- If suppressed hotkeys behave inconsistently on your setup, run with appropriate permissions

### macOS

You must allow:

- Accessibility
- Microphone

Without Accessibility permission:
- global hotkeys will not work correctly
- paste injection will not work correctly

## Hotkeys

Default hotkeys:

- Dictate: `Ctrl+Space`
- Quit app: `Ctrl+Q`

These can be changed from the settings panel. When changed, the visible hotkey labels in the UI update too.

## How dictation works

Current flow:

1. Hold `Ctrl+Space`
2. Audio is captured in streaming chunks
3. Live text preview updates in the UI
4. Release hotkey
5. The app runs a final transcription pass on the full rolling buffer
6. Cleaned text is pasted into the previously focused app
7. History is saved locally if auto-save is enabled

## Settings

The settings window supports:

- hotkey recording
- toggle mode
- model selection
- compute type
- language selection
- beam size
- translate-to-English toggle
- filler word cleanup
- self-correction cleanup
- auto-capitalization
- voice commands
- auto-save
- log format
- history limit
- start with Windows / start at login
- notifications
- silence threshold
- debug mode

Settings are written back to `config.py`.

## Files of interest

- `main.py` - app entrypoint and runtime orchestration
- `voiceflow_ui.py` - floating UI, main window, tray controller
- `gui/settings_window.py` - settings panel
- `hotkey.py` - Windows and macOS hotkey backends
- `streaming_recorder.py` - chunked mic capture
- `streaming_transcriber.py` - live Whisper consumer
- `transcriber.py` - fallback/final transcription path
- `cleaner.py` - text cleanup and chunk dedupe
- `config.py` - generated runtime settings
- `start.bat` - Windows launcher
- `start.command` / `start_mac.command` - macOS launchers

## Audio / notification sounds

The app uses local MP3 files from the repo folder:

- `enter.mp3` - app-ready sound after startup
- `sound.mp3` - transcription complete sound
- `quite.mp3` - quit sound on `Ctrl+Q`

Tray popup notifications are disabled by default in the current config.

## Logging and history

- runtime log: `voiceflow.log`
- startup log: `voiceflow_start.log`
- transcription history: `voiceflow_log.txt`

History entries include:
- text
- date
- time
- character count
- duration

## Known limits

- Windows is the best-supported runtime path
- macOS currently uses CPU/int8 for Whisper in this codebase
- `faster-whisper` on Mac is not using MPS in this project
- macOS support is code-level integrated, but final validation still depends on real Mac testing

## Development notes

### Windows quick dev run

```bat
venv\Scripts\python.exe main.py --debug
```

### macOS quick dev run

```bash
source venv/bin/activate
python main.py --debug
```

## License

MIT. See [LICENSE](LICENSE).

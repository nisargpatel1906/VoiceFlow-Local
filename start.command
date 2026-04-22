#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ ! -d "venv" ]; then
  osascript -e 'display alert "VoiceFlow Local" message "Virtual environment not found. Run install first."' >/dev/null 2>&1
  exit 1
fi

export KMP_DUPLICATE_LIB_OK=TRUE

PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"
fi

nohup "$PYTHON_BIN" "$SCRIPT_DIR/launcher.py" >> "$SCRIPT_DIR/voiceflow_start.log" 2>&1 &
exit 0

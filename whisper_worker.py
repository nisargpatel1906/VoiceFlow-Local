"""
VoiceFlow Local - isolated Whisper subprocess worker.

This script is launched by the UI process for final transcription. Keeping
faster-whisper/CUDA in a child process prevents native DLL/CUDA crashes from
taking down the PyQt app when the hotkey is released.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import traceback


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "Missing audio file path"}))
        return 2

    audio_path = sys.argv[1]

    try:
        import config

        if os.environ.get("VOICEFLOW_FORCE_CPU") == "1":
            config.DEVICE = "cpu"
            config.COMPUTE_TYPE = "int8"
        elif config.DEVICE == "cuda":
            # Auto-detect: if no CUDA GPU is found, switch to CPU before
            # loading the model so the user gets a clear message instead of
            # a cryptic CUDA error deep inside faster-whisper.
            try:
                from gpu_detect import best_device
                if best_device() != "cuda":
                    print("[INFO] No CUDA GPU detected; switching to CPU mode.", file=sys.stderr)
                    config.DEVICE = "cpu"
                    config.COMPUTE_TYPE = "int8"
            except (ImportError, ModuleNotFoundError, Exception) as _gpu_exc:
                print(f"[DEBUG] gpu_detect unavailable ({_gpu_exc}); transcriber.py handles fallback.", file=sys.stderr)

        from transcriber import WhisperTranscriber

        # transcriber.py prints progress; keep stdout clean for JSON.
        with contextlib.redirect_stdout(sys.stderr):
            text = WhisperTranscriber().transcribe(audio_path)

        print(json.dumps({"ok": True, "text": text}, ensure_ascii=False))
        return 0
    except BaseException as exc:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

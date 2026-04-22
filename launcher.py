"""
VoiceFlow Local - crash supervisor.

Runs the main app process and restarts it on unexpected exits. A clean exit
code (0) is treated as an intentional quit and stops the supervisor.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
MAIN_FILE = BASE_DIR / "main.py"
LOG_FILE = BASE_DIR / "voiceflow_supervisor.log"
MAX_RESTARTS = 5
WINDOW_SECONDS = 60
RESTART_DELAY_SECONDS = 2


def log(message: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def main() -> int:
    env = os.environ.copy()
    env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    restarts: list[float] = []

    while True:
        process = subprocess.Popen(
            [sys.executable, str(MAIN_FILE), *sys.argv[1:]],
            cwd=str(BASE_DIR),
            env=env,
        )
        return_code = process.wait()

        if return_code == 0:
            log("[INFO] App exited cleanly. Supervisor stopping.")
            return 0

        now = time.time()
        restarts = [stamp for stamp in restarts if now - stamp <= WINDOW_SECONDS]
        restarts.append(now)
        log(f"[WARNING] App crashed with exit code {return_code}. Restarting.")

        if len(restarts) >= MAX_RESTARTS:
            log("[ERROR] Restart loop limit reached. Supervisor stopping.")
            return return_code

        time.sleep(RESTART_DELAY_SECONDS)


if __name__ == "__main__":
    sys.exit(main())

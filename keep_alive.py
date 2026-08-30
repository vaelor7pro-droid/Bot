"""Botni doimiy ishlatish — to'xtasa qayta ishga tushadi."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


def main() -> None:
    restart_delay = 5
    while True:
        log_file = LOG_DIR / "bot_stdout.log"
        print(f"[keep_alive] Bot ishga tushmoqda... ({PYTHON})")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        with log_file.open("a", encoding="utf-8") as log:
            log.write(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            log.flush()
            proc = subprocess.Popen(
                [PYTHON, "main.py"],
                cwd=str(ROOT),
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
            )
            code = proc.wait()
            log.write(f"--- exit {code} {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")

        print(f"[keep_alive] Bot to'xtadi (code={code}). {restart_delay}s dan keyin qayta...")
        time.sleep(restart_delay)


if __name__ == "__main__":
    main()

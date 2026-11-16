"""One-click launcher: sets up everything on first run, then starts Tracer Tennis and opens it.

Uses only the Python standard library so it can run before anything is installed.
"""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
STAMP = VENV / ".installed"
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"


def say(text: str) -> None:
    print(f"\n== {text}", flush=True)


def requirements_hash() -> str:
    return hashlib.sha256((ROOT / "requirements.txt").read_bytes()).hexdigest()


def pip(*args: str) -> None:
    subprocess.check_call([str(PYTHON), "-m", "pip", "install", "--disable-pip-version-check", *args])


def setup() -> None:
    if sys.version_info < (3, 10):
        sys.exit(f"Python 3.10 or newer is needed; this is {platform.python_version()}. Install it from python.org and run again.")
    if not PYTHON.exists():
        say("First run: creating a private Python environment (about 1 minute)")
        venv.EnvBuilder(with_pip=True, clear=VENV.exists()).create(VENV)
    if STAMP.exists() and STAMP.read_text() == requirements_hash():
        return
    say("Installing the tracking libraries (5 to 10 minutes the first time, about 1.5 GB)")
    if platform.system() == "Darwin":
        pip("torch")
    else:
        pip("torch", "--index-url", TORCH_CPU_INDEX)
    pip("-r", str(ROOT / "requirements.txt"))
    STAMP.write_text(requirements_hash())


def main() -> None:
    os.chdir(ROOT)
    setup()
    say("Starting Tracer Tennis. Leave this window open while you use the app; close it to stop.")
    code = subprocess.call([str(PYTHON), "-m", "app.server", "--open", *sys.argv[1:]])
    sys.exit(code)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"\nSetup failed while running: {' '.join(map(str, exc.cmd))}\nCheck the internet connection and run this again.")
        sys.exit(1)
    except KeyboardInterrupt:
        pass

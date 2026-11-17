"""One-click launcher: sets up everything on first run, then starts Tracer Tennis and opens it.

Uses only the Python standard library so it can run before anything is installed.

Everything that is slow to get or worth keeping lives in one folder per computer, outside the app folder:
    Windows  %LOCALAPPDATA%\\TracerTennis
    Mac      ~/Library/Application Support/Tracer Tennis
    Linux    ~/.local/share/tracer-tennis
with the Python libraries (pyXY), the models, and the saved videos (data/jobs). So when a newer copy of the app is
unzipped somewhere else, it starts in seconds and shows the same saved videos. Set TRACER_TENNIS_HOME to use
another folder.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUPPORTED = [(3, 13), (3, 12), (3, 14)]      # in order of preference; the tracking libraries have builds for these
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"
PORTS = range(8000, 8021)
PYTHON_HELP = {
    "Windows": "Install Python 3.13 from https://www.python.org/downloads/windows/ (tick \"Add python.exe to PATH\"), "
               "or open PowerShell and run:  winget install -e --id Python.Python.3.13",
    "Darwin": "Install Python 3.13 from https://www.python.org/downloads/macos/ (the \"macOS 64-bit universal2 installer\").",
}


def say(text: str) -> None:
    print(f"\n== {text}", flush=True)


def app_home() -> Path:
    env = os.environ.get("TRACER_TENNIS_HOME")
    if env:
        return Path(env).expanduser()
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "TracerTennis"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Tracer Tennis"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "tracer-tennis"


# ---------- picking a Python the libraries support ----------

def supported(version: tuple[int, int]) -> bool:
    return tuple(version[:2]) in SUPPORTED


def candidates() -> list[list[str]]:
    """Commands that might start a supported Python on this computer, best first."""
    out: list[list[str]] = []
    if platform.system() == "Windows":
        out += [["py", f"-{a}.{b}"] for a, b in SUPPORTED]
        out += [["python"], ["python3"]]
    else:
        for a, b in SUPPORTED:
            out.append([f"python{a}.{b}"])
            out.append([f"/Library/Frameworks/Python.framework/Versions/{a}.{b}/bin/python{a}.{b}"])
            out.append([f"/opt/homebrew/bin/python{a}.{b}"])
            out.append([f"/usr/local/bin/python{a}.{b}"])
        out.append(["python3"])
    return out


def probe(cmd: list[str]) -> tuple[tuple[int, int], str, str] | None:
    """(version, executable, machine) for a Python command, or None if it does not run."""
    if os.sep in cmd[0] and not Path(cmd[0]).exists():
        return None
    if os.sep not in cmd[0] and not shutil.which(cmd[0]):
        return None
    code = "import sys, platform, json; print(json.dumps([sys.version_info[:2], sys.executable, platform.machine()]))"
    try:
        out = subprocess.run([*cmd, "-c", code], capture_output=True, text=True, timeout=30)
        version, exe, machine = json.loads(out.stdout.strip().splitlines()[-1])
        return (int(version[0]), int(version[1])), exe, machine
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def apple_silicon() -> bool:
    try:
        return subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True).stdout.strip() == "1"
    except OSError:
        return False


def check_computer() -> None:
    if platform.system() == "Darwin" and not apple_silicon():
        sys.exit("This Mac has an Intel processor. The body tracker Tracer Tennis uses is only made for Apple Silicon "
                 "Macs (M1 and newer) and for Windows PCs, so it cannot run here.")


def ensure_supported_python() -> None:
    """Re-start this launcher under a supported Python if the one that ran it is not."""
    here = sys.version_info[:2]
    if supported(here) and not (platform.system() == "Darwin" and platform.machine() != "arm64"):
        return
    for cmd in candidates():
        found = probe(cmd)
        if found and supported(found[0]) and not (platform.system() == "Darwin" and found[2] != "arm64"):
            say(f"Using Python {found[0][0]}.{found[0][1]} ({found[1]})")
            sys.exit(subprocess.call([found[1], str(ROOT / "launch.py"), *sys.argv[1:]]))
    names = " or ".join(f"{a}.{b}" for a, b in sorted(SUPPORTED))
    if platform.system() == "Darwin" and platform.machine() != "arm64" and supported(here):
        sys.exit("This Python is running in Intel mode on an Apple Silicon Mac, and the body tracker needs the native "
                 "version. " + PYTHON_HELP["Darwin"])
    if platform.system() == "Windows" and offer_python_install():
        return
    sys.exit(f"Tracer Tennis needs Python {names}; this computer has {here[0]}.{here[1]}.\n"
             + PYTHON_HELP.get(platform.system(), "Install Python 3.13 and run this again.")
             + "\nThen start Tracer Tennis again.")


def offer_python_install() -> bool:
    """On Windows, offer to install Python 3.13 with the Python install manager or winget. True if it worked."""
    try:
        answer = input(f"\nTracer Tennis needs Python 3.13, which is not installed. Install it now? (Y/N) ").strip().lower()
    except EOFError:
        return False
    if answer not in ("y", "yes"):
        return False
    for cmd in (["py", "install", "3.13"], ["winget", "install", "-e", "--id", "Python.Python.3.13",
                                            "--accept-source-agreements", "--accept-package-agreements"]):
        if shutil.which(cmd[0]):
            say("Installing Python 3.13")
            if subprocess.call(cmd) == 0:
                found = probe(["py", "-3.13"])
                if found:
                    sys.exit(subprocess.call([found[1], str(ROOT / "launch.py"), *sys.argv[1:]]))
                print("\nPython 3.13 is installed. Close this window and double-click Start Tracer Tennis again.")
                sys.exit(0)
    return False


# ---------- the private Python environment ----------

def requirement_lines() -> list[str]:
    """requirements.txt without PyTorch, which is installed on its own because some computers cannot get it."""
    lines = []
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        name = line.split("#")[0].strip()
        if name and not name.lower().startswith("torch"):
            lines.append(name)
    return lines


def requirements_hash() -> str:
    return hashlib.sha256((ROOT / "requirements.txt").read_bytes()).hexdigest()


def env_paths(home: Path) -> tuple[Path, Path]:
    env = home / f"py{sys.version_info[0]}{sys.version_info[1]}"
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return env, python


def env_works(python: Path) -> bool:
    try:
        return subprocess.run([str(python), "-c", "import sys"], capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def setup(home: Path) -> Path:
    env, python = env_paths(home)
    stamp = env / ".installed"
    if python.exists() and not env_works(python):
        say("The saved Python environment no longer starts (Python was probably updated). Rebuilding it.")
        shutil.rmtree(env, ignore_errors=True)
    if not python.exists():
        say("First run: creating a private Python environment (about 1 minute)")
        venv.EnvBuilder(with_pip=True).create(env)
    if stamp.exists() and stamp.read_text() == requirements_hash():
        return python
    say("Installing the tracking libraries (5 to 10 minutes the first time, about 1.5 GB; updates are much quicker)")
    pip = [str(python), "-m", "pip", "install", "--disable-pip-version-check"]
    subprocess.check_call([*pip, "--upgrade", "pip"])
    subprocess.check_call([*pip, *requirement_lines()])
    torch = [*pip, "torch"] if platform.system() == "Darwin" else [*pip, "torch", "--index-url", TORCH_CPU_INDEX]
    if subprocess.call(torch) != 0:
        say("PyTorch could not be installed on this computer. Swing, Serve and Compare work; Lesson and Match need it "
            "to follow the ball and will say so. Run this again later to retry.")
        return python                     # no stamp, so the next start tries again
    stamp.write_text(requirements_hash())
    return python


# ---------- bringing saved videos over from older copies of the app ----------

MOVED = ".moved-to-shared-folder"


def old_job_folders() -> list[Path]:
    """data/jobs folders of this copy and of other copies of the app unzipped next to it."""
    found = []
    for folder in [ROOT, *(p for p in ROOT.parent.iterdir() if p.is_dir() and p != ROOT)]:
        jobs = folder / "data" / "jobs"
        if (folder / "launch.py").exists() and jobs.is_dir() and not (jobs / MOVED).exists():
            found.append(jobs)
    return found


def bring_over_saved_videos(home: Path) -> int:
    """Copy saved videos from older copies into the shared folder. The old copies are left in place, marked as done."""
    target = home / "data" / "jobs"
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    try:
        sources = old_job_folders()
    except OSError:
        return 0
    for jobs in sources:
        if jobs.resolve() == target.resolve():
            continue
        for job in sorted(jobs.iterdir()):
            if job.is_dir() and (job / "job.json").exists() and not (target / job.name).exists():
                shutil.copytree(job, target / job.name)
                count += 1
        (jobs / MOVED).write_text(f"Saved videos from this folder were copied to {target}\n")
    return count


# ---------- starting, or finding it already running ----------

def running_app(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/info", timeout=2) as r:
            return "computer" in json.loads(r.read())
    except Exception:
        return False


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if os.name != "nt":
            # Lets a port the app just closed be reused straight away, as the server itself does. (Not on Windows,
            # where this option would let two programs share a port.)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def pick_port(last: int | None = None) -> tuple[int, bool]:
    """(port, already running). Reuses a Tracer Tennis that is already up; otherwise the port used last time, so the
    address saved on the iPhone keeps working; otherwise the first free port."""
    order = ([last] if last in PORTS else []) + [p for p in PORTS if p != last]
    for port in order:
        if running_app(port):
            return port, True
        if port_free(port):
            return port, False
    sys.exit("No free network port between 8000 and 8020. Close some programs and try again.")


def main() -> None:
    os.chdir(ROOT)
    check_computer()
    ensure_supported_python()
    home = app_home()
    home.mkdir(parents=True, exist_ok=True)
    settings_file = home / "settings.json"
    try:
        settings = json.loads(settings_file.read_text())
    except (OSError, ValueError):
        settings = {}
    port, up = pick_port(settings.get("port"))
    if up:
        say(f"Tracer Tennis is already running. Opening it: http://localhost:{port}")
        webbrowser.open(f"http://localhost:{port}")
        time.sleep(2)
        return
    if settings.get("port") and settings["port"] != port:
        say(f"Another program is using the usual address, so Tracer Tennis is on port {port} this time. "
            "If the iPhone icon does not open it, open the new address from the QR code on the home page.")
    settings_file.write_text(json.dumps(dict(settings, port=port)))
    python = setup(home)
    moved = bring_over_saved_videos(home)
    if moved:
        say(f"Brought over {moved} saved video{'s' if moved != 1 else ''} from an older copy of the app.")
    say(f"Your saved videos and settings are kept in: {home}")
    say("Starting Tracer Tennis. Leave this window open while you use the app; close it to stop.")
    if platform.system() == "Windows":
        print("   If Windows asks whether to allow Python on the network, tick Private networks and click Allow,"
              " so the iPhone can reach it.", flush=True)
    env = dict(os.environ, TRACER_TENNIS_HOME=str(home))
    sys.exit(subprocess.call([str(python), "-m", "app.server", "--open", "--port", str(port), *sys.argv[1:]], env=env))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"\nSetup failed while running: {' '.join(map(str, exc.cmd))}\nCheck the internet connection and run this again.")
        sys.exit(1)
    except KeyboardInterrupt:
        pass

#!/bin/bash
# macOS: double-click to start Tracer Tennis.
cd "$(dirname "$0")" || exit 1
finish() { echo; read -r -p "Press Return to close this window." _; exit "${1:-0}"; }

if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" != "1" ]; then
  echo "This Mac has an Intel processor. The body tracker Tracer Tennis uses is only made for"
  echo "Apple Silicon Macs (M1 and newer) and for Windows PCs, so it cannot run here."
  finish 1
fi

# Find a Python the tracking libraries support (3.13, 3.12 or 3.14). launch.py double-checks and can switch.
PY=""
for v in 3.13 3.12 3.14; do
  for c in "python$v" "/Library/Frameworks/Python.framework/Versions/$v/bin/python$v" "/opt/homebrew/bin/python$v"; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1; then PY="$c"; break 2; fi
  done
done
# The python3 that ships with macOS is only a stub that pops up an installer, so it is used only if it is real.
if [ -z "$PY" ] && command -v python3 >/dev/null 2>&1; then
  if [ "$(command -v python3)" != "/usr/bin/python3" ] || xcode-select -p >/dev/null 2>&1; then PY="python3"; fi
fi
if [ -z "$PY" ]; then
  echo "Python is not installed on this Mac. Tracer Tennis needs Python 3.13."
  echo "Opening the download page: choose the \"macOS 64-bit universal2 installer\" for Python 3.13,"
  echo "install it, then double-click Start Tracer Tennis again."
  open "https://www.python.org/downloads/macos/" 2>/dev/null
  finish 1
fi

"$PY" launch.py "$@"
finish $?

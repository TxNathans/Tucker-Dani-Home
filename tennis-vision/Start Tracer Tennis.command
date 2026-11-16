#!/bin/bash
# macOS: double-click to start Tracer Tennis.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null; then
  echo "Python 3 is not installed. Install it from https://www.python.org/downloads/ and double-click this file again."
  read -r -p "Press Return to close."
  exit 1
fi
python3 launch.py "$@"
read -r -p "Press Return to close."

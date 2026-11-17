"""Where Tracer Tennis keeps its models and saved videos.

The launcher sets TRACER_TENNIS_HOME to one folder per computer (outside the app folder), so a new copy of the app
reuses the libraries, models and saved videos of the last one. Without it, as when running from a source checkout,
everything stays inside the project folder.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def home() -> Path:
    env = os.environ.get("TRACER_TENNIS_HOME")
    return Path(env) if env else PROJECT


def model_dir() -> Path:
    return home() / "models"


def jobs_dir() -> Path:
    return home() / "data" / "jobs"

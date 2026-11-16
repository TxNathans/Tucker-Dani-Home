"""Tracer Tennis: swing mocap and match tracking from phone video."""
import shutil


def ensure_ffmpeg() -> None:
    """Make ffmpeg and ffprobe available. If they are not installed, fetch static builds once (static-ffmpeg package)."""
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
    except Exception as exc:
        raise RuntimeError(
            "ffmpeg was not found and could not be downloaded automatically. Install it "
            "(Windows: winget install Gyan.FFmpeg, Mac: brew install ffmpeg) and start again."
        ) from exc
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise RuntimeError("ffmpeg was downloaded but is still not on the path. Install it manually and start again.")

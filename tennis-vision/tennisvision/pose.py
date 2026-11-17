"""Markerless motion capture: MediaPipe Pose Landmarker (33 body landmarks, 2D + metric 3D)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

os.environ.setdefault("GLOG_minloglevel", "3")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

from .video import VideoInfo, iter_frames, probe  # noqa: E402
from .paths import model_dir

MODEL_DIR = model_dir()
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
             "pose_landmarker_{v}/float16/latest/pose_landmarker_{v}.task")

NOSE, L_EAR, R_EAR = 0, 7, 8
L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST = 11, 12, 13, 14, 15, 16
L_INDEX, R_INDEX = 19, 20
L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE = 23, 24, 25, 26, 27, 28
L_HEEL, R_HEEL, L_TOE, R_TOE = 29, 30, 31, 32

BONES = [
    (L_SHOULDER, R_SHOULDER), (L_SHOULDER, L_ELBOW), (L_ELBOW, L_WRIST), (R_SHOULDER, R_ELBOW),
    (R_ELBOW, R_WRIST), (L_SHOULDER, L_HIP), (R_SHOULDER, R_HIP), (L_HIP, R_HIP),
    (L_HIP, L_KNEE), (L_KNEE, L_ANKLE), (R_HIP, R_KNEE), (R_KNEE, R_ANKLE),
    (L_ANKLE, L_HEEL), (L_HEEL, L_TOE), (L_ANKLE, L_TOE), (R_ANKLE, R_HEEL), (R_HEEL, R_TOE),
    (R_ANKLE, R_TOE), (L_WRIST, L_INDEX), (R_WRIST, R_INDEX),
]


@dataclass
class PoseSequence:
    """Per-frame pose. xy in pixels of the analysis frame, world in metres (hip-centred, x right, y down, z away)."""
    t: np.ndarray          # (N,)
    xy: np.ndarray         # (N, 33, 2)
    vis: np.ndarray        # (N, 33)
    world: np.ndarray      # (N, 33, 3)
    detected: np.ndarray   # (N,) bool
    width: int
    height: int
    fps: float

    def save(self, path: str) -> None:
        np.savez_compressed(path, t=self.t, xy=self.xy, vis=self.vis, world=self.world,
                            detected=self.detected, meta=np.array([self.width, self.height, self.fps]))

    @classmethod
    def load(cls, path: str) -> "PoseSequence":
        d = np.load(path)
        w, h, fps = d["meta"]
        return cls(d["t"], d["xy"], d["vis"], d["world"], d["detected"], int(w), int(h), float(fps))


def model_path(variant: str = "heavy") -> str:
    path = MODEL_DIR / f"pose_landmarker_{variant}.task"
    if not path.exists():
        import urllib.request
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL.format(v=variant), path)
    return str(path)


def make_landmarker(variant: str = "heavy", video_mode: bool = True, num_poses: int = 1):
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    mode = vision.RunningMode.VIDEO if video_mode else vision.RunningMode.IMAGE
    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=model_path(variant)),
        running_mode=mode, num_poses=num_poses,
        min_pose_detection_confidence=0.4, min_pose_presence_confidence=0.4, min_tracking_confidence=0.4,
    )
    return vision.PoseLandmarker.create_from_options(options), mp


def _interpolate_gaps(seq: PoseSequence) -> None:
    ok = seq.detected
    if ok.all() or not ok.any():
        return
    idx = np.arange(len(ok))
    for arr in (seq.xy, seq.world):
        flat = arr.reshape(len(ok), -1)
        for c in range(flat.shape[1]):
            flat[~ok, c] = np.interp(idx[~ok], idx[ok], flat[ok, c])
    seq.vis[~ok] = 0.0


def extract_pose(path: str, variant: str = "heavy", max_side: int = 1920,
                 info: VideoInfo | None = None, progress=None) -> PoseSequence:
    """Run pose tracking on the most prominent person in every frame of a clip."""
    info = info or probe(path)
    landmarker, mp = make_landmarker(variant)
    n = info.n_frames
    t = np.zeros(n)
    xy = np.zeros((n, 33, 2), np.float32)
    vis = np.zeros((n, 33), np.float32)
    world = np.zeros((n, 33, 3), np.float32)
    detected = np.zeros(n, bool)
    w = h = 0
    count = 0
    last_ms = -1
    for i, ts, frame in iter_frames(path, info, max_side=max_side):
        if i >= n:
            break
        h, w = frame.shape[:2]
        ms = max(int(round(ts * 1000)), last_ms + 1)
        last_ms = ms
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(frame[:, :, ::-1]))
        result = landmarker.detect_for_video(image, ms)
        t[i] = ts
        if result.pose_landmarks:
            lms = result.pose_landmarks[0]
            xy[i] = [(p.x * w, p.y * h) for p in lms]
            vis[i] = [p.visibility for p in lms]
            world[i] = [(p.x, p.y, p.z) for p in result.pose_world_landmarks[0]]
            detected[i] = True
        count = i + 1
        if progress and i % 10 == 0:
            progress(i / max(n, 1))
    landmarker.close()
    seq = PoseSequence(t[:count], xy[:count], vis[:count], world[:count], detected[:count], w, h, info.fps)
    _interpolate_gaps(seq)
    return seq

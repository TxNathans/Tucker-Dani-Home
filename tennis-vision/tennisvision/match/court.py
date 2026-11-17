"""Court geometry and camera calibration.

Calibration starts from four tapped corners of the doubles court, then snaps to the painted lines it finds in the image.
Court coordinates: metres, origin at the centre of the net, x across, y along; the end nearest the camera is negative y.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ..stats.schema import DOUBLES_HALF_WIDTH as DW, HALF_LENGTH as L, SERVICE_LINE as S, SINGLES_HALF_WIDTH as SW

# name: (start, end) in metres
LINES = {
    "far_baseline": ((-DW, L), (DW, L)), "near_baseline": ((-DW, -L), (DW, -L)),
    "left_doubles": ((-DW, -L), (-DW, L)), "right_doubles": ((DW, -L), (DW, L)),
    "left_singles": ((-SW, -L), (-SW, L)), "right_singles": ((SW, -L), (SW, L)),
    "far_service": ((-SW, S), (SW, S)), "near_service": ((-SW, -S), (SW, -S)),
    "centre_service": ((0, -S), (0, S)),
}
CORNERS = np.array([(-DW, L), (DW, L), (DW, -L), (-DW, -L)], np.float32)   # far-left, far-right, near-right, near-left
CORNER_NAMES = ["far left", "far right", "near right", "near left"]


@dataclass
class Court:
    H: np.ndarray            # image pixels -> court metres
    size: tuple[int, int]    # image (width, height) the calibration belongs to

    @classmethod
    def from_corners(cls, corners_px, size: tuple[int, int]) -> "Court":
        """corners_px: doubles-court corners in the order far-left, far-right, near-right, near-left."""
        H, _ = cv2.findHomography(np.asarray(corners_px, np.float32), CORNERS)
        return cls(H, size)

    @classmethod
    def from_points(cls, image_pts, court_pts, size: tuple[int, int]) -> "Court":
        H, _ = cv2.findHomography(np.asarray(image_pts, np.float32), np.asarray(court_pts, np.float32), cv2.RANSAC, 3.0)
        return cls(H, size)

    def scaled(self, size: tuple[int, int]) -> "Court":
        sx, sy = self.size[0] / size[0], self.size[1] / size[1]
        return Court(self.H @ np.diag([sx, sy, 1.0]), size)

    def to_court(self, pts) -> np.ndarray:
        pts = np.asarray(pts, np.float64).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(pts, self.H).reshape(-1, 2)

    def to_image(self, pts) -> np.ndarray:
        pts = np.asarray(pts, np.float64).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(pts, np.linalg.inv(self.H)).reshape(-1, 2)

    def draw(self, img: np.ndarray, color=(0, 255, 255), thickness: int = 1) -> None:
        for a, b in LINES.values():
            p = self.to_image([a, b]).astype(int)
            cv2.line(img, tuple(p[0]), tuple(p[1]), color, thickness, cv2.LINE_AA)
        net = self.to_image([(-DW - 0.914, 0), (DW + 0.914, 0)]).astype(int)
        cv2.line(img, tuple(net[0]), tuple(net[1]), color, thickness, cv2.LINE_AA)

    def to_dict(self) -> dict:
        return dict(H=self.H.tolist(), size=list(self.size))

    @classmethod
    def from_dict(cls, d: dict) -> "Court":
        return cls(np.array(d["H"]), tuple(d["size"]))


def line_mask(frame: np.ndarray) -> np.ndarray:
    """Pixels that look like painted court lines: thin and brighter than the surface beside them."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    k = max(5, int(round(max(frame.shape[:2]) / 110)) | 1)
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    thresh = max(18.0, float(np.percentile(tophat, 96)))
    return ((tophat > thresh) & (gray > np.percentile(gray, 60))).astype(np.uint8)


def _fit_line(points: np.ndarray):
    """Robust 2D line fit. Returns (point_on_line, unit_direction) or None."""
    if len(points) < 8:
        return None
    vx, vy, x0, y0 = cv2.fitLine(points.astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01).flatten()
    return np.array([x0, y0]), np.array([vx, vy])


def _intersect(l1, l2):
    (p, d), (q, e) = l1, l2
    A = np.array([d, -e]).T
    if abs(np.linalg.det(A)) < 1e-6:
        return None
    t = np.linalg.solve(A, q - p)
    return p + t[0] * d


def refine(court: Court, frame: np.ndarray, search_px: int | None = None, rounds: int = 2) -> tuple[Court, int]:
    """Snap an approximate calibration to the painted lines. Returns (court, number_of_lines_found)."""
    h, w = frame.shape[:2]
    mask = line_mask(frame)
    search = search_px or max(6, int(0.012 * max(w, h)))
    found = 0
    for _ in range(rounds):
        fitted = {}
        for name, (a, b) in LINES.items():
            ts = np.linspace(0.04, 0.96, 60)
            model = np.outer(1 - ts, a) + np.outer(ts, b)
            img_pts = court.to_image(model)
            direction = img_pts[-1] - img_pts[0]
            normal = np.array([-direction[1], direction[0]]) / (np.linalg.norm(direction) + 1e-9)
            hits = []
            for p in img_pts:
                best, best_d = None, None
                for off in range(-search, search + 1):
                    q = p + normal * off
                    x, y = int(round(q[0])), int(round(q[1]))
                    if 0 <= x < w and 0 <= y < h and mask[y, x] and (best_d is None or abs(off) < best_d):
                        best, best_d = q, abs(off)
                if best is not None:
                    hits.append(best)
            line = _fit_line(np.array(hits)) if len(hits) >= 20 else None
            if line is not None:
                fitted[name] = line
        found = len(fitted)
        img_pts, court_pts = [], []
        names = list(fitted)
        for i, n1 in enumerate(names):
            for n2 in names[i + 1:]:
                (a1, b1), (a2, b2) = LINES[n1], LINES[n2]
                d1, d2 = np.subtract(b1, a1), np.subtract(b2, a2)
                if abs(d1[0] * d2[1] - d1[1] * d2[0]) < 1e-6:
                    continue                                    # parallel on the court
                # where the two court lines (extended) meet
                A = np.array([d1, -d2]).T
                t = np.linalg.solve(A, np.subtract(a2, a1))
                meet = np.add(a1, t[0] * d1)
                if abs(meet[0]) > DW + 0.01 or abs(meet[1]) > L + 0.01:
                    continue
                p = _intersect(fitted[n1], fitted[n2])
                if p is not None and -0.2 * w < p[0] < 1.2 * w and -0.2 * h < p[1] < 1.2 * h:
                    img_pts.append(p)
                    court_pts.append(meet)
        if len(img_pts) < 6:
            break
        H, _ = cv2.findHomography(np.array(img_pts, np.float32), np.array(court_pts, np.float32), cv2.RANSAC, 0.15)
        if H is None:
            break
        court = Court(H, court.size)
    return court, found


def is_static_camera(frames: list[np.ndarray], tolerance_px: float = 2.5) -> bool:
    """True if the background does not shift between sampled frames (phone on a tripod or fence mount)."""
    if len(frames) < 2:
        return True
    ref = cv2.cvtColor(cv2.resize(frames[0], (480, 270)), cv2.COLOR_BGR2GRAY).astype(np.float32)
    shifts = []
    for f in frames[1:]:
        cur = cv2.cvtColor(cv2.resize(f, (480, 270)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        (dx, dy), _ = cv2.phaseCorrelate(ref, cur, cv2.createHanningWindow((480, 270), cv2.CV_32F))
        shifts.append(np.hypot(dx, dy))
    return max(shifts) < tolerance_px

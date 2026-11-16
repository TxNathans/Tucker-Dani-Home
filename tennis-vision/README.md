# Tennis Vision

Film tennis on an iPhone, upload the video, get back motion capture of the swing and a breakdown of the play.

Two modes:

- **Swing analysis.** One player, one or more swings. Tracks 33 body landmarks and the racket, times the swing
  phases, finds contact from hand speed plus the sound of the hit, and measures joint angles, rotation, the
  kinetic chain, hand speed and estimated racket-head speed. Output: a skeleton-overlay video, key frames, and
  strengths / work-on points with typical ranges.
- **Match or session.** Singles or doubles. Tracks each player (told apart by clothing), the ball, the rackets and
  every hit and bounce. If the camera is fixed and you mark the four court corners, it also gives landing spots,
  in/out, shot speed, serve placement, scoring, the full stat sheet, positioning (where each player stands when
  the opponent hits) and strategy advice.

## Run it

```bash
python -m venv .venv && . .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu     # or the CUDA build on a GPU machine
pip install -r requirements.txt
python -m app.server                                                   # http://0.0.0.0:8000
```

Needs `ffmpeg` on the path. Model weights (about 80 MB) download on first use.

Open `http://<computer-ip>:8000` in Safari on the iPhone (same Wi-Fi) and use Share, Add to Home Screen. Pick a
video from the library or record one, then wait for the report. The computer does the processing; the phone only
uploads and displays.

Command line, without the web app:

```bash
python -m tennisvision.swing.pipeline clip.mov --out out/swing --height 1.70
python -m tennisvision.match.pipeline match.mp4 --out out/match --format doubles \
    --names "Dani,Pat,Opp1,Opp2" --corners 0.30,0.29,0.69,0.27,0.81,0.80,0.20,0.78
pytest tests
```

`--corners` are the doubles-court corners as fractions of the frame: far-left, far-right, near-right, near-left.

## How to film

| For | Camera | Why |
| --- | --- | --- |
| Swing analysis | Side-on or behind, whole body in frame, 60 fps or slow-motion (120/240) | Higher frame rates sharpen contact timing and the racket |
| Match stats, positioning, strategy | Tripod or fence mount, high behind the baseline, whole court visible, phone not moving | Court positions need a fixed view of all four corners |
| Quick session review | Anything, including handheld | You still get players, shots, stroke types and per-shot mocap, but no court positions |

## What is measured

**Swing:** preparation time, tempo, knee bend, stance width, shoulder and hip turn, hip-shoulder separation,
kinetic-chain order and timing, hip and shoulder rotation speed, hand speed (peak and at contact), racket-head
speed (estimate), racket drop below contact, swing path angle, elbow angle at contact, contact height, contact
point in front and to the side, trunk lean, head stability, balance over the base, leg drive, weight shift,
finish height, follow-through length.

**Match (every stat is computed per player and per team):** points won, winners, forced and unforced errors,
winner-to-error ratio; first-serve percentage, points won on first and second serve, aces, double faults,
unreturned serves, serve speed, serve placement (wide / body / T on each side) with win rate, serve plus one,
hold percentage, break points faced and saved; return in-play percentage, return points won against first and
second serves, return winners, breaks, break-point conversion; rally length and win rate by length bucket;
shots by stroke and contact type with in-percentage and speed; error type (net / long / wide); depth and
direction; net points; pressure points (deuce, game, set, break); distance run; point and rest timing;
point-by-point timeline and momentum.

**Doubles on top of that:** serving formation (standard, I-formation, Australian, both back) with win rate, poach
attempts and success, first-volley percentage, who the opponents target, team shape when points end, who finishes
points, return direction, middle balls, lobs.

**Positioning and strategy:** court zone at opponent contact (net, no-man's land, baseline, deep), distance from
the ideal recovery spot, return position against first and second serves, contact depth, net distance; in
doubles the gap between partners, shifting with the ball, the net player's starting spot and the returner's
partner's spot. `tennisvision/stats/strategy.py` turns those into advice with the evidence attached.

## How it works

| Job | Method | Licence |
| --- | --- | --- |
| Body pose (2D + 3D) | MediaPipe Pose Landmarker | Apache-2.0 |
| Players and rackets | YOLOX-s (ONNX Runtime) | Apache-2.0 |
| Ball | WASB HRNet, tennis weights (`tennisvision/match/wasb_hrnet.py` is vendored from WASB-SBDT) | MIT |
| Court | Four tapped corners, snapped to the painted lines by line detection | this repo |
| Hits and bounces | Abrupt velocity changes in the ball track, plus impact sounds | this repo |
| Player identity | Clothing colour histograms, re-matched after occlusion | this repo |

No AGPL or research-only components are used, so the stack can be shipped commercially.

## Known limits

- One camera. Speeds are measured across the camera view; motion toward or away from the lens is under-counted.
  Rotation and joint angles come from a single-camera 3D estimate, good to roughly 10 to 15 degrees.
- Racket-head speed is an estimate from the racket's bounding box and blurs at 30/60 fps. Treat it as a floor.
- Bounces close to a near-side hit are sometimes missed, which leaves that shot without a landing spot or speed.
- When two players overlap in the image, the hitter is marked "check player".
- Automatic scoring needs the serve to be seen and a clear ending. Other rallies are listed as "not scored".
- Changing ends: identity follows clothing, so partners in matching outfits can swap labels.
- Tested on one forehand clip, one 13-second handheld doubles clip, and one 7-second full-court rally. Real
  matches will surface cases these did not.
- CPU speed is about 10 frames per second for match tracking. A one-hour match wants a GPU.

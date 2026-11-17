# Tracer Tennis

Film tennis on an iPhone, upload the video, get back motion capture of the swing and a breakdown of the play.

Five modes:

- **Swing.** One player, one or more swings. Tracks 33 body landmarks and the racket, times the swing phases, and
  finds contact from hand speed plus the sound of the hit. It reads the feet (stance, where each foot points, the
  step into the ball, the back-foot release), the lead and trail leg (knee angles, brace, push, weight over the
  lead leg), the racket (angle with the racket back, at its lowest point and at contact, lag, approach angle,
  swing plane) and how well the swing works through the ball. Every graded number gets one of five grades
  (Strength, On target, Building, Priority, Not graded) against a target range. The screen shows one thing to work
  on first with what was seen, the one cue to think about, and a drill, then what is already working, then every
  number with its target.
- **Serve.** The same tracking, broken into the parts of the serve: start, toss, trophy position, racket drop,
  contact, finish. It grades the toss arm, knee bend, trunk and shoulder tilt, coil, elbow position, racket drop,
  leg drive, contact height and position, the swing up into the ball and the landing. Pick flat, slice or kick
  and it is graded against that serve, or let the app read the type from where the ball was met and how steeply
  the racket came up.
- **Compare.** Any two analysed swings (or two serves) side by side, lined up on contact, with one set of
  controls. The first is the baseline and the second the retest: it shows whether the things the baseline needed
  moved the right way, what else got better, what slipped, and what to keep working on.
- **Match or session.** Singles or doubles. Tracks each player (told apart by clothing), the ball, the rackets and
  every hit and bounce. If the camera is fixed and you mark the four court corners, it also gives landing spots,
  in/out, shot speed, serve placement, scoring, the full stat sheet, positioning (where each player stands when
  the opponent hits) and strategy advice.

- **Lesson.** The same tracking, but every shot is judged on its own landing instead of as part of a point.
  For each player it lists shots by type (forehand, backhand, volleys, overhead, serve), by where they were hit
  from (net, mid-court, baseline), by landing depth, and in / net / long / wide.

## Install it as an app

**On the computer (Windows or Mac)**

1. Install Python 3.10 or newer from python.org if it is not there already (on Windows tick "Add python.exe to PATH").
2. Download this folder and unzip it.
3. Double-click **Start Tracer Tennis.bat** (Windows) or **Start Tracer Tennis.command** (Mac).

The first start takes 5 to 10 minutes: it builds a private Python environment in `.venv` and downloads the tracking
libraries (about 1.5 GB) and, on first use, the model weights (about 80 MB). After that it starts in a few seconds
and opens the app in its own window. Leave the black terminal window open while you use it; close it to stop.
If ffmpeg is not installed it is fetched automatically.

**On the iPhone**

1. Put the phone on the same Wi-Fi as the computer.
2. Scan the QR code on the app's home page on the computer (or type the address shown there into Safari).
3. In Safari tap Share, then **Add to Home Screen**.

It now has its own icon and opens full screen. Pick a video from the library or record one, choose Swing, Serve,
Lesson or Match, and tap Analyze. The computer does the processing, so it has to be on with the app running. Reports stay
in the Recent list.

**Away from home.** The phone can only reach the computer on the same network. To use it from the court, install
Tailscale (free) on both the computer and the iPhone; the app then also lists a `100.x.x.x` address that works from
anywhere while the computer is on. The alternative is to run this on a rented cloud server.

**Who can reach it.** There is no login. Anyone on the same Wi-Fi who knows the address can upload videos and see
reports, so run it on a home network, not a public one.

**The video player.** Swing, serve and compare videos are stored clean, and the app draws everything on top, so
each overlay has its own switch: body lines, hand path, racket tracer (the whole path of the racket head), racket
plane (the surface the racket sweeps, with its tilt), feet, joint angles, contact marker, racket box and labels.
Beside the video are drawing tools: line (shows its angle from level), angle (shows degrees), circle and freehand
in yellow, white or red, with undo, clear and save picture. Playback has frame stepping, a jump to contact, time
in milliseconds from contact and speeds down to 1/10. Space plays and pauses; the arrow keys step a frame.

**Saving.** Every video and its read are kept on the computer automatically (in `data/jobs`) and listed under
Home, where they can be starred, filtered and deleted. The Save button on a read gives a PDF report (the read, the
cue, the drill, key moments, every number, your notes), the marked-up video, a picture of the current frame, and
the numbers as a spreadsheet file. A video can be renamed and given notes there. Drawings made on a video are
saved with it. On an iPhone the picture goes to the share sheet, so it can be saved to Photos or sent.

**Cues.** Each thing to work on has one short cue for the court, two other ways to say it, a self-check ("You got
it when..."), and a drill. "Show me" plays that moment in slow motion and rings the body part on the video with
its number. The question mark in the top bar opens a short guide to the whole app.

**How sure each number is.** One phone camera sees some things directly and has to estimate others. Every number
is marked as seen directly, an estimate (worked out in 3D, read from the racket's outline, or timed between
frames), or not seen clearly (a hidden foot, a blurred racket). Estimates are graded but can never be the reason
something is marked Priority, and numbers that were not seen clearly are left ungraded with the reason shown. A
Video check card says what the clip allowed and what to change next time (frame rate, body and feet in view,
racket, contact sound, camera angle).

**Look.** Light frosted glass by default, with a dark version on the moon button in the top bar. The type is
DM Sans (SIL Open Font License, bundled in `app/static/fonts`).

**Icon.** The icon, logo mark and wordmark in `app/static` are cut from the Tracer Tennis brand sheet. To change
the icon, run `python -m app.icons path/to/app-icon.png` with a square image; it writes the three sizes the home
screen uses.

Developer start, without the launcher: `pip install -r requirements.txt` then `python -m app.server`.

Command line, without the web app:

```bash
python -m tennisvision.swing.pipeline clip.mov --out out/swing --height 1.70
python -m tennisvision.swing.pipeline serve.mov --out out/serve --height 1.80 --serve --serve-type kick
python -m tennisvision.match.pipeline match.mp4 --out out/match --format doubles \
    --names "Dani,Pat,Opp1,Opp2" --corners 0.30,0.29,0.69,0.27,0.81,0.80,0.20,0.78
python -m tennisvision.match.pipeline lesson.mp4 --out out/lesson --lesson --names "Student,Coach" --corners ...
pytest tests
```

`--corners` are the doubles-court corners as fractions of the frame: far-left, far-right, near-right, near-left.

## How to film

| For | Camera | Why |
| --- | --- | --- |
| Swing analysis | Side-on or behind, whole body in frame, 60 fps or slow-motion (120/240) | Higher frame rates sharpen contact timing and the racket |
| Serve analysis | Side-on or from behind, whole body and the full reach of the racket in frame, one serve per clip | Side-on shows how far into the court the ball is met; from behind shows how far out to the side |
| Match stats, positioning, strategy | Tripod or fence mount, high behind the baseline, whole court visible, phone not moving | Court positions need a fixed view of all four corners |
| Quick session review | Anything, including handheld | You still get players, shots, stroke types and per-shot mocap, but no court positions |

## What is measured

**Swing:** preparation time, tempo, knee bend, stance width, shoulder and hip turn, hip-shoulder separation,
kinetic-chain order and timing, hip and shoulder rotation speed, hand speed (peak and at contact), racket-head
speed (estimate), racket drop below contact, swing path angle, elbow angle at contact, contact height, contact
point in front and to the side, trunk lean, head stability, balance over the base, leg drive, weight shift,
finish height, follow-through length; lead and trail knee angle with the racket back and at contact, lead-leg
brace, trail-leg push, share of weight over the lead leg; racket angle with the racket back, at its lowest point
and at contact, racket lag, approach angle into the ball, swing plane. Racket face tilt cannot be measured from
one phone camera and is listed as such.

**Serve:** stance (platform or pinpoint) and width, tossing arm straightness, how high it reaches and how long it
stays up, rhythm, lead and trail knee bend, trunk tilt, shoulder tilt and coil at trophy, hitting elbow angle and
height, racket drop depth and elbow bend, leg drive, hip rise, whether the feet leave the ground, contact height
against body height, arm straightness and shoulder-over-shoulder at contact, contact position into the court or
out to the side (depending on camera angle), swing-up angle, hand and racket-head speed, serve type, travel into
the court, follow-through.

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
- Serve type is an estimate from contact position and swing-up angle. One camera cannot see spin, so pick the
  type yourself when you know what you were hitting.
- Racket angles, the tracer and the plane come from the racket's bounding box. They are good for comparing your
  own swings from the same camera spot, not as absolute numbers.
- Repeatability was checked by running one swing at five video qualities (4K 60 fps, 1080p, a brighter cropped
  copy, 30 fps, and 720p at 30 fps). Grades held across resolution and lighting. At 30 fps the racket numbers near
  contact moved the most, which is why they are left ungraded at that frame rate. This shows the numbers are
  steady, not that they match a lab system: there has been no comparison against marker-based motion capture.
- Tested on one forehand clip, one public serve clip, one 13-second handheld doubles clip, and one 7-second
  full-court rally. Real matches will surface cases these did not.
- CPU speed is about 10 frames per second for match tracking. A one-hour match wants a GPU.

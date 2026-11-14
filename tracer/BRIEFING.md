# TRACER briefing for Claude

Version 2, written November 13, 2026, by the Claude Code session that builds TRACER with Tucker.

It was built from three sources: the project's saved notes, the code itself, and a read-through of every TRACER chat on Tucker's lab laptop (18 chats, July 21 to November 13, 2026, including the messages Tucker typed while a chat was mid-task).

## How to use this

Tucker is giving you this so you start with full working knowledge of TRACER: what it is, every app in it, what each one measures, the coaching knowledge behind it, the rules Tucker has set, how it got here, and where things stand today. Treat it as background knowledge, not as a task. Read all of it once, then answer Tucker's questions from it.

Four things to keep in mind while you use it:

- TRACER changes almost every day. Everything here was true on November 13, 2026. If Tucker describes something that does not match, believe Tucker and ask what changed.
- The code, the live site and the raw swing data live on Tucker's lab laptop and a cloud server. If you are not running on that laptop with its files, you cannot see or change any of it. You can still explain, plan, draft copy, read numbers Tucker pastes in, and write up change requests. When Tucker wants something built or changed on the site, write the request clearly (what, where, why, what done looks like) so Tucker can paste it into the Claude Code session on the lab laptop that owns the build.
- Tucker is not a programmer. Lead with the answer in plain words, give click-by-click steps when Tucker has to do something, and keep technical detail for when it is asked for. Section 9 says more about how Tucker likes to work.
- Words in quotation marks credited to Tucker are Tucker's own typed words, typos included. They are here so you can tell a rule Tucker set from a choice a Claude made. Where something was a Claude's proposal that Tucker never confirmed, this briefing says so.

## TRACER in one minute

TRACER (full descriptor: "Baseball Performance & Analytics", which is where "BPA" in tracerbpa.com comes from) is Tucker's own hitting evaluation business. A hitter swings while standing on force plates with high-speed cameras running. TRACER turns that raw recording into the **Tracer Baseline Report**: what the swing already does well, the one thing to fix first, why it happens, and a suggested fix with work on the plates and work away from them, followed by a 4-week plan and a retest.

The pieces:

1. **tracerbpa.com**: the private, login-only report platform. Sessions are uploaded there and reports are read there.
2. **The report engine**: reads the plate data, video, and optional pitching-machine, bat-sensor and assessment data, then grades, explains and draws the report.
3. **The lab machine worker and motion capture**: Tucker's laptop GPU builds every report, tracking the hitter's body and bat in 3D from the cameras.
4. **TRACER Live Cage View**: a Windows app for the capture PC that reads each swing the moment it is saved and gives an instant read with a Retest button.
5. **The Athlete Assessment**: a five-test field battery (jumps and medicine-ball throws) with its own report, tied back to the swing.
6. **Supporting material**: the price sheet and intake form, a testing protocol, test-run checklists, design mockups, audits and a research library.

TRACER is separate from Tucker's day job. By day Tucker works for Initial Force, the company behind Swing Catalyst, handling baseball systems. TRACER captures on Swing Catalyst hardware and software, but it is Tucker's own venture. Tucker's words when the server was rented: "this is not with initialforce or swing catalyst." Never mix the two: TRACER material is not Initial Force material, Initial Force business does not belong in TRACER work, and TRACER files, videos and accounts stay out of Initial Force systems.

## 1. The business

### What is sold and to whom

- **Today's price sheet** (October 14, 2026) sells evaluations to hitters: Single Evaluation $495. Evaluation + Retest $795 (retest at 4 to 6 weeks, to be used within 6 months). Season Package $1,500 (one evaluation and three retests, marked "Best value"). Team and college pricing on request.
- **Where it started.** TRACER began as consulting for facilities. Tucker, July 23, 2026: "its a consulting fee where a facility would send me the data and i would generate the reports and plans". September 24: "In order to sell this. Im going to need to create a login and password for this so each person can access it", plus a master login for Tucker "if i visit a facility" that "never expires". That is why the site has customer logins. Ideas floated for the facility model (a facility's own branding on reports, batch runs for whole teams, a monthly retainer) were never built.
- **Two ways Tucker uses it** (November 1): one build "to generate lessons reports and plans in person" and one "that generates full analysis and reports". For a team, hitters take "5-8 swings each". For a lesson, "2-3 swings".
- **Booking** is by phone (845-987-4050) and email (tracerbpa@gmail.com). Tucker: "TracerBPA is not a booking site". It is the report platform and login only. Do not put it on booking or marketing material and do not suggest a public landing page for it.
- **Turnaround**: 72 hours is Tucker's internal target. Tucker: "dont put in the report that it will arrive within 72 hours". Hitter-facing words say the report is emailed when it is ready. (The October price sheet still shows a 72-hour step. The rule came later, so ask Tucker before reusing that line.)
- **What a client gets**: an interactive online report plus a PDF, "yours to keep". The price sheet's hero line is "See exactly how your swing uses the ground", with the eyebrow "Force · Pressure · Video".
- **Turned down by Tucker**, so do not bring these back: a liability waiver on the intake form ("dont need a waiver"), and the line "read and delivered by a former professional player".

### The name and the brand

- **Tucker chose the name** on September 1, 2026: "I like Tracer Baseball Performance and Analytics", and when a Claude argued against it, "it logos well and works in my industry." The same day: "I want my branding and the report background to be Called Tracer Baseline Report and rename the App Tracer Report."
- **Names that were considered and not taken**: Pulse, anything with "IQ", Gauge, Baseplate, Proof, coined words. Do not re-pitch them. Tucker's taste for names: "simple but trendy and edgy and direct", "clear and not corny".
- **Two cautions.** Only a web-search screen was done on the name. A company called TRACER Fitness was flagged as the closest conflict and an attorney check was recommended. No record shows it was done. Also, an early claim that "tracer" is slang for a line drive was withdrawn, so do not build copy on it.
- **A tagline was proposed, never confirmed**: "Every swing leaves a trace." Ask before using it.
- **Structure.** Tucker described the consulting company as a branch of an LLC Tucker already owns. Running TRACER as a trade name under that LLC was the advice given. No record shows a filing.
- **The logo is supplied artwork.** The wordmark is white or silver TRACER with a blue ground-force curve rising through the A. Tucker: "i want it to be an exact copy of the second image i attached." Never redraw or restyle it. The icon is a geometric T with the force curve and force bars in a shield.

### The site as a business tool

- **Logins.** Tucker has the master login, which never expires. Customer logins are made on a "Manage logins" page (master only): add a username, a strong password is generated and shown once, and Remove locks that customer out at once. Customers are asked to sign in again every 30 days. A demo login was made in September for showing the product.
- **Important limit: everyone with a login sees the same roster and the same reports.** Separating facilities was planned in September as a separate copy of the site per paying facility. It was never built. Do not hand a login to a second customer expecting privacy between customers.
- **Hosting is Tucker's own.** A small cloud server was rented on September 24, 2026 (Hetzner, in Virginia: 2 processors, 2 GB memory, about 40 GB disk, no graphics card, about $21 a month at the time). The domain tracerbpa.com was bought the same day at Porkbun (about $11 a year, renews September 2027). The accounts are under the TRACER Gmail.
- **Privacy.** Customer videos include minors. Treat every session as private. Backups go to the TRACER Google account, never a work account. Tucker, asked where the backup should live: "for this use tracerbpa@gmail.com".

## 2. How a session is captured

### The recording

The capture software (Swing Catalyst) records each swing as a **take**: a folder holding the plate data as text tables and up to four camera clips. A session is a parent folder of takes, uploaded to the site as one folder or one zip.

Each take contains: `metadata.tsv` (player, plates, cameras), `bookmarks.tsv` (Load, Swing initiation, Contact marks), `data-force-combined.tsv` and one `data-force-<plate>.tsv` per plate (forces Fx, Fy, Fz, moments and centre of pressure at 1,000 samples a second), `cop-distribution.tsv`, `cop-velocity.tsv`, `data-pressure.tsv` (pressure frames), `vertical-force-by-pressure.tsv`, and the `.mp4` clips. Each take holds 3 seconds before the operator's mark and 2 seconds after.

### Two plate systems

| | Force+Motion Plate | Balance Plate XL |
|---|---|---|
| What it is | Two force plates with a pressure pad under the back foot | One pressure plate, 60.3 x 25 in, both feet on it |
| Measures | Force in three directions under each foot, torque under each foot, centre of pressure, back-foot pressure | Pressure, centre of pressure, weight split, vertical force estimated from pressure |
| Cannot measure | (nothing in the report is missing) | Torque, horizontal force, anything that needs sideways force |
| Naming | "Force+Motion Plate". Never "dual force plates" | Always a "plate". Never a "mat". Tucker: "its not a mat its a plate" |

Directions on the plates: X runs catcher to pitcher, Y runs toward first base (the toe-heel direction for a hitter), Z is up. In the viewer the forces use the capture software's own colours, at Tucker's request: vertical blue, horizontal purple, toe-heel green, torque yellow. Solid lines are the front foot and dashed lines the back foot.

### Cameras and rigs

- High-speed cameras with no sound. Earlier rigs record about 194 frames a second at 720 x 540. The main rig records about 298.
- **The primary rig is Vaughn Sports Academy (VSA).** Four fixed cameras: Face on left, Face on right, Down the line, Top Down. It was calibrated on November 12, 2026 from Tucker's own 12-swing test session, called "Tucker Test". Tucker: "the mocap and tracking stuff should be built mostly around the new raw data uploaded today for tucker. because those cameras are going to be used the most".
- At Vaughn the cameras never move. Tucker: "righty batters will hit in there and the plates will move from one batters box to the other but the cameras will stay fixed." The software finds the deck in the overhead picture on every take and re-places the cameras to match. This has been rehearsed with mirrored and re-written test data but not yet on a real right-handed hitter. One real right-handed take is still wanted.
- Older rigs exist: the one Joe DeLuca's September 2025 session came from (labelled WVU in the calibration files), an earlier three-camera setup used for Lee Vaughn, and a Balance Plate facility. They are checked only for "did not break".
- Tucker: "cameras are mostly fixed but they can move." A new facility or a moved camera needs a new dated calibration. The site has a `/calibrate` page for this.

### Other systems that can join a session

- **Trajekt Arc pitching machine**: its file gives the pitch each swing was hit off (type, speed, location) and what the ball did (exit speed, launch angle). Paired to swings by clock time. First paired session was Tucker Test (6 of 12 swings had a pitch).
- **Blast Motion bat sensor**: its file gives bat speed, attack angle, vertical bat angle, time to contact and more. The reader exists but has only been tried on a made-up file. No real export from Tucker has been checked yet, and the report prints a note saying so.
- **The Athlete Assessment** (section 3.6).
- **MLB Statcast benchmarks** for bat-tracking comparisons.

Each system can be switched off for a day when it is down (Tucker: "there may be days we do an eval and blast doesnt work or trajekt doesnt work so we need to have options to turn that off. or options to turn the plate data off too"). A system that is off has its report section left out, not shown empty.

Tucker's picture of a full session (November 11): "Show up. start with a player intake form. put them through a light warmup ... the assestment test. then let them swing to warmup. hit a few off the traject machine ... use swing catalyst plates to record their swings while traject records the pitchers and exit numbers and blast is measuring bat and swing metrics", then tie the raw data together into one TRACER report.

### Facts about the raw data that matter everywhere

1. **Body weight comes from the plates**, never from the typed-in weight. Tucker, July 22: "i dont want to manually enter weight i want weight fromthe data". November 8: "On both systems and all reports". The engine reads the quiet stance before the swing and uses one weight per session day. So hitters should stand still for about two seconds before each swing.
2. **The operator's marks are not measurements.** The "Contact" bookmark is where the operator pressed the spacebar. It can be 150 ms from real contact. Tucker: "some of the bookmarks are wrong and can be early or late so take that into conideration". Real contact is found from the ball in the video (section 4.2). The Load mark is held to at least one second before Contact so a late mark cannot squeeze the early phases together.
3. **Each foot is read from its own plate file**, never the combined file. Tucker: "we want to use the individual force plate data because then we know which foot is applying the force completly". The larger plate (1300 x 1000 mm) is the front foot and the smaller (1000 x 520 mm) is the back foot. Never decide front and back by which plate carries more force at contact: the front-leg brace peaks before contact, and that rule flipped the feet on most of one hitter's swings.
4. **The batting side is typed in.** The export's own handedness flag has been wrong more than once. Tucker: "for handedness i want to be able to enter it manually".
5. **Switch hitters are never blended.** Tucker: "only compare him as lefty to lefty and righty to lefty not blended this is for all switch hitters" (meaning righty to righty). Trends and comparisons keep left-handed and right-handed sessions apart. Joe DeLuca batted left on March 7, 2025 and right on September 20, 2025.
6. **Pressure in baseball is under the back foot only.** Tucker: "remember that we only have pressure of the back foot in baseball", "left foot for lefty batter and right foot for righty batter". Capture-software help pages and channels that assume pressure under both feet are golf material. The software's own Left/Right and Heel/Toe channels blend in the front foot, so the engine works from the per-plate forces and the pad instead.
7. **The pressure pad covers the whole back plate**, and its placement is fitted from the data. Which end is the toes depends on the batting side (Tucker: "the toe of the back foot will always be closer to home plate"). Pads can also be wired differently from one another, so a new pad needs its own check.
8. **Pitch type is tagged by hand**, per take, never guessed: Fastball, Changeup, Slider or Curveball from a right-handed or left-handed pitcher, Tee, Front toss, Machine. Folder names such as "Fastballs" or "RH Slider" tag themselves.
9. **Videos are never deleted.** Every report page streams its video from the uploaded session. An early auto-cleanup once deleted the videos behind live pages. Tucker: "we cant lose videos". If space runs low, add storage.
10. **Small traps**: the 1,000-a-second export drops samples mid-swing, so the engine rebuilds an exact time grid. Cloud-sync duplicates ("file (1)") and a stray take sitting inside another take's folder have each produced a wrong number once. Raw `.take` packages cannot be read, so sessions must be exported as raw data with video.
11. **One page per hitter per day.** A new build for the same hitter and date replaces that day's page.

### How many swings

Guidance given to Tucker on November 10 (a Claude's advice, not yet tested in the field): record 20 to 25 swings of one pitch type to get 15 to 20 clean ones. The outlier guard needs 5 clean swings, consistency readings need 3, posture needs 2. Under 10 swings is a check-in, not a full report.

### How doubts get settled

Tucker's habit, and the right one to suggest: record the capture software's screen while scrubbing through a take, send it with that take's raw folder, and have the numbers matched frame by frame. This settled the pressure orientation and the torque definition. One screen recording is not enough to set a timing correction, though: a "28 ms offset" once turned out to be one frame of a slow recording.

## 3. The apps

### 3.1 tracerbpa.com (the report platform)

A private website. Everything is behind a login. What it does:

- **Upload in three steps.**
  - *Files*: pick the session folder (on a computer) or a zip (phones cannot pick folders). The page reads the file names and fills in what it can (plate type, number of takes, date, hitter name, camera clips, pitch categories). A "Systems in this session" block has tick boxes for plates, Trajekt, Blast and the assessment, with slots for the Trajekt and Blast files. An option builds only the swings that have a Trajekt pitch (Tucker: "we dont need to do 12 swings. we just need to do the ones that match the trajekt with the swing catalyst plate and video data").
  - *Hitter*: pick the hitter from the roster or add a new one. Batting side, **level (required: Youth, Middle School, High School, College, Pro, Adult)**, height (it sets the size of the 3D figure), and the **bat on record** (make and model, length, weight). Swing type chips as listed above, or Mixed (read from folder names).
  - *Report*: choose **Full report** or **Lesson plan (30 to 45 minutes)**. Video analysis and Statcast-style bat tracking are on by default and can be clicked off. More options: skip the videos (a plates-only build takes well under a minute), or add the starred "requested measurements".
- **Queue and progress**: an upload becomes a job. The page shows whether the lab machine is online and its progress lines, then links the finished report.
- **Your reports**: every report, newest layout first. An older "classic layout" page still exists for each and is listed dimmed.
- **Download buttons** in every report's header: Download PDF, and Download file (one self-contained page that opens in any browser with no TRACER login; its videos only play on the site). For phone readers the PDF is the better hand-off, because phone previews do not run the interactive page.
- **Roster and player pages**: each hitter's sessions, trends across sessions, the bat used each day ("bat changed" is flagged), switch hitters shown with separate left and right blocks, and the hitter's assessments. Tucker can rename a hitter, set the batting side and merge duplicates. Old names keep working as aliases.
- **Compare two swings**: upload a good swing and a bad swing, get a ranked plain-language comparison. Tucker asked for this on day two.
- **Lesson retest**: from a lesson page, upload fresh swings at the end of the lesson and see start against finish on that lesson's focus numbers.
- **Athlete Assessment pages**: entry form, list, report, printable protocol sheet, and a master-only correlations page.
- **Camera calibration** (`/calibrate`).
- **Ask** (`/chat`): a coach chat grounded in one session's numbers and the drill library. It needs an Anthropic API key on the server, and none is set, so today it answers that no key was found. Tucker has not decided whether to pay for a key. Tucker pastes any key personally. A Claude never handles it.
- **Cage View download** (`/cage-view`): master login only.
- **Manage logins and Sign out** (section 1).
- A warning card appears on the home page if the server's free disk space gets low. Test builds and test players are hidden from customers.
- Works on a phone and can be added to the home screen.

Older ways to run the engine still exist on the lab PC from before the website: a desktop app (pick a folder, click Generate) and a phone page over home WiFi. The website is the main route now.

### 3.2 The Tracer Baseline Report

This is the product. It is written for coaches and players, in plain words, and it should look premium and never repeat itself. One upload produces an interactive page, a PDF, a lesson page, and a text summary used by the chat.

**Why it is organised the way it is.** The old report was arranged by instrument (force, pressure, video). A coach had to open four tabs to understand the load and read about 8,500 words before reaching the plan. The report is now organised by the swing and by what to do about it. Do not drift back to instrument tabs.

**The seven sections** (reorganised November 12, 2026):

1. **Overview**: the short version in a few sentences, up to five headline tiles (what the ball did, how fast the bat was, the order the body fired in, what the front leg did to the ground, the athlete behind the swing; a tile only appears when its system was in the session), what to work on first, what is already working, and tiles for the five steps of the swing.
2. **Work on**: one panel per issue, then the 4-week plan. Every panel has the same order:
   - *What it is*, *What we saw* (the hitter's own numbers), *What it costs* at the plate
   - *The fix* and **THE FOCUS** (the one cue to think about)
   - **Plate work**: a drill for a day with plates, including which line on the capture screen to watch and what a good rep and a bad rep look like
   - **Off the plates**: an alternative for a day without plates, with what to feel and how to check it is working
   - A fold with extra library drills and how the number is measured next time

   Issues come in three kinds: **fix** (a plate measure that is a real limiter), **watch** (borderline, or a video finding), and **keep** (a strength, called a weapon). Each carries a proof tag: "Plates · proven on N clean swings" or "Video · suggests". Tapping any flagged item anywhere in the report opens the same sheet: what is wrong, what it is causing, the fix, the drills, how it is measured. Week 4 of the plan is a full TRACER retest on the same bat.
3. **The swing**: one swing player used throughout (described below), told in **five steps: Stance, Load, Stride, Launch, Contact**.
4. **Ball & bat**: the bat on record, the Trajekt "Pitch & ball flight" block, the Blast "Bat sensor" block, and the bat path cards.
5. **Body & ground**: the kinematic sequence, the order the forces arrive in, "How it connects" (cause and effect), pressure, posture checks, and a coach-only "Coach's lab" with the per-swing tables.
6. **Athlete**: the assessment results and what they say about the swing.
7. **Player card**: the take-home card with the main feel, the tally, and the retest note.

Plus two utility buttons: **Glossary** (about 86 terms in plain words with a search box, including "other names for the same moment" for each phase) and **Full report** (everything open on one page).

**The swing player.** Tucker asked for this piece by piece, and its rules are Tucker's (section 6):

- Three modes: the real video with the skeleton and measurements drawn on it, skeleton only, and a 3D view that can be dragged around or spun with an "Orbit 360" button.
- Layers switch on and off one at a time: each force, total force, pressure, pressure path, shoulder plane, hip line, spine, skeleton, bat tracer, swing plane, bat angles, the batter's box.
- The whole bat is drawn: knob, handle, barrel, sweet spot and end cap, with the plane it sweeps. When the cameras cannot resolve the bat on a frame it is drawn as a dashed ghost, not a guess.
- Bat angles sit on the bat itself. Near contact they turn green, amber or red with words ("too steep", "too flat", "borderline").
- **Moments.** Each graded number is stamped at the instant it is read (load peak, landing, brace, torque peak, contact). As the swing plays, a numbered badge appears at the foot and the reading shows in a strip under the picture with its target and band. **Coach mode** pauses at every moment so a coach can talk it through, then Continue.
- A star marks the swing closest to the session's typical numbers. Any swing can be picked. Two swings can be compared side by side on video or overlaid in 3D, with the comparison swing in amber.
- The 3D figure is a 34-joint rigged hitter (a smoke-gray see-through body, emerald joints, amber pelvis and barrel, no helmet or face), sized from the hitter's height.
- The back-foot pressure map sits in a small box labelled toe, heel, inside and outside, turned the same way as the plates on screen.
- Slow motion from 0.1x, frame stepping, keyboard control, full screen, and touch controls under the video on a phone.

**The 11 phases of hitting and how each is found:**

| # | Phase | Step | Found from |
|---|---|---|---|
| 1 | Stance | Stance | Pressure map, video |
| 2 | Negative Move | Load | Plates: peak back-leg load |
| 3 | Positive Move | Stride | Plates: front plate unloads |
| 4 | Toe Touch / Ready Position | Stride | Plates: front plate loads again |
| 5 | Heel Plant | Launch | Plates: front foot's pressure runs back to the heel and stops |
| 6 | First Move | Launch | Video estimate: hands start toward the pitcher |
| 7 | Connection | Launch | Video estimate: hands pass the back shoulder |
| 8 | Bat Lag | Contact | Video estimate: barrel drops level with the hands |
| 9 | Contact | Contact | Video and plates together |
| 10 | Extension | Contact | Video estimate (not graded) |
| 11 | Finish | Contact | Video estimate (not graded) |

Say "five steps grouped from the 11 phases of hitting". Do not credit the phases to any outside organisation. Typical timings on the two hitters measured so far: heel plant about 95 ms before contact, first move 125 to 155 ms before, connection about 68 ms before, bat lag about 42 ms before. On both, the hands started forward about 30 ms before the heel was firm, which is the reverse of the teaching order. The report notes it when a hitter fires a phase early and does not grade it.

**Other things the report does:**

- **The order the forces arrive in.** Each push into the ground is numbered in order with its time before contact and a plain verdict (on time, early, late). Tucker asked for this on July 22: "give a 1,2.3.4. ect order of the sequences and when they are happening".
- **The target beside every number**, with what the hitter did and what it means for this swing. Every explanation also prints in the PDF, because a PDF has no hover.
- **Stride length** in inches, how repeatable it is, and whether it changes by pitch type (Tucker's request).
- **The front-leg "two spikes" card** when most swings show a double brace (section 5.3).
- **A lunge check**: a spiky back-foot push during the stride is flagged as a lunge. Tucker: "spike is a lunge".
- **Stepping-stone targets**: the next retest aims halfway from today's value to the full target. A lesson's "benchmark for today" closes 40% of the gap.
- **Since last session**: what was prescribed last time, the number it targeted, and whether it moved, with the bat beside it.
- **Spread and outliers.** Session values are medians. A reading far from the rest is set aside and the page says so ("graded on 4 of 5 swings; 1 set aside as a bad fit"). Tucker: "we also don't want 1 ruining the entire thing". Numbers are rounded to what the spread supports. With one swing the page says "measured on 1 swing", never "proven".
- **Bat on record** (added November 13, 2026). The bat's make and model, length and weight are entered at upload, saved with the session, and printed wherever two readings sit side by side. Reason: a different bat changes bat speed and timing on its own, so a retest is only a clean read on the same bat. A new session day never inherits a bat silently (the form offers the hitter's last bat to confirm). The bat length is also the length the 3D bat is fitted at, with 34 in assumed when blank, so a wrong length biases the video bat numbers and the page says so.
- **Per-pitch-type cards.** Tucker: "the fastballs and breaking balls should not be grouped together". Tee swings are never compared with machine or live swings.
- **Requested measurements.** A starred option adds six measurements that a coach, Bryan Alveari, asked for, and the section carries the label "Bryan's requested measurements": attack angle, bat path direction, hip rotation at lead heel strike, weight disruption at front-foot contact, back-foot heel/toe pressure when the hips start, and hip-to-hand sequencing (Tucker: "by hip to hand i think he means kinamatic sequencing order"). They are starred where they already appear and also get a section of their own.
- **The drill engine.** 151 drills, each tagged by what it develops, with how to run it, the point behind it and the equipment needed. The engine picks the best match for the hitter, does not repeat last session's drills, never prescribes a test as a drill, avoids two drills of the same movement, and includes a bat-in-hand drill in every set. Tucker: "it should rotate to for the best match of that hitter. not always been the same drills", and "make sure that each drill has a meaning and a point behind it". Drills are only added from sources that can actually be watched or read. No source credit is printed.
- **The Player Card "feels".** Each cue says what to feel, not what the number was. Tucker: "its too basic. really paint a picture for the feels".
- **Lesson plan style.** From a few swings it picks the issues that matter most and builds a 30 to 45 minute lesson a coach or the player can run as written: a 5-minute warm-up that always includes pressure and stance, a block per issue (what it fixes, why this drill, how, sets and reps, what a good rep looks like, a benchmark for today, and swap-in drills if it is not clicking), "put it together" swings, and an 8-minute retest. Tucker: "the lesson plan should pull all the raw data numbers just as it does for the full report." The retest page says improved, hit today's benchmark, hit the full target, or not yet.
- **Plates off.** If the plates were down, a lighter "session" page shows only what the other systems measured, and says plainly that nothing on the ground was measured.
- **The PDF** is the page printed on a white background with everything opened: 26 to 36 pages for a full report, 6 to 8 for a lesson.

**The look.** Dark "broadcast" style, chosen by Tucker on November 1 from four directions ("i like a mix of A and C"): deep navy background, electric blue (#2288FF) only for live data and key numbers, condensed uppercase headlines (Barlow Condensed), mono labels (IBM Plex Mono), status colours green / blue / amber / red. Pressure maps run blue (light) to red (heavy). Tucker's brand board asks for premium, scientific, precise, athletic, minimal and "MLB-level", and rules out cartoon icons, baseball seams everywhere, rainbow charts and busy layouts.

### 3.3 The Balance Plate XL report

Balance Plate uploads run through the same full report engine. Tucker, November 5: "i want all the same options in the balance plate xl report available with the numbers we have ... The only thing thats different is that there is no force plate only a pressure plate." The engine builds "virtual" front and back plates from the pressure data (the idea was Tucker's: work out which foot is pressing from where on the plate the pressure sits), then leaves out everything a pressure plate cannot measure.

- Measured: pressure, centre of pressure, weight split, vertical force by pressure, back-leg load and hold, unweighting.
- Not measured, so never graded and never shown as a finding: torque (both feet), horizontal drive, X timing, space, how fast the brace hits.
- The front-leg brace is shown as an **estimate**. Checked against real force plates under the same foot, the pressure pad follows the shape well and steady loads within about 10%, but reads only about 82% of a fast peak. A conversion is applied, taken from one hitter measured on both systems. The brace carries an "Estimate" chip and is left out of the tally and the plan.
- A **Pressure trace** tab exists only on these reports: the path of the centre of pressure through four phases (setup, load, landing, turn), per-foot heel/toe and inside/outside shares, and three fault shapes (spinning, toppling, leaking). The bands are provisional and the page says so.
- The viewer draws one black plate with both feet's pressure on it. Tucker: "the Balance plate XL is 1 single plate".
- When no ball is seen on video, contact is estimated as landing plus 175 ms and labelled "plate estimate".
- The Balance Plate facility's cameras get re-fitted on every take, because between two visits the plate had moved about 17 cm. One hand-held camera there has never been calibrated, so takes filmed with it get a single-camera body and no bat angles.
- The earlier Balance Plate layout also had a hangback check (weight still on the back leg while the front leg braces), a slide-back warning and a stance-width check. Confirm they still show before describing them to a customer.
- Status: Tucker said on November 13, 2026 "lets not worry about the balance plate xl report now". A few small edits are parked until Tucker raises it.

### 3.4 TRACER Live Cage View (Windows app)

An instant read of each swing on the capture PC, the moment the capture software saves it. It is built on the same engine as the report but is its own app and never changes the engine. Tucker asked for it on November 13 and named it ("lets call it Traver Live Cage View").

- **What it shows per swing**: a dial of how many numbers are on target, one plain sentence about the swing, the one thing to work on with the cue and two ways to work on it (plate work, off the plates), all eleven plate numbers against their targets, and the swing video with camera tabs, slow motion, frame stepping, drawing tools (line, angle, circle, freehand) and save-picture.
- **Ground only.** The instant read covers what the feet did. Bat speed, bat angles, posture and firing order are not in it.
- **Retest**: lock in the swing on screen, take another, see the two side by side. One swing against one swing.
- **Stance and pressure**: the plates from above, turned the same way as the camera on screen (so a lefty and a righty are mirror images), with the back foot's pressure. Clicking it enlarges a close-up that shows which part of the foot is on the ground (ball or heel, inside or outside edge) as the video is scrubbed. Tucker: "lets really make this a stand out feature".
- **The load card shows the wobble**: a picture of the back foot's weight line through the hold with the steady band, and the four "read together" cases with this swing's case lit up.
- **Explain**: the swing in plain words, built offline from that swing's numbers (a walk-through, why this is first, what to try next, what could be behind something seen at the plate). No internet and no AI key needed. It came from Tucker's question "whats the point of ask a questions if you cant even use it". Typed AI questions are optional and need a key Tucker has not set.
- **Advice that follows the session.** Tucker: "we want to make sure we arent suggesting the same issue and fix for every swing. it has to make sense". The first time an issue is on top the app gives the cue. If it stays on top and the number has not moved, it steps up to the plate drill (2nd and 3rd time), then the off-plate work (4th and 5th), and at six in a row parks that issue for the day and moves to the next one. "Better" is only said when the number truly moved.
- **Player profiles and trends**: every swing is filed under the hitter and the day (numbers only, never video, stored per computer). A "Developing a trend" strip calls out recurring issues, numbers slipping or improving, what is dependable, and whether a cue is working. Nothing is called on fewer than three swings. A returning hitter's profile shows last session and a suggested plan for this lesson.
- **The batting side is read from the plates** (from the twist the feet put into the ground). It has been right on every confident call so far, including once when the capture software's own flag was wrong.
- **Speed**: the plates-only read takes about 1 to 2 seconds. The five numbers that depend on contact wait about 12 more seconds for a short video check, because plates-only contact proved 20 to 82 ms off at Vaughn.
- **Limits**: Force+Motion Plate recordings only. The timed numbers need calibrated cameras. Not yet tried on a real right-handed hitter at Vaughn. Not code-signed, so Windows shows "More info > Run anyway" the first time.
- **Setup on the capture PC**: in the capture software's auto-export settings, tick Auto-export raw data, point it at the folder chosen in the app's Setup, set subfolders "By recording name", and include raw data and video. A practice mode replays the Tucker Test swings.
- **Access and updates**: a single password-protected download at tracerbpa.com/cage-view (master login only). The download is a zip holding the program and an `_internal` folder, and it must be run from inside the extracted folder. The one failure so far was the program dragged out on its own. The app asks for its password once per computer and has a Sign out button. It carries a frozen copy of the engine, so engine changes reach it only after it is rebuilt and uploaded again, and each PC then needs a fresh download. A private setup-guide PDF holds the logins. That PDF must never be published as a web page, and the password is never written into files, notes or chat.
- **Before giving it to anyone else**: the grading rules and camera calibrations ship inside the download as readable files.
- **Layout Tucker chose** after several rounds ("i dont want any unused space", "Premium feel about this sharp and helpful"): left = swing-read dial, work on first, weight on each foot. Middle = headline and "already working" beside the video, all numbers under it. Right = menu, today's swings, stance and pressure, hitter card. Top = Explain and Retest.
- **Tucker turned these down for the app** ("Nothing from those 3"), so do not offer them again for the app: a "not this" line beside the advice, the bat on record, and hitter ratings after a Retest. That answer was about the app only. The report has the bat on record, and "what not to do" lines for the report's fix panels are being built (section 8).

### 3.5 The lab machine worker and motion capture

- Reports are not built on the web server, which has no graphics card. Every upload becomes a job that Tucker's laptop (an RTX 4070 GPU) picks up, builds, and sends back. The site shows "lab machine online" when the worker's heartbeat is fresh. If the worker is off, uploads wait with no error.
- Build times: several minutes per swing for a full report with the 3D body and bat, more with four cameras. A lesson-style build is quicker, and its written plan is ready well before the 3D pages finish.
- **Body tracking**: a 2D pose model on every camera, triangulation across cameras, then a whole-take fit of the body that respects bone lengths, smooth motion and the plates (a planted foot is held over where the plate says the force is). Measured against held-out cameras it lands about 11 to 14 pixels from the true picture where the older single-camera method was 25 to 34. Bone lengths hold steady to about half a centimetre. The body's movement agrees with the plates' forces (correlation 0.97 along the pitch line on the best rig).
- **Bat tracking**: the blurred bat is found as a line in each camera (the detector learns the bat's colour and ignores the net, elbows and background lines), a segmentation model outlines it, and a single 3D bat of fixed length is fitted through the whole swing. Against Tucker's hand-traced bat lines it is about 7 degrees off at the median, and 1 to 2 degrees against a held-out camera through the swing. Tucker's hand-traced lines are kept as test data only, never training data.
- **Hips and rib cage**: a full body model is run per camera to read pelvis and rib-cage turn, because joint dots alone over-read hip speed.
- **One clock**: plate time and video time are tied together exactly (the cameras' stated frame rate is slightly wrong, which once put the drawn bat 2 to 3 frames off the picture).
- **Known limits to be honest about**: the two face-on cameras at Vaughn look at each other, so how far the hips have turned is seen well by one camera only. The overhead camera cannot see hips, knees or face, and it sways on its mount (a rigid mount is the real fix). The cameras are not perfectly in step with each other (up to about half a frame). With only two cameras the finish of the swing is partly guided by assumptions, not fully measured.
- **Licences**: nothing with a copyleft or non-commercial licence should ship in a paid service. The person detector has been swapped for a commercially clean one. The foot tracker and one pose model still in use have non-commercial or unclear terms and are due to be replaced.

### 3.6 The TRACER Athlete Assessment

A short field test of the athlete behind the swing. Tucker's brief (November 8): "I want this test to be fairly straight forward. but a good benchmark a player can go through testing wise to see some good and some areas they need to get better at. and then i want to be able to tie some of these findings in with the tracer hitting report and see correlations." Live since November 8, 2026.

- **Off the plates.** Tucker: "this testing will not be on the plates." Every number is typed into a tablet form on the site.
- **The five tests** (Tucker: "Only my original five"): seated medicine-ball chest pass, seated overhead medicine-ball throw (sitting on the floor, back on the wall), vertical jump on a Vertec, single-leg vertical jump left and right, and rotational medicine-ball throw from the hitting stance on both sides.
- **How it is scored**: throws by distance (tape, feet to the first bounce). 4 lb ball for middle school, 6 lb for high school and up, and the same ball at every retest. Best of three, all three trials stored. Left/right gaps over 10% are flagged.
- **How it is run**: a fixed 10-minute warm-up, the same every time. Jumps first, then the rotational throw, then the seated throws. No step into the jump, and the same hand for reach and jump. The rotational throw is from a line with no run-up. Retest every 8 to 12 weeks at the same time of day. Do not swap the Vertec for a jump mat or a plate: the level ranges are Vertec-based and other devices read lower.
- **The form**: type the standing reach once, then the vane touched on each jump, and the height shows live. Ball weight fills in from the level. Picking a known hitter fills in what the swing sessions already know.
- **Levels**: Tucker: "I want to have it by age. middle school, high school, college, Milb, MLB. MILB and MLB can be grouped together but also have can be seperate. This should also be able to be filtered by age ranges."
- **Body weight**: the plates' reading on a plate day. On a day with no plate session it is typed in and marked "entered".
- **Honesty policy on norms**: level ranges are shown where real ones exist (the Vertec jump). Where none exist, the hitter is compared with the hitter's own retests and the TRACER group as it grows. The rotational-throw table is labelled "Coach benchmark, not a study". Never invent a target. The research supports the rotational throw measured by radar speed, not by distance, so the report must not claim that throw distance predicts bat speed until TRACER's own pairs show it.
- **Tie to the swing**: when a plate session exists within 60 days, the assessment report gets a "what this says about your swing" panel. Group comparisons only appear with ten or more paired players and always print the count.
- **Timing**: about 40 minutes solo with full rests, about 33 with a leaner rest plan. (The site's sheet still says 25, and the testing protocol says 35. Not reconciled.)
- **Decisions Tucker made**: "i dont want a sit up i want overhead throw from a seated positon". No grip test until the lab has a hand dynamometer ("i dont have a grip test yet"). On the ball: "keep 6 but it may change".
- **Wording**: no study citations or author names in the assessment report or protocol sheet (Tucker: "Yes, remove them", "Yes, clean it").
- **Record so far**: one real assessment, saved under "Tucker Test" on November 12.

### 3.7 Supporting documents and tools

These are private pages in Tucker's Claude account. Tucker can open them. You can only read them if you run in that same account with the right tools.

| What | Link |
|---|---|
| TRACER Testing Protocol (assessment + swing test, 75 minutes) | https://claude.ai/artifact/Xy79sbDbqzZMuvUyZcquzK |
| Assessment review: what to adjust | https://claude.ai/artifact/Qb5kcNjrxtFc2BSKLihaox |
| Assessment test-run checklist | https://claude.ai/artifact/21LCWZ61hkY8dXwQQvAsfP |
| Swing test-run checklist (plates, Blast, Trajekt) | https://claude.ai/artifact/NYEctaEXhFvAFhiab3iJdH |
| Price sheet and intake form | https://claude.ai/artifact/2AVDV9WZe1wTYBR91o6Wyn |
| Phone intake and session page mockup (not built) | https://claude.ai/artifact/DX2CgZkGKbSn7bpbJjM42h |
| Grading audit (how every number is measured and graded) | https://claude.ai/artifact/72e1sEmnmL44g72WdUGeGi |
| Full audit of site and reports, November 9 | https://claude.ai/artifact/Y3WoGswE1E7bjsGwCS1U8A |
| Grading proposal (not built) | https://claude.ai/artifact/NYrPyuro1FSvmi28P2goji |
| Report redesign: the four look directions | https://claude.ai/artifact/2M9nsghhf4NZ9uEUuj6446 |
| Trajekt data field guide | https://claude.ai/artifact/Nbk1WhfTX9drqgyrk9ioe9 |
| Blast Motion data field guide | https://claude.ai/artifact/Rh3iE4LQATjwNrS6J9s7Ub |

**The testing protocol in brief** (a proposal, not yet field-tested): check-in 5 minutes, assessment 35, break and hitting warm-up 8, tee baseline of 8 recorded swings, then Trajekt: 5 look pitches and 4 rounds totalling 34 pitches. About 75 minutes and 42 recorded swings per hitter. Tucker's pitch rules: "Only want Fastballs down the middle. For college and mlb we can do fastballs and breaking balls", and minor league counts as pro. Tucker's aim for machine speed: "we want them to have success and be able to hit the ball without struggle so we can actually measure their swing." Starting speeds by level have been suggested twice with different numbers, so nothing is settled there. The protocol also holds the checklist for proving the camera bat speed against Blast (section 4.4).

**The two test-run checklists** are live pages that save ticks, typed values and step times as Tucker runs a session, with a rest timer and a file-name maker.

**Designed but not built**: the phone intake form and per-hitter session page. Tucker's intake fields: name, birth date, level, bats, throws ("i also want to know which hand they throw with"), dominant leg, main position ("should put position"), height, bat length and weight, bat brand and model as optional, metal or wood, goal, pain or injury, emails, a parent for under 18, consent. Also not built: a new five-pillar grading design (proposal only), and a list of eleven report ideas from comparing TRACER with another lab's decks.

**Education booklets.** Tucker wrote teaching manuals for Swing Catalyst baseball (a ground-force manual, "The Hitter's Engine", two assessment guides, the "Reading the Ground" booklet). They are Swing Catalyst material, not TRACER products, but they are the teaching background for the report and are kept in step with its grading. When the grading changes, they may need matching edits.

## 4. What TRACER measures and how it is graded

### 4.1 The plate scorecard (grading version 3, November 11, 2026)

Eleven numbers in swing order. Nine are graded. Two are shown and explained but never counted. The page shows a **tally** ("N of 9 plate measures on target"), not a score out of 10. All forces are a percentage of body weight (BW). Only clean swings count (a take where the back foot barely loads is treated as a check swing and left out) and session values are medians.

| Step | What the report calls it | What it is | On target |
|---|---|---|---|
| Load | Loads the back leg and holds it | Weight held on the back leg through the first third of the forward move | 98% BW or more, on a flat line (moving no more than 8% BW) |
| Load | Holds the load into the move | Whether that load stays until the front foot is down | 85 or more (in-house working line) |
| Load | Back-leg torque winds the hips | The back foot twisting into the ground, per kg of body mass | 0.34 N·m per kg or more (provisional) |
| Stride | Gets light in the stride | How light the hitter gets before toe touch | Shown, not graded |
| Stride | Back leg stays in it | Whether the back leg is still pushing when the front leg catches the move | 80% or more. 50 or below is deficient |
| Launch | Front-leg brace | How hard the front leg pushes into the ground | By level: Pro 160, College 150, High School 135, Middle School 125, Youth 115% BW. 200 is the elite line, not a pass mark |
| Launch | The brace arrives on time | When that push peaks | 40 to 140 ms before contact |
| Launch | How fast the brace hits | How quickly the push builds, in body weights per second | Shown, not graded |
| Launch | Front leg stops the forward move | The front leg's horizontal brake | 70% BW or more |
| Contact | Front-leg torque turns the hips | The front foot screwing into the ground, per kg | 0.24 N·m per kg or more (provisional) |
| Contact | Room for the inside pitch | The front foot's toe-heel push over the back foot's | 1.5 to 1 or more, with the two peaks within 30 ms |

Four more readings are shown and never counted: the front leg against the back-leg load (transfer), the vertical and horizontal brake arriving together, which way the brace points, and both feet turning the body (net torque).

How the grading thinks:

- **Bands**: Above target, Proficient, Developing, Deficient. "Tracked" means shown only.
- **Fix the earliest weak step first.** This was Tucker's own idea on day one: "things should be addressed at the begging of the swing first since if thats fixed it can affect the issues and fix the issues later on". The plan starts at the earliest broken step and takes the biggest gap first inside it.
- **Fix or watch.** Tucker: "its important to identify limiters in a swing to be aware of but you should also see if thats something that needs to be addressed or to just be aware of." Real limiters outrank watch items.
- **Three ways to make speed**: vertical, horizontal, and torque. Each is read from its front-side number. Most hitters own two of the three. Build on the strengths, and treat a miss on a force the hitter does not lead with as a watch item, not an emergency.
- **Timing over size.** Within one hitter, when the front-leg peak arrives tracks how hard the ball is hit. How big it is does not. That is why timing has its own line.
- **Why per kilogram and by level**: so a 150 lb high-schooler and a 220 lb pro sit on one fair scale. Tucker's view (November 9) is that percent-of-body-weight numbers let youth hitters aim at the same pattern as pros. That holds for the pattern measures (load, hold, timing, shares). For the brace, Tucker then asked for levels ("research on this and also for different ages and levels. make this make sense").
- **Provisional lines are labelled.** There are no published torque standards for hitting. Those lines come from a pro reference session on these plates and will be replaced by TRACER's own tables as hitters accumulate (about 30 hitters per level for usable bands, 50 to 60 for percentiles). Tucker: "the more we learn the better we can adjust and make things more accurate".
- **One swing is still read.** Tucker: "when its only 1 swing measure it on only 1 swing and flag it as an issue and explain why, what causes it and how to fix it."
- **No movement screens yet.** Tucker: "I do not have movement screens yet so we have to find ways to address certain issues with drills or suggestions." So where a coach might reach for a screen, the report gives a drill or an on-plate test.
- Grade on the number as displayed (rounded), never the hidden raw one, so the page never shows "80%" graded as a miss.

**What "torque" means here.** It is each foot's free moment: the twist that foot puts into the ground about its own centre of pressure. The capture software calls this "Torque (Person)" for a single foot. Its default "Torque (Plate)" graph is a different number that changes with where the hitter stands. Tucker settled which one to use on September 10, 2026, after the report's torque flipped between the two three times in a week, and the choice is pinned in the code with a note not to change it without Tucker's say-so. Torque is printed per kg of body mass, which the capture software's newer screens call "Force Factor". A coach can switch the live graph to Torque (Person) to match the report. The older manuals' torque targets (45 and 85 to 100 N·m) are in the plate-graph currency and do not compare with the report's per-kg lines.

**How the lines have changed**, so older pages and older habits make sense:

| | Earlier | Now |
|---|---|---|
| Overall | Score out of 10 | Tally of measures on target. Tucker, November 4: "a score out of 10 doesnt really mean much" |
| Front-leg brace | 200% BW for everyone | A line per level. 200 is the elite line |
| Brace timing | Several earlier windows | 40 to 140 ms before contact |
| Getting light | Graded (30% BW or lower) | Shown and explained, not graded |
| How fast the brace hits | Graded against a fixed number | Shown in body weights per second, not graded |
| Torque | Raw N·m | Per kg |
| Room for the inside pitch | A net difference of about 15% BW | A ratio of 1.5 to 1 with the peaks together |

Pages built before November 11 may still show "N of 10".

**Reading the back-leg load.** Over 100% BW on the back leg is normal and good (the hitter is sinking into it). Roughly 85 to 95 is passive, 97 to 105 is the target zone, and a sustained 130 or more is suspicious (a stomp, or the wrong moment being read).

### 4.2 Contact time

Everything read "at contact" depends on finding real contact. Tucker: "we need to use all sources to get as accurate as possible with contact". Sources, best first: the ball seen meeting the bat on video confirmed by the impact shock in the plates, then the ball on video alone, then plates only, then the operator's mark. Every ball contact gets a second, independent read and a vote if the two disagree by more than 6 ms. On the Tucker Test swings the two reads agree within 0.8 ms.

- At Vaughn, plates-only contact is switched off because it was 20 to 82 ms early on five of five swings.
- **A swing with no measured contact** (a miss or a dry swing) is left out of everything read at contact, and the page says how many swings a number was read from ("graded on 5 of 6 swings").
- Why this matters so much: each millisecond of contact error moves the attack angle by about 2 degrees.
- A handy sanity check: on good swings the bat reaches top speed 18 to 22 ms before contact, every time.

### 4.3 Video measures and the honesty rules

Tucker's rule, which shapes the whole report: **"the visual data is a suggestion where the force plate data is proven."**

- **Posture checks** from the tracked body: side lean at load. Lean, shoulder tilt, hip tilt and forward bend at landing, and whether the bend is held. Shoulders at launch. Shoulders, lean, hips and posture kept at contact. Tucker asked that each be labelled "in range out of range and if its too much or too little and what it can cause and how to fix it". A borderline band of about 8 degrees shows amber. A reading too uncertain to grade says so and stays out of the plan. Cards show their measurement band.
- **Cause and effect ("How it connects")**. Tucker: "like we see hangback because of this from the plates and no hoizontal move and this can then cause a chain reaction". Six chains link what the plates prove to what the video suggests: Stays on the back side, Leaves the back leg early, Soft front side, Lets the back-leg load fade, Little load into the back leg, Little hip coil. A chain always starts at a plate limiter. Video only joins with the words "the video suggests" (or "may", when it rests on one swing). If the plates and the video disagree, the plates win. At most three chains show. Two readings of one problem are joined into one chain so their drills do not pull in opposite directions.
- **Bat angles**: attack angle (in range 4 to 16 degrees) and vertical bat angle (in range about -42 to -18 for a middle pitch, shifted for pitch height because low pitches are hit steeper). A bat-angle fault needs two precise swings before it can enter the plan. On a calibrated multi-camera rig, a swing with no good 3D bat says "not measured". It never falls back to a single-camera guess.
- **Bat path cards**: attack direction (pull or opposite field) and swing path tilt, drawn on the hitter's own contact frames and set against the MLB middle band. The optional Statcast-style tab adds swing length, contact point and ideal attack angle rate, each carrying a "Not yet validated" label until it has been checked.
- **Kinematic sequence**: top turning speed and timing for hips, shoulders, lead arm and bat, with the order they fire in. Tucker: "we should have a basic kinematic sequence on this. list the order it fires in". It is **listed, not graded**. Hips and shoulders are flagged as estimates and the report never calls a swing "out of order" through them. On Tucker's own page the speeds read hips 617, shoulders 900, lead arm 1,130, bat 2,417 degrees a second.
- **Estimates are labelled** wherever they appear, and anything not measured says "not measured" instead of showing a guess.

### 4.4 Bat speed is hidden on purpose

The cameras compute a bat speed on every swing but Tucker has kept it off the report until it is proven. October 25: "we shouldn't include bat speed just yet but let's keep Working on it". October 27, after one swing read 85.7 mph: "keep it hidden his swing speed is way too high on that one so something is off".

- Why it is hard: a face-on camera cannot see the barrel moving toward or away from it, so speed reads low unless other cameras fill that in, and two ways of setting the scale once disagreed by 15%.
- A built-in physics check compares each bat speed with the least the ball's exit speed would need. It can catch a reading that is too slow, never one that is too fast.
- The agreed test is a paired session with a Blast sensor: at least 15 matched swings, the session average within 3 mph of Blast, no single swing more than 6 mph off, and attack angle within 4 degrees. Two passing sessions before it shows for everyone.
- Sense check for any bat speed: MLB average is about 72 mph, a fast swing is 75 or more, the leaders are near 80, contact hitters near 62. A single swing over about 85 is a tracking error, not a hitter.

### 4.5 Pressure

- On Force+Motion rigs the pad is under the back foot. Which end is the toes depends on the batting side, and the inside edge faces the pitcher. Right-handers were drawn mirrored until this was fixed on November 13, 2026.
- Never trust a pressure picture that ignores the batting side. The capture software's own pad view can be rotated in its settings and re-centres on the active pressure, so where the blob sits on that screen is not proof of anything.
- Pressure maps show the whole foot, every panel the same size. Tucker: "it should show the whole foot". They are drawn smooth, not as blocks.
- The heel/toe and inside/outside shares use a split that gives an odd middle row or column to one half. An exact half-and-half split exists but is switched off because it would change several findings. That is Tucker's call and is still open.

## 5. The knowledge behind it

### 5.1 The framework

TRACER's grading grew out of the "Three Force Vectors" way of reading a swing (vertical, horizontal, torque) and the idea of the hitter's "engine": load the back leg and hold it, move forward under control and get light, brace hard and on time with the front leg, turn the hips with torque from both feet, and keep room for the hands. Its coaching philosophy:

- Compare the hitter with the hitter's own earlier sessions first.
- Most hitters own two of the three forces. Lean into the strengths rather than only chasing weaknesses.
- Braking (stopping the forward move) is where athleticism shows.
- Fix the earliest link in the chain first.

### 5.2 Reader-safe coaching knowledge

This block may be taught in plain words as "what testing of hitters shows". It carries no names and no figures on purpose. Keep it that way in anything a coach or hitter reads. Tucker asked for it everywhere: "we want to include this into all tracer reports. live cage view and all. for knowledge base."

- What, how, why: the game or the launch monitor shows what happened. The plates and video show how. Movement and power explain why.
- Movement (order, timing, mobility) explains more of the bat-speed gap between hitters than raw power does. Power is a real but smaller share. Never promise bat speed from strength work alone.
- Medicine-ball throws carry over to exit velocity far more than the vertical jump does. When the throws lag the jump, the trunk is not passing on what the legs make.
- Real strength adds bat speed without adding time to contact. Speed that comes with a longer time to contact is not a gain.
- At the same height, body mass and a longer torso help. Arm span does not.
- A movement screen or field test is a flag, not a forecast. It says where to look. The plates and video say what the body did.
- Flag-to-swing links, always worded "can" or "tends to": a trail hip that cannot turn tends to go with a front leg that pushes less and shoulders that turn back further to make up for it. A stiff mid-back tends to go with a slower chest and arms. Hips that cannot turn under a still chest tend to go with a head that keeps drifting toward the pitcher after landing.
- The turn has four events in order: the up-and-down drive, the turn's drive, the up-and-down brake, the turn's brake. A tee at the letters trains the turn's brake. A tee at the knees trains the up-and-down pattern. Inside pitches need the turn.
- Read the total force first, then the single forces. A ragged curve with no clean peak means the body is not sure of the move. A clean pattern is one spike per foot, both at the same instant, early.
- More vertical force is not always better. A very large vertical push can cost contact.
- When the hips are already fast and the chest follows too soon, the work is mobility and making the chest wait, not faster hips. Never prescribe work for a link that is already a strength.
- Training the weaker pattern can cost the stronger one. A veteran is often better used where the swing already works.
- The bat is part of the swing. A different model, weight or balance changes timing. Before comparing two sessions, ask whether the bat was the same.

### 5.3 Plain-words coaching reads built up in the chats

These are TRACER's own ways of explaining things. They are safe to use with coaches and hitters as written.

**Posture through the swing.**

- *Stance*: forward tilt set, hips back, chest over the plate, athletic and not upright.
- *Load to toe touch*: an "attacking posture", a slight upper-body lean toward the pitcher. The head stays inside the back foot. The tilt is held without swaying back.
- *Heel plant*: the lean reverses to a slight lean away from the pitcher, so the head stops and the body can turn.
- *Launch*: the hips open under a quiet chest. The chest stays over the plate while the hands are still back.
- *Contact*: the forward bend has turned into side bend. The back shoulder is clearly below the front one, steeper for a low pitch and flatter for a high one, by about the bend the hitter started with. The bat's plane matches the shoulder plane. The head is behind the ball and the front side is firm.
- *Finish*: posture may break only after contact.
- *Common faults*: standing up early (weak or topped contact), flat shoulders at contact (under low pitches), too much lean back at foot plant (pulls off the outside pitch), and the front shoulder dropping at contact (from pulling the head and lunging).

**Pressure under the back foot.**

- In the load: pressure into the inside edge and heel is a good coil. Pressure on the outside edge is a sway, and it kills the back foot's torque. Pressure on the toes means pushing off the back side and drifting.
- Through the stride: heel to ball is good.
- At launch: on the ball of the foot means the back foot is free to turn. Stuck on the heel means blocked hips.
- Strong hitters stack pressure at the heel and the ball with the arch light.

**The feet twist the body like a bottle cap.** Turning a cap with one finger is hard. With two fingers pushing opposite ways at the same moment it is easy. The back foot pushes one way and the front foot the other, and that pair starts the hips turning. Timing is everything: the two pushes should land at nearly the same instant. A gap between them is a power leak.

**The front-leg double spike.** Many hitters land, let the knee absorb, then brace again. It is common and normal. The second peak should be the bigger one and the dip between them shallow. Cues: "land firm, don't sit into it" and "land firm, bounce out".

**Getting light.** A short drop in weight before the front foot lands lets the body move forward and makes room for the brace. It only helps if the front leg catches it. Too floaty hurts timing on off-speed. Cue: "make the valley deeper without making it longer". It takes a fast move, so a slow drill cannot train it.

**The back leg's push.** The back leg pushes toward the pitcher, then hands off as the body turns. One odd rep is a video check. The same oddity across sessions is coachable.

**Torque.** The foot twists into the ground with the big toe down, and the ground turns the body back. If the foot rolls to its outside edge, the torque disappears. The report says "Torque can add bat speed without changing the swing path". Tucker approved that line on September 10 ("lets add this in the report and roll with it") with no name attached. It is still an idea waiting on a bat-sensor test, so do not strengthen it.

**An early brace is a fooled swing.** When the front leg peaks much earlier than usual, the hitter committed before reading the pitch. A peak at contact is too late to help.

**The pressure trace on a Balance Plate.** Setup centred through the balls of the feet. Load into the inside edge and heel of the back foot. Stride in a direct line to the ball of the front foot. Brace by snapping from the ball of the front foot into its heel. Three fault shapes: spinning (pressure stays on the back foot), toppling (pressure into the toes of both feet) and leaking (pressure to the outside edge of the front foot). More than one trace style can work, so judge a trace against the hitter's own history.

**A cue says what to feel**, not what the number was.

### 5.4 What the outside data sources mean

**Statcast bat tracking** (season averages for qualified MLB hitters, 2026): bat speed median about 72 mph with the middle 80% from about 69 to 76. Attack angle median 10 degrees, and 5 to 20 counts as ideal on a single swing. Attack direction median about 2 degrees to the pull side. Swing path tilt about 32 to 33 degrees, middle 80% about 28 to 38. Swing length about 7.3 ft. Things to know: these are averages of each hitter's fastest swings, so compare a hitter's session average with them, never one swing. Statcast's tilt is the tilt of the swing's plane, which is not the same as vertical bat angle. There are no Statcast norms for high school or college.

**Trajekt.** The machine throws but does not measure. Its numbers come from the tracker in the cage. The file has one row per pitch with the pitch and the batted ball together. It does not say whether the hitter swung, which side the hitter bats from, or the spin. "No contact" can be a take or a miss, so chase and whiff rates cannot come from Trajekt alone, but the plates can settle it because a swing shows in the force trace. Distance is carry to the first bounce. Its pitch height reads about 4 in lower than the cameras measure from the floor. What only TRACER can add: where the hitter's load, stride and landing fall relative to the pitch's release.

**Blast.** Trust its bat speed. Treat its angles as a trend. It tags each swing left or right. Bat speed is highest off a tee, so compare like with like, and a new bat needs a new baseline. Reads that go together: a fast swing with weak exit speed means not squaring the ball up, not lack of power. Good bat speed with a long time to contact means off-speed beats the hitter. Bat speed low for the hand speed means the barrel is dragging.

### 5.5 The research library (internal reference only)

These live in the report project's `config/research/` folder. They are for getting things right. **Never cite an author, year, journal, school or company to a reader.** Tucker: "Drop where it says study citations". Say "research on pro hitters" or "research on college hitters" and give the finding.

- **Ground forces in hitting.** Key findings used in grading: in pro hitters the load and first weight transfer are the same for every pitch type, and what changes is the front-foot peak, which comes 15 to 35 ms early when a changeup fools the hitter. Front-leg peak timing averages about 93 ms before contact on fastballs hit, 107 on changeups hit, 126 on changeups missed. In college hitters the front foot's peak vertical force averages about 159% BW and tracks bat speed. Rotation comes from both feet pushing in opposite directions as a couple. Tee and machine swings differ systematically. Variation early in the swing is partly useful, and variation that survives into launch is the red flag. Pros plant the front foot at about 123% BW, and the hips peak before the shoulders.
- **Centre-of-pressure trace**: the four-phase model and its fault shapes. No peer-reviewed baseball study validates the template, which is why it is labelled a coaching framework.
- **Statcast bat tracking**, **Trajekt and Blast** notes (above).
- **Athlete assessment research**: which field tests predict hitting and how strongly.
- **A movement-and-swing method distilled from the OnBaseU Level 1 Hitting manual**: the 11 positions, common swing faults with the video check for each, and movement screens. TRACER uses the method in its own words. OnBaseU is never named to readers and the manual is never copied (its first page forbids reproducing it without written consent). Its screens should not go into a paid product without that organisation's written OK or a rebuild from standard range-of-motion tests.
- **Notes from BPL (Baseball Performance Lab): its webinar, video library and private club decks.** Tucker's rule: "yes lean on it but dont publish it tho with bpl numbers". TRACER may use BPL's data to set or sanity-check its own targets, but BPL's numbers and BPL's name never appear in a report, guide, web page, sales piece or chat answer. Those figures are kept only in one internal file on the lab laptop, which is deliberately kept off the server. They are not in this briefing either. What was said publicly at the webinar may be taught without attribution, which is what section 5.2 is. One of BPL's hip-test findings rests on a test name that the manual defines differently, so it needs confirming before use.
- **The November 11 grading audit**: every graded measure on 14 takes was recomputed from the raw files with separately written code and matched.

### 5.6 Where the framework came from (internal, never in reader text)

So you recognise the names when Tucker uses them:

- The Three Force Vectors idea and its first targets trace to an education video series on ground force in the baseball swing (Tucker has 2024 screen recordings of it), and to the Swing Catalyst Hitting Performance Manual and "Hitter's Engine" documents.
- "Scott" in Tucker's messages is Dr. Scott Lynn, a biomechanist. A recorded conversation with Scott settled how the whole-body turn adds up (each foot's own twist plus the two pairs of opposite pushes) and that vertical force adds nothing to torque. "Liam" is Liam Mucklow, credited alongside Scott on the older manuals.
- Tucker's rule for all of them: "do not mention liam or scott or any other company". On the 1.5-to-1 rule for room on the inside pitch: "follow dr. lynn and explain in report why its measured this way. do not include lynns name".
- **Names that were scrubbed from the report and must stay out of reader-facing text**: Driveline, OnBaseU, TPI, K-Vest, BPL, Pro Skills Baseball, and any individual coach or researcher. You are told them here only so you can recognise and avoid them. The drill library's sources are kept in an internal file behind one switch in the code. If that switch is undone, outside names come back on 139 of the 151 drills.

### 5.7 The coach-owned settings files

The report's words and thresholds live in plain settings files so they can be tuned without touching code: the scorecard and targets, plain-words text for every issue (what, wrong, costs, fix, focus, plate work, off-plate work), the drill library, the cause-and-effect chains, posture ranges, player cues and "feels" for the player card, the glossary, the assessment tests and norms, MLB bat-tracking benchmarks, per-rig contact rules, and the brand rules.

## 6. Rules for anything a coach or hitter reads

Tucker set each of these. Follow them in any report text, drill, glossary entry, chat answer or handout you draft.

**Words**

1. **Plain words.** "Every fix and issue and identification needs to be clearly explained in lamens terms." No axis letters, no lab units a parent would not know, no anatomy terms. Keep the word "torque" (Tucker rejected "twist").
2. **Every finding comes with something to do about it.** "i dont just want to tell them whats wrong or right. i also want to make sure they know what they can do to fix these issues or improve upon things."
3. **Every fix has three parts**: work on the plates, an alternative off the plates ("not everyone will have plates outside of testing"), and the focus.
4. **Say "suggested fix", not "how to fix".** "because each player is different and different drills help different players". (The current fix panel is headed "The fix". Tucker has not been asked whether that is close enough.)
5. **Not bloated.** Each fact appears once. "I also dont want a bloated report that keeps repeating itself."
6. **Never say he, his or him (or she, her) for the hitter.** Use the first name, or "the hitter", or reword. It has to read right for any hitter, including softball and female hitters.
7. **No outside names.** No other company, coach, researcher, school or study citation (section 5.6). The exception is the systems that supplied a session's data: Statcast, the launch monitor, Trajekt and Blast may be named as data sources ("yes you canuse them").
8. **Do not name Swing Catalyst in report text.** Say "the capture software" or "the plates". (Setup instructions for an operator may name it, since the operator has to find the setting.)
9. **Balance Plate is a plate, never a mat.** Force+Motion Plate, never "dual force plates".
10. **No long dashes** in report or outreach copy, and nothing that reads machine-written. Short, direct sentences.
11. **Never tell a hitter the report comes within 72 hours.**
12. **Explain paired numbers as cases.** When two numbers overlap (for example "loads the back leg" and "holds the load"), give a short "how they read together" list (high/high, high/low, low/low, one plain sentence each on what the hitter is doing) and say which case this swing is. Tucker called this "very good explination" and found a bare definition unclear.

**Honesty**

13. **Plates prove, video suggests.** Word them differently, every time.
14. **Never invent a number or a target.** If it was not measured, say "not measured". If it is an estimate, label it. If a line is provisional, say so.
15. **No scores out of 10.** Use the tally. No score on a cover either ("as to not deter anyone from seeing a score first thing").
16. **Bat speed stays hidden** until the Blast check passes.
17. **Never publish BPL's numbers or name.**
18. **Body weight is the plates' reading.**
19. **Pitch types and batting sides are never blended.**
20. **Zero mistakes is the bar.** "i need this report to be an expert report with zero mistakes or issues."

**Look and visuals**

21. **Premium, and Tracer's own.** "This has to be premier looking and very user friendly user interface." "Keep tracer branding and color identity". The brand rules hold on every page. Never change a data value, invent a metric or alter its meaning for the sake of design.
22. **Clinical, not cartoon.** "it looks to animated. it needs to look medical and data accurate."
23. **Measurements on the real video beat drawings.** After two rounds of drawn figures Tucker said of overlays on the hitter's own frames: "this is much much better". Start there whenever a calibrated camera exists.
24. **Nothing covers the picture.** "we cant have texts blocking the visuals on top of each other." Readings go beside or under the picture, with a small badge on it.
25. **Only the skeleton goes over the live video**, never the 3D body. "i also dont want to put the 3d overlay over the live video. only the skeleton over the live video. .it doesnt match up."
26. **The figure must match the real hitter**, frame by frame. "make sure that the skeleto fully matches the video. it has to be exact." The bat stays in the hands, is the size of the real bat, and moves smoothly ("a baseball swing is not choppy").
27. **The report shows the face-on view**, "the open side to the hitter". The other cameras are there to make the numbers accurate.
28. **The plates on screen face the same way as the video.**
29. **Show good, bad and how close**, "visually easy to read and see with graphics and colors", and never by colour alone.
30. **Use the space.** No unused space, and the video is big enough to follow.

## 7. Under the hood (for a Claude with access to the lab laptop)

Skip this section if you cannot see the files.

- **Folders** (under the laptop's `Claude Code` working folder): `baseball-report-v1-upgraded` is the report engine, the website (`webapp.py`) and the worker (`worker.py`). The odd name comes from Tucker's September 1 instruction to keep the first version untouched and build the upgrade beside it. `tracer-mocap` is body and bat tracking. `tracer-live` is the Cage View app. `tracer-price-sheet`, `trajekt-research`, `blast-research` and `tracer-report-redesign` hold supporting work. None of these are git repositories, so backups are dated `_backup_*` folders and the server's rollback images. Look before overwriting.
- **Engine map** (`baseball-report-v1-upgraded/src`): `parsers/` (capture software, Trajekt, Blast), `features/force_features.py` (plate numbers), `coaching/` (scoring, chains, lesson, chat), `report/` (generator, chapters, issues, plain words, overview, contact, posture, kinematic sequence, bat tracking, camera calibration, motion viewer payload, rig, bat on record, sources, light report, special measurements), `assess/` (assessment), `model/` (data model and the player database), `virtualplates.py` and `balance.py` (Balance Plate). Templates are in `src/report/templates`. Settings are in `config/`.
- **Python**: tests and renders run with the `baseball-report/.venv` interpreter with UTF-8 mode on. The worker and tracking use `tracer-mocap/.venv` (GPU). 174 unit tests, run with unittest. Five old phase tests are known to error.
- **Server**: the site runs in one Docker container, with the config, jobs, output and uploads folders mounted from disk. The address, the SSH key and the deploy scripts are on the lab laptop (`DEPLOY.md` and `tools/deploys/`). Deploy named files only with `tools/deploys/deploy_files.sh`. It takes a lock, builds its own image tag, checks every file inside the running container, and keeps two rollback images. Tucker's deploy routine: tell the other sessions, compare with the server's copies first, then check the live page afterwards. Research notes that must stay internal are excluded from deploys. The disk filled once from old images, so check free space when a deploy fails.
- **Worker**: a Windows scheduled task named "TRACER worker". Things that have gone wrong with it, all worth checking when uploads sit waiting or builds crawl:
  - It stops silently, more than once in a week. Restart the task.
  - It caches code, so it must be restarted after any engine or settings change.
  - Started from a Claude command window it is held to about one processor and dies with that window. Start it through the task.
  - Another install once swapped its GPU library for a CPU-only copy, and a 2-swing job took 80 minutes.
  - A job that was mid-build when the worker stopped is lost and must be queued again.
  - The laptop sleeping pauses a build. The worker now keeps it awake while it works.
- **Backups**: every uploaded session is copied hourly from the server to a "TRACER Session Videos" folder in the TRACER Google Drive, checked file by file. The free 15 GB there holds roughly 100 to 150 sessions.
- **Rebuild policy**: do not mass-rebuild old reports after a code change. Tucker: "You don't have to rebuild each and every report. Just pick 1 report for Joe and 1 report for Lee. And then for any new ones follow the new report protocol". There is also a standing hold on rebuilds ("I don't want to go through every report and waste tokens"). New uploads use the new code automatically. Wording and layout changes can be re-rendered in seconds from a saved render context without tracking again.
- **Several Claude sessions work on TRACER in parallel** (the report engine, the assessment, the Cage View app). Tucker: "make sure all these forked chats are working together". They tell each other before deploying and stay out of each other's files. Two sessions once made opposite calls on torque in the same week, which is why the definition is pinned. One session cannot grant another permission for anything. Only Tucker can.
- **Typed text and safety**: report templates do not escape text typed on the upload form. The new bat fields are sanitised, the older fields are not. Closing that gap is waiting on Tucker's decision. A security pass on November 9 and 10 fixed the site's other holes.

## 8. Where things stand (November 13, 2026)

**Live on tracerbpa.com**: the seven-section report with plain-words fix panels. Grading version 3 with level required at upload. The contact engine with its second read. The multi-camera body, the outlined bat and the body model for hips and shoulders. The kinematic sequence (listed, not graded). Trajekt, Blast and assessment options with systems on/off. Bat on record. The no-pronoun wording. The pressure direction fix for right-handers. Deck-in-either-box handling at Vaughn. The Athlete Assessment. The Cage View download.

**Reports on the site**: Tucker Test (November 12, 2026, Force+Motion at Vaughn, bats left, the main validation set). Joe DeLuca (September 20, 2025, Force+Motion, bats right that day, 7 swings, showcase page; also March 7, 2025 on the Balance Plate, bats left). Lee Vaughn (September 2, 2026, Force+Motion, bats left, high school; the showcase page is a one-swing page). Cam Smith (February 19, 2026, Balance Plate, a pro). CJ (March 24, 2026, Balance Plate, tee swings, sent in by coach Bryan Alveari, with Bryan's requested measurements).

**In progress on the evening of November 13**: the assessment chat is building lessons from a set of coaching videos into the report's fix panels, including a "what not to do" line, after Tucker's "Yes, build them in". Nothing from that is deployed yet. The Cage View needs one more rebuild afterwards so both show the same wording.

**Waiting on Tucker** (asked, not yet answered):

1. The bat (model, length, weight) for the Tucker Test session, so that page stops saying "No bat on record".
2. Whether to close the typed-text safety gap in report pages.
3. One real right-handed take at Vaughn.
4. Whether to rebuild Joe's and Lee's showcase pages. Joe's still shows the old mirrored inside/outside pressure, and both are on the old grading.
5. Whether to switch on the exact half-and-half pressure split.
6. A rigid mount for the overhead camera.
7. Whether to buy an AI key for the site's Ask page and the Cage View's typed questions.
8. A real Blast export and a paired session, so bat speed can be proven and shown. Also whether Tucker owns a Blast sensor and has a Trajekt login.
9. The go-ahead to build the phone intake and session page, and whether Tucker runs sessions alone or with help.
10. Video load in the testing protocol. Tucker: "if it's 30 swings that's a lot of swing catalyst videos to analyze from a 3 or 4 camera view." The question put back (full video on about six swings per hitter, numbers only on the rest) was never answered, and that mode is not built.
11. The assessment's open points: the lean 33-minute version, the chest-pass ball weight, radar on the rotational throw, making height and weight required, what to do with a broken trial or a throw off the tape, and the stated duration.
12. Whether the fix panel's heading should read "Suggested fix" (rule 4 in section 6).
13. One drill in the library is named after a player, and the bat path card prints the names of MLB hitters as flat and steep examples. Neither has been cleared against the no-names rule.
14. Deleting the Hugging Face access token named "tracer", since a copy was once pasted into a chat.

**Offered to Tucker and never answered**, so they are not decisions either way:

- An instant report option on the website. Tucker asked on November 2 ("i want a option for a report in tracerbpa where i can get an instant report and analysis"). A plates-only build was proposed and never approved. The Cage View now gives instant reads on the capture PC.
- Faster lessons: send the lesson PDF as soon as it is ready and track the 3D body on the featured swing only.
- Video checks for hands-and-bat swing faults (casting, a flying elbow, pushing the bat).
- A guard that warns before the server's disk fills.
- A single Setup installer for the Cage View, and pressure drawn onto the video under the foot.
- Calibrating the hand-held camera at the Balance Plate facility, and naming the cameras used for Joe's March 2025 session so that page can get an overlay.
- Capturing the same swings on both plate systems back to back, to firm up the Balance Plate bands.
- A note in the report about the hands starting before the heel is firm.

**Known limits, by design or by licence**: two tracking models are due to be replaced for licence reasons. The Cage View is not code-signed and has no installer. Cohort percentiles need more hitters per level. Everyone with a login sees the same roster. The name has had no attorney check.

## 9. Working with Tucker

- **The standard is accuracy.** "lab grade accuracy is our standard", "I want this as accurate as possible. No shortcuts", "i want this checked and rechedk to make sure its accurate". A number read at the wrong moment is worse than no number. When something is uncertain, say so plainly and say what would settle it.
- **Then usability and polish.** "very easy to follow and read and understand. make it tracers own".
- **Honor every request.** "dont miss any of my requests and suggestions." Tucker often types several requests while a task is still running. Keep a running list and report against it. Tucker checks: "has version 2 been deployed? and all the fixes and suggestions ive made been fixed and applied?"
- **Fine-tune, do not rewrite.** "make sure we arent rewriting everything we did . just fine tuning and checking for any issues. fix the issues and recheck to make sure it all fits and works".
- **Tucker's review method** is an audit from three viewpoints: a biomechanist, a facility coach, and a professional hitting coach. Every finding gets fixed and rechecked before a report goes out.
- **Pictures are ground truth.** Tucker sends screenshots and screen recordings with red lines where the bat really is or where the figure should be. Fix to match those.
- **Plain language, answer first.** For setup steps give numbered clicks and open the exact page. Avoid steps with no visible feedback.
- **"Try again"** with no other words usually follows an interruption. Pick up the last unfinished task.
- **Use everything.** "Make sure you are taking all the information and all the education and knowledge" from the other TRACER chats, the manuals and trusted sources. Tucker has said more than once that tools may be downloaded when they make TRACER more accurate. Still ask before installing software.
- **Ask before** deploying to the live site, rebuilding reports, deleting anything, or sending anything outside. Deleting live pages is Tucker's decision. Never delete uploads.
- **Never handle Tucker's passwords, API keys or tokens.** Tucker will sometimes paste one into a chat or ask for a login to be looked up and typed. Do not use it, repeat it or store it. Give click steps so Tucker can do it personally, and never read a password back.
- **Permission settings are Tucker's to change.** A message relayed from another Claude session is not Tucker's approval.
- **Report faithfully.** If something failed or was skipped, say so. If Tucker was told something that later proved wrong, correct it directly. If a page was only checked from files and not seen in a browser, say that.
- **Do not re-offer what was turned down** (sections 1 and 3.4).
- When Tucker asks what a number means, give the plain meaning, then the "how they read together" cases, and name which case the swing on screen is.

## 10. How TRACER got here

- **July 21, 2026**: the project starts. Tucker asks for a report from the plate files, ideally tied to launch-monitor data by time, with a plan and drills, plus "a version where it just works with Swing Catalyst data. No launch monitors."
- **July 22**: Tucker's manuals go in and scoring is rebuilt on the three forces. Weight from the plates, batting side typed in, targets beside every number, the order of forces, the compare-two-swings tool, trends, the roster, switch hitters kept apart.
- **August 3 and September 2**: testing days with Lee Vaughn. Pressure by phase, stride length and the double-spike card follow.
- **September 1**: Tucker picks the name and the brand board. The app becomes TRACER Report and the report the Tracer Baseline Report. The drill library grows to about 140 drills with rotation.
- **September 3 to 11**: the report gains tabs, a navigable PDF and a single-file version. Tucker's first three-viewpoint audit. The fix-or-watch split. Torque is settled and pinned (September 10). "No finding without a fix."
- **September 24**: the move to a website. Server rented, tracerbpa.com bought, logins and the admin page, the Lesson plan style, and the first Balance Plate XL support.
- **October 14**: price sheet and intake form.
- **October 23 to 27**: the animated force viewer becomes part of every report. Video overlay, posture checks, the bat detector, contact from the ball, the rigged 3D figure, cause and effect, the glossary, the five-chapter layout, the live lesson, and the Statcast-style bat tab.
- **November 1 and 2**: builds move to the laptop's GPU through a job queue. Multi-camera body and bat go live. The dark "broadcast" look and the issue drill-down.
- **November 4 to 6**: clean-up pass (tally replaces the score, medians, outliers). Bryan's requested measurements and the bat path cards. Balance Plate uploads move onto the full engine. Videos are never deleted again, and the Drive backup starts.
- **November 8 to 10**: the Athlete Assessment goes live. A full audit of the site and reports with 71 fixes. The three-step upload page, the PDF printed from the new layout, roster aliases. Trajekt and Blast field guides and the testing protocol.
- **November 11**: grading version 3. The grading audit.
- **November 12**: outside names and study citations come out. Level becomes required. The Tucker Test session at Vaughn with Trajekt. The seven-section report overhaul. Options for Trajekt, Blast and the assessment.
- **November 13**: the four-camera Tucker Test page. The body model for hips and shoulders. Right-handed handling at Vaughn. No-pronoun wording. TRACER Live Cage View built and put up for download. Bat on record. This briefing.

## 11. Short glossary

- **Take**: one recorded swing (a folder). **Session**: one hitter's takes from one day.
- **BW**: body weight. Forces are shown as a percentage of it.
- **Centre of pressure (CoP)**: the point where the force under a foot, or under the whole body, is centred.
- **Torque (free moment)**: the twist a foot puts into the ground about its own centre of pressure. **Force Factor**: the capture software's name for torque per kg of body mass.
- **Unweighting**: how light the hitter gets during the stride.
- **Brace**: the front leg's push into the ground that stops the forward move.
- **X timing**: whether the back leg is still pushing when the front leg catches the move.
- **Space**: the front foot out-pushing the back foot in the toe-heel direction at the same moment, which clears the hips and makes room for the hands.
- **Hangback**: weight still on the back foot when it should be on the front.
- **Attack angle**: the direction the barrel is travelling at contact, up or down. **Vertical bat angle**: how much the barrel is below the hands at contact. **Attack direction**: toward pull side or opposite field. **Swing path tilt**: the tilt of the plane the barrel sweeps before contact.
- **Clean swing**: a full swing that counts. Partial and check swings are left out.
- **Moment**: an instant in the swing where a graded number is read and shown in the player.
- **Weapon / fix / watch**: a strength to keep, a proven limiter to fix, something borderline to keep an eye on.
- **Showcase page**: the one current report per player that is kept up to date.
- **Lab machine**: Tucker's laptop, which builds every report.

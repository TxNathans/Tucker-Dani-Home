"""Coaching tables for the serve: areas, plain-language fixes, praise and meter ranges."""
from __future__ import annotations

SERVE_CATEGORIES = [
    ("toss", "Stance and toss", ("serve_toss_arm_straight", "serve_toss_arm_up", "serve_toss_arm_hold")),
    ("trophy", "Trophy position", ("serve_knee_lead", "serve_trunk_tilt", "serve_shoulder_tilt", "serve_coil",
                                   "serve_elbow_trophy", "serve_elbow_height")),
    ("drive", "Racket drop and leg drive", ("serve_racket_drop", "serve_elbow_drop", "serve_leg_drive_lead", "serve_rise")),
    ("contact", "Contact", ("serve_contact_height", "serve_elbow_contact", "serve_shoulder_over", "serve_contact_front",
                            "serve_contact_side")),
    ("finish", "Finish and landing", ("serve_into_court", "serve_follow_through")),
]


def _in(cm: float) -> str:
    return f"{abs(cm) / 2.54:.0f} inches"


SERVE_TIPS = {
    "serve_knee_lead": (9, lambda v, s: dict(
        title="Bend your knees before you swing",
        saw=f"Your front knee only bent to {v:.0f} degrees. A loaded serve gets down to about 115.",
        why="The legs are the engine of the serve. Without a knee bend there is nothing to push up from, so the arm has to make all the speed.",
        cue="Toss, sit, then explode up.",
        drill="Serve from your knees-bent trophy pose: toss, pause for a count of one in the bent position, then go. 10 serves.")),
    "serve_leg_drive_lead": (8, lambda v, s: dict(
        title="Drive up with your legs",
        saw=f"Your front leg straightened only {v:.0f} degrees on the way up to the ball.",
        why="Pushing up hard is what drops the racket deep behind you and then throws it up at the ball.",
        cue="Jump up to the ball, don't wait for it to come down.",
        drill="Serve and land inside the baseline on your front foot every time. If you are still behind the line, the legs did not drive. 12 serves.")),
    "serve_rise": (7, lambda v, s: dict(
        title="Get your body going up",
        saw=f"Your hips rose only {_in(v)} from the bottom of the knee bend to contact.",
        why="The serve is hit up, not down. If the body stays at one height the contact point is low and the ball goes into the net.",
        cue="Hips up through the ball.",
        drill="Stand a ball can a racket-length above your reach on the fence. Shadow-serve and try to brush it with the racket tip. 15 reps.")),
    "serve_toss_arm_straight": (7, lambda v, s: dict(
        title="Lift the toss with a straight arm",
        saw=f"Your tossing arm was bent ({v:.0f} degrees) when you let go of the ball.",
        why="A bent arm flicks the ball, so the toss lands somewhere different every time. A straight arm lifts it to the same spot.",
        cue="Lift it like an elevator, let go at eye level.",
        drill="Toss without swinging and let the ball drop: it should land on a racket laid on the court in front of your front foot. 20 tosses.")),
    "serve_toss_arm_up": (6, lambda v, s: dict(
        title="Keep your tossing arm up",
        saw=f"At the trophy position your tossing arm was {v:.0f} degrees off vertical.",
        why="The tossing arm pointing up keeps the front shoulder high and the chest closed. That is your coil.",
        cue="Point at the ball until you start to swing.",
        drill="Toss, hold the trophy pose with the tossing hand pointing at the ball, and catch it with that hand without moving your feet. 10 reps.")),
    "serve_toss_arm_hold": (6, lambda v, s: dict(
        title="Don't let the tossing arm fall early",
        saw=f"Your tossing hand had already dropped {_in(v)} below your head when the racket started down.",
        why="When the tossing arm drops early the front shoulder drops with it, the chest opens, and you lose the shoulder-over-shoulder action.",
        cue="Tossing hand stays up, then tucks into your stomach as you swing.",
        drill="Serve at half speed, counting 'up, up, swing': the tossing hand stays above your head for both 'ups'. 10 serves.")),
    "serve_shoulder_tilt": (7, lambda v, s: dict(
        title="Tilt your shoulders at the trophy",
        saw=f"Your shoulders were almost level at the trophy position ({v:.0f} degrees of tilt).",
        why="Front shoulder up and back shoulder down sets up the cartwheel that brings the hitting shoulder up and over at contact.",
        cue="Front shoulder to the sky, back shoulder to the court.",
        drill="In front of a mirror or a window, toss and freeze: your shoulders should make a line that slopes down toward the back fence. 10 reps.")),
    "serve_trunk_tilt": (5, lambda v, s: dict(
        title="Lean into the bow",
        saw=f"Your upper body was {v:.0f} degrees off vertical at the trophy position; about 25 is typical.",
        why="A small lean back and to the side loads the trunk. Too little and there is no spring; too much and you lose balance.",
        cue="Hips forward over the baseline, chest up to the ball.",
        drill="Trophy-pose holds: hip pushed toward the net, weight on the balls of the feet, hold for three seconds, then serve. 8 reps.")),
    "serve_elbow_height": (7, lambda v, s: dict(
        title="Get your hitting elbow up",
        saw=f"At the trophy position your hitting elbow was {_in(v)} below your shoulder line.",
        why="A low elbow shortens the racket's path and makes the shoulder do work the legs and trunk should be doing.",
        cue="Elbow level with your shoulder, like a waiter holding a tray.",
        drill="Hold the trophy pose with your back against a fence: elbow and racket hand both touch the fence. Step away and copy it. 10 reps.")),
    "serve_elbow_trophy": (4, lambda v, s: dict(
        title="Set an L-shaped arm at the trophy",
        saw=f"Your hitting arm was at {v:.0f} degrees at the trophy position; a right angle is the reference.",
        why="An arm that is too straight or too folded has to re-set itself before it can swing, which breaks the rhythm.",
        cue="Make an L, racket tip to the sky.",
        drill="Start 10 serves from the trophy pose with the arm already in an L, to feel where it should arrive.")),
    "serve_racket_drop": (8, lambda v, s: dict(
        title="Let the racket drop behind you",
        saw=f"Your racket head only dropped {_in(v)} below your hand.",
        why="The drop is the wind-up. A deeper drop gives the racket more distance to speed up before it meets the ball.",
        cue="Scratch your back, then throw the racket up at the ball.",
        drill="Throw a ball as high as you can from the trophy pose: your elbow leads and the hand drops behind your head on its own. 10 throws, then 10 serves.")),
    "serve_elbow_drop": (6, lambda v, s: dict(
        title="Fold the elbow in the racket drop",
        saw=f"Your hitting elbow stayed fairly open ({v:.0f} degrees) at the lowest point of the swing.",
        why="An arm that stays open never lets the racket fall behind the back, so the swing is a push rather than a throw.",
        cue="Loose arm. Let the racket fall.",
        drill="Swing a sock with a ball in it through a serve motion: it only loops smoothly if the arm is relaxed and the elbow folds. 15 reps.")),
    "serve_contact_height": (9, lambda v, s: dict(
        title="Reach up to the ball",
        saw=f"Your hand was at {v:.2f} times your height at contact. Full reach is about 1.2 or more.",
        why="A higher contact point gives a better angle over the net and into the box, and it only happens with a straight arm and the legs driving up.",
        cue="Hit it at the top of your reach, on your toes.",
        drill="Hold your racket up at full stretch and note where the strings are. Toss so the ball peaks just above that spot. 10 serves.")),
    "serve_elbow_contact": (8, lambda v, s: dict(
        title="Straighten your arm at contact",
        saw=f"Your hitting arm was bent ({v:.0f} degrees) when you met the ball.",
        why="A bent arm at contact lowers the hitting point and gives away racket speed.",
        cue="Long arm, reach for the sky.",
        drill="Serve from the service line and watch your hitting hand: it should be the highest point of your body at contact. 10 serves.")),
    "serve_shoulder_over": (7, lambda v, s: dict(
        title="Bring your hitting shoulder up and over",
        saw=f"At contact your hitting shoulder was only {v:.0f} degrees above your tossing shoulder.",
        why="The shoulders should cartwheel: the back shoulder that started low finishes high. That is what lifts the contact point.",
        cue="Shoulder over shoulder.",
        drill="Throw a ball steeply upward over a high fence from the trophy pose. Your throwing shoulder has to come up and over. 10 throws.")),
    "serve_contact_front": (7, lambda v, s: dict(
        title="Put the toss where this serve needs it",
        saw=f"You met the ball {_in(v)} in front of your front foot.",
        why="Each serve has its own contact point. A flat serve is met well out in front; a kick serve is met back over the head. Too far behind for the serve you want and the ball floats; too far in front and it drops into the net.",
        cue="Toss into the court for flat, over your head for kick.",
        drill="Lay your racket on the court pointing forward from your front toe. Toss and let it drop: flat-serve tosses should land near the strings. 15 tosses.")),
    "serve_contact_side": (6, lambda v, s: dict(
        title="Move the toss left or right for this serve",
        saw=f"You met the ball {_in(v)} to the hitting side of your head.",
        why="Slice is met out to the hitting side, flat a little less so, and kick over or just behind the head. The toss decides which serve is possible.",
        cue="Slice: toss to one o'clock. Kick: toss to eleven.",
        drill="Hold your tossing arm up and note where it points for each serve type. Hit 5 of each, saying the clock position before every toss.")),
    "serve_into_court": (6, lambda v, s: dict(
        title="Land inside the court",
        saw=f"Your body moved only {_in(v)} toward the net through the serve.",
        why="A serve that drives up and forward carries you into the court. Staying behind the line means the weight never went into the ball.",
        cue="Land on your front foot, a step inside the baseline.",
        drill="Put a towel just inside the baseline. Serve and land with your front foot past it. 12 serves.")),
    "serve_follow_through": (5, lambda v, s: dict(
        title="Finish the swing",
        saw=f"Your hand dropped only {_in(v)} after contact.",
        why="Stopping the racket up high means the arm was braking before the ball left. A full finish across the body is easier on the shoulder too.",
        cue="Racket finishes by your opposite hip.",
        drill="Serve and freeze the finish for two seconds: racket by the opposite hip, back foot swung forward. 10 serves.")),
}

SERVE_PROBLEMS = {
    "serve_knee_lead": lambda v: "Your legs stay straight on the serve.",
    "serve_leg_drive_lead": lambda v: "Your legs don't drive up to the ball.",
    "serve_rise": lambda v: "Your body isn't going up to meet the ball.",
    "serve_toss_arm_straight": lambda v: "Your toss comes from a bent arm.",
    "serve_toss_arm_up": lambda v: "Your tossing arm comes down too soon.",
    "serve_toss_arm_hold": lambda v: "Your tossing arm falls before you swing.",
    "serve_shoulder_tilt": lambda v: "Your shoulders stay level at the trophy.",
    "serve_trunk_tilt": lambda v: "Your body lean at the trophy is off.",
    "serve_elbow_height": lambda v: "Your hitting elbow is low at the trophy.",
    "serve_elbow_trophy": lambda v: "Your arm isn't set at the trophy.",
    "serve_racket_drop": lambda v: "Your racket doesn't drop behind you.",
    "serve_elbow_drop": lambda v: "Your arm stays stiff through the racket drop.",
    "serve_contact_height": lambda v: "You're meeting the ball too low.",
    "serve_elbow_contact": lambda v: "Your arm is bent at contact.",
    "serve_shoulder_over": lambda v: "Your hitting shoulder doesn't come up and over.",
    "serve_contact_front": lambda v: "Your toss is in the wrong spot for this serve.",
    "serve_contact_side": lambda v: "Your toss is off to the side for this serve.",
    "serve_into_court": lambda v: "You're not moving into the court.",
    "serve_follow_through": lambda v: "Your swing stops after the ball.",
}

SERVE_PRAISE = {
    "serve_knee_lead": "Good knee bend: your legs were loaded.",
    "serve_leg_drive_lead": "Strong leg drive up to the ball.",
    "serve_rise": "Your body was travelling up into contact.",
    "serve_toss_arm_straight": "You tossed with a straight arm.",
    "serve_toss_arm_up": "Your tossing arm stayed up at the trophy.",
    "serve_toss_arm_hold": "Your tossing arm stayed up until the racket dropped.",
    "serve_shoulder_tilt": "Good shoulder tilt at the trophy position.",
    "serve_trunk_tilt": "Your body was leaned into a good bow.",
    "serve_coil": "Your shoulders were coiled past your hips.",
    "serve_elbow_height": "Your hitting elbow was up, level with the shoulder.",
    "serve_elbow_trophy": "Your arm made a clean L at the trophy position.",
    "serve_racket_drop": "Deep racket drop behind the back.",
    "serve_elbow_drop": "Your arm folded loosely through the racket drop.",
    "serve_contact_height": "You met the ball at full reach.",
    "serve_elbow_contact": "Your arm was straight at contact.",
    "serve_shoulder_over": "Your hitting shoulder came up and over.",
    "serve_contact_front": "The contact point suited this type of serve.",
    "serve_contact_side": "The toss was in the right place, side to side, for this serve.",
    "serve_into_court": "You moved forward into the court.",
    "serve_follow_through": "Full follow-through across the body.",
}

SERVE_METERS = {
    "serve_toss_arm_straight": (90, 180, 160, 180), "serve_toss_arm_up": (0, 90, 0, 25), "serve_toss_arm_hold": (-80, 60, 0, 60),
    "serve_knee_lead": (80, 180, 100, 135), "serve_knee_trail": (80, 180, 100, 140), "serve_trunk_tilt": (0, 60, 15, 35),
    "serve_shoulder_tilt": (-20, 70, 20, 45), "serve_coil": (0, 60, 15, 35), "serve_elbow_trophy": (20, 180, 70, 110),
    "serve_elbow_height": (-40, 30, -8, 30), "serve_racket_drop": (0, 90, 30, 70), "serve_elbow_drop": (20, 150, 50, 90),
    "serve_leg_drive_lead": (0, 80, 20, 60), "serve_leg_drive_trail": (0, 80, 20, 60), "serve_rise": (0, 60, 15, 40),
    "serve_feet_off": (0, 40, 5, 30), "serve_contact_height": (0.9, 1.45, 1.18, 1.4), "serve_elbow_contact": (100, 180, 155, 180),
    "serve_shoulder_over": (-20, 80, 25, 55), "serve_contact_front": (-40, 110, 30, 70), "serve_contact_side": (-50, 90, 10, 40),
    "serve_swing_up": (-20, 80, 0, 25), "serve_into_court": (-30, 150, 30, 90), "serve_follow_through": (0, 200, 90, 180),
    "serve_stance_width": (0.3, 2.5, 1.0, 1.6), "serve_racket_speed": (0, 50, 35, 45),
}

SERVE_STRENGTH_AT = {
    "serve_knee_lead": (-1, 120), "serve_leg_drive_lead": (1, 40), "serve_rise": (1, 28), "serve_contact_height": (1, 1.26),
    "serve_elbow_contact": (1, 168), "serve_shoulder_over": (1, 40), "serve_racket_drop": (1, 50), "serve_toss_arm_up": (-1, 10),
    "serve_into_court": (1, 60),
}

SERVE_BOOK = dict(categories=SERVE_CATEGORIES, tips=SERVE_TIPS, problems=SERVE_PROBLEMS, praise=SERVE_PRAISE,
                  situational=set(), meters=SERVE_METERS, strength_at=SERVE_STRENGTH_AT)

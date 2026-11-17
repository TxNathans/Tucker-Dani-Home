"""Cue book: for each thing to work on, one short cue, two other ways to say it, and a self-check.

Cues are written to be said out loud on court: a few words, one action, pointed at the ball, the racket or the
court rather than at a body part where that is possible. Players respond to different words, so each fix carries
alternatives. The self-check is how a player knows, without a coach or a camera, that the rep was right.

A value may be a function of (value, stroke) when the right words depend on the measurement or the stroke.
"""
from __future__ import annotations


def _c(cue, alts, check):
    return dict(cue=cue, alts=alts, check=check)


CUES = {
    # ---- groundstrokes and volleys ----
    "contact_in_front": _c("Meet it out front.", ["Hit the ball before it reaches your front hip.", "Reach out like a handshake."],
                           "At contact you can see the ball and the back of your hitting hand in the same glance."),
    "extension": _c("Chase the ball with the strings.", ["Swing through three balls in a row.", "Send the racket to the target, then let it wrap."],
                    "A moment after contact your hitting arm is long and pointing at the target."),
    "speed_carried": _c("Fastest after the ball.", ["Make the swoosh in front of you.", "Swing through it, not at it."],
                        "The swoosh of the racket comes after your contact point, not beside you."),
    "weight_through": _c("Walk through the shot.", ["Belt buckle to the net.", "Land on your front foot."],
                         "You finish balanced on the front foot and could take a step forward."),
    "chest_lead": _c("Chest over the ball.", ["Nose over your front knee.", "Stay down through the hit."],
                     "At contact your head is level with your belt buckle or ahead of it, not behind."),
    "shoulder_turn": _c(lambda v, s: "Chin on your front shoulder." if s == "backhand" else "Show your back to the net.",
                        ["Front shoulder points at the ball.", "Turn first, then swing."],
                        "With the racket back, your front shoulder points at the incoming ball."),
    "separation": _c("Shoulders turn, hips wait.", ["Wind up like a spring.", "Feel the stretch across your stomach."],
                     "You feel a stretch through your trunk just before you swing."),
    "knee_bend_dom": _c("Sit, then hit.", ["Get low like sitting on a bar stool.", "Load the back thigh."],
                        "Your back thigh is working: after ten balls you can feel it."),
    "leg_drive": _c("Push the court away.", ["Bend, then rise through the ball.", "Finish taller than you started."],
                    "You are taller at the finish than you were with the racket back."),
    "front_foot_angle": _c("Front toes to the net post.", ["Step toward the target, not the side fence.", "Open the door for your hips."],
                           "Look down at the finish: your front toes point between the net post and your target."),
    "back_foot_angle": _c("Back foot sideways.", ["Back foot along the baseline.", "Turn the foot with the shoulders."],
                          "With the racket back, your back foot is parallel to the baseline."),
    "back_foot_pivot": _c("Back heel up at the finish.", ["Shoelaces to the net.", "Squash a bug with your back toe."],
                          "At the finish your back heel is off the ground and that knee points forward."),
    "trunk_lean": _c("Feet first, stay tall.", ["Head on top of your hips.", "Take one more small step."],
                     "A cup of water on your head would not have spilled."),
    "head_stability": _c("Eyes on the contact spot.", ["Head still until the ball is gone.", "See it, hit it, then look."],
                         "You are still looking at the contact spot as the ball crosses the net."),
    "balance": _c("Wide base, hips in the middle.", ["Hold the finish for two seconds.", "Get your feet under you before you swing."],
                  "You can hold your finish without taking a step."),
    "swing_path": _c("Under it, then up.", ["Brush up the back of the ball.", "Low to high, like a ramp."],
                     "The racket finishes higher than the spot where you met the ball."),
    "racket_drop": _c("Drop the racket head first.", ["Pat the dog.", "Racket tip to knee height, then swing."],
                      "Just before you swing forward, the racket head is lower than your hand."),
    "contact_spacing": _c(lambda v, s: "Arm's length from the ball." if v < 35 else "Let the ball come to you.",
                          lambda v, s: ["Elbow off your ribs.", "Give the ball room."] if v < 35 else ["Take one more step.", "Hit it beside you, not out there."],
                          "At contact your arm is comfortably long: not locked, not folded."),
    "elbow_contact": _c("Elbow off your ribs.", ["Give the ball room.", "Long arm at the hit."],
                        "At contact there is a clear gap between your elbow and your side."),
    "follow_length": _c(lambda v, s: "Hands finish by your ear." if s == "backhand" else "Racket over your shoulder.",
                        ["Catch the racket with your other hand.", "Finish the whole swing."],
                        "The racket ends over your shoulder with the butt of the handle pointing at the net."),
    "finish_height": _c("Finish by your ear.", ["Kiss your bicep.", "Up and over the shoulder."],
                        "Your hitting hand ends above the opposite shoulder."),
    "prep_time": _c("Turn when it crosses the net.", ["Racket back before the bounce.", "Say it out loud: bounce, hit."],
                    "Your racket is already back when the ball bounces on your side."),
    "sequence": _c("Hips first, arm last.", ["Throw from the ground up.", "Let the arm be a whip."],
                   "You feel your hips start to turn while the racket is still back."),

    # ---- serve ----
    "serve_knee_lead": _c("Toss, sit, explode.", ["Knees over your toes.", "Coil like a spring."],
                          "Your heels are off the ground before you hit."),
    "serve_leg_drive_lead": _c("Jump up to the ball.", ["Push the court away.", "Leave the ground."],
                               "You land inside the baseline on your front foot."),
    "serve_rise": _c("Hips up through the ball.", ["Grow tall into contact.", "Launch upward, not forward."],
                     "At contact you are at full stretch, on your toes or off the ground."),
    "serve_toss_arm_straight": _c("Lift it like an elevator.", ["Straight arm, no flick.", "Place the ball, don't throw it."],
                                  "The ball leaves your hand around eye level with almost no spin on it."),
    "serve_toss_arm_up": _c("Point at the ball.", ["Reach for the sky with the tossing hand.", "Hold the pose."],
                            "Your tossing hand is still above your head when the racket drops."),
    "serve_toss_arm_hold": _c("Tossing hand stays up.", ["Hold it there one beat longer.", "Tuck the arm in only as you swing."],
                              "If you froze at the trophy, you could catch the ball with your tossing hand."),
    "serve_shoulder_tilt": _c("Front shoulder to the sky.", ["Tilt like a seesaw.", "Back shoulder down."],
                              "At the trophy your tossing shoulder is clearly higher than your hitting shoulder."),
    "serve_trunk_tilt": _c("Bow the body.", ["Hips over the baseline.", "Chest up to the ball."],
                           "From the side, your body makes a bow shape at the trophy."),
    "serve_elbow_height": _c("Elbow up, tray level.", ["Elbow level with your shoulder.", "Like a waiter holding a tray."],
                             "At the trophy your hitting elbow is as high as your shoulder."),
    "serve_elbow_trophy": _c("Make an L.", ["Racket tip to the sky.", "Right angle at the elbow."],
                             "Upper arm and forearm make a right angle at the trophy."),
    "serve_racket_drop": _c("Scratch your back.", ["Let the racket fall behind you.", "Throw the racket up at the ball."],
                            "For an instant the racket tip points at the ground behind you."),
    "serve_elbow_drop": _c("Loose arm, let it fall.", ["Spaghetti arm.", "Hold the grip at 3 out of 10."],
                           "The racket head drops below your elbow without you forcing it there."),
    "serve_contact_height": _c("Hit it at the top.", ["Reach up, on your toes.", "Meet it at full stretch."],
                               "Your arm is straight and your heels are up at contact."),
    "serve_elbow_contact": _c("Long arm, reach up.", ["Reach for the sky.", "One straight line from hip to racket tip."],
                              "Arm and racket make one straight line at contact."),
    "serve_shoulder_over": _c("Shoulder over shoulder.", ["Cartwheel the shoulders.", "Hitting shoulder to the sky."],
                              "At contact your hitting shoulder is above the other one."),
    "serve_contact_front": _c("Toss where this serve lives.", ["Flat: a foot inside the baseline.", "Kick: back over your head."],
                              "Let a toss drop without hitting it and see how far inside the baseline it lands."),
    "serve_contact_side": _c("Move the toss, not the swing.", ["Slice: toss out toward your hitting side.", "Kick: toss back over your head."],
                             "Let a toss drop without hitting it and see which side of your front foot it lands."),
    "serve_into_court": _c("Land inside the baseline.", ["Follow the ball into the court.", "Front foot lands first."],
                           "After the serve your landing foot is inside the baseline."),
    "serve_follow_through": _c("Finish by your opposite hip.", ["Let the racket swing all the way down.", "Relax the arm after the hit."],
                               "The racket ends beside your opposite hip with the arm relaxed."),
}


def cue_for(key: str, value, stroke: str) -> dict | None:
    """The cue, its alternatives and the self-check for one fix, with any value-dependent wording resolved."""
    entry = CUES.get(key)
    if entry is None:
        return None
    resolve = lambda x: x(value, stroke) if callable(x) else x
    return dict(cue=resolve(entry["cue"]), alts=list(resolve(entry["alts"])), check=resolve(entry["check"]))

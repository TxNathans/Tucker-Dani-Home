"""Pull WHOOP data (sleep, recovery, cycles, workouts, profile, body) into notes/personal/health/whoop/.

Runs in GitHub Actions (.github/workflows/health-sync.yml). Needs two repo secrets:
WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET. The WHOOP login token rotates on every refresh,
so it is kept encrypted (with a key derived from the client secret) in .whoop/token.enc.

  python tools/whoop/whoop_sync.py login-url        print the WHOOP login link
  python tools/whoop/whoop_sync.py login CODE_OR_URL  finish login, then pull full history
  python tools/whoop/whoop_sync.py sync             pull new data since the last run
"""

import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "notes" / "personal" / "health" / "whoop"
TOKEN_FILE = ROOT / ".whoop" / "token.enc"

API = "https://api.prod.whoop.com/developer"
AUTH = "https://api.prod.whoop.com/oauth/oauth2"
REDIRECT_URI = "http://localhost/callback"
SCOPES = "read:profile read:body_measurement read:cycles read:recovery read:sleep read:workout offline"

# Collections: file name -> (API path, id field). Stored as JSON Lines, one record per line.
COLLECTIONS = {
    "sleep": ("/v2/activity/sleep", "id"),
    "recovery": ("/v2/recovery", "sleep_id"),
    "cycles": ("/v2/cycle", "id"),
    "workouts": ("/v2/activity/workout", "id"),
}
# Re-pull this many days on each sync so late scoring and edits are picked up.
OVERLAP_DAYS = 10


def env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"Missing {name}. Add it under GitHub repo Settings > Secrets and variables > Actions.")
    return value


def fernet():
    secret = os.environ.get("WHOOP_TOKEN_KEY") or env("WHOOP_CLIENT_SECRET")
    key = hashlib.pbkdf2_hmac("sha256", secret.encode(), b"tucker-dani-whoop-token", 200_000)
    return Fernet(base64.urlsafe_b64encode(key))


def save_token(token):
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_bytes(fernet().encrypt(json.dumps(token).encode()))


def load_token():
    if not TOKEN_FILE.exists():
        sys.exit("Not logged in to WHOOP yet. Run the Health sync workflow with the login code first.")
    return json.loads(fernet().decrypt(TOKEN_FILE.read_bytes()))


def post_token(fields):
    body = urllib.parse.urlencode(
        {**fields, "client_id": env("WHOOP_CLIENT_ID"), "client_secret": env("WHOOP_CLIENT_SECRET")}
    ).encode()
    req = urllib.request.Request(
        f"{AUTH}/token", data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        # The response body can echo request details, so only report the status.
        sys.exit(f"WHOOP login step failed (HTTP {e.code}). If this keeps happening, log in again.")
    token = {"access_token": data["access_token"], "refresh_token": data["refresh_token"]}
    # Save right away: the old refresh token is now dead, so losing this one means logging in again.
    save_token(token)
    return token


def refresh():
    return post_token({"grant_type": "refresh_token", "refresh_token": load_token()["refresh_token"], "scope": "offline"})


def get(token, path, params=None):
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token['access_token']}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(int(e.headers.get("Retry-After") or 2 ** (attempt + 2)))
                continue
            sys.exit(f"WHOOP request {path} failed: HTTP {e.code}")
    sys.exit(f"WHOOP request {path} kept failing; try again later.")


def fetch_all(token, path, start=None):
    records, next_token = [], None
    while True:
        params = {"limit": 25}
        if start:
            params["start"] = start
        if next_token:
            params["nextToken"] = next_token
        page = get(token, path, params)
        records.extend(page.get("records", []))
        next_token = page.get("next_token")
        if not next_token:
            return records
        time.sleep(0.7)  # WHOOP allows 100 requests a minute


def read_jsonl(path):
    if not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {str(r["_key"]): r for r in rows}


def write_jsonl(path, rows):
    ordered = sorted(rows.values(), key=lambda r: r.get("start") or r.get("created_at") or "")
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in ordered))


def last_start(rows):
    starts = [r.get("start") or r.get("created_at") for r in rows.values()]
    starts = [s for s in starts if s]
    if not starts:
        return None
    latest = datetime.fromisoformat(max(starts).replace("Z", "+00:00"))
    return (latest - timedelta(days=OVERLAP_DAYS)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def sync(token, full=False):
    OUT.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, (path, key) in COLLECTIONS.items():
        file = OUT / f"{name}.jsonl"
        rows = read_jsonl(file)
        start = None if full else last_start(rows)
        new = fetch_all(token, path, start)
        for r in new:
            r["_key"] = r[key]
            rows[str(r[key])] = r
        write_jsonl(file, rows)
        counts[name] = (len(new), len(rows))
    (OUT / "profile.json").write_text(json.dumps(get(token, "/v2/user/profile/basic"), indent=2) + "\n")
    (OUT / "body.json").write_text(json.dumps(get(token, "/v2/user/measurement/body"), indent=2) + "\n")
    write_sleep_log()
    for name, (fetched, total) in counts.items():
        print(f"{name}: {fetched} fetched, {total} stored")


def hours(ms):
    return f"{ms / 3_600_000:.1f}" if ms is not None else ""


def local_date(iso, offset):
    moment = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    sign = -1 if offset.startswith("-") else 1
    h, m = offset.lstrip("+-").split(":")
    return moment.astimezone(timezone(sign * timedelta(hours=int(h), minutes=int(m)))).date().isoformat()


def write_sleep_log():
    """Readable table of every night, newest first, joined with that morning's recovery."""
    sleeps = read_jsonl(OUT / "sleep.jsonl")
    recovery = {r["sleep_id"]: r for r in read_jsonl(OUT / "recovery.jsonl").values()}
    lines = [
        "# WHOOP sleep log",
        "",
        "Generated by `tools/whoop/whoop_sync.py`. Hours are asleep time (light + deep + REM). "
        "Raw data with every field is in the `.jsonl` files next to this one.",
        "",
        "| Night of | Asleep h | In bed h | Perf % | Effic % | Consist % | Deep h | REM h | Light h | Awake h "
        "| Disturb | Resp | Recovery % | HRV ms | RHR |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    nights = [s for s in sleeps.values() if not s.get("nap") and s.get("score_state") == "SCORED"]
    for s in sorted(nights, key=lambda s: s["end"], reverse=True):
        sc, st = s["score"], s["score"]["stage_summary"]
        asleep = st["total_light_sleep_time_milli"] + st["total_slow_wave_sleep_time_milli"] + st["total_rem_sleep_time_milli"]
        rec = (recovery.get(s["id"]) or {}).get("score") or {}
        hrv = rec.get("hrv_rmssd_milli")
        lines.append(
            "| "
            + " | ".join(
                str(v)
                for v in [
                    local_date(s["end"], s["timezone_offset"]),
                    hours(asleep),
                    hours(st["total_in_bed_time_milli"]),
                    sc.get("sleep_performance_percentage", ""),
                    round(sc["sleep_efficiency_percentage"]) if sc.get("sleep_efficiency_percentage") else "",
                    sc.get("sleep_consistency_percentage", ""),
                    hours(st["total_slow_wave_sleep_time_milli"]),
                    hours(st["total_rem_sleep_time_milli"]),
                    hours(st["total_light_sleep_time_milli"]),
                    hours(st["total_awake_time_milli"]),
                    st.get("disturbance_count", ""),
                    round(sc["respiratory_rate"], 1) if sc.get("respiratory_rate") else "",
                    rec.get("recovery_score", ""),
                    round(hrv) if hrv else "",
                    rec.get("resting_heart_rate", ""),
                ]
            )
            + " |"
        )
    (OUT / "sleep-log.md").write_text("\n".join(lines) + "\n")


def login_code(arg):
    """Accept either the bare code or the whole localhost URL WHOOP redirected to."""
    if "code=" in arg:
        return urllib.parse.parse_qs(urllib.parse.urlparse(arg).query)["code"][0]
    return arg.strip()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if cmd == "login-url":
        state = base64.urlsafe_b64encode(os.urandom(12)).decode()
        params = {"client_id": env("WHOOP_CLIENT_ID"), "redirect_uri": REDIRECT_URI,
                  "response_type": "code", "scope": SCOPES, "state": state}
        print(f"{AUTH}/auth?{urllib.parse.urlencode(params)}")
    elif cmd == "login":
        if len(sys.argv) < 3:
            sys.exit("Usage: whoop_sync.py login CODE_OR_URL")
        token = post_token({"grant_type": "authorization_code", "code": login_code(sys.argv[2]),
                            "redirect_uri": REDIRECT_URI})
        sync(token, full=True)
    elif cmd == "sync":
        sync(refresh(), full="--full" in sys.argv)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

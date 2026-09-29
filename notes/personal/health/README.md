# Health data (WHOOP + Apple Health)

- `whoop/` - filled automatically every morning by the **Health sync** GitHub Action.
  - `sleep-log.md` - one line per night: hours asleep, sleep performance, stages, recovery, HRV, resting HR.
  - `sleep.jsonl`, `recovery.jsonl`, `cycles.jsonl`, `workouts.jsonl`, `profile.json`, `body.json` - every field WHOOP gives, full history.
- `apple/` - built from an Apple Health export by `tools/apple_health/parse_export.py`.
  - `sleep.csv` (per night, per source), `daily.csv` (steps, energy, heart rate, HRV, SpO2, weight...), `workouts.csv`.

Everything here is free: WHOOP developer access costs nothing and the Action uses about 1 of GitHub's 2,000 free minutes a month.

## One-time WHOOP setup (about 10 minutes)

0. **Make this repo private first.** GitHub > Settings > General > Danger Zone > Change visibility > Private. The sync refuses to run while the repo is public.
1. Go to https://developer.whoop.com, sign in with your WHOOP account, and create an app.
   - Redirect URL: `http://localhost/callback`
   - Scopes: tick every `read:` box and `offline`.
2. In this repo on GitHub: Settings > Secrets and variables > Actions.
   - **Variables** tab > New variable: `WHOOP_CLIENT_ID` = the app's Client ID.
   - **Secrets** tab > New secret: `WHOOP_CLIENT_SECRET` = the app's Client Secret.
3. Actions tab > **Health sync** > Run workflow > action `login-url` > Run. Open the finished run; the summary shows a link.
4. Open the link, log in to WHOOP, allow access. The browser lands on a `localhost` page that "can't be reached". That is expected. Copy that whole address.
5. Within 10 minutes: Actions > **Health sync** > Run workflow > paste the address into `whoop_login` > Run. This pulls your full history.

After that it runs on its own at 7:47am and 10:47am Central. The WHOOP login is kept encrypted in `.whoop/token.enc`. If a run ever says the login failed, repeat steps 3-5.

## Apple Health

Apple has no online API, so this is a manual export whenever you want fresh data:

1. iPhone: Health app > your picture (top right) > **Export All Health Data** > Export.
2. Share sheet > **Save to Files** > Google Drive (or upload it to Google Drive).
3. Tell Claude "update my Apple Health data". Claude downloads the zip and runs `python tools/apple_health/parse_export.py export.zip`. The raw zip is not kept in git.

WHOOP can also write its sleep into Apple Health (WHOOP app > More > App Settings > Integrations > Apple Health), so `apple/sleep.csv` shows WHOOP and Apple Watch side by side.

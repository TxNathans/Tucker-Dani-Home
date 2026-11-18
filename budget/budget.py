"""Dani's budget tracker.

Pulls read-only transactions and balances from SimpleFIN Bridge into a local
SQLite file, sorts them into categories, finds recurring bills, and writes a
monthly report with savings and 401(k) guidance.

Everything personal lives in budget/data/, which git ignores. Nothing here
can move money: SimpleFIN access is read-only.

Commands (run from the repo root):
    python budget/budget.py setup TOKEN     claim a SimpleFIN setup token
    python budget/budget.py sync [--days N] pull transactions (default 30 days, first run 365)
    python budget/budget.py import FILE.csv --account NAME   load a bank CSV export instead
    python budget/budget.py accounts        list accounts and balances
    python budget/budget.py report [YYYY-MM] spending, bills and savings for a month
    python budget/budget.py plan            savings rate, emergency fund and 401(k) plan
    python budget/budget.py recategorize    re-apply categories.json to every transaction
    python budget/budget.py split [YYYY-MM] shared household bills and joint card: who owes whom
    python budget/budget.py owe CATEGORY..  one-off shared costs (e.g. owe Honeymoon Wedding)
    python budget/budget.py bills           auto-draft calendar for your bank accounts
    python budget/budget.py ledger          update the running shared ledger in budget/shared/
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import sqlite3
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DB_PATH = DATA / "budget.db"
ACCESS_PATH = DATA / "simplefin_access_url.txt"
CONFIG_PATH = DATA / "config.json"
CONFIG_EXAMPLE = HERE / "config.example.json"
RULES_PATH = HERE / "categories.json"
LOCAL_RULES_PATH = DATA / "categories.json"  # personal keywords (names, trips); git ignores it
REPORTS = DATA / "reports"
# Shared with Tucker in git: split settings, the keywords the split needs, and the running ledger.
SHARED = HERE / "shared"
SHARED_SPLIT = SHARED / "split.json"
SHARED_RULES = SHARED / "categories.json"
LEDGER_JSON = SHARED / "ledger.json"
LEDGER_MD = SHARED / "OWED.md"
SHARED_OVERRIDES = SHARED / "overrides.json"  # {row_id: partner's percent} set on the shared dashboard


def row_id(key: str) -> str:
    """Short stable id for a ledger entry, used by the dashboards."""
    import hashlib
    return key if key.startswith(("carry", "manual")) else hashlib.sha1(key.encode()).hexdigest()[:12]

# IRS limits for 2026 (employee elective deferrals).
LIMIT_401K = 24_500
CATCHUP_401K_50 = 8_000

ONE_TIME = {"Wedding", "Honeymoon", "Wedding & Honeymoon", "Travel"}  # shown, but left out of "regular" monthly spending
NON_SPENDING = {"Transfer", "Credit Card Payment", "Income", "Savings & Investing"}
# SimpleFIN's firewall blocks Python's default User-Agent (Cloudflare error 1010).
USER_AGENT = "budget-tracker/1.0"
MAX_WINDOW_DAYS = 45  # SimpleFIN Bridge recommends 45 days per request
OVERLAP_DAYS = 5


# ---------------------------------------------------------------- storage

def db() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            name TEXT,
            institution TEXT,
            kind TEXT,              -- checking, savings, credit, retirement, investment, loan, other
            currency TEXT,
            balance REAL,
            available REAL,
            balance_date TEXT
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT,
            account_id TEXT,
            date TEXT,              -- YYYY-MM-DD
            amount REAL,            -- negative = money out
            description TEXT,
            payee TEXT,
            pending INTEGER DEFAULT 0,
            category TEXT,
            category_locked INTEGER DEFAULT 0,
            PRIMARY KEY (account_id, id)
        );
        CREATE INDEX IF NOT EXISTS tx_date ON transactions(date);
        """
    )
    return con


def load_config() -> dict:
    src = CONFIG_PATH if CONFIG_PATH.exists() else CONFIG_EXAMPLE
    with open(src) as f:
        cfg = json.load(f)
    cfg["_from_example"] = src == CONFIG_EXAMPLE
    if SHARED_SPLIT.exists():
        with open(SHARED_SPLIT) as f:
            cfg["split"] = json.load(f)
    return cfg


def load_rules() -> dict:
    """Personal rules in budget/data/categories.json are checked before the shared ones."""
    with open(RULES_PATH) as f:
        rules = json.load(f)
    merged = {}
    for path in (LOCAL_RULES_PATH, SHARED_RULES):
        if path.exists():
            with open(path) as f:
                for k, v in json.load(f).get("rules", {}).items():
                    merged.setdefault(f"local:{k}", []).extend(v)
    merged.update(rules["rules"])
    rules["rules"] = merged
    return rules


def write_private(path: Path, text: str) -> None:
    DATA.mkdir(exist_ok=True)
    path.write_text(text)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


# ---------------------------------------------------------------- categories

def guess_kind(name: str) -> str:
    n = name.lower()
    for kind, words in [
        ("retirement", ["401", "403(b)", "403b", "ira", "roth", "retirement", "tsp"]),
        ("credit", ["credit", "card", "visa", "mastercard", "amex", "sapphire", "freedom", "discover", "rewards"]),
        ("savings", ["savings", "money market", "high yield", "hysa", "cd "]),
        ("investment", ["brokerage", "invest", "individual", "stock"]),
        ("loan", ["loan", "mortgage", "auto", "student"]),
        ("checking", ["checking", "chk", "spending", "everyday"]),
    ]:
        if any(w in n for w in words):
            return kind
    return "other"


def categorize(desc: str, amount: float, kind: str, rules: dict) -> str:
    text = " ".join(desc.lower().split())  # banks pad descriptions with runs of spaces
    for cat, words in rules["rules"].items():
        if any(w.lower() in text for w in words):
            return cat.removeprefix("local:")
    if amount > 0:
        # Money in on a credit card is a payment or refund, not income.
        return "Refund" if kind == "credit" else "Income"
    return "Uncategorized"


def apply_categories(con: sqlite3.Connection, only_new: bool) -> int:
    rules = load_rules()
    kinds = {r["id"]: r["kind"] for r in con.execute("SELECT id, kind FROM accounts")}
    where = "WHERE category_locked = 0" + (" AND category IS NULL" if only_new else "")
    rows = con.execute(f"SELECT account_id, id, description, payee, amount FROM transactions {where}").fetchall()
    for r in rows:
        desc = f"{r['description'] or ''} {r['payee'] or ''}"
        cat = categorize(desc, r["amount"], kinds.get(r["account_id"], "other"), rules)
        con.execute("UPDATE transactions SET category=? WHERE account_id=? AND id=?", (cat, r["account_id"], r["id"]))
    con.commit()
    return len(rows)


# ---------------------------------------------------------------- SimpleFIN

def cmd_setup(args) -> None:
    token = args.token.strip()
    try:
        claim_url = base64.b64decode(token + "=" * (-len(token) % 4)).decode()
    except Exception:
        sys.exit("That does not look like a SimpleFIN setup token (it should be one long base64 string).")
    if not claim_url.startswith("https://"):
        sys.exit("Decoded token is not an https URL. Copy the whole setup token from SimpleFIN Bridge.")
    req = urllib.request.Request(claim_url, data=b"", method="POST", headers={"Content-Length": "0", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            access_url = resp.read().decode().strip()
    except urllib.error.HTTPError as e:
        if e.code == 403:
            sys.exit(
                "SimpleFIN says this token was already claimed or does not exist.\n"
                "If you did not claim it yourself, disable it in SimpleFIN Bridge and make a new one."
            )
        sys.exit(f"SimpleFIN returned HTTP {e.code}.")
    write_private(ACCESS_PATH, access_url + "\n")
    print(f"Connected. Access key saved to {ACCESS_PATH.relative_to(HERE.parent)} (git ignores it).")
    print("Next: python budget/budget.py sync")


def simplefin_get(start: datetime, end: datetime) -> dict:
    # SIMPLEFIN_ACCESS_URL lets a scheduled cloud run use a credential its network proxy injects.
    raw = os.environ.get("SIMPLEFIN_ACCESS_URL") or (ACCESS_PATH.read_text().strip() if ACCESS_PATH.exists() else "")
    if not raw:
        sys.exit("Not connected yet. Run: python budget/budget.py setup YOUR_SETUP_TOKEN")
    access = urllib.parse.urlsplit(raw)
    base = f"{access.scheme}://{access.hostname}{':' + str(access.port) if access.port else ''}{access.path}"
    auth = base64.b64encode(
        f"{urllib.parse.unquote(access.username or '')}:{urllib.parse.unquote(access.password or '')}".encode()
    ).decode()
    q = urllib.parse.urlencode(
        {"start-date": int(start.timestamp()), "end-date": int(end.timestamp()), "pending": 1, "version": 2}
    )
    req = urllib.request.Request(f"{base}/accounts?{q}", headers={"Authorization": f"Basic {auth}", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 402:
            sys.exit("SimpleFIN says payment is required. Check your SimpleFIN Bridge subscription.")
        if e.code == 403:
            sys.exit("SimpleFIN refused the access key (revoked or invalid). Make a new setup token and run setup again.")
        sys.exit(f"SimpleFIN returned HTTP {e.code}.")


def cmd_sync(args) -> None:
    con = db()
    first_run = con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
    days = args.days or (365 if first_run else 30)
    end = datetime.now(timezone.utc) + timedelta(days=1)
    start = end - timedelta(days=days + 1)
    seen_tx = 0
    warnings: list[str] = []
    window_end = end
    while window_end > start:
        window_start = max(start, window_end - timedelta(days=MAX_WINDOW_DAYS))
        data = simplefin_get(window_start, window_end)
        warnings += [e.get("msg", str(e)) if isinstance(e, dict) else str(e) for e in data.get("errlist", []) + data.get("errors", [])]
        conns = {c["conn_id"]: c.get("name", "") for c in data.get("connections", [])}
        for a in data.get("accounts", []):
            inst = conns.get(a.get("conn_id"), "") or (a.get("org") or {}).get("name", "")
            existing = con.execute("SELECT kind FROM accounts WHERE id=?", (a["id"],)).fetchone()
            kind = existing["kind"] if existing else guess_kind(f"{inst} {a['name']}")
            con.execute(
                """INSERT INTO accounts (id, name, institution, kind, currency, balance, available, balance_date)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET name=excluded.name, institution=excluded.institution,
                     balance=excluded.balance, available=excluded.available, balance_date=excluded.balance_date""",
                (
                    a["id"], a["name"], inst, kind, a.get("currency", "USD"),
                    float(a.get("balance") or 0),
                    float(a["available-balance"]) if a.get("available-balance") not in (None, "") else None,
                    datetime.fromtimestamp(a.get("balance-date", 0), timezone.utc).date().isoformat(),
                ),
            )
            for t in a.get("transactions", []):
                ts = t.get("transacted_at") or t.get("posted") or 0
                d = datetime.fromtimestamp(ts, timezone.utc).date().isoformat() if ts else date.today().isoformat()
                con.execute(
                    """INSERT INTO transactions (id, account_id, date, amount, description, payee, pending)
                       VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(account_id, id) DO UPDATE SET date=excluded.date, amount=excluded.amount,
                         description=excluded.description, payee=excluded.payee, pending=excluded.pending""",
                    (t["id"], a["id"], d, float(t["amount"]), t.get("description", ""), t.get("payee", ""), int(bool(t.get("pending")))),
                )
                seen_tx += 1
        con.commit()
        if window_start <= start:
            break
        window_end = window_start + timedelta(days=OVERLAP_DAYS)
    # Pending charges that have since posted come back with a new id; drop stale pending ones.
    con.execute("DELETE FROM transactions WHERE pending=1 AND date < ?", ((date.today() - timedelta(days=10)).isoformat(),))
    con.commit()
    n = apply_categories(con, only_new=True)
    accts = con.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    print(f"Synced {accts} accounts, {seen_tx} transactions seen, {n} newly categorized.")
    for w in dict.fromkeys(warnings):
        print(f"  SimpleFIN note: {w}")


# ---------------------------------------------------------------- CSV import

def cmd_import(args) -> None:
    con = db()
    acct_id = "csv:" + re.sub(r"\W+", "-", args.account.lower()).strip("-")
    kind = args.kind or guess_kind(args.account)
    con.execute(
        "INSERT OR IGNORE INTO accounts (id, name, institution, kind, currency) VALUES (?,?,?,?, 'USD')",
        (acct_id, args.account, "CSV import", kind),
    )
    with open(args.file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = {c.lower().strip(): c for c in reader.fieldnames or []}

        def col(*names):
            for n in names:
                if n in cols:
                    return cols[n]
            return None

        c_date = col("date", "transaction date", "posting date", "posted date", "trans. date")
        c_desc = col("description", "payee", "name", "merchant", "memo")
        c_amt = col("amount")
        c_debit, c_credit = col("debit", "withdrawal", "withdrawals"), col("credit", "deposit", "deposits")
        if not c_date or not c_desc or not (c_amt or c_debit):
            sys.exit(f"Could not find date/description/amount columns in {args.file}. Columns: {list(cols)}")
        n = 0
        for row in reader:
            raw = (row.get(c_date) or "").strip()
            d = None
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y"):
                try:
                    d = datetime.strptime(raw, fmt).date()
                    break
                except ValueError:
                    pass
            if not d:
                continue

            def num(s):
                s = (s or "").replace("$", "").replace(",", "").strip()
                if s.startswith("(") and s.endswith(")"):
                    s = "-" + s[1:-1]
                return float(s) if s else 0.0

            if c_amt:
                amt = num(row.get(c_amt))
                if kind == "credit" and args.flip:
                    amt = -amt
            else:
                amt = num(row.get(c_credit)) - abs(num(row.get(c_debit)))
            desc = row.get(c_desc, "").strip()
            tid = f"{d}|{amt:.2f}|{desc}|{n}"
            con.execute(
                "INSERT OR IGNORE INTO transactions (id, account_id, date, amount, description, payee) VALUES (?,?,?,?,?, '')",
                (tid, acct_id, d.isoformat(), amt, desc),
            )
            n += 1
    con.commit()
    apply_categories(con, only_new=True)
    print(f"Imported {n} rows into {args.account} ({kind}).")


# ---------------------------------------------------------------- analysis

def month_bounds(ym: str) -> tuple[str, str]:
    y, m = map(int, ym.split("-"))
    start = date(y, m, 1)
    end = date(y + (m == 12), m % 12 + 1, 1)
    return start.isoformat(), end.isoformat()


def prev_months(ym: str, n: int) -> list[str]:
    y, m = map(int, ym.split("-"))
    out = []
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append(f"{y:04d}-{m:02d}")
    return out


def full_months(con, months: list[str]) -> list[str]:
    """Drop months that began before the first synced transaction (partial data skews averages)."""
    first = con.execute("SELECT MIN(date) FROM transactions").fetchone()[0]
    if not first:
        return []
    return [m for m in months if m > first[:7] or (m == first[:7] and int(first[8:10]) <= 3)]


def month_totals(con, ym: str) -> dict:
    s, e = month_bounds(ym)
    rows = con.execute(
        """SELECT t.category, t.amount, t.description, t.payee, t.date, a.kind
           FROM transactions t JOIN accounts a ON a.id = t.account_id
           WHERE t.date >= ? AND t.date < ? AND a.kind NOT IN ('retirement', 'investment')""",
        (s, e),
    ).fetchall()
    income = sum(r["amount"] for r in rows if r["category"] == "Income")
    # Saved = pay deposited straight into savings, plus money sent to savings/investing from other
    # accounts. Moves out of savings into investments are not counted again.
    saved = sum(r["amount"] for r in rows if r["category"] == "Income" and r["kind"] == "savings") \
        - sum(r["amount"] for r in rows if r["category"] == "Savings & Investing" and r["amount"] < 0 and r["kind"] != "savings")
    by_cat: dict[str, float] = defaultdict(float)
    for r in rows:
        if r["category"] in NON_SPENDING:
            continue
        by_cat[r["category"]] -= r["amount"]  # refunds reduce spending
    by_cat.pop("Refund", None)
    refunds = sum(r["amount"] for r in rows if r["category"] == "Refund")
    spending = sum(v for v in by_cat.values()) - refunds
    merchants: dict[str, float] = defaultdict(float)
    for r in rows:
        if r["category"] not in NON_SPENDING and r["amount"] < 0:
            merchants[normalize(r["payee"] or r["description"])] -= r["amount"]
    one_time = sum(v for c, v in by_cat.items() if c in ONE_TIME)
    # The partner's half of shared costs is not Dani's spending: it comes back to her.
    partner_by_cat: dict[str, float] = defaultdict(float)
    split_cfg = load_config().get("split")
    if split_cfg:
        for it in shared_items(con, split_cfg, s):
            if it["date"] < e and it["kind"] in ("household bill", "joint card", "trip"):
                partner_by_cat[it["category"]] += it["share"]
    partner_one_time = sum(v for c, v in partner_by_cat.items() if c in ONE_TIME or c in (split_cfg or {}).get("one_off_categories", []))
    partner_regular = sum(partner_by_cat.values()) - partner_one_time
    return {"income": income, "spending": spending, "saved": saved, "by_cat": dict(by_cat), "refunds": refunds,
            "one_time": one_time, "regular": spending - one_time,
            "partner_by_cat": dict(partner_by_cat), "partner_regular": partner_regular, "partner_one_time": partner_one_time,
            "my_regular": spending - one_time - partner_regular, "my_one_time": one_time - partner_one_time,
            "merchants": merchants, "count": len(rows)}


def normalize(desc: str) -> str:
    d = (desc or "").upper()
    d = re.split(r"\s+DES:", d)[0]  # Bank of America: "FPL DIRECT DEBIT DES:ELEC PYMT ID:..."
    d = re.sub(r"^(ONLINE BANKING PAYMENT TO|APLPAY|SQ \*|TST\* ?)", " ", d)
    d = re.sub(r"\bCONFIRMATION.*", " ", d)
    d = re.sub(r"\b(POS|ACH|DEBIT|PURCHASE|RECURRING|PMT|PAYMENT|CARD|ONLINE|WEB|ID:?\S*|PPD|CCD)\b", " ", d)
    d = re.sub(r"[#*]\S*|\d{3,}|\b\d+/\d+\b", " ", d)
    d = re.sub(r"[^A-Z& ]+", " ", d)
    words = d.split()[:3]
    return " ".join(words).title() or "Unknown"


def find_bills(con, months: int = 4) -> list[dict]:
    """Charges from the same merchant in at least 3 of the last N months with steady amounts."""
    since = (date.today().replace(day=1) - timedelta(days=31 * months)).isoformat()
    rows = con.execute(
        """SELECT t.date, t.amount, t.description, t.payee, t.category FROM transactions t
           JOIN accounts a ON a.id=t.account_id
           WHERE t.amount < 0 AND t.date >= ? AND a.kind NOT IN ('retirement','investment')""",
        (since,),
    ).fetchall()
    groups: dict[str, list] = defaultdict(list)
    for r in rows:
        if r["category"] in ("Transfer", "Credit Card Payment", "Savings & Investing"):
            continue
        groups[normalize(r["payee"] or r["description"])].append(r)
    bills = []
    for name, txs in groups.items():
        by_month: dict[str, float] = defaultdict(float)
        for t in txs:
            by_month[t["date"][:7]] -= t["amount"]
        if len(by_month) < 3:
            continue
        amounts = list(by_month.values())
        med = statistics.median(amounts)
        if med <= 0 or max(amounts) > med * 1.6:  # too variable to be a bill (e.g. groceries)
            continue
        if len(txs) > len(by_month) * 2:  # many charges a month = shopping habit, not a bill
            continue
        last = max(t["date"] for t in txs)
        bills.append({"name": name, "monthly": med, "category": txs[-1]["category"], "last": last,
                      "day": int(statistics.median(int(t["date"][8:10]) for t in txs))})
    return sorted(bills, key=lambda b: -b["monthly"])


def money(x: float) -> str:
    return f"-${-x:,.0f}" if x < 0 else f"${x:,.0f}"


def cmd_accounts(args) -> None:
    con = db()
    rows = con.execute("SELECT * FROM accounts ORDER BY kind, institution, name").fetchall()
    if not rows:
        sys.exit("No accounts yet. Run setup and sync first.")
    total = 0.0
    print(f"{'Account':40} {'Type':11} {'Balance':>12}  As of")
    for r in rows:
        bal = r["balance"] or 0
        total += bal
        print(f"{(r['institution'] + ' ' + r['name']).strip()[:40]:40} {r['kind']:11} {money(bal):>12}  {r['balance_date'] or ''}")
    print(f"{'Net worth (these accounts)':52} {money(total):>12}")
    print("\nWrong type? Fix it with: python budget/budget.py set-kind \"ACCOUNT NAME\" savings")


def cmd_set_kind(args) -> None:
    con = db()
    n = con.execute("UPDATE accounts SET kind=? WHERE name LIKE ?", (args.kind, f"%{args.name}%")).rowcount
    con.commit()
    apply_categories(con, only_new=False)
    print(f"Updated {n} account(s) to {args.kind}.")


def cmd_recategorize(args) -> None:
    con = db()
    print(f"Re-categorized {apply_categories(con, only_new=False)} transactions.")


def cmd_report(args) -> None:
    con = db()
    ym = args.month or date.today().strftime("%Y-%m")
    cur = month_totals(con, ym)
    hist = [month_totals(con, m) for m in full_months(con, prev_months(ym, 3))]
    hist = [h for h in hist if h["count"]]
    cfg = load_config()
    budgets = cfg.get("monthly_budgets", {})

    lines = [f"# Budget report: {ym}", ""]
    if ym == date.today().strftime("%Y-%m"):
        lines.append(f"_Month in progress (through {date.today():%b %d})._\n")
    net = cur["income"] - cur["spending"]
    lines += [
        f"- Income: **{money(cur['income'])}**",
        f"- Spending: **{money(cur['spending'])}**" + (f" (refunds and card credits {money(cur['refunds'])} already subtracted)" if cur["refunds"] else ""),
        *( [f"  - Regular spending: **{money(cur['regular'])}**; one-time trips and wedding: {money(cur['one_time'])}"] if cur["one_time"] else [] ),
        f"- Saved (pay into savings + money sent to savings/investing): **{money(cur['saved'])}**",
        f"- Left over: **{money(net)}**" + (f" ({net / cur['income']:.0%} of income)" if cur["income"] > 0 else ""),
        "",
        "## Spending by category",
        "",
        "| Category | This month | 3-mo avg | Budget | |",
        "|---|---:|---:|---:|---|",
    ]
    cats = set(cur["by_cat"]) | {c for h in hist for c in h["by_cat"]}
    for c in sorted(cats, key=lambda c: -cur["by_cat"].get(c, 0)):
        v = cur["by_cat"].get(c, 0)
        avg = statistics.mean(h["by_cat"].get(c, 0) for h in hist) if hist else 0
        b = budgets.get(c)
        flag = ""
        if b and v > b:
            flag = "over budget"
        elif avg and v > avg * 1.25 and v - avg > 50:
            flag = "up vs usual"
        lines.append(f"| {c} | {money(v)} | {money(avg) if hist else '-'} | {money(b) if b else '-'} | {flag} |")

    lines += ["", "## Top merchants", ""]
    for name, v in sorted(cur["merchants"].items(), key=lambda kv: -kv[1])[:10]:
        lines.append(f"- {name}: {money(v)}")

    bills = find_bills(con)
    if bills:
        lines += ["", "## Recurring bills and subscriptions", "", "| Bill | Monthly | Usually on | Category |", "|---|---:|---:|---|"]
        for b in bills:
            lines.append(f"| {b['name']} | {money(b['monthly'])} | day {b['day']} | {b['category']} |")
        lines.append(f"\nTotal recurring: **{money(sum(b['monthly'] for b in bills))}/month**")

    unc = con.execute(
        """SELECT date, amount, description FROM transactions WHERE category='Uncategorized'
           AND date >= ? AND date < ? ORDER BY amount LIMIT 15""",
        month_bounds(ym),
    ).fetchall()
    if unc:
        lines += ["", "## Uncategorized (add keywords to budget/categories.json)", ""]
        lines += [f"- {r['date']} {money(-r['amount'])} {r['description']}" for r in unc]

    out = "\n".join(lines) + "\n"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{ym}.md").write_text(out)
    print(out)
    print(f"(Saved to {(REPORTS / f'{ym}.md').relative_to(HERE.parent)})")


def cmd_plan(args) -> None:
    con = db()
    cfg = load_config()
    this_month = date.today().strftime("%Y-%m")
    months = full_months(con, prev_months(this_month, 6))
    hist = [month_totals(con, m) for m in months]
    hist = [h for h in hist if h["count"]]
    lines = ["# Savings and 401(k) plan", ""]
    if cfg["_from_example"]:
        lines.append("_Using placeholder numbers from config.example.json. Copy it to budget/data/config.json and fill in your real pay and 401(k) details._\n")
    if not hist:
        sys.exit("Need at least one full month of transactions. Run sync first.")

    take_home = statistics.mean(h["income"] for h in hist)
    spend = statistics.mean(h["regular"] for h in hist)
    one_time = statistics.mean(h["one_time"] for h in hist)
    saved = statistics.mean(h["saved"] for h in hist)
    bills = sum(b["monthly"] for b in find_bills(con))
    liquid = con.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE kind IN ('checking','savings')").fetchone()[0]
    cash_savings = con.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE kind='savings'").fetchone()[0]
    card_debt = -con.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE kind='credit' AND balance<0").fetchone()[0]

    lines += [
        f"Based on the last {len(hist)} full month(s):",
        "",
        f"- Average take-home pay: **{money(take_home)}/month**",
        f"- Average regular spending: **{money(spend)}/month** (recurring bills about {money(bills)} of that)"
        + (f"; plus {money(one_time)}/month of one-time trips and wedding costs" if one_time else ""),
        f"- Average moved to savings: **{money(saved)}/month**",
        f"- Cash left over after spending: **{money(take_home - spend)}/month**"
        + (f" ({(take_home - spend) / take_home:.0%} of take-home)" if take_home > 0 else ""),
        f"- Checking + savings today: **{money(liquid)}**; credit card balances: **{money(card_debt)}**",
        "",
        "## Emergency fund",
        "",
    ]
    target_months = cfg.get("emergency_fund_months", 6)
    need = spend * target_months
    have_months = cash_savings / spend if spend else 0
    lines.append(f"Savings accounts cover **{have_months:.1f} months** of spending. Target is {target_months} months = {money(need)}.")
    if cash_savings < need:
        gap = need - cash_savings
        if take_home - spend > 0:
            lines.append(f"Gap: {money(gap)}. At {money((take_home - spend) * 0.5)}/month (half your leftover) that takes about "
                         f"{gap / ((take_home - spend) * 0.5):.0f} months.")
        else:
            lines.append(f"Gap: {money(gap)}. Spending is running above take-home pay, so close that first (see the report).")
    else:
        lines.append("You're fully funded. Extra cash can go to the 401(k), a Roth IRA, or goals.")

    if card_debt > 0:
        lines += ["", f"**Credit cards show {money(card_debt)} owed.** If any of that is carried month to month (not paid in full), "
                  "paying it off beats any investment return. Pay it before raising savings beyond the 401(k) match."]

    k = cfg.get("401k", {})
    salary = cfg.get("annual_salary_gross", 0)
    lines += ["", "## 401(k)", ""]
    if not salary:
        lines.append("Add `annual_salary_gross` and the `401k` section to budget/data/config.json to get numbers here.")
    else:
        cur_pct = k.get("current_contribution_pct", 0) / 100
        match_rate = k.get("employer_match_rate_pct", 0) / 100
        match_cap = k.get("employer_match_up_to_pct", 0) / 100
        age = cfg.get("age", 30)
        limit = LIMIT_401K + (CATCHUP_401K_50 if age >= 50 else 0)
        per_pay = cfg.get("paychecks_per_year", 26)
        roth = k.get("roth", False)
        marginal = cfg.get("marginal_tax_rate_pct", 22) / 100

        def row(p):
            contrib = min(salary * p, limit)
            match = salary * min(p, match_cap) * match_rate
            # Pre-tax: take-home drops by the contribution minus the income tax saved
            # (Social Security and Medicare still apply). Roth: by the full amount.
            takehome_cost = contrib if roth else contrib * (1 - marginal)
            return contrib, match, takehome_cost / 12

        lines.append(f"Salary {money(salary)}, contributing {cur_pct:.0%}, employer matches {match_rate:.0%} of the first {match_cap:.0%}. "
                     f"2026 limit: {money(limit)}.")
        lines += ["", "| Contribute | You put in/yr | Employer adds/yr | Take-home drops by/mo |", "|---:|---:|---:|---:|"]
        options = sorted({cur_pct, match_cap, 0.10, 0.15, round(min(limit / salary, 1), 3)} - {0})
        for p in options:
            c, m, cost = row(p)
            tag = " (now)" if abs(p - cur_pct) < 1e-9 else (" (full match)" if abs(p - match_cap) < 1e-9 else (" (max)" if c >= limit else ""))
            lines.append(f"| {p:.0%}{tag} | {money(c)} | {money(m)} | {money(cost)} |")

        leftover = take_home - spend
        lines += ["", "**Recommendation:**", ""]
        if match_cap and cur_pct < match_cap:
            _, lost, _ = row(match_cap)
            _, have, _ = row(cur_pct)
            lines.append(f"1. Raise to at least {match_cap:.0%} now. You're leaving {money(lost - have)}/yr of free employer money on the table.")
        else:
            lines.append("1. You're getting the full employer match. Good.")
        # How far can leftover cash push it? Use ~half of leftover so the emergency fund still grows.
        spare = max(leftover, 0) * (0.5 if cash_savings < need else 0.8)
        best = cur_pct
        cost_now = row(cur_pct)[2]
        for p in [x / 100 for x in range(round(cur_pct * 100), 101)]:
            c, _, cost = row(p)
            if cost - cost_now <= spare and salary * p <= limit:
                best = p
        best = max(best, match_cap if cur_pct < match_cap else cur_pct)
        capped = cash_savings < need and best > 0.15
        if capped:
            best = 0.15  # build the emergency fund before going past 15%
        if best > cur_pct:
            lines.append(f"2. Your leftover cash supports **{best:.0%}** without cutting current spending "
                         f"(take-home drops about {money(row(best)[2] - row(cur_pct)[2])}/month).")
            if capped:
                lines.append("   There's room for more, but finish the emergency fund first, then raise it further or open a Roth IRA.")
        else:
            lines.append("2. Leftover cash is tight. Trim one or two categories in the report before raising it further.")
        lines.append("3. Bump it 1 point each raise or each January until you hit 15% (counting the match).")
        lines.append("\n_Estimates only. Tax savings assume your marginal rate from config; check a payroll preview before changing it._")

    out = "\n".join(lines) + "\n"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "plan.md").write_text(out)
    print(out)


# ---------------------------------------------------------------- shared costs with partner

def cmd_split(args) -> None:
    """Who paid the shared household costs this month, and who owes whom.

    Cash basis: a joint card counts when its bill is paid, by whoever paid it. Household
    bills paid from your own accounts count as you paying them.
    """
    con = db()
    cfg = load_config().get("split") or sys.exit("Add a \"split\" section to budget/data/config.json (see config.example.json).")
    ym = args.month or date.today().strftime("%Y-%m")
    s, e = month_bounds(ym)
    partner = cfg.get("partner", "Partner")
    my_pct = cfg.get("my_share_pct", 50) / 100
    joint_names = [n.lower() for n in cfg.get("joint_accounts", [])]
    household = set(cfg.get("household_categories", []))
    household_kw = [k.lower() for k in cfg.get("household_keywords", [])]
    exclude_kw = [k.lower() for k in cfg.get("not_household_keywords", [])]
    partner_kw = [k.lower() for k in cfg.get("partner_transfer_keywords", [partner])]
    # True when you pay the whole joint card bill: split its charges as they happen, not its payments.
    joint_by_charges = cfg.get("i_pay_joint_card", False)

    accts = {r["id"]: r for r in con.execute("SELECT * FROM accounts")}
    joint = {i for i, a in accts.items() if any(n in a["name"].lower() for n in joint_names)}
    rows = con.execute(
        "SELECT * FROM transactions WHERE date >= ? AND date < ? ORDER BY date",
        (month_bounds(ym)[0], (date.fromisoformat(e) + timedelta(days=5)).isoformat()),
    ).fetchall()
    in_month = [r for r in rows if r["date"] < e]

    bills, joint_pay, to_partner, from_partner, joint_charges = [], [], [], [], defaultdict(float)
    for r in in_month:
        text = " ".join(f"{r['description']} {r['payee']}".lower().split())
        if r["account_id"] in joint:
            if r["category"] == "Credit Card Payment" and r["amount"] > 0:
                joint_pay.append(r)
            elif r["category"] not in ("Credit Card Payment", "Transfer") and r["category"] not in ONE_TIME - {"Travel"} \
                    and r["category"] not in cfg.get("exclude_categories", []):
                joint_charges[r["category"]] -= r["amount"]
            continue
        if r["category"] in ("Transfer", "Payments to People (review)") and any(k in text for k in partner_kw):
            (from_partner if r["amount"] > 0 else to_partner).append(r)
            continue
        is_household = (r["category"] in household or any(k in text for k in household_kw)) and not any(k in text for k in exclude_kw)
        if is_household and r["amount"] < 0:
            bills.append(r)

    # Was each joint-card payment made from one of my accounts? Match amount within 5 days.
    mine = [r for r in rows if r["account_id"] not in joint and r["category"] == "Credit Card Payment" and r["amount"] < 0]
    used, me_paid_joint, partner_paid_joint = set(), 0.0, 0.0
    for p in joint_pay:
        d = date.fromisoformat(p["date"])
        match = next((m for m in mine if (m["account_id"], m["id"]) not in used and abs(-m["amount"] - p["amount"]) < 0.01
                      and abs((date.fromisoformat(m["date"]) - d).days) <= 5), None)
        if match:
            used.add((match["account_id"], match["id"]))
            me_paid_joint += p["amount"]
        else:
            partner_paid_joint += p["amount"]

    if joint_by_charges:
        me_paid_joint, partner_paid_joint = sum(joint_charges.values()), 0.0
    partner_bills = cfg.get("partner_pays_monthly", {})
    my_bills = -sum(r["amount"] for r in bills)
    partner_fixed = sum(partner_bills.values())
    total = my_bills + me_paid_joint + partner_paid_joint + partner_fixed
    my_paid = my_bills + me_paid_joint
    partner_paid = partner_paid_joint + partner_fixed
    sent = -sum(r["amount"] for r in to_partner)
    got = sum(r["amount"] for r in from_partner)
    # Payments from the partner that never hit a linked account (e.g. still in a Venmo balance).
    manual = [m for m in cfg.get("partner_payments_manual", []) if m["date"][:7] == ym]
    got += sum(m["amount"] for m in manual)
    # Positive = partner owes me.
    owed = (my_paid - total * my_pct) - got + sent

    L = [f"# Shared costs with {partner}: {ym}", ""]
    L += ["## Household bills you paid", "", "| Date | Bill | Category | Amount |", "|---|---|---|---:|"]
    for r in bills:
        L.append(f"| {r['date']} | {normalize(r['payee'] or r['description'])} | {r['category']} | {money(-r['amount'])} |")
    L.append(f"| | **Total** | | **{money(my_bills)}** |")
    L += ["", f"## Joint card ({', '.join(accts[i]['name'] for i in joint) or 'none found'})", ""]
    if joint_by_charges:
        L.append(f"- You pay this card, so every charge is split as it happens. Charges this month: **{money(me_paid_joint)}**"
                 " (wedding and honeymoon charges are left out; use the owe command for those)")
    else:
        L.append(f"- Card bill paid by you: **{money(me_paid_joint)}**")
        L.append(f"- Card bill paid by {partner} (or another account): **{money(partner_paid_joint)}**")
    if joint_charges:
        L.append(f"- New charges this month: {money(sum(joint_charges.values()))} ("
                 + ", ".join(f"{c} {money(v)}" for c, v in sorted(joint_charges.items(), key=lambda kv: -kv[1]) if v > 0) + ")")
    if partner_bills:
        L += ["", f"## Bills {partner} pays (from config)", ""] + [f"- {k}: {money(v)}" for k, v in partner_bills.items()]
    L += ["", "## Settle up", "",
          f"- Shared total: **{money(total)}**. Your {my_pct:.0%}: {money(total * my_pct)}; {partner}'s {1 - my_pct:.0%}: {money(total * (1 - my_pct))}",
          f"- You paid {money(my_paid)}; {partner} paid {money(partner_paid)}",
          f"- Already sent: you to {partner} {money(sent)}; {partner} to you {money(got)}"
          + (" (includes " + ", ".join(f"{m['date']} {money(m['amount'])} {m.get('note', '')}".strip() for m in manual) + ", entered by hand)" if manual else ""),
          ""]
    if abs(owed) < 1:
        L.append("**You're even.**")
    elif owed > 0:
        L.append(f"**{partner} owes you {money(owed)} for {ym}.**")
    else:
        L.append(f"**You owe {partner} {money(-owed)} for {ym}.**")
    L.append(f"\n_{'Joint card charges count when charged' if joint_by_charges else 'Joint card counts when its bill is paid'}. Bills {partner} pays from his own accounts aren't visible here; "
             f"add them under split.partner_pays_monthly in config._")
    out = "\n".join(L) + "\n"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"split-{ym}.md").write_text(out)
    print(out)


def cmd_owe(args) -> None:
    """One-off shared costs (a trip, a wedding): everything in these categories, who paid, and the split."""
    con = db()
    cfg = load_config().get("split", {})
    partner = cfg.get("partner", "Partner")
    my_pct = cfg.get("my_share_pct", 50) / 100
    joint_names = [n.lower() for n in cfg.get("joint_accounts", [])]
    L = [f"# What {partner} owes for shared one-off costs", ""]
    grand = 0.0
    for cat in args.categories:
        rows = con.execute(
            """SELECT t.date, t.amount, t.description, a.name FROM transactions t JOIN accounts a ON a.id=t.account_id
               WHERE t.category = ? ORDER BY t.date""", (cat,)).fetchall()
        if not rows:
            L += [f"## {cat}", "", "Nothing found in this category.", ""]
            continue
        mine = [r for r in rows if cfg.get("i_pay_joint_card") or not any(n in r["name"].lower() for n in joint_names)]
        joint = [r for r in rows if r not in mine]
        L += [f"## {cat}", "", "| Date | What | Paid with | Amount |", "|---|---|---|---:|"]
        for r in mine:
            what = re.sub(r"\s+", " ", re.split(r"\s+DES:|\s+\d{2}/\d{2}\s", r["description"])[0]).removeprefix("AplPay ").title()[:34]
            L.append(f"| {r['date']} | {what} | {r['name'][:24]} | ${-r['amount']:,.2f} |")
        paid = -sum(r["amount"] for r in mine)
        share = paid * (1 - my_pct)
        grand += share
        L += [f"| | **You paid** | | **${paid:,.2f}** |", "", f"{partner}'s {1 - my_pct:.0%}: **${share:,.2f}**"]
        if joint:
            L.append(f"\n(Also {money(-sum(r['amount'] for r in joint))} on the joint card, already shared through it: "
                     + ", ".join(f"{normalize(r['description'])} {money(-r['amount'])}" for r in joint) + ".)")
        L.append("")
    L += [f"## Total {partner} owes you: **${grand:,.2f}**", "",
          f"_Only charges on your own accounts are counted. If {partner} paid for anything on these trips himself, subtract half of it._"]
    out = "\n".join(L) + "\n"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / ("owe-" + "-".join(c.lower().replace(" ", "_") for c in args.categories) + ".md")).write_text(out)
    print(out)


def shared_items(con, cfg: dict, since: str) -> list[dict]:
    """Every posted transaction since `since` that affects what the partner owes."""
    partner = cfg.get("partner", "Partner")
    their = 1 - cfg.get("my_share_pct", 50) / 100
    joint_names = [n.lower() for n in cfg.get("joint_accounts", [])]
    household = set(cfg.get("household_categories", []))
    household_kw = [k.lower() for k in cfg.get("household_keywords", [])]
    not_household = [k.lower() for k in cfg.get("not_household_keywords", [])]
    one_off = set(cfg.get("one_off_categories", []))
    skip_joint = set(cfg.get("exclude_categories", [])) | {"Credit Card Payment", "Transfer"} | (ONE_TIME - {"Travel"})
    partner_kw = [k.lower() for k in cfg.get("partner_transfer_keywords", [partner])]
    review_kw = [k.lower() for k in cfg.get("review_keywords", [])]
    overrides = json.loads(SHARED_OVERRIDES.read_text()) if SHARED_OVERRIDES.exists() else {}
    out = []
    rows = con.execute(
        """SELECT t.*, a.name AS acct FROM transactions t JOIN accounts a ON a.id=t.account_id
           WHERE t.date >= ? AND t.pending = 0 ORDER BY t.date""", (since,)).fetchall()
    for r in rows:
        text = " ".join(f"{r['description']} {r['payee']}".lower().split())
        joint = any(n in r["acct"].lower() for n in joint_names)
        what = re.split(r"\s+DES:|\s+ID:|\s+Conf#", r["description"])[0]
        what = re.sub(r"^(AplPay|TST\*|SQ \*|B2P\*|IN \*)\s*|\s+[A-Z]{2}$|\d{4,}|#\S*", " ", what.strip())
        what = re.sub(r"\s+", " ", what).strip().title()[:40]
        item = {"key": f"{r['account_id']}|{r['id']}", "date": r["date"], "what": what, "account": r["acct"][:24],
                "category": r["category"], "total": round(-r["amount"], 2)}
        if r["category"] in one_off:
            item.update(kind="trip", share=round(-r["amount"] * their, 2))
        elif joint:
            if r["category"] == "Credit Card Payment" and r["amount"] > 0:
                item.update(kind="card paid", share=0.0, total=r["amount"])
            elif r["category"] in skip_joint:
                continue
            else:
                item.update(kind="joint card", share=round(-r["amount"] * their, 2))
        elif r["category"] in ("Transfer", "Payments to People (review)") and any(k in text for k in partner_kw):
            # Money from the partner lowers what they owe; money sent to them raises it.
            item.update(kind=f"from {partner}" if r["amount"] > 0 else f"to {partner}", share=round(-r["amount"], 2),
                        total=abs(r["amount"]))
        elif any(k in text for k in review_kw):
            item.update(kind="review", share=0.0, total=r["amount"])
        elif r["amount"] < 0 and (r["category"] in household or any(k in text for k in household_kw)) \
                and not any(k in text for k in not_household):
            item.update(kind="household bill", share=round(-r["amount"] * their, 2))
        else:
            continue
        pct = overrides.get(row_id(item["key"]))
        if pct is not None and item["kind"] in ("household bill", "joint card", "trip"):
            item["share"] = round(-r["amount"] * float(pct) / 100, 2)
            item["override"] = float(pct)
        out.append(item)
    return out


def cmd_ledger(args) -> None:
    """Add new shared items to the running ledger in budget/shared and rewrite OWED.md."""
    con = db()
    cfg = load_config().get("split") or sys.exit("No split settings found (budget/shared/split.json).")
    partner, me = cfg.get("partner", "Partner"), cfg.get("me", "Me")
    ledger = json.loads(LEDGER_JSON.read_text()) if LEDGER_JSON.exists() else {"start": args.start or date.today().strftime("%Y-%m-01"), "entries": []}
    have = {e["key"]: e for e in ledger["entries"]}
    added, changed = [], False
    for item in shared_items(con, cfg, ledger["start"]):
        old = have.get(item["key"])
        if old is None:
            ledger["entries"].append(item)
            have[item["key"]] = item
            added.append(item)
        elif not old.get("locked") and (old["share"], old["total"]) != (item["share"], item["total"]):
            old.update(item)  # amount changed after posting
            changed = True
    ledger["entries"].sort(key=lambda e: (e["date"], e["key"]))
    # Only touch the files when something changed, so a quiet day makes no commit.
    if added or changed or not LEDGER_MD.exists():
        ledger["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        SHARED.mkdir(exist_ok=True)
        LEDGER_JSON.write_text(json.dumps(ledger, indent=1) + "\n")
    else:
        print(f"No new shared items. {partner} owes {me} ${sum(e['share'] for e in ledger['entries']):,.2f}.")
        return

    E = ledger["entries"]
    balance = sum(e["share"] for e in E)
    L = [f"# What {partner} owes {me}", "",
         f"## {partner} owes {me} **${balance:,.2f}**" if balance >= 0 else f"## {me} owes {partner} **${-balance:,.2f}**",
         "", f"_Last changed {ledger['updated']} from {me}'s linked accounts. Shared items only; nothing personal is listed here._", ""]
    review = [e for e in E if e["kind"] == "review" and not e.get("resolved")]
    if review:
        L += ["### Needs a look", ""]
        L += [f"- {e['date']}: {e['what']} {money(e['total'])}. If this was from {partner}, tell Claude and it gets counted." for e in review]
        L.append("")
    L += ["## By month", "", f"| Month | Shared costs {me} paid | {partner}'s share | {partner} paid | Added to balance |", "|---|---:|---:|---:|---:|"]
    months = sorted({e["date"][:7] for e in E}, reverse=True)
    for m in months:
        es = [e for e in E if e["date"][:7] == m]
        costs = sum(e["total"] for e in es if e["kind"] in ("household bill", "joint card", "trip", "carried over"))
        owed = sum(e["share"] for e in es if e["share"] > 0 and not e["kind"].startswith("to "))
        paid = -sum(e["share"] for e in es if e["kind"].startswith("from "))
        L.append(f"| {m} | {money(costs)} | {money(owed)} | {money(paid)} | {money(sum(e['share'] for e in es))} |")
    for m in months:
        L += ["", f"### {m}", "", f"| Date | What | Type | Amount | {partner}'s part |", "|---|---|---|---:|---:|"]
        for e in reversed([e for e in E if e["date"][:7] == m]):
            part = "" if e["share"] == 0 else (f"${e['share']:,.2f}" if e["share"] > 0 else f"-${-e['share']:,.2f}")
            note = f" ({e['note']})" if e.get("note") else ""
            L.append(f"| {e['date']} | {e['what']}{note} | {e['kind']} | ${e['total']:,.2f} | {part} |")
    L += ["", "## How this works", "",
          f"- Household bills {me} pays (mortgage, electric, water and other utilities) and every charge on the joint Gold card are split "
          f"{100 - cfg.get('my_share_pct', 50)}% to {partner}. Gold card charges count when they post, so paying the card bill doesn't count them again.",
          "- Shared trips are listed as trip. Payments between you lower or raise the balance.",
          f"- Venmo cash-outs are listed under Needs a look, since a cash-out can include money from other people."]
    LEDGER_MD.write_text("\n".join(L) + "\n")
    print(f"{len(added)} new item(s). {partner} owes {me} ${balance:,.2f}." if balance >= 0 else f"{len(added)} new item(s). {me} owes {partner} ${-balance:,.2f}.")
    for e in added:
        print(f"  + {e['date']} {e['what']} [{e['kind']}] {partner}'s part {e['share']:+,.2f}")


def cmd_statement(args) -> None:
    """Monthly statement for the partner: balance carried in, the month's shared items, payments, and the total.

    Writes statement.txt, statement.html and subject.txt to out_dir. Extra payments (recorded on the
    dashboard, e.g. Venmo) can be passed as a JSON list of {date, amount, note}.
    """
    import html as H
    cfg = load_config().get("split") or sys.exit("No split settings found.")
    partner, me = cfg.get("partner", "Partner"), cfg.get("me", "Me")
    L = json.loads(LEDGER_JSON.read_text())
    E = list(L["entries"])
    if args.payments:
        for i, p in enumerate(json.loads(Path(args.payments).read_text())):
            E.append({"key": f"recorded|{i}", "date": str(p["date"]), "what": "Payment recorded on the dashboard" + (f" ({p['note']})" if p.get("note") else ""),
                      "kind": f"from {partner}", "total": float(p["amount"]), "share": -float(p["amount"]), "category": ""})
    ym = args.month or prev_months(date.today().strftime("%Y-%m"), 1)[0]
    s, e = month_bounds(ym)
    month_name = datetime.strptime(ym, "%Y-%m").strftime("%B %Y")
    before = sum(x["share"] for x in E if x["date"] < s)
    items = sorted([x for x in E if s <= x["date"] < e], key=lambda x: x["date"])
    after = sum(x["share"] for x in E if x["date"] >= e)
    total = before + sum(x["share"] for x in items) + after

    def group(x):
        k = x["kind"]
        if k == "household bill":
            return "Mortgage" if x.get("category") == "Housing" else "Household utilities"
        if k == "joint card":
            return "Gold card charges"
        if k in ("trip", "carried over"):
            return "Trips and one-offs"
        if k.startswith("from "):
            return f"Payments from {partner}"
        if k.startswith("to "):
            return f"Money {me} sent {partner}"
        return None
    groups: dict[str, list] = defaultdict(list)
    for x in items:
        g = group(x)
        if g:
            groups[g].append(x)
    order = ["Mortgage", "Household utilities", "Gold card charges", "Trips and one-offs", f"Money {me} sent {partner}", f"Payments from {partner}"]
    m = lambda v: f"-${-v:,.2f}" if v < 0 else f"${v:,.2f}"
    zelle = args.zelle or "Dani"
    owes_line = (f"You owe {me} {m(total)}." if total > 0.005 else
                 f"{me} owes you {m(-total)}." if total < -0.005 else "You and Dani are even.")
    subject = (f"Shared bills for {month_name}: you owe {me} {m(total)}" if total > 0.005 else f"Shared bills for {month_name}")

    # Plain text
    T = [f"Hi {partner},", "", f"Here's our shared bills summary for {month_name}. {owes_line}", "",
         f"Balance from before {month_name}: {m(before)}"]
    for g in order:
        if g in groups:
            T.append(f"{g}: {m(sum(x['share'] for x in groups[g]))}")
    if abs(after) > 0.005:
        T.append(f"Since {month_name} ended: {m(after)}")
    T += [f"Total you owe now: {m(total)}", ""]
    if total > 0.005:
        T += [f"To pay, send {m(total)} with Zelle to {me} at {zelle}. Open your bank app, choose Send with Zelle, and enter that number.",
              "Zelle payments are picked up automatically, so you don't need to tell me when you've paid.", ""]
    T.append(f"Every item for {month_name} (your half):")
    for g in order:
        for x in groups.get(g, []):
            T.append(f"  {x['date'][5:]}  {x['what'][:48]:48}  {m(x['total']):>11}  your part {m(x['share'])}")
    T += ["", "Shared costs are split 50/50: the mortgage, utilities, every Gold card charge and shared trips.",
          "This email was put together automatically from Dani's accounts by Claude."]
    # HTML
    rows = "".join(
        f"<tr><td style='padding:4px 8px;color:#666'>{H.escape(x['date'][5:])}</td><td style='padding:4px 8px'>{H.escape(x['what'])}</td>"
        f"<td style='padding:4px 8px;color:#666'>{H.escape(group(x))}</td><td style='padding:4px 8px;text-align:right'>{m(x['total'])}</td>"
        f"<td style='padding:4px 8px;text-align:right;font-weight:600'>{m(x['share'])}</td></tr>"
        for g in order for x in groups.get(g, []))
    summary = "".join(f"<tr><td style='padding:4px 8px'>{H.escape(g)}</td><td style='padding:4px 8px;text-align:right'>{m(sum(x['share'] for x in groups[g]))}</td></tr>"
                      for g in order if g in groups)
    pay = (f"<p style='font-size:16px'><b>To pay:</b> send <b>{m(total)}</b> with Zelle to {H.escape(me)} at <b>{H.escape(zelle)}</b>. "
           "Open your bank app, choose Send with Zelle, and enter that number. Zelle payments are picked up automatically, "
           "so you don't need to tell me when you've paid.</p>") if total > 0.005 else ""
    after_row = f"<tr><td style='padding:4px 8px'>Since {H.escape(month_name)} ended</td><td style='padding:4px 8px;text-align:right'>{m(after)}</td></tr>" if abs(after) > 0.005 else ""
    Hh = f"""<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#222;max-width:640px">
<p>Hi {H.escape(partner)},</p>
<p>Here's our shared bills summary for {H.escape(month_name)}.</p>
<p style="font-size:28px;margin:12px 0"><b>{H.escape(owes_line)}</b></p>
{pay}
<h3 style="margin:20px 0 6px">Summary</h3>
<table style="border-collapse:collapse;font-size:14px">
<tr><td style="padding:4px 8px">Balance from before {H.escape(month_name)}</td><td style="padding:4px 8px;text-align:right">{m(before)}</td></tr>
{summary}{after_row}
<tr><td style="padding:6px 8px;border-top:1px solid #ccc"><b>Total you owe now</b></td><td style="padding:6px 8px;border-top:1px solid #ccc;text-align:right"><b>{m(total)}</b></td></tr>
</table>
<h3 style="margin:20px 0 6px">Every item for {H.escape(month_name)}</h3>
<table style="border-collapse:collapse;font-size:13px">
<tr style="color:#666"><th style="text-align:left;padding:4px 8px">Date</th><th style="text-align:left;padding:4px 8px">What</th><th style="text-align:left;padding:4px 8px">Type</th><th style="text-align:right;padding:4px 8px">Amount</th><th style="text-align:right;padding:4px 8px">Your part</th></tr>
{rows}
</table>
<p style="color:#666;font-size:13px;margin-top:20px">Shared costs are split 50/50: the mortgage, utilities, every Gold card charge and shared trips. This email was put together automatically from Dani's accounts by Claude.</p>
</div>"""
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "statement.txt").write_text("\n".join(T) + "\n")
    (out / "statement.html").write_text(Hh)
    (out / "subject.txt").write_text(subject + "\n")
    print(subject)


DRAFT_NAMES = {"Cmg Mortgage Inc": "Mortgage (CMG)", "American Express": "AmEx card autopay", "Dept Education": "Student loan",
               "Fpl Direct": "FPL electric", "Morgan Stanley": "Morgan Stanley investing", "Chase Credit Crd": "Chase card autopay",
               "Cfg": "Lexus car loan"}


def cmd_export(args) -> None:
    """Write ledger.json and drafts.json ({rows, meta}) for the shared bills dashboard."""
    con = db()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    L = json.loads(LEDGER_JSON.read_text())
    rows = [{"id": row_id(e["key"]),
             "date": e["date"], "month": e["date"][:7], "what": e["what"] + (f" ({e['note']})" if e.get("note") else ""),
             "type": e["kind"], "category": e.get("category") or "", "paid_with": e.get("account", ""),
             "amount": round(e["total"], 2), "tucker_part": round(e["share"], 2),
             "split": e.get("override", 50.0) if e["kind"] in ("household bill", "joint card", "trip") else None} for e in L["entries"]]
    (out / "ledger.json").write_text(json.dumps({"rows": rows, "meta": [
        {"label": "Built from", "value": "budget/shared/ledger.json in TxNathans/Tucker-Dani-Home"},
        {"label": "Ledger updated", "value": L.get("updated", "")}]}, indent=1))
    drafts, start = build_drafts(con)
    (out / "drafts.json").write_text(json.dumps({"rows": drafts, "meta": [
        {"label": "Built from", "value": f"Auto-drafts in Dani's checking and savings since {start[:7]} (monthly average)"}]}, indent=1))
    print(f"Wrote {len(rows)} ledger rows and {len(drafts)} auto-drafts to {out}")


def build_drafts(con) -> tuple[list[dict], str]:
    since = full_months(con, prev_months(date.today().strftime("%Y-%m"), 4))
    start = (min(since) + "-01") if since else "0000"
    q = con.execute(
        """SELECT t.date, t.amount, t.description, t.category, a.name FROM transactions t JOIN accounts a ON a.id=t.account_id
           WHERE t.amount < 0 AND a.kind IN ('checking','savings') AND t.date >= ?
             AND t.category NOT IN ('Payments to People (review)', 'Transfer', 'Venmo / Zelle (review)')""", (start,)).fetchall()
    groups: dict[tuple, list] = defaultdict(list)
    for r in q:
        groups[(normalize(r["description"]), r["name"])].append(r)
    n = max(len({r["date"][:7] for r in q}), 1)
    drafts = []
    for (name, acct), txs in groups.items():
        months = {t["date"][:7] for t in txs}
        if len(months) < min(2, n):
            continue
        amts = [-t["amount"] for t in txs]
        drafts.append({"what": DRAFT_NAMES.get(name, name), "day": int(statistics.median(int(t["date"][8:10]) for t in txs)),
                       "from_account": "Savings" if "savings" in acct.lower() else "Checking",
                       "monthly": round(sum(amts) / len(months), 2), "varies": max(amts) > 1.15 * min(amts),
                       "category": txs[-1]["category"], "shared": "yes" if txs[-1]["category"] in ("Housing", "Utilities") else "no"})
    drafts.sort(key=lambda d: d["day"])
    return drafts, start


RECURRING_CATS = {"Housing", "Utilities", "Insurance", "Subscriptions", "Loan Payments", "Fees & Interest",
                  "Sports & Fitness", "Health & Fitness"}


def cmd_export_personal(args) -> None:
    """Files for Dani's private money dashboard. Nothing here goes to git."""
    con = db()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    first = con.execute("SELECT MIN(date) FROM transactions").fetchone()[0] or date.today().isoformat()
    this = date.today().strftime("%Y-%m")
    months_all = sorted({r[0] for r in con.execute("SELECT DISTINCT substr(date,1,7) FROM transactions")})
    full = set(full_months(con, months_all))
    r2 = lambda v: round(v, 2)
    months, cats = [], []
    for m in months_all:
        if m not in full and m != this:
            continue
        t = month_totals(con, m)
        months.append({"month": m, "complete": m != this, "take_home": r2(t["income"]), "regular": r2(t["regular"]),
                       "tucker_regular": r2(t["partner_regular"]), "my_regular": r2(t["my_regular"]),
                       "one_time": r2(t["one_time"]), "my_one_time": r2(t["my_one_time"]), "saved": r2(t["saved"])})
        for c, v in t["by_cat"].items():
            tp = t["partner_by_cat"].get(c, 0.0)
            cats.append({"month": m, "category": c, "total": r2(v), "tucker_part": r2(tp), "mine": r2(v - tp),
                         "one_time": c in ONE_TIME})
    pay = defaultdict(lambda: {"to_checking": 0.0, "to_savings": 0.0})
    for r in con.execute("""SELECT t.date, t.amount, a.kind FROM transactions t JOIN accounts a ON a.id=t.account_id
                            WHERE t.category='Income' AND (t.description LIKE '%PAYROLL%')"""):
        pay[r["date"]]["to_savings" if r["kind"] == "savings" else "to_checking"] += r["amount"]
    paychecks = [{"date": d, "to_checking": r2(v["to_checking"]), "to_savings": r2(v["to_savings"]),
                  "total": r2(v["to_checking"] + v["to_savings"])} for d, v in sorted(pay.items())]
    accounts = [{"name": a["name"], "institution": a["institution"], "kind": a["kind"], "balance": r2(a["balance"] or 0),
                 "as_of": a["balance_date"]} for a in con.execute("SELECT * FROM accounts ORDER BY kind, name")]
    # Recurring charges anywhere (cards included): a subscription and annual-fee watch.
    groups: dict[str, list] = defaultdict(list)
    for r in con.execute("""SELECT t.date, t.amount, t.description, t.payee, t.category FROM transactions t
                            WHERE t.amount < 0 AND t.pending = 0 AND t.category NOT IN
                            ('Transfer','Credit Card Payment','Payments to People (review)','Savings & Investing','Venmo / Zelle (review)')"""):
        if r["category"] in RECURRING_CATS or "fee" in r["description"].lower():
            name = normalize(r["description"])
            groups[DRAFT_NAMES.get(name, name)].append(r)
    recurring = []
    for name, txs in groups.items():
        ms = sorted({t["date"][:7] for t in txs})
        amts = [-t["amount"] for t in txs]
        fee = any(("annual" in t["description"].lower() or "membership fee" in t["description"].lower()) for t in txs)
        if not fee and (len(ms) < 2 or len(txs) > len(ms) * 2):
            continue
        med = statistics.median(amts)
        if not fee and max(amts) > med * 1.6:
            continue
        last = max(txs, key=lambda t: t["date"])
        yearly = med if fee else med * 12
        recurring.append({"name": name, "category": txs[-1]["category"], "typical": r2(med), "yearly": r2(yearly),
                          "kind": "annual fee" if fee else "monthly", "last_date": last["date"], "last_amount": r2(-last["amount"]),
                          "first_seen": min(t["date"] for t in txs), "went_up": (-last["amount"]) > med * 1.10,
                          "maybe_business": "keepa" in name.lower()})
    recurring.sort(key=lambda x: -x["yearly"])
    credits = [{"date": r["date"], "card": r["name"], "credit": " ".join(r["description"].split())[:40], "amount": r2(r["amount"])}
               for r in con.execute("""SELECT t.date, t.amount, t.description, a.name FROM transactions t JOIN accounts a ON a.id=t.account_id
                                       WHERE a.kind='credit' AND t.amount > 0 AND lower(t.description) LIKE '%credit%'
                                         AND t.category != 'Credit Card Payment' ORDER BY t.date""")]
    drafts, _ = build_drafts(con)
    note = [{"label": "Built from", "value": f"Dani's linked accounts via SimpleFIN, {first} to {date.today().isoformat()}"}]
    for name, rows in [("months", months), ("categories", cats), ("paychecks", paychecks), ("accounts", accounts),
                       ("recurring", recurring), ("credits", credits), ("drafts", drafts)]:
        (out / f"{name}.json").write_text(json.dumps({"rows": rows, "meta": note}, indent=1))
    print("Wrote " + ", ".join(f"{n} ({len(r)})" for n, r in [("months", months), ("categories", cats), ("paychecks", paychecks),
          ("accounts", accounts), ("recurring", recurring), ("credits", credits), ("drafts", drafts)]))


def upcoming_drafts(con, days: int) -> list[dict]:
    drafts, _ = build_drafts(con)
    today = date.today()
    out = []
    for i in range(1, days + 1):
        d = today + timedelta(days=i)
        for x in drafts:
            if x["day"] == d.day:
                out.append({**x, "on": d.isoformat()})
    return out


def cmd_alerts(args) -> None:
    """Warn when checking or savings won't cover the auto-drafts due in the next N days."""
    con = db()
    bal = {k: con.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE kind=?", (k,)).fetchone()[0] for k in ("checking", "savings")}
    due = upcoming_drafts(con, args.days)
    warned = False
    for k, label in (("checking", "Checking"), ("savings", "Savings")):
        need = sum(x["monthly"] for x in due if x["from_account"].lower() == k)
        if need and bal[k] < need + args.cushion:
            warned = True
            items = ", ".join(f"{x['what']} ~${x['monthly']:,.0f} on {x['on'][5:]}" for x in due if x["from_account"].lower() == k)
            print(f"LOW BALANCE: {label} has ${bal[k]:,.2f} but about ${need:,.2f} drafts in the next {args.days} days ({items}). "
                  f"Move about ${need + args.cushion - bal[k]:,.0f} in before then.")
    if not warned:
        print(f"OK: balances cover the next {args.days} days of auto-drafts.")


def cmd_checkin(args) -> None:
    """Weekly summary: last 7 days of spending vs a usual week, bills coming up, and the shared balance."""
    con = db()
    today = date.today()
    start = (today - timedelta(days=7)).isoformat()
    rows = con.execute("""SELECT t.category, t.amount FROM transactions t JOIN accounts a ON a.id=t.account_id
                          WHERE t.date > ? AND a.kind NOT IN ('retirement','investment')""", (start,)).fetchall()
    week: dict[str, float] = defaultdict(float)
    for r in rows:
        if r["category"] not in NON_SPENDING and r["category"] != "Refund":
            week[r["category"]] -= r["amount"]
    hist = [month_totals(con, m) for m in full_months(con, prev_months(today.strftime("%Y-%m"), 3))]
    usual = defaultdict(float)
    for h in hist:
        for c, v in h["by_cat"].items():
            usual[c] += v / len(hist) / 4.33
    total = sum(week.values())
    print(f"Weekly check-in, week ending {today:%b %d}")
    print(f"Spent ${total:,.0f} this week (a usual week is about ${sum(v for c, v in usual.items() if c not in ONE_TIME):,.0f}).")
    hot = sorted(((c, v, usual.get(c, 0)) for c, v in week.items()
                  if v > usual.get(c, 0) * 1.3 + 25 and c not in RECURRING_CATS and c not in ONE_TIME),
                 key=lambda x: -(x[1] - x[2]))[:3]
    for c, v, u in hot:
        print(f"  Running high: {c} ${v:,.0f} (usual ${u:,.0f}/week)")
    due = upcoming_drafts(con, 7)
    if due:
        print("Coming up: " + "; ".join(f"{x['what']} ~${x['monthly']:,.0f} on {x['on'][5:]}" for x in due))
    if LEDGER_JSON.exists():
        bal = sum(e["share"] for e in json.loads(LEDGER_JSON.read_text())["entries"])
        print(f"Tucker owes you ${bal:,.2f}.")


def cmd_bills(args) -> None:
    """Auto-drafts out of checking/savings: what comes out, on what day, and how much cash to keep."""
    con = db()
    since = full_months(con, prev_months(date.today().strftime("%Y-%m"), 4))
    start = (min(since) + "-01") if since else "0000"
    rows = con.execute(
        """SELECT t.date, t.amount, t.description, t.payee, t.category, a.name FROM transactions t
           JOIN accounts a ON a.id=t.account_id
           WHERE t.amount < 0 AND a.kind IN ('checking','savings') AND t.date >= ?
             AND t.category NOT IN ('Payments to People (review)', 'Transfer', 'Venmo / Zelle (review)')""",
        (start,),
    ).fetchall()
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        groups[(normalize(r["description"]), r["name"])].append(r)
    nmonths = max(len({r["date"][:7] for r in rows}), 1)
    drafts = []
    for (name, acct), txs in groups.items():
        months = {t["date"][:7] for t in txs}
        if len(months) < min(2, nmonths):
            continue
        per_month = -sum(t["amount"] for t in txs) / len(months)
        days = sorted(int(t["date"][8:10]) for t in txs)
        drafts.append({"name": name, "acct": acct, "amt": per_month, "day": int(statistics.median(days)),
                       "cat": txs[-1]["category"], "varies": max(-t["amount"] for t in txs) > 1.15 * min(-t["amount"] for t in txs)})
    drafts.sort(key=lambda d: d["day"])
    L = ["# Auto-drafts from your bank accounts", "", "| Day | What | From | About | Category |", "|---:|---|---|---:|---|"]
    for d in drafts:
        L.append(f"| {d['day']} | {d['name']} | {d['acct'][:22]} | {money(d['amt'])}{' (varies)' if d['varies'] else ''} | {d['cat']} |")
    first = sum(d["amt"] for d in drafts if d["day"] <= 15)
    second = sum(d["amt"] for d in drafts if d["day"] > 15)
    L += ["", f"- Days 1 to 15: about **{money(first)}** comes out",
          f"- Days 16 to 31: about **{money(second)}** comes out",
          f"- Total per month: about **{money(first + second)}**", "",
          "Card autopays (marked varies) depend on that month's card spending. Keep at least the bigger half-month total, "
          "plus a cushion, in each account before its drafts hit."]
    out = "\n".join(L) + "\n"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "bills.md").write_text(out)
    print(out)


# ---------------------------------------------------------------- main

def main() -> None:
    p = argparse.ArgumentParser(description="Dani's budget tracker")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup", help="claim a SimpleFIN setup token")
    s.add_argument("token")
    s.set_defaults(fn=cmd_setup)
    s = sub.add_parser("sync", help="pull transactions from SimpleFIN")
    s.add_argument("--days", type=int)
    s.set_defaults(fn=cmd_sync)
    s = sub.add_parser("import", help="import a bank CSV export")
    s.add_argument("file")
    s.add_argument("--account", required=True)
    s.add_argument("--kind", choices=["checking", "savings", "credit", "retirement", "investment", "loan", "other"])
    s.add_argument("--flip", action="store_true", help="credit card CSV shows purchases as positive numbers")
    s.set_defaults(fn=cmd_import)
    sub.add_parser("accounts").set_defaults(fn=cmd_accounts)
    s = sub.add_parser("set-kind", help="fix an account's type")
    s.add_argument("name")
    s.add_argument("kind", choices=["checking", "savings", "credit", "retirement", "investment", "loan", "other"])
    s.set_defaults(fn=cmd_set_kind)
    s = sub.add_parser("report")
    s.add_argument("month", nargs="?")
    s.set_defaults(fn=cmd_report)
    sub.add_parser("plan").set_defaults(fn=cmd_plan)
    s = sub.add_parser("split", help="shared household costs and who owes whom")
    s.add_argument("month", nargs="?")
    s.set_defaults(fn=cmd_split)
    s = sub.add_parser("owe", help="split one-off shared costs, e.g.: owe Honeymoon Wedding")
    s.add_argument("categories", nargs="+")
    s.set_defaults(fn=cmd_owe)
    s = sub.add_parser("ledger", help="update the running list of what your partner owes (budget/shared/OWED.md)")
    s.add_argument("--start", help="first date for a new ledger, YYYY-MM-DD")
    s.set_defaults(fn=cmd_ledger)
    s = sub.add_parser("statement", help="monthly email statement for your partner")
    s.add_argument("out_dir")
    s.add_argument("--month", help="YYYY-MM (default: last month)")
    s.add_argument("--zelle", help="phone or email to show for Zelle")
    s.add_argument("--payments", help="JSON list of extra payments recorded on the dashboard")
    s.set_defaults(fn=cmd_statement)
    s = sub.add_parser("export-personal", help="files for Dani's private money dashboard")
    s.add_argument("out_dir")
    s.set_defaults(fn=cmd_export_personal)
    s = sub.add_parser("alerts", help="warn if balances won't cover upcoming auto-drafts")
    s.add_argument("--days", type=int, default=10)
    s.add_argument("--cushion", type=float, default=500)
    s.set_defaults(fn=cmd_alerts)
    sub.add_parser("checkin", help="weekly spending check-in").set_defaults(fn=cmd_checkin)
    s = sub.add_parser("export", help="write ledger.json and drafts.json for the shared bills dashboard")
    s.add_argument("out_dir")
    s.set_defaults(fn=cmd_export)
    sub.add_parser("bills", help="auto-draft calendar for your bank accounts").set_defaults(fn=cmd_bills)
    sub.add_parser("recategorize").set_defaults(fn=cmd_recategorize)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

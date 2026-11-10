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
REPORTS = DATA / "reports"

# IRS limits for 2026 (employee elective deferrals).
LIMIT_401K = 24_500
CATCHUP_401K_50 = 8_000

NON_SPENDING = {"Transfer", "Credit Card Payment", "Income", "Savings & Investing"}
MAX_WINDOW_DAYS = 85  # SimpleFIN Bridge allows 90 days per request
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
    return cfg


def load_rules() -> dict:
    with open(RULES_PATH) as f:
        return json.load(f)


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
        ("credit", ["credit", "card", "visa", "mastercard", "amex", "sapphire", "freedom", "discover"]),
        ("savings", ["savings", "money market", "high yield", "hysa", "cd "]),
        ("investment", ["brokerage", "invest", "individual", "stock"]),
        ("loan", ["loan", "mortgage", "auto", "student"]),
        ("checking", ["checking", "chk", "spending", "everyday"]),
    ]:
        if any(w in n for w in words):
            return kind
    return "other"


def categorize(desc: str, amount: float, kind: str, rules: dict) -> str:
    text = desc.lower()
    for cat, words in rules["rules"].items():
        if any(w.lower() in text for w in words):
            return cat
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
        desc = f"{r['payee'] or ''} {r['description'] or ''}"
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
    req = urllib.request.Request(claim_url, data=b"", method="POST", headers={"Content-Length": "0"})
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
    if not ACCESS_PATH.exists():
        sys.exit("Not connected yet. Run: python budget/budget.py setup YOUR_SETUP_TOKEN")
    access = urllib.parse.urlsplit(ACCESS_PATH.read_text().strip())
    base = f"{access.scheme}://{access.hostname}{':' + str(access.port) if access.port else ''}{access.path}"
    auth = base64.b64encode(
        f"{urllib.parse.unquote(access.username or '')}:{urllib.parse.unquote(access.password or '')}".encode()
    ).decode()
    q = urllib.parse.urlencode(
        {"start-date": int(start.timestamp()), "end-date": int(end.timestamp()), "pending": 1, "version": 2}
    )
    req = urllib.request.Request(f"{base}/accounts?{q}", headers={"Authorization": f"Basic {auth}"})
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


def month_totals(con, ym: str) -> dict:
    s, e = month_bounds(ym)
    rows = con.execute(
        """SELECT t.category, t.amount, t.description, t.payee, t.date, a.kind
           FROM transactions t JOIN accounts a ON a.id = t.account_id
           WHERE t.date >= ? AND t.date < ? AND a.kind NOT IN ('retirement', 'investment')""",
        (s, e),
    ).fetchall()
    income = sum(r["amount"] for r in rows if r["category"] == "Income")
    saved = -sum(r["amount"] for r in rows if r["category"] == "Savings & Investing" and r["amount"] < 0)
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
    return {"income": income, "spending": spending, "saved": saved, "by_cat": dict(by_cat), "refunds": refunds,
            "merchants": merchants, "count": len(rows)}


def normalize(desc: str) -> str:
    d = (desc or "").upper()
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
    hist = [month_totals(con, m) for m in prev_months(ym, 3)]
    hist = [h for h in hist if h["count"]]
    cfg = load_config()
    budgets = cfg.get("monthly_budgets", {})

    lines = [f"# Budget report: {ym}", ""]
    if ym == date.today().strftime("%Y-%m"):
        lines.append(f"_Month in progress (through {date.today():%b %d})._\n")
    net = cur["income"] - cur["spending"]
    lines += [
        f"- Income: **{money(cur['income'])}**",
        f"- Spending: **{money(cur['spending'])}**" + (f" (refunds {money(cur['refunds'])} already subtracted)" if cur["refunds"] else ""),
        f"- Moved to savings/investing: **{money(cur['saved'])}**",
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
    months = prev_months(this_month, 3)
    hist = [month_totals(con, m) for m in months]
    hist = [h for h in hist if h["count"]]
    lines = ["# Savings and 401(k) plan", ""]
    if cfg["_from_example"]:
        lines.append("_Using placeholder numbers from config.example.json. Copy it to budget/data/config.json and fill in your real pay and 401(k) details._\n")
    if not hist:
        sys.exit("Need at least one full month of transactions. Run sync first.")

    take_home = statistics.mean(h["income"] for h in hist)
    spend = statistics.mean(h["spending"] for h in hist)
    saved = statistics.mean(h["saved"] for h in hist)
    bills = sum(b["monthly"] for b in find_bills(con))
    liquid = con.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE kind IN ('checking','savings')").fetchone()[0]
    cash_savings = con.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE kind='savings'").fetchone()[0]
    card_debt = -con.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE kind='credit' AND balance<0").fetchone()[0]

    lines += [
        f"Based on the last {len(hist)} full month(s):",
        "",
        f"- Average take-home pay: **{money(take_home)}/month**",
        f"- Average spending: **{money(spend)}/month** (recurring bills about {money(bills)} of that)",
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
        lines.append(f"Gap: {money(gap)}. At {money(max(take_home - spend, 0) * 0.5)}/month (half your leftover) that takes about "
                     f"{gap / max((take_home - spend) * 0.5, 1):.0f} months.")
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
    sub.add_parser("recategorize").set_defaults(fn=cmd_recategorize)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

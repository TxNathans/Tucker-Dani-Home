# Dani's budget tracker

Pulls every bank account, credit card and savings account into one place (read-only),
sorts spending into categories, finds recurring bills, and works out how much to save
and what to put in the 401(k).

**Privacy:** this repo is shared with Tucker. Only the code is in git. Your transactions,
balances, settings and SimpleFIN key live in `budget/data/` on your own computer, and git
ignores that folder, so none of it gets pushed.

## One-time setup (about 15 minutes)

1. **Link your accounts in SimpleFIN Bridge.** Go to https://bridge.simplefin.org, sign up
   (about $15/year), and add each bank, credit card and savings account. You log into your
   banks there, not here. SimpleFIN is read-only: nothing in this tracker can move money.
2. **Make a setup token.** In SimpleFIN Bridge, choose *New app connection* and copy the
   setup token (one long string).
3. **Connect the tracker.** On your computer, from this repo's folder:
   ```bash
   git pull
   python budget/budget.py setup PASTE_TOKEN_HERE
   python budget/budget.py sync
   python budget/budget.py accounts
   ```
   The first sync pulls up to a year of history (whatever each bank allows).
   If an account's type looks wrong (for example savings shown as checking), fix it:
   `python budget/budget.py set-kind "High Yield" savings`
4. **Add your pay and 401(k) details.** Copy `budget/config.example.json` to
   `budget/data/config.json` and fill in your salary, current 401(k) percent, employer
   match, and any monthly category budgets. Your HR or benefits portal shows the match
   (for example "50% of the first 6%").

## Using it

| Command | What it does |
|---|---|
| `python budget/budget.py sync` | Pull the latest transactions (run daily or weekly) |
| `python budget/budget.py report` | This month: income, spending by category vs. your usual, top merchants, recurring bills |
| `python budget/budget.py report 2026-10` | Same for a past month |
| `python budget/budget.py plan` | Savings rate, emergency fund gap, and a 401(k) table and recommendation |
| `python budget/budget.py accounts` | Every account and balance |

Reports are also saved to `budget/data/reports/`. You can open Claude Code in this repo and
ask things like "read my October report and tell me where I can cut $300".

**Fixing categories:** anything the tracker can't place shows up under *Uncategorized* at
the bottom of the report. Add a keyword for it to `budget/categories.json` and run
`python budget/budget.py recategorize`.

**A bank SimpleFIN can't reach?** Download a CSV from the bank's website and import it:
`python budget/budget.py import statement.csv --account "Target Card" --kind credit --flip`
(use `--flip` when the card's CSV shows purchases as positive numbers).

## How it counts things
- Credit card payments and transfers between your own accounts are left out of spending, so nothing gets counted twice.
- Transfers to savings and brokerages count as savings.
- 401(k) money comes out before your paycheck lands, so income here is take-home pay.
- The 401(k) table uses the 2026 IRS limit ($24,500, plus $8,000 catch-up at 50 or older).
  Pre-tax contributions lower your take-home by less than the contribution because of the income tax saved.
- The plan always says get the full employer match first. It also says to build a 6-month
  emergency fund and pay off any card balance you carry before going much past 15%.

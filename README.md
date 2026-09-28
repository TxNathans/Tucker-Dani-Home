# Tucker & Dani — Home Base

One place for our notes and Claude context, so any computer we sign into has the same info.

## What already syncs on its own

Everything in our **Claude account** (chats, projects, project files, memory, artifacts)
lives in the cloud. Sign into claude.ai or the Claude app on any computer with the same
account and it's all there — nothing to copy.

This repo covers what does **not** sync automatically:

- **`CLAUDE.md`** — instructions and background Claude Code reads automatically whenever it
  works in this repo, on any computer.
- **`notes/`** — our own notes (business, home, personal) in plain Markdown.
- **`claude-export/`** — a backup copy of our Claude account data, if we want one.

## Using it on a new computer

```bash
git clone https://github.com/TxNathans/Tucker-Dani-Home.git
cd Tucker-Dani-Home
claude          # Claude Code picks up CLAUDE.md automatically
```

Pull before you start (`git pull`) and push when you're done (`git push`) so every computer
stays in sync.

## Backing up our Claude account data

1. On claude.ai, open **Settings → Privacy → Export data**.
2. Claude emails a download link; download the `.zip`.
3. Unzip it into `claude-export/` and commit.

## ⚠️ Keep this repo private

Before adding anything personal — business plans, finances, addresses, family details, chat
exports — make the repo private: GitHub → **Settings → General → Danger Zone → Change
visibility → Private**.

Never store passwords, full account numbers, SSNs, or API keys here, even in a private repo.
Use a password manager for those.

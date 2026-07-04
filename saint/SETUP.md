# Saint — Setup

Written from the steps actually taken and verified while building this codebase.
Do these in order; each step is checkable before moving to the next.

## 1. Python 3.12

This machine's system `python3` is 3.9.6 (Xcode Command Line Tools) — too old for
this project's dependencies. Homebrew is already installed here but has no newer
Python formula yet.

```sh
brew install python@3.12
cd saint
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
python --version   # confirm 3.12.x, not 3.9.x
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt   # only needed to run the test suite (pytest)
```

## 2. Google Cloud — two separate OAuth clients

Set up **two** Google Cloud projects (or two OAuth clients within existing
projects) — one for `personal_google`, one for `ogami_google`. Each needs:

1. The following APIs enabled: **Gmail API**, **Google Drive API**, **Google
   Docs API**, **Google Sheets API**, **Google Calendar API**, **Google Tasks
   API**.
2. An OAuth consent screen (External or Internal, your call).
3. An OAuth client of type **Desktop app** (not Web application — this avoids
   having to pre-register a redirect URI). Note the **Client ID** and **Client
   Secret**.

Scopes are requested by the code, not chosen in the Cloud Console UI — only
`gmail.modify`, `drive`, `calendar.events`, and `tasks` are ever requested.
**`gmail.send` is never requested; there is no way to grant it.**

## 3. Telegram bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram, `/newbot`, follow
   the prompts. Save the **bot token**.
2. Get your numeric Telegram user ID (e.g. message [@userinfobot](https://t.me/userinfobot)).
   This is your **owner ID** — only this ID may ever command the bot.

## 4. Fill in `.env`

```sh
cp .env.example .env
```

Edit `.env` and fill in: `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_OWNER_ID`, both Google accounts' `CLIENT_ID`/`CLIENT_SECRET`, and
`SAINT_TIMEZONE` (an IANA name, e.g. `America/New_York`). Leave `SPOTIFY_*` and
the token-path/budget/runtime defaults as-is unless you have a reason to change
them. **`.env` is gitignored — never commit it.**

## 5. Authorize both Google accounts

Run this from the venv (never inside Docker — there's no browser in a
container):

```sh
python authorize.py --account personal_google
```

A browser opens. Sign in with your **personal** Google account. Check the
consent screen before clicking through — confirm it does **not** list a "send
email on your behalf" permission. Repeat for the business account:

```sh
python authorize.py --account ogami_google
```

Confirm both token files landed in `secrets/` and are gitignored:

```sh
git status   # secrets/*.json should not appear as untracked
```

## 6. Run it

**Locally (recommended for first run):**

```sh
python main.py
```

**Or via Docker** (steady-state / Mac mini deployment), reusing the same
already-authorized tokens:

```sh
docker compose up --build
```

## 7. Smoke test

In Telegram:

1. `/briefing` → should reply with stub text within a few seconds.
2. Ask something Read-class, e.g. *"what's on my personal calendar this
   week?"* → answers directly, no approval prompt.
3. Ask something consequential, e.g. *"add a test event on my Ogami calendar
   tomorrow at 3pm"* → Saint replies that it's queued, then a **separate**
   message arrives with the proposed action and Approve/Reject buttons.
4. Tap **Reject** → confirms rejection; nothing appears on the calendar.
5. Repeat and tap **Approve** → confirms execution; the event appears on the
   real calendar.
6. From a different Telegram account, send Saint a message → it should not
   respond (owner-only allowlist).

## Notes on the two deployment environments

- **MacBook (now):** venv, browser available, easiest for `authorize.py` and
  day-to-day development.
- **Mac mini (later):** Docker for `main.py`, plus one local `authorize.py` run
  per account on the Mac mini itself (tokens aren't expected to transfer
  machine-to-machine) using a temporary venv there.

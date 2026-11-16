# Driving Simulation Study — Booking Website

A lightweight, mobile-friendly, multi-user booking system for research sessions, built with Flask and SQLite.

## Features
- Participants select an available slot and book using their name/email.
- Booked slots disappear immediately for everyone; a database constraint prevents double bookings.
- Unique confirmation link and self-service cancellation.
- Password-protected researcher dashboard to generate slots, remove slots, cancel bookings, and export CSV.
- Times interpreted in `America/Toronto` by default.
- No automatic emails (the confirmation screen tells participants to save their link).

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Set environment variables (see .env.example). On Windows PowerShell:
# $env:ADMIN_PASSWORD='your-long-random-password'
# $env:SECRET_KEY='a-long-random-secret'
python app.py
```

Go to http://127.0.0.1:5000 to see the participant page. Go to http://127.0.0.1:5000/admin to log in and create session slots. Before production, set ADMIN_PASSWORD and SECRET_KEY.

## Deploy

Deploy the folder as a Python web service on a provider supporting a **persistent writable volume**, such as a Railway service configured with a volume. Install `pip install -r requirements.txt` and launch with `gunicorn --workers 1 --bind 0.0.0.0:$PORT app:app`. Set environment variables as shown in `.env.example`. Mount a persistent volume and set `DATABASE_PATH` to an absolute file path **inside the mounted volume**. Without persistent storage, bookings can disappear after restart/deployment! Use a single worker with SQLite.

Once hosted, share your deployed public URL with participants. Only share the `/admin` link and password with your research team.

## Ethical / operational notes

- This is a research scheduling tool, **not** an informed consent system. Collect consent separately.
- Name and email are stored in plaintext in the application database. Use only research-board-approved hosting/storage, HTTPS, access controls, backups, and an appropriate retention/deletion policy.
- For real production use, add rate-limiting, CSRF protections, a password hashing / researcher identity solution, and email verification if required by your institution.
- Confirm that the experiment length (including setup and reset) is reflected in time slot durations.
- The system currently doesn't send email notifications or calendar invites; avoid claiming it does.


## New scheduling features (v2)

- Public booking page uses a navigable seven-day, Outlook-style week view. Blue events are available, grey are booked. Participant details are never sent to the public calendar.
- Admin **Gap between sessions (min)** is configurable (0–240, default 30). Example: 60 minute sessions with a 30 minute gap begin at 09:00, 10:30, 12:00. Daily end time limits the *end of the final session* (not the trailing break).
- Admin **Delete existing sessions** allows deletion of all unbooked slots with a typed `DELETE ALL` confirmation. Check **Also delete booked sessions** to delete all reservations too. This action is irreversible; export your CSV first.
- Existing SQLite data is kept on deployment; updating code does **not** automatically delete old sessions.
- GitHub/Railway deployment: upload changed `app.py`, `templates/index.html`, `templates/admin.html`, `static/style.css`, and **new** `static/calendar.js` to the repository, then redeploy. Do not upload a local database or replace the Railway volume.

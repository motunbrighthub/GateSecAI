# GateSecAI

An offline, AI-powered vehicle gate security system — built to replace
the paper gate logbook with something smarter: automatic license plate
recognition via camera, instant sync between entry and exit gates, and
an SMS-based panic alert system, all running **without needing internet
access**.

## What it does

- **Vehicle entry/exit logging** — replaces the paper logbook. A vehicle
  registered at the entry gate is instantly visible at the exit gate.
- **AI-powered plate scanning** — point a phone camera at a vehicle's
  plate, and GateSecAI reads it automatically using offline computer
  vision (OpenCV + EasyOCR). No internet required after the one-time
  model download.
- **Panic alert system** — any resident, with any phone (no app, no
  data plan needed), can send an SMS to trigger an instant alert on the
  security dashboard, via a connected GSM module.
- **Fully local** — runs on one PC on a local network (or a PC-created
  Wi-Fi hotspot with zero internet), so it works even where internet
  access is unreliable or unavailable.

## How the gates "sync"

Both the entry-gate device and the exit-gate device open the SAME web
app in a browser, over the local network. Because they both talk to one
running server backed by one database, a vehicle registered at entry
appears on the exit screen within seconds via auto-refresh — no manual
syncing needed.

## Project structure

```
GateSecAI/
├── app/
│   ├── main.py          # FastAPI routes (pages + JSON API)
│   ├── database.py       # DB connection/session setup (MySQL or SQLite)
│   ├── models.py         # Vehicle + PanicAlert table definitions
│   ├── schemas.py        # Request/response validation
│   ├── crud.py           # Database read/write functions
│   ├── vision.py         # Offline computer vision: plate detection + OCR
│   ├── gsm_panic.py       # GSM module listener for panic-alert SMS
│   └── captures/          # Captured vehicle photos (gitignored)
├── templates/              # HTML pages (Jinja2)
├── static/                  # CSS + JS (auto-refresh, camera capture UI)
├── .env                      # Local database & GSM configuration
├── .env.example
├── requirements.txt
└── README.md
```

## Setup

1. **Install Python 3.10+** if you don't have it.

2. **Create a virtual environment and install dependencies:**

   ```bash
   cd GateSecAI
   python -m venv gate
   gate\Scripts\activate      # on Mac/Linux: source gate/bin/activate
   pip install -r requirements.txt
   ```

   This installs FastAPI, SQLAlchemy, the MySQL driver, and the
   computer-vision stack (OpenCV, EasyOCR) — the CV install is the
   largest part and can take a few minutes.

3. **Configure your database.** Copy `.env.example` to `.env` and fill
   in your MySQL details:

   ```
   DB_HOST=localhost
   DB_PORT=3306
   DB_NAME=gatesecai
   DB_USER=root
   DB_PASSWORD=your_password
   ```

   Create the database itself first (the app creates the tables, not
   the database):
   ```sql
   CREATE DATABASE IF NOT EXISTS gatesecai;
   ```

4. **(Optional) Enable the panic-alert SMS listener.** If you have a
   SIM800L GSM module wired up, find its COM port in Device Manager
   and add to `.env`:
   ```
   GSM_PORT=COM5
   ```
   Without this set, the app runs fine — the panic-alert feature just
   stays off, except for the built-in **simulate** test tool on the
   dashboard (useful for demos without hardware).

5. **Run the server:**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Watch the startup output — it prints which database it's using and
   whether the GSM listener is active, so misconfiguration is obvious
   immediately instead of silently failing.

6. **Open it:**
   - On the server machine: `http://localhost:8000`
   - On other devices on the same network/hotspot: `http://<server-ip>:8000`

   Point the entry gate device at `/register` (or `/scan` for the
   camera flow) and the exit gate device at `/checkout`. `/panic-alerts`
   shows active emergency alerts.

## Running fully offline (no router needed)

If there's no local Wi-Fi router available, turn on **Windows Mobile
Hotspot** on the server PC (Settings → Network & Internet → Mobile
hotspot). This creates its own local network — always at a fixed
address, typically `192.168.137.1` — that other gate devices connect
to directly. No internet connection is required for any of this.

## Notes

- **Backups:** if using SQLite instead of MySQL, the whole database is
  one file (`gateman.db`) — copy it anywhere to back it up.
- **Security:** this version has no login/authentication yet — anyone
  on the local network can access every page. Recommended before real
  deployment: guard login accounts and an audit trail of who checked
  vehicles in/out.
- **OCR accuracy:** works best with a clean, well-lit, front-facing shot
  of the plate. Always review/edit the detected plate number before
  saving — it's a shortcut, not a silent authority.
- **Panic alerts:** the SMS trigger keywords (`HELP`, `PANIC`, `SOS`)
  are configurable in `app/gsm_panic.py`.

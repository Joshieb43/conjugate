<p align="center">
  <img src="gorilla.png" alt="Conjugate logo" width="120">
</p>

<h1 align="center">Conjugate Training Tool</h1>

<p align="center">
  A workout planner and logger for the conjugate method: plan your max-effort and dynamic-effort days, then log your sets and track PRs, all in one page.
</p>

<p align="center">
  <a href="https://conjugateday.streamlit.app/"><strong>Open the app →</strong></a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-7740ba">
  <img alt="Streamlit" src="https://img.shields.io/badge/built%20with-Streamlit-9863d7">
  <img alt="License" src="https://img.shields.io/badge/use-personal%20training-332348">
</p>

---

## What it does

The conjugate method (popularized by Westside Barbell) splits the training week into four sessions:

| Day | Goal | What the app gives you |
|---|---|---|
| **ME Upper** | Work up to a heavy single, triple or 5 on a bench variation | Top-set load, warmup ramp, plates per side |
| **DE Upper** | Fast speed-bench sets at 50–60% | Wave-week percentages, band/chain loading |
| **ME Lower** | Heavy squat or deadlift variation | Top-set load based on that variation's own max |
| **DE Lower** | Speed squats or speed pulls | Wave percentages, sets × reps, plates |

Pick the day, enter your maxes, and the app builds the session: main lift, warmups, accessories and a place to log every set.

## Features

**Planning**
- Load calculations for ME and DE days, rounded to your plate increment
- 3-week DE wave (50 / 55 / 60% by default, editable)
- Band and chain support. You can keep the bar at the wave % with bands on top (Westside style), or subtract the band tension from the bar
- Plate calculator for the top set and every warmup
- Accessory suggestions for upper, squat and deadlift days, with editable sets, reps and RPE, plus links to technique videos
- lb or kg

**Logging and progress**
- Log sets in a couple of taps. The weight, reps and RPE fields prefill from your last set
- Rest timer that starts automatically after each set (60 s on DE days, 3 min on ME days)
- Estimated 1RM for each set (Epley formula, adjusted for reps left in reserve from RPE)
- Progress tab with a trend chart per exercise, a PR board and your ME rotation history
- **ME rotation reminders.** The app warns you when you've used the same max-effort variation for 3 or more weeks in a row, and shows "last time you did this" with your best set
- CSV export and import (imports skip duplicate sets)
- Optional Google Sheets sync, so your history survives refreshes and app restarts

## Using the app

1. **Today tab:** choose the training day and wave week, then enter your training maxes.
2. Follow the warmups, then hit the top set or the speed sets shown.
3. **Log tab:** record each set. The rest timer starts on its own.
4. **Progress tab:** check your e1RM trends, PRs and which ME variations you've been rotating through.
5. **Settings tab:** units, rounding, custom warmup percentages and band-loading mode.

> **Your log lives in your browser session** unless Google Sheets sync is set up. Export a CSV before you close the tab if you want to keep your sets.

## Run it locally

```bash
git clone https://github.com/Joshieb43/conjugate.git
cd conjugate
pip install -r requirements.txt
streamlit run APP.py
```

The app opens at `http://localhost:8501`.

## Optional: Google Sheets sync

1. Create a Google Sheet with a tab named `logs`.
2. In Google Cloud, create a service account, download its JSON key, and share the sheet with the service account's email address (Editor access).
3. Add your secrets. Locally, put them in `.streamlit/secrets.toml`. On Streamlit Cloud, go to **App settings → Secrets**:

```toml
sync_key = "choose-a-password"

[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID"
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
```

4. Open the **Settings** tab in the app and enter your `sync_key`. Visitors who don't have the key keep a private, session-only log, so their sets never end up in your sheet.

> Never commit `secrets.toml` to GitHub.

## Project structure

```
conjugate/
├── APP.py                 # The whole app
├── requirements.txt       # streamlit, pandas, st-gsheets-connection
├── .streamlit/
│   └── config.toml        # Purple theme
├── gorilla.png            # Logo
└── rpe_chart.png          # RPE reference chart (Settings tab)
```

## Disclaimer

Loads are starting estimates based on the maxes you enter. Let bar speed and RPE decide the day's actual weights. Check with a qualified coach or medical professional before starting a new training program.

---

<p align="center">Built by <a href="https://github.com/Joshieb43">Josh B</a> · <a href="https://joshbudimir.com">joshbudimir.com</a></p>

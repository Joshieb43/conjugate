"""Conjugate Training Tool — single-page workout dashboard.

What's new in this version
- Fixed the DE Lower crash (selectbox does not accept `horizontal`).
- Optional Google Sheets sync so your log survives refreshes and app sleeps.
- Estimated 1RM (Epley, RPE-adjusted) and per-variation maxes for ME days.
- Rotation reminders and "last time you did this" for ME variations.
- Plate calculator, rest timer, lb/kg toggle, band-loading modes.
- Tabs for a phone-friendly layout; CSV import skips duplicate sets.

Requirements: streamlit, pandas. For Google Sheets sync also install
st-gsheets-connection and add a [connections.gsheets] block to secrets.
"""

import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent

ACCESSORY_DEFAULTS = {
    "Upper": [
        ("Close-grip Bench", 3, 6, 8),
        ("Incline Dumbbell Press", 3, 8, 7.5),
        ("Pendlay Row", 4, 6, 8),
        ("Face Pulls", 3, 15, 7),
        ("Tricep Pressdown", 3, 10, 7),
        ("Overhead Press", 3, 5, 8),
        ("Lat Pulldown", 3, 8, 7.5),
        ("Dumbbell Row", 4, 8, 8),
        ("Banded Push-ups", 3, 10, 7),
        ("Hammer Curl", 3, 10, 7),
    ],
    "Lower": [
        ("Romanian Deadlift", 3, 6, 8),
        ("Reverse Lunges", 3, 8, 7.5),
        ("GHR / Hamstring Curl", 3, 8, 8),
        ("Back Extensions", 3, 12, 7),
        ("Ab Wheel / Plank", 3, 30, 7),
        ("Front Squat (variations)", 3, 5, 8),
        ("Goblet Squat", 3, 8, 7.5),
        ("Leg Press", 3, 10, 7),
        ("Calf Raises", 4, 12, 7),
        ("Hip Thrust", 3, 8, 8),
        ("Hanging Leg Raise", 3, 10, 7),
        ("Ab Wheel", 3, 10, 7.5),
        ("Plank", 3, 60, 7),
        ("Cable Crunch", 3, 12, 7),
        ("Russian Twist", 3, 20, 7),
    ],
    "Deadlift": [
        ("Deficit Deadlift", 3, 3, 8),
        ("Rack Pulls", 3, 5, 8),
        ("Bent-over Row", 4, 6, 8),
        ("Hamstring Curl", 3, 10, 7),
        ("Back Extensions", 3, 12, 7),
        ("Block Pulls", 3, 3, 8),
        ("Kettlebell Swings", 3, 12, 7),
        ("Glute Bridge", 3, 8, 7.5),
        ("Farmer Carries", 3, 40, 7),
        ("Single-leg RDL", 3, 8, 7.5),
    ],
}

DAY_TYPES = ["DE Upper", "ME Upper", "DE Lower", "ME Lower"]
WAVE_DEFAULTS = {1: 50.0, 2: 55.0, 3: 60.0}
LOG_COLUMNS = ["timestamp_utc", "day", "exercise", "weight_lb", "reps", "rpe", "wave_week", "role"]
REQUIRED_COLUMNS = LOG_COLUMNS[:-1]  # "role" is optional so older CSV exports still import.
ME_VARIATIONS = {
    "Upper": ["Competition Bench", "Close-grip Bench", "Floor Press", "Board Press", "Incline Bench", "Pin Press", "Custom"],
    "Lower": ["Competition Squat", "Box Squat", "Front Squat", "Safety-bar Squat", "Competition Deadlift",
              "Deficit Deadlift", "Rack Pull", "Custom"],
}
DE_EXERCISE = {"Bench": "Speed Bench Press", "Squat": "Speed Squat", "Deadlift": "Speed Deadlift"}
DE_PRESCRIPTION = {"Bench": ("8–10 × 3", 3), "Squat": ("8–12 × 2", 2), "Deadlift": ("6–10 × 1", 1)}
ME_TARGETS = {"Heavy single": (0.95, 1), "Heavy triple": (0.92, 3), "Heavy 5": (0.90, 5)}

KG_PER_LB = 0.45359237
UNITS = {
    "lb": {"factor": 1.0, "rounding": [2.5, 5.0, 10.0], "round_index": 1, "bar": 45.0,
           "plates": [45, 35, 25, 10, 5, 2.5], "maxes": (135.0, 225.0, 315.0), "step": 5.0},
    "kg": {"factor": KG_PER_LB, "rounding": [1.0, 2.5, 5.0], "round_index": 1, "bar": 20.0,
           "plates": [25, 20, 15, 10, 5, 2.5, 1.25], "maxes": (60.0, 100.0, 140.0), "step": 2.5},
}
ROTATION_WARN_WEEKS = 3


# ----------------------------------------------------------------------------
# Pure helpers (no Streamlit calls, easy to test)
# ----------------------------------------------------------------------------

def round_weight(value: float, increment: float) -> float:
    """Round to the selected plate increment, never below zero."""
    return max(0.0, round(value / increment) * increment)


def parse_percentages(raw: str, defaults: list[float]) -> tuple[list[float], bool]:
    """Parse comma-separated percentages into fractions. Returns (values, was_valid)."""
    if not raw.strip():
        return defaults, True
    try:
        parsed = [float(part.strip()) / 100 for part in raw.split(",") if part.strip()]
        if parsed and all(0 < p < 1 for p in parsed):
            return parsed, True
    except ValueError:
        pass
    return defaults, False


def estimated_1rm(weight: float, reps: int, rpe: float | None = None) -> float:
    """Epley e1RM, counting reps left in the tank (10 − RPE) when RPE is given."""
    reps_in_reserve = max(0.0, 10.0 - rpe) if rpe else 0.0
    total_reps = reps + reps_in_reserve
    if total_reps <= 1:
        return float(weight)
    return float(weight) * (1 + total_reps / 30)


def plates_per_side(total: float, bar: float, plates: list[float]) -> tuple[list[tuple[float, int]], float] | None:
    """Greedy plate breakdown per side. Returns ([(plate, count)], leftover) or None if below the bar."""
    per_side = round((total - bar) / 2, 4)
    if per_side < 0:
        return None
    breakdown = []
    for plate in plates:
        count = int(per_side // plate + 1e-9)
        if count:
            breakdown.append((plate, count))
            per_side = round(per_side - count * plate, 4)
    return breakdown, per_side


def normalize_row(row: dict) -> dict:
    """Validate and clean one log row (from CSV or Google Sheets)."""
    weight = float(row["weight_lb"])
    reps = int(float(row["reps"]))
    rpe = float(row["rpe"])
    if not (0 <= weight <= 5000 and 1 <= reps <= 100 and 1 <= rpe <= 10):
        raise ValueError("Workout log has weights, reps or RPE values out of range.")

    def text(key: str, limit: int) -> str:
        value = row.get(key, "")
        return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)[:limit]

    role = text("role", 20) or "main"
    return {
        "timestamp_utc": text("timestamp_utc", 40),
        "day": text("day", 60),
        "exercise": text("exercise", 120),
        "weight_lb": weight,
        "reps": reps,
        "rpe": rpe,
        "wave_week": text("wave_week", 20).removesuffix(".0"),
        "role": role if role in {"main", "accessory"} else "main",
    }


def load_csv(raw: bytes) -> list[dict]:
    """Validate a previously exported workout log."""
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not set(REQUIRED_COLUMNS).issubset(reader.fieldnames or []):
        raise ValueError("CSV is missing the expected workout-log columns.")
    rows = []
    for row in reader:
        rows.append(normalize_row(row))
        if len(rows) > 10000:
            raise ValueError("The import limit is 10,000 sets.")
    return rows


def row_key(row: dict) -> tuple:
    return (row["timestamp_utc"], row["exercise"], round(float(row["weight_lb"]), 2), int(row["reps"]))


def merge_without_duplicates(existing: list[dict], incoming: list[dict]) -> tuple[list[dict], int]:
    """Append only rows not already present. Returns (new rows, number skipped)."""
    seen = {row_key(r) for r in existing}
    added = []
    for row in incoming:
        key = row_key(row)
        if key not in seen:
            seen.add(key)
            added.append(row)
    return added, len(incoming) - len(added)


def csv_bytes(rows: list[dict]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=LOG_COLUMNS)
    writer.writeheader()
    writer.writerows([{col: row.get(col, "") for col in LOG_COLUMNS} for row in rows])
    return output.getvalue().encode("utf-8-sig")


def parse_time(stamp: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(stamp)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def best_e1rm(rows: list[dict], exercise: str) -> float | None:
    values = [estimated_1rm(r["weight_lb"], r["reps"], r["rpe"]) for r in rows if r["exercise"] == exercise]
    return max(values) if values else None


def last_session(rows: list[dict], exercise: str) -> tuple[datetime, dict] | None:
    """Most recent date the exercise was logged, and the best set that day."""
    dated = [(parse_time(r["timestamp_utc"]), r) for r in rows if r["exercise"] == exercise]
    dated = [(t, r) for t, r in dated if t]
    if not dated:
        return None
    last_date = max(t for t, _ in dated).date()
    that_day = [r for t, r in dated if t.date() == last_date]
    best = max(that_day, key=lambda r: estimated_1rm(r["weight_lb"], r["reps"], r["rpe"]))
    return max(t for t, _ in dated), best


def weeks_in_a_row(rows: list[dict], day: str, exercise: str, now: datetime) -> int:
    """How many consecutive ISO weeks (ending this week) `exercise` was the ME main lift on `day`."""
    by_week: dict[tuple[int, int], set[str]] = {}
    for r in rows:
        if r["day"] != day or r.get("role", "main") != "main":
            continue
        t = parse_time(r["timestamp_utc"])
        if t:
            by_week.setdefault(tuple(t.isocalendar()[:2]), set()).add(r["exercise"])
    count = 0
    cursor = now
    while True:
        week = tuple(cursor.isocalendar()[:2])
        if week in by_week and exercise in by_week[week]:
            count += 1
        elif count or week != tuple(now.isocalendar()[:2]):
            break  # Allow this week to be empty (not trained yet); stop at the first gap after that.
        cursor = cursor - pd.Timedelta(days=7)
    return count


# ----------------------------------------------------------------------------
# Persistence: optional Google Sheets, otherwise session state + CSV
# ----------------------------------------------------------------------------

def get_sheet_connection():
    """Return a Google Sheets connection if it's configured and unlocked, else None."""
    try:
        if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
            return None
        from streamlit_gsheets import GSheetsConnection
    except Exception:
        return None
    # If a sync_key is set in secrets, only sync once the visitor enters it, so a
    # public app doesn't write strangers' sets into your sheet.
    sync_key = st.secrets.get("sync_key")
    if sync_key and st.session_state.get("sync_key_entered") != sync_key:
        return None
    return st.connection("gsheets", type=GSheetsConnection)


def load_from_sheet(conn) -> list[dict]:
    df = conn.read(worksheet="logs", ttl=0)
    if df is None or df.empty or not set(REQUIRED_COLUMNS).issubset(df.columns):
        return []
    rows = []
    for record in df.dropna(how="all").to_dict("records"):
        try:
            rows.append(normalize_row(record))
        except (ValueError, TypeError, KeyError):
            continue  # Skip a bad row rather than losing the whole history.
    return rows


def save_logs() -> None:
    conn = st.session_state.get("_sheet_conn")
    if conn is None:
        return
    try:
        conn.update(worksheet="logs", data=pd.DataFrame(st.session_state.logs, columns=LOG_COLUMNS))
    except Exception as exc:  # Keep the session copy even if the write fails.
        st.error(f"Couldn't save to Google Sheets ({exc}). Your sets are still in this session; export a CSV to be safe.")


def init_state() -> None:
    if "logs" not in st.session_state:
        st.session_state.logs = []
    conn = get_sheet_connection()
    st.session_state._sheet_conn = conn
    if conn is not None and not st.session_state.get("_sheet_loaded"):
        try:
            remote = load_from_sheet(conn)
            added, _ = merge_without_duplicates(remote, st.session_state.logs)
            st.session_state.logs = remote + added
            st.session_state._sheet_loaded = True
        except Exception as exc:
            st.warning(f"Couldn't load from Google Sheets ({exc}). Using this session only.")


# ----------------------------------------------------------------------------
# UI helpers
# ----------------------------------------------------------------------------

def fmt(value: float) -> str:
    return f"{round(value, 1):g}"


def plate_text(total: float, unit_cfg: dict, unit: str) -> str:
    result = plates_per_side(total, unit_cfg["bar"], unit_cfg["plates"])
    if result is None:
        return f"Below the {fmt(unit_cfg['bar'])} {unit} bar"
    breakdown, leftover = result
    if not breakdown:
        return "Empty bar"
    text = " + ".join(f"{fmt(p)}×{n}" if n > 1 else fmt(p) for p, n in breakdown) + " per side"
    if leftover > 0.01:
        text += f" (+{fmt(leftover)} {unit} not loadable)"
    return text


def rest_timer(default_seconds: int, autostart: bool) -> None:
    """Client-side countdown so it keeps running without Streamlit reruns."""
    options = [45, 60, 90, 120, 180, 240]
    buttons = "".join(f'<button onclick="go({s})">{s // 60}:{s % 60:02d}</button>' for s in options)
    components.html(
        f"""
        <div style="font-family:sans-serif;color:#f5f2ff;background:#332348;border:1px solid #5c417e;
                    border-radius:14px;padding:10px 14px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
          <span style="font-size:13px;color:#d2c1e7">Rest</span>
          <span id="t" style="font-size:28px;font-weight:700;min-width:84px">0:00</span>
          <span>{buttons}<button onclick="stop()">Stop</button></span>
        </div>
        <style>button{{background:#4a3266;color:#fff;border:1px solid #7a5aa3;border-radius:8px;
                       padding:6px 9px;margin:2px;cursor:pointer}}</style>
        <script>
          let end = 0, iv = null;
          const el = document.getElementById("t");
          function show(s) {{ el.textContent = Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); }}
          function tick() {{
            const left = Math.max(0, Math.round((end - Date.now()) / 1000));
            show(left);
            if (left === 0) {{ clearInterval(iv); iv = null; el.style.color = "#7dffb0";
              try {{ navigator.vibrate && navigator.vibrate([200, 100, 200]); }} catch (e) {{}} }}
          }}
          function go(s) {{ end = Date.now() + s * 1000; el.style.color = "#f5f2ff";
            if (iv) clearInterval(iv); iv = setInterval(tick, 250); tick(); }}
          function stop() {{ if (iv) clearInterval(iv); iv = null; show(0); }}
          {"go(" + str(default_seconds) + ");" if autostart else "show(" + str(default_seconds) + ");"}
        </script>
        """,
        height=72,
    )


def logs_table(rows: list[dict], factor: float, unit: str) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=LOG_COLUMNS)
    df[f"weight ({unit})"] = (df["weight_lb"] * factor).round(1)
    df[f"e1RM ({unit})"] = [round(estimated_1rm(w, r, p) * factor, 1) for w, r, p in zip(df.weight_lb, df.reps, df.rpe)]
    df["when"] = [t.astimezone().strftime("%b %d %H:%M") if (t := parse_time(s)) else s for s in df.timestamp_utc]
    return df[["when", "day", "exercise", f"weight ({unit})", "reps", "rpe", f"e1RM ({unit})", "role"]]


# ----------------------------------------------------------------------------
# App
# ----------------------------------------------------------------------------

st.set_page_config(page_title="Conjugate Training Tool", page_icon="🏋️", layout="wide")
st.markdown(
    """
    <style>
      .stApp {background:linear-gradient(155deg,#1b122d 0%,#28183f 55%,#161322 100%);color:#f5f2ff}
      .block-container {max-width:1220px;padding-top:1.25rem;padding-bottom:3rem}
      div[data-testid="stMetric"] {border:1px solid #5c417e;background:#332348;border-radius:14px;padding:12px 16px}
      div[data-testid="stMetricValue"] {color:#f7f0ff}
      div[data-testid="stMetricLabel"] {color:#d2c1e7}
      .stButton>button[kind="primary"] {background:#7740ba;color:white;border-color:#9863d7}
      h1,h2,h3 {color:#faf5ff}
      @media (max-width: 640px) {
        .block-container {padding-left:.8rem;padding-right:.8rem}
        div[data-testid="stMetricValue"] {font-size:1.35rem}
        h1 {font-size:1.6rem}
      }
    </style>
    """,
    unsafe_allow_html=True,
)

init_state()
logs: list[dict] = st.session_state.logs
now = datetime.now(timezone.utc)

# HEADER
header_text, header_image = st.columns([5, 1], vertical_alignment="center")
with header_text:
    st.title("🏋️ Conjugate Training Tool")
    sync_note = "Synced to Google Sheets" if st.session_state._sheet_conn else "Session-only log (export CSV to keep it)"
    st.caption(f"Your training day at a glance · Developed by Josh B · {sync_note}")
with header_image:
    gorilla = ROOT / "gorilla.png"
    if gorilla.exists():
        st.image(str(gorilla), width=105)

tab_today, tab_log, tab_progress, tab_ref = st.tabs(["🏋️ Today", "📝 Log sets", "📈 Progress", "ℹ️ Settings & reference"])

# --- Settings tab (rendered first in code so values are available everywhere) ---
with tab_ref:
    st.subheader("Settings")
    unit = st.radio("Units", list(UNITS), horizontal=True, key="unit")
    ucfg = UNITS[unit]
    factor = ucfg["factor"]
    rounding = st.selectbox(f"Round bar weight to nearest ({unit})", ucfg["rounding"], index=ucfg["round_index"],
                            key=f"rounding_{unit}")
    custom_me_warmups = st.text_input("ME warmups (%)", placeholder="30,45,60,75,88")
    custom_de_warmups = st.text_input("DE warmups (%)", placeholder="30,45")
    band_mode = st.radio(
        "When using bands/chains on DE days",
        ["Bar at wave %, bands added on top", "Total at wave %, bands subtracted from bar"],
        help="Westside-style speed work usually keeps the bar at the wave % and adds band tension on top.",
    )

# --- Today tab ---
with tab_today:
    st.subheader("Build today's workout")
    day_col, week_col = st.columns([2, 1])
    with day_col:
        day = st.radio("Training day", DAY_TYPES, horizontal=True, key="training_day")
    with week_col:
        week = st.radio("DE wave week", [1, 2, 3], horizontal=True, disabled=day.startswith("ME"), key="wave_week")

    upper = "Upper" in day
    is_de = day.startswith("DE")
    movement_family = "Upper" if upper else "Lower"

    if upper:
        lift_family = "Bench"
    elif is_de:
        lift_family = st.radio("Speed movement", ["Squat", "Deadlift"], horizontal=True, key="de_lower_lift")
    else:
        lift_family = None  # ME lower is decided by the chosen variation below.

    if is_de:
        exercise = DE_EXERCISE[lift_family]
    else:
        variation = st.selectbox("Today's max-effort variation", ME_VARIATIONS[movement_family],
                                 key=f"me_variation_{movement_family}")
        if variation == "Custom":
            exercise = st.text_input("Custom movement name", value="Custom ME variation", max_chars=100).strip() or "Custom ME variation"
        else:
            exercise = variation
        if not upper:
            lift_family = "Deadlift" if any(w in exercise.lower() for w in ["deadlift", "rack pull", "block pull", "pull"]) else "Squat"

    with st.expander(f"Training maxes ({unit})", expanded=not logs):
        mx1, mx2, mx3 = st.columns(3)
        b0, s0, d0 = ucfg["maxes"]
        with mx1:
            bench_max = st.number_input("Bench", min_value=0.0, value=b0, step=ucfg["step"], key=f"bench_tm_{unit}")
        with mx2:
            squat_max = st.number_input("Squat", min_value=0.0, value=s0, step=ucfg["step"], key=f"squat_tm_{unit}")
        with mx3:
            deadlift_max = st.number_input("Deadlift", min_value=0.0, value=d0, step=ucfg["step"], key=f"deadlift_tm_{unit}")
        st.caption("The starting values are examples. Enter your own competition maxes.")
    family_max = {"Bench": bench_max, "Squat": squat_max, "Deadlift": deadlift_max}[lift_family]

    if is_de:
        p1, p2 = st.columns(2)
        with p1:
            wave_pct = st.number_input("Speed work percentage (%)", min_value=1.0, max_value=100.0,
                                       value=WAVE_DEFAULTS[week], step=2.5, key=f"wave_{lift_family}_{week}")
        with p2:
            band_top = st.number_input(f"Bands/chains at lockout ({unit})", min_value=0.0, value=0.0,
                                       step=ucfg["step"], key=f"band_{lift_family}_{unit}",
                                       help="Estimated extra resistance at the top of the lift.")
        top_pct = wave_pct / 100
        base_max = family_max
        if band_mode.startswith("Bar"):
            bar_weight = round_weight(base_max * top_pct, rounding)
            target_total = bar_weight + band_top
        else:
            target_total = base_max * top_pct
            bar_weight = round_weight(max(0.0, target_total - band_top), rounding)
        prescription, target_reps = DE_PRESCRIPTION[lift_family]
        main_note = "Fast, controlled reps. Short rests; lower the load if bar speed drops."
    else:
        band_top = 0.0
        var_best = best_e1rm(logs, exercise)
        default_base = var_best * factor if var_best else family_max
        source = "your best logged e1RM for this variation" if var_best else f"your {lift_family.lower()} training max"
        me1, me2, me3 = st.columns(3)
        with me1:
            base_max = st.number_input(f"Max for {exercise} ({unit})", min_value=0.0,
                                       value=float(round(default_base, 1)), step=ucfg["step"],
                                       key=f"varmax_{exercise}_{unit}_{round(default_base, 1)}",
                                       help=f"Defaults to {source}.")
        with me2:
            me_target = st.selectbox("Top-set target", list(ME_TARGETS) + ["Custom %"], key="me_target")
        with me3:
            if me_target == "Custom %":
                top_pct = st.number_input("Top-set % of max", min_value=50.0, max_value=110.0,
                                          value=95.0, step=0.5, key="me_custom_pct") / 100
                target_reps = 1
            else:
                top_pct, target_reps = ME_TARGETS[me_target]
                st.caption(f"Based on {source}. Adjust by RPE on the day.")
        target_total = base_max * top_pct
        bar_weight = round_weight(target_total, rounding)
        prescription = f"Work up to {target_reps} rep{'s' if target_reps != 1 else ''}"
        main_note = "Treat this as a starting estimate; let bar speed and RPE decide the top set."

        # Rotation and history for this variation.
        streak = weeks_in_a_row(logs, day, exercise, now)
        previous = last_session(logs, exercise)
        if previous:
            when, best_set = previous
            st.info(f"Last time: {when.astimezone().strftime('%b %d')} — best set "
                    f"{fmt(best_set['weight_lb'] * factor)} {unit} × {best_set['reps']} @ RPE {fmt(best_set['rpe'])}.")
        if streak >= ROTATION_WARN_WEEKS:
            st.warning(f"{exercise} has been your {day} lift for {streak} weeks in a row. "
                       "Conjugate usually rotates ME variations every 1–3 weeks.")

    # Hero metrics
    st.markdown(f"### {exercise}")
    a, b, c, d = st.columns(4)
    with a:
        st.metric("Load bar to", f"{fmt(bar_weight)} {unit}")
    with b:
        st.metric("Sets × reps", prescription)
    with c:
        st.metric("Target %", f"{fmt(top_pct * 100)}%")
    with d:
        st.metric("Total at top (est.)", f"{fmt(target_total)} {unit}")
    st.caption(f"🔩 Plates: {plate_text(bar_weight, ucfg, unit)} · {main_note}")
    if is_de and band_top:
        st.caption(f"Includes about {fmt(band_top)} {unit} of band/chain tension at lockout; actual tension varies.")

    warmup_col, accessories_col = st.columns([1, 1.5], gap="large")
    with warmup_col:
        st.subheader("Warmups")
        default_pcts = [0.30, 0.45] if is_de else [0.30, 0.45, 0.60, 0.75, 0.88]
        pcts, valid = parse_percentages(custom_de_warmups if is_de else custom_me_warmups, default_pcts)
        if not valid:
            st.warning("Invalid warmup percentages in Settings. Using the defaults.")
        for p in pcts:
            if is_de:
                reps = 10 if p < 0.4 else 5
            else:
                reps = 10 if p < 0.4 else 5 if p < 0.55 else 3 if p < 0.70 else 2 if p < 0.85 else 1
            w = round_weight(base_max * p, rounding)
            st.write(f"**{fmt(p * 100)}%** · {fmt(w)} {unit} × {reps}  \n"
                     f"<span style='color:#b9a6d6;font-size:.85em'>{plate_text(w, ucfg, unit)}</span>",
                     unsafe_allow_html=True)
        if not is_de:
            st.caption("Then take progressively heavier singles or triples up to your top set.")

    with accessories_col:
        st.subheader("Accessories")
        pool_key = "Upper" if upper else ("Deadlift" if lift_family == "Deadlift" else "Lower")
        pool = {name: (s, r, rpe) for name, s, r, rpe in ACCESSORY_DEFAULTS[pool_key]}
        initial = list(pool)[:3] + (["Hanging Leg Raise"] if pool_key == "Lower" else [])
        chosen = st.multiselect("Exercises", options=list(pool), default=initial, key=f"acc_{day}_{pool_key}")

        def acc_key(field: str, name: str) -> str:
            return f"{field}_{day}_{pool_key}_{name}"

        accessory_plan = []
        for name in chosen:
            s, r, rpe = pool[name]
            rpe = min(rpe, 7.0) if is_de else rpe
            accessory_plan.append((name,
                                   st.session_state.get(acc_key("sets", name), s),
                                   st.session_state.get(acc_key("reps", name), r),
                                   st.session_state.get(acc_key("rpe", name), float(rpe)),
                                   (s, r, float(rpe))))
        if accessory_plan:
            for name, s, r, rpe, _ in accessory_plan:
                st.write(f"**{name}** — {s} × {r} · RPE {fmt(rpe)}")
        else:
            st.caption("Choose exercises to add to your session.")

        with st.expander("Edit accessory targets / technique videos"):
            st.caption("ME days: accessories generally RPE 7–8. DE days: generally 6–7. Adjust for recovery.")
            for name, _, _, _, (s0, r0, rpe0) in accessory_plan:
                st.markdown(f"**{name}** · [technique videos](https://www.youtube.com/results?search_query="
                            f"{quote_plus(name + ' exercise technique')})")
                ax, ay, az = st.columns(3)
                with ax:
                    st.number_input("Sets", min_value=1, max_value=10, value=s0, key=acc_key("sets", name))
                with ay:
                    st.number_input("Reps", min_value=1, max_value=100, value=r0, key=acc_key("reps", name))
                with az:
                    st.number_input("RPE", min_value=1.0, max_value=10.0, value=rpe0, step=0.5, key=acc_key("rpe", name))

# --- Log tab ---
with tab_log:
    st.subheader(f"{day} · {exercise}")
    log_options = [exercise] + [name for name in chosen if name != exercise]
    log_exercise = st.selectbox("Exercise", log_options, key="log_exercise")
    is_main = log_exercise == exercise

    # Prefill from the most recent set of this exercise; otherwise from today's plan.
    recent = next((r for r in reversed(logs) if r["exercise"] == log_exercise), None)
    if recent:
        default_w, default_r, default_rpe = recent["weight_lb"] * factor, recent["reps"], recent["rpe"]
    elif is_main:
        default_w, default_r, default_rpe = bar_weight, target_reps, 7.0 if is_de else 8.0
    else:
        _, s, r, rpe, _ = next(item for item in accessory_plan if item[0] == log_exercise)
        default_w, default_r, default_rpe = 0.0, int(r), float(rpe)
    default_w = float(round(default_w, 1))

    suffix = f"{log_exercise}_{unit}_{default_w}_{default_r}_{default_rpe}"
    w1, w2, w3 = st.columns(3)
    with w1:
        logged_weight = st.number_input(f"Weight ({unit})", min_value=0.0, value=default_w,
                                        step=rounding, key=f"lw_{suffix}")
    with w2:
        logged_reps = st.number_input("Reps", min_value=1, max_value=100, value=int(default_r), step=1, key=f"lr_{suffix}")
    with w3:
        logged_rpe = st.number_input("RPE", min_value=1.0, max_value=10.0, value=float(default_rpe),
                                     step=0.5, key=f"lp_{suffix}")
    if logged_weight:
        st.caption(f"🔩 {plate_text(logged_weight, ucfg, unit)} · e1RM ≈ "
                   f"{fmt(estimated_1rm(logged_weight, logged_reps, logged_rpe))} {unit}")

    if st.button("+ Log set", type="primary", use_container_width=True):
        logs.append({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "day": day,
            "exercise": log_exercise,
            "weight_lb": round(logged_weight / factor, 2),
            "reps": int(logged_reps),
            "rpe": float(logged_rpe),
            "wave_week": str(week) if is_de else "",
            "role": "main" if is_main else "accessory",
        })
        save_logs()
        st.session_state._start_timer = True
        st.rerun()

    default_rest = 60 if is_de else 180
    rest_timer(default_rest, autostart=st.session_state.pop("_start_timer", False))

    if logs:
        today_sets = [r for r in logs if (t := parse_time(r["timestamp_utc"])) and t.astimezone().date() == now.astimezone().date()]
        st.caption(f"{len(today_sets)} set{'s' if len(today_sets) != 1 else ''} logged today · {len(logs)} total")
        st.dataframe(logs_table(list(reversed(logs[-25:])), factor, unit), use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("↩ Undo last set", use_container_width=True):
                logs.pop()
                save_logs()
                st.rerun()
        with c2:
            st.download_button("⬇ Export CSV", data=csv_bytes(logs), file_name="conjugate_workout_log.csv",
                               mime="text/csv", use_container_width=True)
    else:
        st.info("No sets logged yet. Logged sets appear here.")

    with st.expander("Restore a previous CSV log"):
        history_file = st.file_uploader("Select a previously exported workout log", type=["csv"])
        if history_file and st.button("Import workout log"):
            try:
                incoming = load_csv(history_file.getvalue())
                added, skipped = merge_without_duplicates(logs, incoming)
                logs.extend(added)
                logs.sort(key=lambda r: r["timestamp_utc"])
                save_logs()
                st.success(f"Imported {len(added)} sets" + (f", skipped {skipped} duplicates." if skipped else "."))
            except (ValueError, UnicodeDecodeError, TypeError, KeyError) as exc:
                st.error(f"Could not import CSV: {exc}")

# --- Progress tab ---
with tab_progress:
    if not logs:
        st.info("Log some sets and your progress charts and PRs will show up here.")
    else:
        df = pd.DataFrame(logs, columns=LOG_COLUMNS)
        df["e1rm"] = [estimated_1rm(w, r, p) * factor for w, r, p in zip(df.weight_lb, df.reps, df.rpe)]
        df["weight"] = df.weight_lb * factor
        df["date"] = [t.astimezone().date() if (t := parse_time(s)) else None for s in df.timestamp_utc]
        df = df.dropna(subset=["date"])

        exercises = sorted(df.exercise.unique(), key=lambda e: (e != exercise, e))
        pick = st.selectbox("Exercise", exercises, key="progress_exercise")
        sub = df[df.exercise == pick]
        daily = sub.groupby("date")["e1rm"].max().rename(f"Best e1RM ({unit})")

        best_row = sub.loc[sub.e1rm.idxmax()]
        heavy_row = sub.loc[sub.weight.idxmax()]
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Best e1RM", f"{fmt(best_row.e1rm)} {unit}")
        with m2:
            st.metric("Heaviest set", f"{fmt(heavy_row.weight)} {unit} × {int(heavy_row.reps)}")
        with m3:
            st.metric("Sessions", f"{sub.date.nunique()}")
        if len(daily) > 1:
            st.line_chart(daily)
        else:
            st.caption("Log this exercise on another day to see a trend line.")
        st.caption("e1RM uses the Epley formula and counts reps in reserve from RPE (e.g. 5 reps @ RPE 8 counts as 7).")

        st.subheader("PR board")
        board = (df.sort_values("e1rm", ascending=False).groupby("exercise").head(1)
                 .assign(**{f"Best e1RM ({unit})": lambda x: x.e1rm.round(1),
                            "Set": lambda x: [f"{fmt(w)} × {int(r)} @ {fmt(p)}" for w, r, p in zip(x.weight, x.reps, x.rpe)],
                            "Date": lambda x: x.date.astype(str)})
                 [["exercise", f"Best e1RM ({unit})", "Set", "Date"]])
        st.dataframe(board, use_container_width=True, hide_index=True)

        me_main = df[(df.role == "main") & df.day.str.startswith("ME")]
        if not me_main.empty:
            st.subheader("ME rotation history")
            me_main = me_main.assign(week=[f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}" for d in me_main.date])
            rotation = me_main.groupby(["week", "day"])["exercise"].first().unstack("day").sort_index(ascending=False)
            st.dataframe(rotation.head(12), use_container_width=True)

# --- Reference (bottom of the Settings tab) ---
with tab_ref:
    try:
        needs_key = bool(st.secrets.get("sync_key")) and "gsheets" in st.secrets.get("connections", {})
    except Exception:
        needs_key = False
    if needs_key:
        st.subheader("Sync")
        entered = st.text_input("Sync key", type="password", help="Enter the key from your app secrets to sync with Google Sheets.")
        if entered and entered != st.session_state.get("sync_key_entered"):
            st.session_state.sync_key_entered = entered
            st.session_state._sheet_loaded = False
            st.rerun()
        st.caption("Synced ✅" if st.session_state._sheet_conn else "Not syncing — enter your key to load and save your history.")

    st.subheader("Reference")
    chart = next((ROOT / c for c in ["rpe_chart.png", "rpe_chart.jpg", "rpe_chart.jpeg", "rpe_chart.svg"] if (ROOT / c).exists()), None)
    if chart:
        st.image(str(chart), caption="RPE chart", width=520)
    st.markdown("[Understanding RPE](https://www.youtube.com/results?search_query=RPE+scale+explained) · "
                "[Bench technique](https://www.youtube.com/results?search_query=bench+press+technique) · "
                "[Squat technique](https://www.youtube.com/results?search_query=squat+technique) · "
                "[Deadlift technique](https://www.youtube.com/results?search_query=deadlift+technique)")
    collage = ROOT / "collage"
    if collage.is_dir():
        pictures = [p for p in sorted(collage.iterdir()) if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg"}]
        if pictures and st.checkbox("Show collage photos", value=False):
            st.image([str(p) for p in pictures[:12]], width=150)

st.caption("Training suggestions are estimates; adjust by bar speed and RPE. "
           + ("Your log syncs to Google Sheets." if st.session_state._sheet_conn
              else "Your log lives in this browser session only, so export a CSV before closing.")
           + "  ·  [Source on GitHub](https://github.com/Joshieb43/)")

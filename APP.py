"""Conjugate Day — single-page workout dashboard.

Drop-in replacement for the original APP.py. Requires only Streamlit.
Workout logs live in session state, with CSV export/import for portability.
"""

import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import streamlit as st


ROOT = Path(__file__).resolve().parent
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
    </style>
    """,
    unsafe_allow_html=True,
)


# Original accessory library, including default sets/reps/RPE.
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
LOG_COLUMNS = ["timestamp_utc", "day", "exercise", "weight_lb", "reps", "rpe", "wave_week"]
ME_VARIATIONS = {
    "Upper": ["Competition Bench", "Close-grip Bench", "Floor Press", "Board Press", "Incline Bench", "Pin Press", "Custom"],
    "Lower": ["Competition Squat", "Box Squat", "Front Squat", "Safety-bar Squat", "Competition Deadlift", "Deficit Deadlift", "Rack Pull", "Custom"],
}


def round_weight(value: float, increment: float) -> float:
    """Round to the selected plate increment, never below zero."""
    return max(0.0, round(value / increment) * increment)


def parse_percentages(raw: str, defaults: list[float]) -> list[float]:
    """Parse comma-separated percentages, as fractions between zero and one."""
    if not raw.strip():
        return defaults
    try:
        parsed = [float(part.strip()) / 100 for part in raw.split(",") if part.strip()]
        if parsed and all(0 < p < 1 for p in parsed):
            return parsed
    except ValueError:
        pass
    st.warning("Invalid warmup percentages. Using the defaults instead.")
    return defaults


def load_csv(file) -> list[dict]:
    """Validate a previously exported workout log before adding to the session."""
    reader = csv.DictReader(io.StringIO(file.getvalue().decode("utf-8-sig")))
    if not set(LOG_COLUMNS).issubset(reader.fieldnames or []):
        raise ValueError("CSV is missing the expected workout-log columns.")
    rows = []
    for row in reader:
        weight = float(row["weight_lb"])
        reps = int(row["reps"])
        rpe = float(row["rpe"])
        if not (0 <= weight <= 5000 and 1 <= reps <= 100 and 1 <= rpe <= 10):
            raise ValueError("Workout log has weights, reps or RPE values out of range.")
        rows.append({
            "timestamp_utc": row["timestamp_utc"][:40],
            "day": row["day"][:60],
            "exercise": row["exercise"][:120],
            "weight_lb": weight,
            "reps": reps,
            "rpe": rpe,
            "wave_week": row["wave_week"][:20],
        })
        if len(rows) > 10000:
            raise ValueError("The import limit is 10,000 sets.")
    return rows


def csv_bytes(rows: list[dict]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=LOG_COLUMNS)
    writer.writeheader()
    writer.writerows([{col: row.get(col, "") for col in LOG_COLUMNS} for row in rows])
    return output.getvalue().encode("utf-8-sig")


if "logs" not in st.session_state:
    st.session_state.logs = []

# HEADER
header_text, header_image = st.columns([5, 1], vertical_alignment="center")
with header_text:
    st.title("🏋️ Conjugate Training Tool")
    st.caption("Your training day at a glance · Developed by Josh B")
with header_image:
    gorilla = ROOT / "gorilla.png"
    if gorilla.exists():
        st.image(str(gorilla), width=105)

# ROW 1 — CONTROLS
st.subheader("Build today's workout")
day_col, week_col = st.columns([2, 1])
with day_col:
    day = st.radio("Training day", DAY_TYPES, horizontal=True, key="training_day")
with week_col:
    week = st.radio("DE wave", [1, 2, 3], horizontal=True, disabled=day.startswith("ME"))

upper = "Upper" in day
is_de = day.startswith("DE")
movement_family = "Upper" if upper else "Lower"

if upper:
    lift_family = "Bench"
elif is_de:
    lift_family = st.selectbox("Speed movement", ["Squat", "Deadlift"], horizontal=False)
else:
    lift_family = None  # ME lower determined from exercise selection below.

if not is_de:
    variations = ME_VARIATIONS[movement_family]
    variation = st.selectbox("Today's max-effort variation", variations)
    exercise = st.text_input("Custom movement name", value="Custom ME variation", max_chars=100) if variation == "Custom" else variation
    if not upper:
        lift_family = "Deadlift" if any(word in exercise.lower() for word in ["deadlift", "rack pull", "block pull"]) else "Squat"
else:
    exercise = {"Bench": "Speed Bench Press", "Squat": "Speed Squat", "Deadlift": "Speed Deadlift"}[lift_family]

st.caption("Set your training maxes (lb)")
mx1, mx2, mx3 = st.columns(3)
with mx1:
    bench_max = st.number_input("Bench", min_value=0.0, value=135.0, step=5.0, key="bench_tm")
with mx2:
    squat_max = st.number_input("Squat", min_value=0.0, value=225.0, step=5.0, key="squat_tm")
with mx3:
    deadlift_max = st.number_input("Deadlift", min_value=0.0, value=315.0, step=5.0, key="deadlift_tm")

with st.expander("⚙️ Advanced calculator settings"):
    rounding = st.selectbox("Round bar weight to nearest (lb)", [2.5, 5.0, 10.0], index=1)
    st.caption("The starting maxes are examples, not your actual maxes. Inputs last for this active browser session.")
    custom_me_warmups = st.text_input("ME warmups (%)", placeholder="30,45,60,75,88")
    custom_de_warmups = st.text_input("DE warmups (%)", placeholder="30,45")

# Calculate against the selected lift family.
max_for_family = {"Bench": bench_max, "Squat": squat_max, "Deadlift": deadlift_max}[lift_family]

if is_de:
    p1, p2 = st.columns([1, 1])
    with p1:
        wave_pct = st.number_input("Speed work percentage (%)", min_value=1.0, max_value=100.0,
                                   value=WAVE_DEFAULTS[week], step=2.5, key=f"wave_{week}")
    with p2:
        band_top = st.number_input("Bands/chains at lockout (lb)", min_value=0.0,
                                   value=0.0, step=5.0, help="Estimated additional resistance at the top.")
    top_pct = wave_pct / 100
    target_total = max_for_family * top_pct
    bar_weight = round_weight(max(0.0, target_total - band_top), rounding)
    prescription = {"Bench": "8–10 × 3", "Squat": "8–12 × 2", "Deadlift": "6–10 × 1"}[lift_family]
    target_reps = {"Bench": 3, "Squat": 2, "Deadlift": 1}[lift_family]
    main_note = "Fast, controlled reps. Short rests; lower load if bar speed drops."
else:
    me1, me2 = st.columns([1, 1])
    with me1:
        me_target = st.selectbox("Top-set target", ["Heavy single", "Heavy triple", "Heavy 5", "Custom %"])
    top_frac = {"Heavy single": .95, "Heavy triple": .92, "Heavy 5": .90}.get(me_target, .95)
    with me2:
        if me_target == "Custom %":
            top_frac = st.number_input("Top-set % of training max", min_value=50.0, max_value=100.0,
                                       value=95.0, step=.5) / 100
        else:
            st.caption("ME loads are rough starting estimates, not guaranteed rep maxes.")
    target_reps = {"Heavy single": 1, "Heavy triple": 3, "Heavy 5": 5}.get(me_target, 1)
    top_pct = top_frac
    target_total = max_for_family * top_pct
    bar_weight = round_weight(target_total, rounding)
    band_top = 0.0
    prescription = f"Work up to {target_reps} rep{'s' if target_reps != 1 else ''}"
    main_note = "A different variation may have a different true max; adjust by RPE."

# ROW 2 — HERO METRICS
st.markdown(f"### {exercise}")
a, b, c, d = st.columns(4)
with a:
    st.metric("Load plates for", f"{bar_weight:g} lb")
with b:
    st.metric("Sets × reps", prescription)
with c:
    st.metric("Target %", f"{top_pct * 100:g}%")
with d:
    st.metric("Total at top (est.)", f"{target_total:g} lb")
st.caption(main_note)
if is_de and band_top:
    st.caption(f"Estimated {band_top:g} lb bands/chains at lockout; actual tension varies.")

# ROW 3 — WARMUPS AND ACCESSORIES
warmup_col, accessories_col = st.columns([1, 1.5], gap="large")
with warmup_col:
    st.subheader("Warmup progression")
    default_pcts = [.30, .45] if is_de else [.30, .45, .60, .75, .88]
    pcts = parse_percentages(custom_de_warmups if is_de else custom_me_warmups, default_pcts)
    for index, p in enumerate(pcts):
        suggested_reps = (10 if p < .4 else 5) if is_de else (10 if p < .4 else 5 if p < .55 else 3 if p < .70 else 2 if p < .85 else 1)
        weight = round_weight(max_for_family * p, rounding)
        st.write(f"**{p * 100:g}%** · {weight:g} lb × {suggested_reps}")
    if not is_de:
        st.caption("Finish with progressively heavier singles/triples as appropriate before your top set.")

with accessories_col:
    st.subheader("Suggested accessories")
    pool_key = "Upper" if upper else ("Deadlift" if lift_family == "Deadlift" else "Lower")
    options = [entry[0] for entry in ACCESSORY_DEFAULTS[pool_key]]
    initial = options[:3]
    if pool_key == "Lower":
        initial.append("Hanging Leg Raise")
    # day-specific key retains different accessory choices for each day.
    chosen = st.multiselect("Exercises", options=options, default=initial, key=f"accessories_{day}_{pool_key}")
    accessory_plan = []
    for name in chosen:
        _, s, r, suggested_rpe = next(item for item in ACCESSORY_DEFAULTS[pool_key] if item[0] == name)
        day_rpe = suggested_rpe if not is_de else min(suggested_rpe, 7.0)
        # Read edited widget values when available; use the pool defaults otherwise.
        s = st.session_state.get(f"sets_{day}_{name}", s)
        r = st.session_state.get(f"reps_{day}_{name}", r)
        day_rpe = st.session_state.get(f"rpe_{day}_{name}", day_rpe)
        accessory_plan.append((name, s, r, day_rpe))
    if accessory_plan:
        for name, s, r, rpe in accessory_plan:
            st.write(f"**{name}** — {s} × {r} · RPE {rpe:g}")
    else:
        st.caption("Choose exercises to add to your session.")

    with st.expander("Edit accessory targets / watch technique demos"):
        st.caption("ME accessory work: generally RPE 7–8; DE: generally 6–7. Tailor by recovery.")
        for name, suggested_sets, suggested_reps, suggested_rpe in accessory_plan:
            st.markdown(f"**{name}**")
            ax, ay, az = st.columns(3)
            with ax:
                sets = st.number_input("Sets", min_value=1, max_value=10, value=suggested_sets, key=f"sets_{day}_{name}")
            with ay:
                reps = st.number_input("Reps", min_value=1, max_value=100, value=suggested_reps, key=f"reps_{day}_{name}")
            with az:
                rpe = st.number_input("RPE", min_value=1.0, max_value=10.0, value=float(suggested_rpe), step=.5, key=f"rpe_{day}_{name}")
            st.caption(f"Plan: {sets} × {reps} @ RPE {rpe:g}  ·  [Technique videos](https://www.youtube.com/results?search_query={quote_plus(name + ' exercise technique')})")

# ROW 4 — LOG SETS AND PR
st.divider()
log_col, records_col = st.columns([1, 1.4], gap="large")
with log_col:
    st.subheader("Log a completed set")
    log_exercise = st.selectbox("Exercise logged", [exercise] + [name for name in chosen if name != exercise])
    w1, w2, w3 = st.columns(3)
    with w1:
        logged_weight = st.number_input("Weight (lb)", min_value=0.0, value=float(bar_weight) if log_exercise == exercise else 0.0, step=2.5, key=f"log_weight_{log_exercise}")
    with w2:
        logged_reps = st.number_input("Reps", min_value=1, max_value=100, value=target_reps if log_exercise == exercise else 8, step=1, key=f"log_reps_{log_exercise}")
    with w3:
        logged_rpe = st.number_input("RPE", min_value=1.0, max_value=10.0, value=8.0, step=.5, key=f"log_rpe_{log_exercise}")
    if st.button("+ Log set", type="primary", use_container_width=True):
        st.session_state.logs.append({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "day": day,
            "exercise": log_exercise,
            "weight_lb": logged_weight,
            "reps": logged_reps,
            "rpe": logged_rpe,
            "wave_week": str(week) if is_de else "",
        })
        st.success("Set added to today's session log.")

with records_col:
    st.subheader("Session history & PR")
    matches = [r for r in st.session_state.logs if r["exercise"] == log_exercise]
    if matches:
        best = max(matches, key=lambda r: (float(r["weight_lb"]), int(r["reps"])))
        st.metric(f"Best logged {log_exercise} weight", f"{float(best['weight_lb']):g} lb × {int(best['reps'])}")
        st.caption("Heaviest recorded set (not an estimated 1RM).")
    else:
        st.caption("Log a set to begin tracking your best performance for each movement.")
    if st.session_state.logs:
        st.dataframe(list(reversed(st.session_state.logs[-20:])), use_container_width=True, hide_index=True)
        st.download_button("⬇ Export workout history (CSV)", data=csv_bytes(st.session_state.logs),
                           file_name="conjugate_workout_log.csv", mime="text/csv", use_container_width=True)
        if st.button("Undo last set", use_container_width=True):
            st.session_state.logs.pop()
            st.rerun()
    else:
        st.info("No sets logged in this browser session yet.")
    with st.expander("Restore a previous CSV log"):
        history_file = st.file_uploader("Select a previously exported workout log", type=["csv"])
        if history_file and st.button("Import workout log"):
            try:
                incoming = load_csv(history_file)
                st.session_state.logs.extend(incoming)
                st.success(f"Imported {len(incoming)} sets.")
                st.rerun()
            except (ValueError, UnicodeDecodeError, TypeError) as exc:
                st.error(f"Could not import CSV: {exc}")

with st.expander("RPE chart, exercise links & optional collage"):
    chart = next((ROOT / candidate for candidate in ["rpe_chart.png", "rpe_chart.jpg", "rpe_chart.jpeg", "rpe_chart.svg"] if (ROOT / candidate).exists()), None)
    if chart:
        st.image(str(chart), caption="Original RPE chart", width=520)
    else:
        st.caption("Add rpe_chart.png alongside APP.py to display your RPE chart.")
    st.markdown("[Understanding RPE](https://www.youtube.com/results?search_query=RPE+scale+explained) · [Bench technique](https://www.youtube.com/results?search_query=bench+press+technique) · [Squat technique](https://www.youtube.com/results?search_query=squat+technique) · [Deadlift technique](https://www.youtube.com/results?search_query=deadlift+technique)")
    collage = ROOT / "collage"
    if collage.is_dir():
        pictures = [p for p in sorted(collage.iterdir()) if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg"}]
        if pictures and st.checkbox("Show original collage photos", value=False):
            st.image([str(p) for p in pictures[:12]], width=150)

st.caption("Training suggestions are estimates. Your log lives in this browser session only: export CSV before closing/restarting. For permanent cross-device history, a database and user accounts are needed.  ·  [Source on GitHub](https://github.com/Joshieb43/)")

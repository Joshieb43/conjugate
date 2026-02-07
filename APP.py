import streamlit as st

st.set_page_config(page_title="Conjugate Weight Picker", page_icon="purple_ape.svg", layout="centered")

st.title("🏋️ Conjugate Weight Picker")
st.caption("Enter your maxes, pick the DE day + wave, and get your bar weight automatically.")

# --- Styling: purple background and adjusted text color ---
st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #6a0dad 0%, #4b0082 100%);
            color: #fff;
        }
        .stMarkdown, .stText, .css-1v3fvcr {
            color: #fff;
        }
        .stButton>button {
            background-color: #7b1fa2;
            color: white;
        }
        .stMetricValue, .stMetricLabel { color: #fff; }
        </style>
        """,
        unsafe_allow_html=True,
)

# change the visible heading emoji to match icon style
st.title("🦧 Conjugate Weight Picker")

# ---- Helpers ----
def round_to_increment(x: float, inc: float) -> float:
    return round(x / inc) * inc

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

# Typical Westside-style waves (common starting point)
DE_UPPER_WAVE = {1: 0.50, 2: 0.55, 3: 0.60}  # of training max
DE_LOWER_WAVE = {1: 0.50, 2: 0.55, 3: 0.60}  # many run similar; adjust as desired

# Suggested set/rep defaults (you can change later)
DEFAULTS = {
    "DE Upper (Speed Bench)": "8–10 x 3 (short rests, fast reps)",
    "DE Lower (Speed Squat)": "8–12 x 2 (fast reps)",
    "DE Lower (Speed Deadlift)": "6–10 x 1 (fast pulls)",
}

st.subheader("1) Enter your maxes (lb)")
c1, c2, c3 = st.columns(3)

with c1:
    bench_max = st.number_input("Bench max (or training max)", min_value=0.0, value=305.0, step=5.0)
with c2:
    squat_max = st.number_input("Squat max (or training max)", min_value=0.0, value=495.0, step=5.0)
with c3:
    deadlift_max = st.number_input("Deadlift max (or training max)", min_value=0.0, value=565.0, step=5.0)

st.subheader("2) Pick your day + wave")
day = st.selectbox(
    "Day",
    [
        "ME Upper (Bench)",
        "DE Upper (Speed Bench)",
        "ME Lower (Squat)",
        "DE Lower (Speed Squat)",
        "ME Lower (Deadlift)",
        "DE Lower (Speed Deadlift)",
    ],
)

week = st.radio("Wave week", [1, 2, 3], horizontal=True)

rounding = st.selectbox("Round bar weight to nearest", [2.5, 5.0, 10.0], index=1)

# Optional: show/hide warmups and allow custom percentages
show_warmups = st.checkbox("Show warmups", value=True)

with st.expander("Customize warmup percentages (optional)"):
    st.write("Leave blank to use defaults.")
    me_pcts_text = st.text_input("ME warmup percentages (comma-separated %, e.g. 30,45,60,75,88)", value="")
    de_pcts_text = st.text_input("DE warmup percentages (comma-separated %, e.g. 30,45)", value="")


st.subheader("3) Optional accommodating resistance")
use_bands = st.toggle("I’m using bands/chains (estimate top weight)")
band_top = 0.0
if use_bands:
    band_top = st.number_input("Estimated band/chain weight at the TOP (lb)", min_value=0.0, value=0.0, step=5.0)
    st.caption("The app will subtract this from your target 'total at top' to estimate bar weight.")

st.divider()

# ---- Compute ----
def compute_base_for_day(day_name):
    if "Bench" in day_name:
        return bench_max
    if "Deadlift" in day_name:
        return deadlift_max
    return squat_max


def parse_pct_list(text, default_list):
    if not text or not text.strip():
        return default_list
    try:
        parts = [float(p.strip()) for p in text.split(',') if p.strip()]
        parts = [p / 100.0 for p in parts if 0 < p < 100]
        if not parts:
            return default_list
        return parts
    except Exception:
        return default_list


def show_me_warmups(base, rounding, me_pcts=None):
    # adjusted warmup percentages for ME days
    default = [0.30, 0.45, 0.60, 0.75, 0.88]
    warmup_pcts = me_pcts or default
    reps_map = {0.30: 10, 0.45: 5, 0.60: 3, 0.75: 2, 0.88: 1}
    warmups = []
    for p in warmup_pcts:
        w = round_to_increment(base * p, rounding)
        reps = reps_map.get(p, 3 if p >= 0.5 else 5)
        warmups.append((int(p * 100), reps, w))
    top_pct = 0.95
    top_w = round_to_increment(base * top_pct, rounding)
    # display
    st.subheader("Warmup progression (ME)")
    for pct, reps, w in warmups:
        st.write(f"{pct}% x {reps}: {w:.1f} lb")
    st.write(f"Top work suggestion: {int(top_pct*100)}% -> {top_w:.1f} lb (work up to a heavy single)")


# determine base
base = compute_base_for_day(day)

if day.startswith("DE"):
    # keep existing DE behavior
    if "Bench" in day:
        pct = DE_UPPER_WAVE[week]
    else:
        pct = DE_LOWER_WAVE[week]

    target_total = base * pct
    # If bands/chains: estimate bar = target_total - top tension
    bar_est = target_total - band_top
    bar_est = clamp(bar_est, 0, 10_000)
    bar_final = round_to_increment(bar_est, rounding)

    st.metric("Target %", f"{int(pct*100)}%")
    st.metric("Target total load (approx)", f"{round(target_total, 1)} lb")

    if use_bands:
        st.metric("Estimated BAR weight to load", f"{bar_final:.1f} lb")
        st.caption("Note: band/chain tension varies a lot. This is a practical estimate, not physics-accurate.")
    else:
        st.metric("BAR weight to load", f"{bar_final:.1f} lb")

    # show light warmups for DE days (user can customize)
    st.subheader("Suggested warmups (DE)")
    de_default = [0.30, 0.45]
    de_pcts = parse_pct_list(de_pcts_text, [p*100 for p in de_default])
    # parse_pct_list returns fractions if provided previously; ensure fractions
    if all(p > 1 for p in de_pcts):
        de_pcts = [p/100.0 for p in de_pcts]
    if not de_pcts:
        de_pcts = de_default
    for p in de_pcts:
        st.write(f"{int(p*100)}% x {10 if p<0.4 else 5}: {round_to_increment(base*p, rounding):.1f} lb")

else:
    # ME day: show warmups and top-work suggestion
    # allow custom ME percentages
    me_pct_defaults = [30,45,60,75,88]
    me_pcts_parsed = parse_pct_list(me_pcts_text, me_pct_defaults)
    # normalize to fractions
    if all(p > 1 for p in me_pcts_parsed):
        me_pcts_parsed = [p/100.0 for p in me_pcts_parsed]
    # fallback
    if not me_pcts_parsed:
        me_pcts_parsed = [0.30, 0.45, 0.60, 0.75, 0.88]
    show_me_warmups(base, rounding, me_pcts=me_pcts_parsed)

st.subheader("Suggested sets × reps")
st.write(DEFAULTS[day])

st.divider()

with st.expander("Customize the percentages (optional)"):
    st.write("If you want different waves, adjust these in the code:")
    st.code("DE_UPPER_WAVE = {1: 0.50, 2: 0.55, 3: 0.60}\nDE_LOWER_WAVE = {1: 0.50, 2: 0.55, 3: 0.60}")

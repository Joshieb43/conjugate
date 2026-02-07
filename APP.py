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
    ["DE Upper (Speed Bench)", "DE Lower (Speed Squat)", "DE Lower (Speed Deadlift)"]
)

week = st.radio("Wave week", [1, 2, 3], horizontal=True)

rounding = st.selectbox("Round bar weight to nearest", [2.5, 5.0, 10.0], index=1)

st.subheader("3) Optional accommodating resistance")
use_bands = st.toggle("I’m using bands/chains (estimate top weight)")
band_top = 0.0
if use_bands:
    band_top = st.number_input("Estimated band/chain weight at the TOP (lb)", min_value=0.0, value=0.0, step=5.0)
    st.caption("The app will subtract this from your target 'total at top' to estimate bar weight.")

st.divider()

# ---- Compute ----
if day == "DE Upper (Speed Bench)":
    base = bench_max
    pct = DE_UPPER_WAVE[week]
elif day == "DE Lower (Speed Squat)":
    base = squat_max
    pct = DE_LOWER_WAVE[week]
else:
    base = deadlift_max
    pct = DE_LOWER_WAVE[week]  # common starting point; tweak if you prefer

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

st.subheader("Suggested sets × reps")
st.write(DEFAULTS[day])

st.divider()

with st.expander("Customize the percentages (optional)"):
    st.write("If you want different waves, adjust these in the code:")
    st.code("DE_UPPER_WAVE = {1: 0.50, 2: 0.55, 3: 0.60}\nDE_LOWER_WAVE = {1: 0.50, 2: 0.55, 3: 0.60}")

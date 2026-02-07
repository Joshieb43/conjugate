import streamlit as st
from pathlib import Path
import base64
import os

st.set_page_config(page_title="Conjugate Weight Suggestion Tool", page_icon="purple_ape.svg", layout="centered")

col1, col2 = st.columns([3, 1])  # adjust ratio as needed

with col1:
    st.title("Conjugate Weight Suggestion Tool")

with col2:
    st.image("gorilla.png", width=120)
st.caption("Enter your maxes, pick the DE day + wave, and get your bar weight automatically.")
st.markdown("This app is a practical tool to help you quickly determine your working weights for Westside-style conjugate training days. It provides suggested warmup progressions, accommodates optional band/chain resistance, and offers accessory exercise ideas. Perfect for lifters who want to spend less time calculating and more time lifting! (Note: the app provides estimates based on typical percentage guidelines; adjust as needed based on your experience and how you feel on a given day.)")
st.markdown("Developed by [Josh B]. Source code available on [GitHub](https://github.com/Joshieb43/). For feedback or suggestions, feel free to reach out!")
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
st.title("Conjugate Weight Picker")

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

# Common conjugate accessories with suggested sets, reps and RPE
ACCESSORY_DEFAULTS = {
    'Upper': [
        ('Close-grip Bench', 3, 6, 8),
        ('Incline Dumbbell Press', 3, 8, 7.5),
        ('Pendlay Row', 4, 6, 8),
        ('Face Pulls', 3, 15, 7),
        ('Tricep Pressdown', 3, 10, 7),
        ('Overhead Press', 3, 5, 8),
        ('Lat Pulldown', 3, 8, 7.5),
        ('Dumbbell Row', 4, 8, 8),
        ('Banded Push-ups', 3, 10, 7),
        ('Hammer Curl', 3, 10, 7),
    ],
    'Lower': [
        ('Romanian Deadlift', 3, 6, 8),
        ('Reverse Lunges', 3, 8, 7.5),
        ('GHR / Hamstring Curl', 3, 8, 8),
        ('Back Extensions', 3, 12, 7),
        ('Ab Wheel / Plank', 3, 30, 7),
        ('Front Squat (variations)', 3, 5, 8),
        ('Goblet Squat', 3, 8, 7.5),
        ('Leg Press', 3, 10, 7),
        ('Calf Raises', 4, 12, 7),
        ('Hip Thrust', 3, 8, 8),
        # Ab finishers
        ('Hanging Leg Raise', 3, 10, 7),
        ('Ab Wheel', 3, 10, 7.5),
        ('Plank', 3, 60, 7),
        ('Cable Crunch', 3, 12, 7),
        ('Russian Twist', 3, 20, 7),
    ],
    'Deadlift': [
        ('Deficit Deadlift', 3, 3, 8),
        ('Rack Pulls', 3, 5, 8),
        ('Bent-over Row', 4, 6, 8),
        ('Hamstring Curl', 3, 10, 7),
        ('Back Extensions', 3, 12, 7),
        ('Block Pulls', 3, 3, 8),
        ('Kettlebell Swings', 3, 12, 7),
        ('Glute Bridge', 3, 8, 7.5),
        ('Farmer Carries', 3, 40, 7),
        ('Single-leg RDL', 3, 8, 7.5),
    ]
}

# Optional video links (we'll provide YouTube search links if no direct video provided)
ACCESSORY_VIDEOS = {
    'Back Extensions': '',
    'Close-grip Bench': '',
    'Incline Dumbbell Press': '',
    'Pendlay Row': '',
    'Face Pulls': '',
    'Tricep Pressdown': '',
    'Overhead Press': '',
    'Lat Pulldown': '',
    'Dumbbell Row': '',
    'Banded Push-ups': '',
    'Hammer Curl': '',
    'Romanian Deadlift': '',
    'Reverse Lunges': '',
    'GHR / Hamstring Curl': '',
    'Ab Wheel / Plank': '',
    'Front Squat (variations)': '',
    'Goblet Squat': '',
    'Leg Press': '',
    'Calf Raises': '',
    'Hip Thrust': '',
    'Deficit Deadlift': '',
    'Rack Pulls': '',
    'Bent-over Row': '',
    'Hamstring Curl': '',
    'Block Pulls': '',
    'Kettlebell Swings': '',
    'Glute Bridge': '',
    'Farmer Carries': '',
    'Single-leg RDL': '',
}

st.subheader("1) Enter your maxes (lb)")
c1, c2, c3 = st.columns(3)

with c1:
    bench_max = st.number_input("Bench max (or training max)", min_value=0.0, value=135.0, step=5.0)
with c2:
    squat_max = st.number_input("Squat max (or training max)", min_value=0.0, value=225.0, step=5.0)
with c3:
    deadlift_max = st.number_input("Deadlift max (or training max)", min_value=0.0, value=315.0, step=5.0)

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

# If ME day is chosen, allow choosing target rep (1/3/5) or custom top percentage
me_top_choice = None
me_custom_pct = None
if day.startswith("ME"):
    me_top_choice = st.selectbox("ME target", ["1RM (single)", "3RM", "5RM", "Custom %"])
    if me_top_choice == "Custom %":
        me_custom_pct = st.number_input("Custom top % of 1RM (e.g. 90 for 90%)", min_value=50.0, max_value=100.0, value=95.0, step=0.5)


st.subheader("3) Optional accommodating resistance")
use_bands = st.toggle("I’m using bands/chains (estimate top weight)")
band_top = 0.0
if use_bands:
    band_top = st.number_input("Estimated band/chain weight at the TOP (lb)", min_value=0.0, value=0.0, step=5.0)
    st.caption("The app will subtract this from your target 'total at top' to estimate bar weight.")

st.divider()

# --- Decorative collage in side spaces (optional) ---
show_collage = st.checkbox("Show side collage (decorative)", value=False)
if show_collage:
    collage_dir = Path(__file__).parent / 'collage'
    if not collage_dir.exists():
        try:
            collage_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    # collect images
    exts = ('.png', '.jpg', '.jpeg', '.svg', '.gif')
    files = [p for p in sorted(collage_dir.iterdir()) if p.suffix.lower() in exts]
    if not files:
        st.info("No collage images found. Save images (png/jpg/svg) into the 'collage' folder next to APP.py to use the collage.")
    else:
        img_size = st.slider('Collage image width (px)', min_value=60, max_value=180, value=100)
        img_opacity = st.slider('Collage opacity', min_value=0.1, max_value=1.0, value=0.9)

        left_imgs = files[0::2]
        right_imgs = files[1::2]

        def to_data_uri(path: Path):
            b = path.read_bytes()
            typ = 'svg+xml' if path.suffix.lower() == '.svg' else path.suffix.lower().lstrip('.')
            b64 = base64.b64encode(b).decode('utf-8')
            return f"data:image/{typ};base64,{b64}"

        left_html = ''.join([f'<img src="{to_data_uri(p)}" style="width:{img_size}px;border-radius:8px;margin:6px;opacity:{img_opacity};"/>' for p in left_imgs])
        right_html = ''.join([f'<img src="{to_data_uri(p)}" style="width:{img_size}px;border-radius:8px;margin:6px;opacity:{img_opacity};"/>' for p in right_imgs])

        collage_html = f"""
        <style>
        #left-collage, #right-collage {{position:fixed; top:80px; bottom:40px; width:{img_size+24}px; overflow:auto; display:flex; flex-direction:column; align-items:center; gap:6px; pointer-events:none; z-index:9999;}}
        #left-collage {{left:6px}}
        #right-collage {{right:6px}}
        @media print {{ #left-collage, #right-collage {{ display:none }} }}
        </style>
        <div id="left-collage">{left_html}</div>
        <div id="right-collage">{right_html}</div>
        """

        st.markdown(collage_html, unsafe_allow_html=True)

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


def show_me_warmups(base, rounding, me_pcts=None, top_pct=0.95, top_desc=None):
    # adjusted warmup percentages for ME days
    default = [0.30, 0.45, 0.60, 0.75, 0.88]
    warmup_pcts = me_pcts or default
    reps_map = {0.30: 10, 0.45: 5, 0.60: 3, 0.75: 2, 0.88: 1}
    warmups = []
    for p in warmup_pcts:
        w = round_to_increment(base * p, rounding)
        reps = reps_map.get(p, 3 if p >= 0.5 else 5)
        warmups.append((int(p * 100), reps, w))
    top_w = round_to_increment(base * top_pct, rounding)
    # display
    st.subheader("Warmup progression (ME)")
    for pct, reps, w in warmups:
        st.write(f"{pct}% x {reps}: {w:.1f} lb")
    desc = top_desc or ("work up to a heavy single" if abs(top_pct-0.95)<0.01 else f"work up to target ({int(top_pct*100)}% of 1RM)")
    st.write(f"Top work suggestion: {int(top_pct*100)}% -> {top_w:.1f} lb ({desc})")


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

    # determine top percentage based on user choice
    # sensible defaults: 1RM ~95%, 3RM ~92%, 5RM ~90%
    top_pct = 0.95
    top_desc = None
    try:
        if me_top_choice == "3RM":
            top_pct = 0.92
            top_desc = "work up to a heavy triple"
        elif me_top_choice == "5RM":
            top_pct = 0.90
            top_desc = "work up to a heavy 5RM"
        elif me_top_choice == "Custom %" and me_custom_pct:
            top_pct = float(me_custom_pct) / 100.0
            top_desc = f"custom target ({int(float(me_custom_pct))}%)"
        else:
            top_pct = 0.95
            top_desc = "work up to a heavy single"
    except Exception:
        top_pct = 0.95
        top_desc = "work up to a heavy single"

    show_me_warmups(base, rounding, me_pcts=me_pcts_parsed, top_pct=top_pct, top_desc=top_desc)

st.subheader("Suggested sets × reps")
st.write(DEFAULTS.get(day, {}))

# --- Accessories Section ---
st.subheader("Accessories")
# pick accessory pool based on day
if 'Bench' in day or 'Upper' in day:
    pool_key = 'Upper'
elif 'Deadlift' in day:
    pool_key = 'Deadlift'
else:
    pool_key = 'Lower'

# Layout: accessories on left, RPE chart on right
left_col, right_col = st.columns([2, 1])

# Beginner-friendly option: show how-to video links
if 'show_videos' not in st.session_state:
    st.session_state['show_videos'] = True
show_videos = st.checkbox("Show how-to video links for accessories (beginner friendly)", value=st.session_state['show_videos'])
st.session_state['show_videos'] = show_videos

with left_col:
    options = [a[0] for a in ACCESSORY_DEFAULTS.get(pool_key, [])]
    # on lower days offer an option to include ab finishers by default
    include_ab_finishers = False
    if pool_key == 'Lower':
        include_ab_finishers = st.checkbox('Include ab finishers (recommended for lower days)', value=True)
    # default selection: first 3 items; if include_ab_finishers, expand defaults to include common finishers
    default_sel = options[:3]
    if pool_key == 'Lower' and include_ab_finishers:
        # try to include ab finishers by name
        ab_names = ['Hanging Leg Raise', 'Ab Wheel', 'Plank', 'Ab Wheel / Plank']
        for n in options:
            if n in ab_names and n not in default_sel:
                default_sel.append(n)

    chosen = st.multiselect("Choose accessories", options=options, default=default_sel)

    if chosen:
        st.write("Customize sets / reps / RPE for selected accessories:")
        for name in chosen:
            # find defaults
            default = next((t for t in ACCESSORY_DEFAULTS[pool_key] if t[0] == name), None)
            d_sets, d_reps, d_rpe = (default[1], default[2], default[3]) if default else (3, 8, 7.5)
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                sets = st.number_input(f"{name} sets", min_value=1, max_value=10, value=d_sets, key=f"{name}-sets")
            with c2:
                reps = st.number_input(f"{name} reps", min_value=1, max_value=30, value=d_reps, key=f"{name}-reps")
            with c3:
                rpe = st.slider(f"{name} RPE", min_value=6.0, max_value=10.0, value=float(d_rpe), step=0.5, key=f"{name}-rpe")
            st.write(f"• {name}: {sets} x {reps} @ RPE {rpe}")
            # show beginner video link if user wants
            if st.session_state.get('show_videos', True):
                vid = ACCESSORY_VIDEOS.get(name, '')
                if vid:
                    st.markdown(f"[Watch how to: {name}]({vid})")
                else:
                    # fallback to YouTube search link
                    query = name.replace(' ', '+')
                    search_url = f"https://www.youtube.com/results?search_query={query}+exercise+technique"
                    st.markdown(f"[Search videos for: {name}]({search_url})")
    else:
        st.write("No accessories selected. Use the pick list to add common accessories for this day.")

with right_col:
    # load RPE chart relative to this script
    base = Path(__file__).parent
    # prefer common raster image if user saved the provided image
    candidates = [base / 'rpe_chart.png', base / 'rpe_chart.jpg', base / 'rpe_chart.jpeg', base / 'rpe_chart.svg']
    found = None
    for p in candidates:
        if p.exists():
            found = p
            break
    if found:
        st.image(str(found), caption="RPE Chart", use_column_width=True)
    else:
        st.write("RPE chart not found. Save the provided image as 'rpe_chart.png' next to this script.")

# Quick starter videos and links for beginners
with st.expander("Beginner: Quick starter videos and links", expanded=False):
    st.markdown("**Suggested starter links**")
    links = {
        'How to warm up (search)': 'https://www.youtube.com/results?search_query=warm+up+for+strength+training',
        'Understanding RPE (search)': 'https://www.youtube.com/results?search_query=RPE+scale+explanation',
        'How to squat (search)': 'https://www.youtube.com/results?search_query=how+to+squat+technique',
        'How to bench press (search)': 'https://www.youtube.com/results?search_query=how+to+bench+press+technique',
        'How to deadlift (search)': 'https://www.youtube.com/results?search_query=how+to+deadlift+technique',
    }
    for label, url in links.items():
        st.markdown(f"- [{label}]({url})")

st.divider()

with st.expander("Customize the percentages (optional)"):
    st.write("If you want different waves, adjust these in the code:")
    st.code("DE_UPPER_WAVE = {1: 0.50, 2: 0.55, 3: 0.60}\nDE_LOWER_WAVE = {1: 0.50, 2: 0.55, 3: 0.60}")

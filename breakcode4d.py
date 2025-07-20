import streamlit as st
import random
from datetime import datetime

# --- Fungsi Baca Fail draws.txt ---
def load_draws(filename="draws.txt"):
    draws = []
    try:
        with open(filename, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2:
                    date, number = parts
                    if len(number) == 4 and number.isdigit():
                        draws.append({'date': date, 'number': number})
    except FileNotFoundError:
        return []
    return draws

# --- Fungsi Dapatkan 5 Digit Terbaik per Pick (Frequency) ---
def get_top5_digits(draws, recent_n=30):
    last_draws = draws[-recent_n:]
    freq = [dict() for _ in range(4)]

    for draw in last_draws:
        number = draw['number']
        for i, digit in enumerate(number):
            freq[i][digit] = freq[i].get(digit, 0) + 1

    top5_per_pick = []
    for f in freq:
        sorted_digits = sorted(f.items(), key=lambda x: (-x[1], x[0]))
        top5_digits = [d[0] for d in sorted_digits[:5]]
        top5_per_pick.append(top5_digits)

    return top5_per_pick

# --- Fungsi Elak Pick Sama ---
def ensure_unique_picks(top5_per_pick):
    picks = []
    used = set()
    max_attempt = 50
    for i in range(4):
        attempt = 0
        while attempt < max_attempt:
            pick = random.sample(top5_per_pick[i], 5)
            key = tuple(pick)
            if key not in used:
                picks.append(pick)
                used.add(key)
                break
            attempt += 1
        else:
            picks.append(random.sample("0123456789", 5))  # fallback
    return picks

# --- Fungsi Jana 10 Kombinasi Ramalan ---
def generate_predictions(picks):
    predictions = []
    for _ in range(10):
        num = ''.join(random.choice(picks[i]) for i in range(4))
        predictions.append(num)
    return predictions

# --- UI Streamlit ---
st.set_page_config(page_title="Breakcode4D", layout="centered")

draws = load_draws()
if not draws:
    st.error("❌ Gagal baca draws.txt")
    st.stop()

last_draw = draws[-1]
last_date = last_draw['date']
last_number = last_draw['number']

st.markdown(f"### 📅 Tarikh Draw Terkini: `{last_date}`  —  🎯 Nombor: `{last_number}`")
st.title("🔐 Breakcode4D Predictor (Streamlit)")

# --- Butang Jana Ramalan ---
if st.button("🧠 Jana Ramalan"):
    base = get_top5_digits(draws)
    picks = ensure_unique_picks(base)
    predictions = generate_predictions(picks)

    st.subheader("📦 Padanan 5 Digit Setiap Pick:")
    for i, p in enumerate(picks, 1):
        st.text(f"Pick {i}: {' '.join(p)}")

    st.subheader("🎯 10 Nombor Ramalan:")
    row1 = '   '.join(predictions[:5])
    row2 = '   '.join(predictions[5:])
    st.markdown(f"<pre style='text-align: center; font-size: 20px'>{row1}\n{row2}</pre>", unsafe_allow_html=True)

# --- Footer ---
st.markdown("---")
st.markdown("🧮 Powered by **Breakcode4D AI** | Versi Streamlit ✅")

import streamlit as st
import random
from datetime import datetime
import os

# ==== Tetapan Laluan Fail ====
DATA_DIR = "data"
DRAW_PATH = os.path.join(DATA_DIR, "draw.txt")
BASE_PATH = os.path.join("output", "base.txt")
RAMALAN_PATH = os.path.join("output", "ramalan.txt")

# ==== Fungsi: Muat Data Draw ====
def load_draws(n=30):
    if not os.path.exists(DRAW_PATH):
        return []
    with open(DRAW_PATH, "r") as f:
        lines = f.readlines()
    lines = [line.strip() for line in lines if line.strip()]
    return lines[-n:]

# ==== Fungsi: Simulasi Kemas Kini Draw ====
def update_draw_data():
    today = datetime.today().strftime("%Y-%m-%d")
    fake_number = f"{random.randint(0, 9999):04d}"
    new_line = f"{today} {fake_number}\n"
    with open(DRAW_PATH, "a") as f:
        f.write(new_line)
    return new_line.strip()

# ==== Fungsi: Kira Frequency Digit ====
def digit_frequency(draws):
    freq = [0] * 10
    for entry in draws:
        _, number = entry.split()
        for digit in number:
            freq[int(digit)] += 1
    return freq

# ==== Fungsi: Pilih Top 5 Digit ====
def select_top_digits(freq):
    return sorted(range(10), key=lambda x: freq[x], reverse=True)[:5]

# ==== Fungsi: Jana Base.txt ====
def generate_base(draws):
    picks = []
    for i in range(4):  # Pick 1–4
        freq = [0] * 10
        for entry in draws:
            _, number = entry.split()
            digit = number[i]
            freq[int(digit)] += 1
        top_digits = select_top_digits(freq)
        picks.append(top_digits)
    with open(BASE_PATH, "w") as f:
        for i, pick in enumerate(picks, 1):
            f.write(f"Pick {i}: {' '.join(map(str, pick))}\n")
    return picks

# ==== Fungsi: Jana 10 Kombinasi Ramalan ====
def generate_predictions(picks):
    all_combos = []
    while len(all_combos) < 10:
        combo = [str(random.choice(pick)) for pick in picks]
        if combo not in all_combos:
            all_combos.append(combo)
    with open(RAMALAN_PATH, "w") as f:
        for i, combo in enumerate(all_combos, 1):
            f.write(f"{i:02d}. {''.join(combo)}\n")
    return all_combos

# ==== UI ====
st.set_page_config(page_title="Breakcode4D", layout="centered")
st.title("🔮 Breakcode4D – Sistem Ramalan 4D")

st.markdown("Ramalan berdasarkan 30 draw terakhir")

# --- Butang Kemas Kini Draw ---
if st.button("🔁 Kemas Kini Draw"):
    new_result = update_draw_data()
    st.success(f"Kemas Kini Berjaya: {new_result}")
    st.stop()  # Gantikan rerun, supaya reload berlaku bersih

# --- Papar Keputusan Terkini ---
draws = load_draws()
if draws:
    last_date, last_number = draws[-1].split()
    st.markdown(f"📅 **Keputusan Terkini:** `{last_date}` - **{last_number}**")

st.divider()

# --- Butang Jana Ramalan ---
if st.button("🧠 Jana Ramalan"):
    picks = generate_base(draws)
    ramalan = generate_predictions(picks)
    st.success("Ramalan berjaya dijana!")

    # Papar hasil ramalan
    st.subheader("🔢 10 Ramalan Breakcode4D:")
    ramalan_baris_1 = ramalan[:5]
    ramalan_baris_2 = ramalan[5:]
    baris_1 = "  ".join("**" + "".join(r) + "**" for r in ramalan_baris_1)
    baris_2 = "  ".join("**" + "".join(r) + "**" for r in ramalan_baris_2)
    st.markdown(f"<div style='text-align: center; font-size: 24px;'>{baris_1}<br>{baris_2}</div>", unsafe_allow_html=True)

# --- Debug: Lihat Draw.txt ---
with st.expander("📖 Lihat 30 Draw Terakhir"):
    st.text("\n".join(draws))
# breakcode4d.py

import streamlit as st
from datetime import datetime
from collections import Counter
import random
import os
import requests
import re

DRAW_PATH = "data/draw.txt"
BASE_PATH = "output/base.txt"
PREDICT_PATH = "output/ramalan.txt"

# === Fungsi Asas ===

def load_draws(file_path=DRAW_PATH):
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r") as f:
        lines = f.read().splitlines()
        draws = []
        for line in lines:
            try:
                date_str, number = line.strip().split()
                draws.append({"date": date_str, "number": number})
            except:
                continue
        return draws

def save_draws(draws, file_path=DRAW_PATH):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        for draw in draws:
            f.write(f"{draw['date']} {draw['number']}\n")

def update_draw_data():
    url = "https://www.gdlotto.com/Result/4D"
    response = requests.get(url)
    if not response.ok:
        return 0
    html = response.text
    pattern = r"(\d{2}-\d{2}-\d{4})\s*<.*?>\s*1st Prize\s*<.*?>\s*(\d{4})"
    matches = re.findall(pattern, html)
    new_draws = [{"date": datetime.strptime(d, "%d-%m-%Y").strftime("%Y-%m-%d"), "number": n} for d, n in matches]
    if not new_draws:
        return 0
    existing = load_draws()
    existing_dates = {d["date"] for d in existing}
    combined = existing + [d for d in new_draws if d["date"] not in existing_dates]
    combined.sort(key=lambda x: x["date"])
    save_draws(combined)
    return len(combined) - len(existing)

def get_last_draw(draws):
    return draws[-1] if draws else {"date": "-", "number": "----"}

# === Analisis Frequency dan Ramalan ===

def analyze_frequency(draws, limit=30):
    picks = [[], [], [], []]
    for draw in draws[-limit:]:
        number = draw["number"]
        if len(number) == 4:
            for i in range(4):
                picks[i].append(number[i])
    freq_result = []
    for i in range(4):
        counter = Counter(picks[i])
        top5 = [x[0] for x in counter.most_common(5)]
        freq_result.append(top5)
    return freq_result

def generate_combinations(base_digits):
    return [f"{a}{b}{c}{d}" for a in base_digits[0] for b in base_digits[1] for c in base_digits[2] for d in base_digits[3]]

def generate_predictions(base_digits, count=10):
    all_combos = generate_combinations(base_digits)
    return random.sample(all_combos, min(count, len(all_combos)))

def save_base(base_digits, path=BASE_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for i, pick in enumerate(base_digits):
            f.write(f"Pick {i+1}: {' '.join(pick)}\n")

def save_predictions(predictions, path=PREDICT_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for i, pred in enumerate(predictions, 1):
            f.write(f"{i:02d}: {pred}\n")

# === Insight ===

def get_last_result_insight(draws, limit=30):
    if not draws:
        return "Tiada data draw tersedia."
    last_draw = draws[-1]
    last_number = last_draw["number"]
    last_date = last_draw["date"]

    all_numbers = [d["number"] for d in draws[-(limit+1):-1]]
    digit_counter = [Counter() for _ in range(4)]
    for number in all_numbers:
        for i, digit in enumerate(number):
            digit_counter[i][digit] += 1

    insight_lines = [f"📅 Nombor terakhir naik: {last_number} pada {last_date}", ""]
    for i, digit in enumerate(last_number):
        freq = digit_counter[i][digit]
        pick_name = f"Pick {i+1}"
        rank = sorted(digit_counter[i].values(), reverse=True).index(freq) + 1 if freq else "Tiada"
        insight_lines.append(f"{pick_name}: Digit '{digit}' berada pada ranking #{rank} (frekuensi: {freq}x)")
    insight_lines.append("")
    insight_lines.append("💡 Kemungkinan naik semula:")
    insight_lines.append("- Digit dengan ranking tinggi biasanya konsisten muncul.")
    insight_lines.append("- Pantau digit yang sudah muncul 2–3 kali dalam 10 draw terakhir.")
    return "\n".join(insight_lines)

# === Dummy Tambahan ===

def cross_pick_analysis(draws, limit=30):
    return "📊 Cross Pick: Analisis silang digit antara setiap Pick sedang dalam pembangunan."

def ai_tuner_suggestion(draws):
    return "🧠 AI Tuner: Sistem akan laraskan filter & scoring secara automatik."

def system_recommendation(draws):
    return "💡 Cadangan: Gabungkan digit ranking tinggi + yang belum muncul dalam 20 draw."

# === Streamlit UI ===

st.set_page_config(page_title="Breakcode4D", layout="centered")
st.title("🎯 Breakcode4D - Ramalan 4D Berasaskan Analisis")

draws = load_draws()

# Butang Kemas Kini Draw
if st.button("📥 Kemas Kini Draw"):
    added = update_draw_data()
    if added > 0:
        st.success(f"{added} draw baru telah dikemaskini.")
    else:
        st.info("Tiada draw baru ditemui.")
    st.experimental_rerun()

draws = load_draws()
last_draw = get_last_draw(draws)
st.markdown(f"**Keputusan Terkini:** `{last_draw['date']} - {last_draw['number']}`")

# Insight
with st.expander("🔍 Analisis Insight"):
    st.text(get_last_result_insight(draws))

# Papar Base Semalam
if os.path.exists(BASE_PATH):
    st.markdown("### 📦 Base.txt Semalam")
    with open(BASE_PATH) as f:
        st.code(f.read())

# Butang Tambahan
col1, col2, col3 = st.columns(3)
if col1.button("📊 Analisis Cross Pick"):
    st.info(cross_pick_analysis(draws))
if col2.button("🧠 Tuner AI"):
    st.success(ai_tuner_suggestion(draws))
if col3.button("💡 Cadangan Sistem Terbaik"):
    st.warning(system_recommendation(draws))

# Butang Jana Ramalan
if st.button("🚀 Jana Ramalan Terkini"):
    base = analyze_frequency(draws, limit=30)
    save_base(base)
    ramalan = generate_predictions(base)
    save_predictions(ramalan)
    st.success("Ramalan berjaya dijana!")
    st.markdown("### 🔮 Ramalan 10 Nombor")
    colA, colB = st.columns(2)
    for i, r in enumerate(ramalan):
        (colA if i < 5 else colB).markdown(f"**{i+1:02d}**: `{r}`")
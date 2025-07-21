# ===================== IMPORT =====================
import streamlit as st
import os
import re
import requests
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import random
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# ===================== FUNGSI FAIL & DRAW =====================
def load_draws(file_path='data/draws.txt'):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            lines = f.read().splitlines()
            draws = []
            for line in lines:
                match = re.match(r"(\d{4}-\d{2}-\d{2})\s+(\d{4})", line)
                if match:
                    date, number = match.groups()
                    draws.append({'date': date, 'number': number})
            return draws
    else:
        return []

def save_draws(draws, file_path='data/draws.txt'):
    with open(file_path, 'w') as f:
        for d in draws:
            f.write(f"{d['date']} {d['number']}\n")

def get_1st_prize():
    url = "https://gdlotto.net"
    try:
        response = requests.get(url)
        matches = re.findall(r"(\d{4})\s+1st", response.text)
        if matches:
            today = datetime.today().strftime('%Y-%m-%d')
            return {'date': today, 'number': matches[0]}
    except:
        return None

def update_draws():
    draws = load_draws()
    latest_draw = get_1st_prize()
    if latest_draw and (not draws or draws[-1]['number'] != latest_draw['number']):
        draws.append(latest_draw)
        save_draws(draws)

# ===================== BASE FUNCTIONS =====================
def load_base_from_file(path='data/base.txt'):
    if os.path.exists(path):
        with open(path, "r") as f:
            lines = f.read().splitlines()
            return [list(map(int, line.strip().split())) for line in lines if line.strip()]
    return []

def save_base_to_file(base, path='data/base.txt'):
    with open(path, 'w') as f:
        for line in base:
            f.write(' '.join(map(str, line)) + '\n')

def score_digits(numbers, n=30):
    digit_scores = [Counter() for _ in range(4)]
    recent_draws = numbers[-n:]

    for number in recent_draws:
        for pos, digit in enumerate(number):  # '1234' → digit '1', '2', ...
            digit_scores[pos][digit] += 1

    top_digits = []
    for counter in digit_scores:
        top = [int(d) for d, _ in counter.most_common(5)]
        top_digits.append(top)

    return top_digits

def generate_predictions(base, n=4):
    predictions = set()
    while len(predictions) < n:
        number = ''.join(str(random.choice(base[i])) for i in range(4))
        predictions.add(number)
    return list(predictions)

# ===================== RUN BACKTEST =====================
def run_backtest(draws, num_days=10):
    if len(draws) < num_days:
        st.warning("❗ Tidak cukup draw untuk backtest.")
        return

    results = []
    st.markdown("### 🔁 Backtest 10 Hari Terakhir")

    for i in range(num_days):
        draw = draws[-(i+1)]
        draw_date, first_prize = draw['date'], draw['number']
        training_draws = draws[:-(i+1)]
        if len(training_draws) < 30:
            st.warning(f"❗ Tak cukup data sebelum {draw_date}. Skip.")
            continue
        training_numbers = [d['number'] for d in training_draws]
        base = score_digits(training_numbers, 30)
        predictions = generate_predictions(base, n=4)
        insight = ["✅" if p == first_prize else "❌" for p in predictions]

        results.append({
            "Tarikh": draw_date,
            "Result 1st": first_prize,
            "P1": predictions[0],
            "P2": predictions[1],
            "P3": predictions[2],
            "P4": predictions[3],
            "Insight": f"P1:{insight[0]} P2:{insight[1]} P3:{insight[2]} P4:{insight[3]}"
        })

        st.markdown(f"### 🎯 Tarikh: {draw_date}")
        st.markdown(f"**Result 1st**: `{first_prize}`")
        for j, b in enumerate(base):
            st.text(f"P{j+1}: {' '.join(str(d) for d in b)}")
        st.markdown(f"**Insight:** `{results[-1]['Insight']}`")
        st.markdown("---")

    df = pd.DataFrame(results[::-1])
    success_count = sum(1 for r in results if "✅" in r["Insight"])
    st.success(f"🎉 Jumlah menang tepat: {success_count} daripada {len(results)}")
    st.markdown("### 📊 Ringkasan Backtest:")
    st.dataframe(df, use_container_width=True)

# ===================== STREAMLIT LAYOUT =====================
st.set_page_config(page_title="Breakcode4D Predictor", layout="wide")
st.title("🔮 Breakcode4D Predictor")

# Butang atas
col1, col2 = st.columns([1, 1])
with col1:
    if st.button("🔁 Update Draw Terkini"):
        update_draws()
        st.success("✅ Draw telah dikemaskini!")

with col2:
    st.markdown(
        '<a href="https://batman11.net/RegisterByReferral.aspx?MemberCode=BB1845" target="_blank"><button style="width:100%;padding:10px;font-size:16px;">📝 Register Sini</button></a>',
        unsafe_allow_html=True
    )

# ===================== TABS =====================
tabs = st.tabs(["📈 Insight", "📊 Visualisasi", "🧠 Ramalan AI", "🔁 Backtest"])

with tabs[0]:
    draws = load_draws()
    if draws:
        st.markdown("### 📅 Draw Terkini")
        st.write(draws[-1])
        st.markdown("### 🧮 Base Sekarang:")
        numbers = [d['number'] for d in draws]
        base = score_digits(numbers, 30)
        for i, b in enumerate(base):
            st.text(f"P{i+1}: {' '.join(str(d) for d in b)}")
    else:
        st.warning("Tiada draw data.")

with tabs[1]:
    draws = load_draws()
    if draws:
        df = pd.DataFrame(draws)
        digit_count = [Counter() for _ in range(4)]
        for d in df['number']:
            for i, ch in enumerate(d):
                digit_count[i][int(ch)] += 1
        fig, axs = plt.subplots(1, 4, figsize=(16, 4))
        for i in range(4):
            sns.barplot(x=list(digit_count[i].keys()), y=list(digit_count[i].values()), ax=axs[i])
            axs[i].set_title(f'Digit Posisi {i+1}')
        st.pyplot(fig)
    else:
        st.warning("Tiada data untuk visualisasi.")

with tabs[2]:
    draws = load_draws()
    if draws:
        numbers = [d['number'] for d in draws]
        base = score_digits(numbers, 30)
        predictions = generate_predictions(base, 10)
        st.markdown("### 🤖 Nombor Diramal:")
        for p in predictions:
            st.code(p)
    else:
        st.warning("Tiada data untuk ramalan.")

with tabs[3]:
    draws = load_draws()
    if draws:
        run_backtest(draws, num_days=10)
    else:
        st.warning("Tiada data untuk backtest.")
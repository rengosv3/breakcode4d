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

# ========== Fungsi Asas ==========
def load_draws(file_path='data/draws.txt'):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r') as f:
        return [{'date': line.split()[0], 'number': line.split()[1]} for line in f if len(line.strip().split()) == 2]

def save_base_to_file(base_digits, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        for pick in base_digits:
            f.write(' '.join(pick) + '\n')

def load_base_from_file(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r') as f:
        return [line.strip().split() for line in f if line.strip()]

def get_1st_prize(date_str):
    url = f"https://gdlotto.net/results/ajax/_result.aspx?past=1&d={date_str}"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if r.status_code == 200:
            match = re.search(r'id="1stPz">(\d{4})<', r.text)
            return match.group(1) if match else None
    except:
        return None

def update_draws(file_path='data/draws.txt', max_days_back=60):
    draws = load_draws(file_path)
    last_date = datetime.today() - timedelta(days=max_days_back) if not draws else datetime.strptime(draws[-1]['date'], "%Y-%m-%d")
    today = datetime.today()
    current = last_date + timedelta(days=1)
    added = []
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'a') as f:
        while current <= today:
            date_str = current.strftime("%Y-%m-%d")
            prize = get_1st_prize(date_str)
            if prize:
                f.write(f"{date_str} {prize}\n")
                added.append({'date': date_str, 'number': prize})
            current += timedelta(days=1)
    return f"✔ {len(added)} draw baru ditambah." if added else "✔ Tiada draw baru ditambah."

def score_digits(draws, recent_n=30):
    weights = [Counter() for _ in range(4)]
    for i, draw in enumerate(draws[-recent_n:]):
        for j, digit in enumerate(draw['number']):
            weights[j][digit] += recent_n - i
    return [[d for d, _ in w.most_common(5)] for w in weights]

def generate_super_base(draws):
    b30 = score_digits(draws, 30)
    b60 = score_digits(draws, 60)
    b120 = score_digits(draws, 120)
    super_base = []
    for i in range(4):
        common = set(b30[i]) & set(b60[i]) & set(b120[i])
        combined = list(common) + [d for d in b30[i] if d not in common]
        super_base.append(combined[:5])
    return super_base

def generate_predictions(base_digits, n=10):
    result = set()
    while len(result) < n:
        combo = ''.join(random.choice(base_digits[i]) for i in range(4))
        result.add(combo)
    return sorted(list(result))

def cross_pick_analysis(draws):
    pick_data = [defaultdict(int) for _ in range(4)]
    for draw in draws:
        for i, digit in enumerate(draw['number']):
            pick_data[i][digit] += 1
    return [f"Pick {i+1}: " + ', '.join(f"{d} ({c}x)" for d, c in sorted(pd.items(), key=lambda x: -x[1])[:5])
            for i, pd in enumerate(pick_data)]

def show_digit_distribution(draws):
    df = pd.DataFrame([list(d['number']) for d in draws], columns=["P1", "P2", "P3", "P4"])
    fig, axs = plt.subplots(2, 2, figsize=(10, 6))
    for i in range(4):
        sns.countplot(x=df.iloc[:, i], ax=axs[i // 2][i % 2], palette="Set2")
        axs[i // 2][i % 2].set_title(f"Digit Pick {i+1}")
    st.pyplot(fig)

# ========== UI Streamlit ==========
st.set_page_config(page_title="Breakcode4D", layout="wide")
st.title("🔢 Breakcode4D Predictor")

col1, col2 = st.columns([2, 2])
with col1:
    if st.button("📥 Update Draw Terkini"):
        msg = update_draws()
        st.success(msg)
with col2:
    st.markdown('[🔗 Register Sini Batman11](https://batman11.net/RegisterByReferral.aspx?MemberCode=BB1845)', unsafe_allow_html=True)

draws = load_draws()
latest_number = draws[-1]['number'] if draws else 'Tiada'
latest_date = draws[-1]['date'] if draws else 'Tiada'
base = load_base_from_file('data/base.txt')
super_base = generate_super_base(draws)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📌 Insight", "🎯 Base & Ramalan", "🌟 Super Base", "💡 AI Tuner", "📊 Visualisasi", "🔁 Cross Pick"])

with tab1:
    st.subheader("📌 Insight Nombor Terakhir")
    st.markdown(f"📅 Nombor terakhir naik: **{latest_number}** pada {latest_date}")
    for i in range(4):
        st.markdown(f"Pick {i+1}: " + ' '.join(base[i]))
    st.info("💡 AI Insight:\n- Digit dalam Base & Cross berkemungkinan besar naik semula.\n- Ranking tinggi (Top 3) menunjukkan konsistensi kuat.")

with tab2:
    st.subheader("🎯 Base dan Ramalan")
    for i in range(4):
        st.markdown(f"Pick {i+1}: " + ' '.join(base[i]))
    preds = generate_predictions(base)
    st.markdown("📈 Ramalan Nombor:")
    st.code('\n'.join(preds), language='text')

with tab3:
    st.subheader("🌟 Super Base")
    for i in range(4):
        st.markdown(f"Pick {i+1}: " + ' '.join(super_base[i]))

with tab4:
    st.subheader("💡 AI Tuner (Preview)")
    st.markdown("🚧 Bahagian ini sedang dibangunkan...")

with tab5:
    st.subheader("📊 Visualisasi Digit")
    if draws:
        show_digit_distribution(draws)
    else:
        st.warning("Tiada data draw untuk visualisasi.")

with tab6:
    st.subheader("🔁 Cross Pick Analysis")
    cp = cross_pick_analysis(draws)
    for line in cp:
        st.markdown(line)
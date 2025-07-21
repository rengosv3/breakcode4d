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
    if not os.path.exists(file_path): return []
    draws = []
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                draws.append({'date': parts[0], 'number': parts[1]})
    return draws

def save_base_to_file(base_digits, file_path='data/base.txt'):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        for pick in base_digits:
            f.write(' '.join(pick) + '\n')

def load_base_from_file(file_path):
    if not os.path.exists(file_path): return []
    with open(file_path, 'r') as f:
        return [line.strip().split() for line in f if line.strip()]

def display_base_as_text(file_path):
    if not os.path.exists(file_path): return "⚠️ Tiada fail dijumpai."
    with open(file_path, 'r') as f:
        return '\n'.join([f"Pick {i+1}: {line.strip()}" for i, line in enumerate(f) if line.strip()])

def get_1st_prize(date_str):
    url = f"https://gdlotto.net/results/ajax/_result.aspx?past=1&d={date_str}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if resp.status_code != 200: return None
        match = re.search(r'id="1stPz">(\d{4})<', resp.text)
        return match.group(1) if match else None
    except: return None

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
    if added:
        draws = load_draws(file_path)
        latest_base = score_digits(draws)
        save_base_to_file(latest_base, 'data/base.txt')
        save_base_to_file(latest_base, 'data/base_last.txt')
    return f"✔ {len(added)} draw baru ditambah." if added else "✔ Tiada draw baru ditambah."

# ========== Logik Base ==========
def score_digits(draws, recent_n=30):
    weights = [Counter() for _ in range(4)]
    for i, draw in enumerate(draws[-recent_n:]):
        for j, digit in enumerate(draw['number']):
            weights[j][digit] += recent_n - i
    return [[d for d, _ in pick.most_common(5)] for pick in weights]

def generate_super_base(draws):
    base_30 = score_digits(draws, 30)
    base_60 = score_digits(draws, 60)
    base_120 = score_digits(draws, 120)
    return [
        list(set(base_30[i]) & set(base_60[i]) & set(base_120[i])) + [d for d in base_30[i] if d not in base_60[i]]
        for i in range(4)
    ]

def generate_predictions(base_digits, n=10):
    result = set()
    while len(result) < n:
        result.add(''.join(random.choice(base_digits[i]) for i in range(4)))
    return sorted(result)

def ai_tuner(draws):
    base = score_digits(draws, 30)
    return [[d for d in pick if int(d)%2==0 or d in '579'] for pick in base]

def cross_pick_analysis(draws):
    pick_data = [defaultdict(int) for _ in range(4)]
    for draw in draws:
        for i, digit in enumerate(draw['number']):
            pick_data[i][digit] += 1
    return '\n'.join([
        f"Pick {i+1}: {', '.join(f'{d} ({c}x)' for d, c in sorted(pd.items(), key=lambda x:-x[1])[:5])}"
        for i, pd in enumerate(pick_data)
    ])

def get_last_result_insight(draws):
    if not draws: return "Tiada data draw tersedia."
    today = datetime.today().strftime("%Y-%m-%d")
    last_valid = next((d for d in reversed(draws) if d['date'] < today), None)
    if not last_valid: return "Tiada draw semalam."
    last_number = last_valid['number']
    last_date = last_valid['date']

    insight = [f"📅 Nombor terakhir naik: **{last_number}** pada {last_date}", "**Base Digunakan:**"]
    base_path = 'data/base_last.txt'
    if not os.path.exists(base_path):
        save_base_to_file(score_digits(draws[:-1]), base_path)
    base_digits = load_base_from_file(base_path)
    for i, pick in enumerate(base_digits):
        insight.append(f"- Pick {i+1}: {' '.join(pick)}")

    all_numbers = [d['number'] for d in draws if len(d['number']) == 4]
    digit_counter = [Counter() for _ in range(4)]
    for number in all_numbers:
        for i, digit in enumerate(number):
            digit_counter[i][digit] += 1
    cross_top = [[d for d, _ in c.most_common(5)] for c in digit_counter]

    for i, digit in enumerate(last_number):
        freq = digit_counter[i][digit]
        rank = sorted(digit_counter[i].values(), reverse=True).index(freq) + 1
        in_base = "✅" if digit in base_digits[i] else "❌"
        in_cross = "✅" if digit in cross_top[i] else "❌"
        score = 2*(rank <= 3) + (rank <= 5) + 2*(in_base == "✅") + (in_cross == "✅")
        label = "🔥 Sangat berpotensi" if score >= 4 else "👍 Berpotensi" if score >= 3 else "❓ Kurang pasti"
        insight.append(f"Pick {i+1}: Digit '{digit}' - Ranking #{rank}, Base: {in_base}, Cross: {in_cross} → **{label}**")

    insight += ["", "💡 **AI Insight:**", "- Digit dalam Base & Cross berkemungkinan besar naik semula.", "- Ranking tinggi (Top 3) menunjukkan konsistensi kuat."]
    return '\n'.join(insight)

def show_digit_heatmap(draws):
    df = pd.DataFrame([list(d['number']) for d in draws[-100:]], columns=["P1","P2","P3","P4"])
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.heatmap(df.apply(pd.Series.value_counts).fillna(0).T, annot=True, cmap="YlGnBu", ax=ax)
    st.pyplot(fig)

def show_digit_distribution(draws):
    df = pd.DataFrame([list(d['number']) for d in draws], columns=["P1","P2","P3","P4"])
    fig, axs = plt.subplots(2, 2, figsize=(10, 6))
    for i in range(4):
        sns.countplot(x=df.iloc[:, i], ax=axs[i], palette="Set2")
        axs[i].set_title(f"Digit di Pick {i+1}")
    st.pyplot(fig)

# ========== UI Streamlit ==========
st.set_page_config(page_title="Breakcode4D Predictor", layout="wide")
st.title("🔮 Breakcode4D Predictor")

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("📥 Update Draw Terkini"):
        msg = update_draws()
        st.success(msg)
        st.code(display_base_as_text('data/base.txt'))

with col2:
    st.markdown(
        """
        <a href="https://batman11.net/RegisterByReferral.aspx?MemberCode=BB1845" target="_blank">
            <button style="background-color:#4CAF50;color:white;padding:0.5em 1em;border:none;border-radius:5px;cursor:pointer;font-weight:bold;">
                🔗 Register Sini Batman11 & Dapat Bonus
            </button>
        </a>
        """,
        unsafe_allow_html=True,
    )

draws = load_draws()
if not draws:
    st.warning("⚠️ Sila klik 'Update Draw Terkini' dahulu, tunggu sehinga selesai 1-2 minit.")
    st.stop()

tabs = st.tabs(["📌 Insight", "🧠 Ramalan", "🧪 AI Tuner", "📊 Visual", "🔁 Cross Pick"])
with tabs[0]:
    st.markdown(get_last_result_insight(draws))

with tabs[1]:
    st.subheader("Base Digunakan")
    base_digits = load_base_from_file('data/base_super.txt') if os.path.exists('data/base_super.txt') else load_base_from_file('data/base.txt')
    for i, pick in enumerate(base_digits):
        st.write(f"Pick {i+1}: {' '.join(pick)}")
    st.subheader("📊 10 Ramalan")
    preds = generate_predictions(base_digits)
    colA, colB = st.columns(2)
    for i in range(5):
        colA.text(preds[i])
        colB.text(preds[i+5])

with tabs[2]:
    if st.button("🚀 Jana Super Base"):
        super_base = generate_super_base(draws)
        save_base_to_file(super_base, 'data/base_super.txt')
        st.success("✔ Super Base disimpan.")
        st.code(display_base_as_text('data/base_super.txt'))
    if st.button("🎯 AI Tuner"):
        tuned = ai_tuner(draws)
        for i, pick in enumerate(tuned):
            st.write(f"Tuned Pick {i+1}: {' '.join(pick)}")

with tabs[3]:
    show_digit_distribution(draws)
    show_digit_heatmap(draws)

with tabs[4]:
    if st.button("🔁 Papar Cross Pick"):
        st.text(cross_pick_analysis(draws))
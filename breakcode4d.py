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

# ===================== Load Draws =====================
def load_draws(file_path='data/draws.txt'):
    if not os.path.exists(file_path):
        return []
    draws = []
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                draws.append({'date': parts[0], 'number': parts[1]})
    return draws

# ===================== Save & Load Base =====================
def save_base_to_file(base_digits, file_path='data/base.txt'):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        for pick in base_digits:
            f.write(' '.join(pick) + '\n')

def load_base_from_file(file_path):
    if not os.path.exists(file_path):
        return []
    base = []
    with open(file_path, 'r') as f:
        for line in f:
            digits = line.strip().split()
            if digits:
                base.append(digits)
    return base

def display_base_as_text(file_path):
    if not os.path.exists(file_path):
        return "⚠️ Tiada fail dijumpai."
    lines = []
    with open(file_path, 'r') as f:
        for i, line in enumerate(f):
            digits = line.strip()
            if digits:
                lines.append(f"Pick {i+1}: {digits}")
    return '\n'.join(lines)

# ===================== Update Draw =====================
def get_1st_prize(date_str):
    url = f"https://gdlotto.net/results/ajax/_result.aspx?past=1&d={date_str}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if resp.status_code != 200:
            return None
        match = re.search(r'id="1stPz">(\d{4})<', resp.text)
        return match.group(1) if match else None
    except:
        return None

def update_draws(file_path='data/draws.txt', max_days_back=60):
    draws = load_draws(file_path)
    if not draws:
        last_date = datetime.today() - timedelta(days=max_days_back)
    else:
        last_date = datetime.strptime(draws[-1]['date'], "%Y-%m-%d")
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

# ===================== Score & Super Base =====================
def score_digits(draws, recent_n=30):
    weights = [Counter() for _ in range(4)]
    for i, draw in enumerate(draws[-recent_n:]):
        for j, digit in enumerate(draw['number']):
            weights[j][digit] += recent_n - i
    base = []
    for pick in weights:
        base.append([digit for digit, _ in pick.most_common(5)])
    return base

def generate_super_base(draws):
    base_30 = score_digits(draws, 30)
    base_60 = score_digits(draws, 60)
    base_120 = score_digits(draws, 120)
    super_base = []
    for i in range(4):
        common = set(base_30[i]) & set(base_60[i]) & set(base_120[i])
        combined = list(common) + [d for d in base_30[i] if d not in common]
        super_base.append(combined[:5])
    return super_base

# ===================== Prediction =====================
def generate_predictions(base_digits, n=10):
    all_combinations = set()
    while len(all_combinations) < n:
        combo = ''.join(random.choice(base_digits[i]) for i in range(4))
        all_combinations.add(combo)
    return sorted(list(all_combinations))

def cross_pick_analysis(draws):
    pick_data = [defaultdict(int) for _ in range(4)]
    for draw in draws:
        for i, digit in enumerate(draw['number']):
            pick_data[i][digit] += 1
    lines = []
    for i, pd in enumerate(pick_data):
        common = sorted(pd.items(), key=lambda x: -x[1])[:5]
        lines.append(f"Pick {i+1}: {', '.join(f'{d} ({c}x)' for d, c in common)}")
    return '\n'.join(lines)

# ===================== Last Insight =====================
def get_last_result_insight(draws):
    if not draws:
        return "Tiada data draw tersedia."

    today_str = datetime.today().strftime("%Y-%m-%d")
    last_valid = next((d for d in reversed(draws) if d['date'] < today_str), None)
    if not last_valid:
        return "Tiada data draw semalam tersedia."

    last_number = last_valid['number']
    last_date = last_valid['date']
    insight_lines = [f"📅 Nombor terakhir naik: **{last_number}** pada {last_date}\n"]

    all_numbers = [d['number'] for d in draws if len(d['number']) == 4]
    digit_counter = [Counter() for _ in range(4)]
    for number in all_numbers:
        for i, digit in enumerate(number):
            digit_counter[i][digit] += 1

    base_path = 'data/base_last.txt'
    if not os.path.exists(base_path):
        base_digits = score_digits(draws[:-1])
        save_base_to_file(base_digits, base_path)
    base_digits = load_base_from_file(base_path)

    cross_data = [defaultdict(int) for _ in range(4)]
    for number in all_numbers:
        for i, digit in enumerate(number):
            cross_data[i][digit] += 1
    cross_top = [[d for d, _ in sorted(c.items(), key=lambda x: -x[1])[:5]] for c in cross_data]

    insight_lines.append("**Base Digunakan:**")
    for i, pick in enumerate(base_digits):
        insight_lines.append(f"- Pick {i+1}: {' '.join(pick)}")
    insight_lines.append("")

    for i, digit in enumerate(last_number):
        freq = digit_counter[i][digit]
        rank = sorted(digit_counter[i].values(), reverse=True).index(freq) + 1
        in_base = "✅" if digit in base_digits[i] else "❌"
        in_cross = "✅" if digit in cross_top[i] else "❌"
        score = (2 if rank <= 3 else 1 if rank <= 5 else 0) + (2 if in_base == "✅" else 0) + (1 if in_cross == "✅" else 0)
        label = "🔥 Sangat berpotensi" if score >= 4 else "👍 Berpotensi" if score >= 3 else "❓ Kurang pasti"
        insight_lines.append(f"Pick {i+1}: Digit '{digit}' - Ranking #{rank}, Base: {in_base}, Cross: {in_cross} → **{label}**")

    insight_lines.append("\n💡 **AI Insight:**")
    insight_lines.append("- Digit dalam Base & Cross berkemungkinan besar naik semula.")
    insight_lines.append("- Ranking tinggi (Top 3) menunjukkan konsistensi kuat.")
    return '\n'.join(insight_lines)

# ===================== AI Tuner =====================
def ai_tuner(draws):
    base_score = score_digits(draws, recent_n=30)
    filtered = [[d for d in pick if int(d) % 2 == 0 or d in '579'] for pick in base_score]
    return filtered

# ===================== Visualization =====================
def show_digit_heatmap(draws):
    df = pd.DataFrame([list(d['number']) for d in draws[-100:]], columns=["P1", "P2", "P3", "P4"])
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.heatmap(df.apply(pd.Series.value_counts).fillna(0).T, annot=True, cmap="YlGnBu", ax=ax)
    st.pyplot(fig)

def show_digit_distribution(draws):
    df = pd.DataFrame([list(d['number']) for d in draws], columns=["P1", "P2", "P3", "P4"])
    fig, axs = plt.subplots(2, 2, figsize=(10, 6))
    for i in range(4):
        sns.countplot(x=df.iloc[:, i], ax=axs[i // 2][i % 2], palette="Set2")
        axs[i // 2][i % 2].set_title(f"Digit di Pick {i+1}")
    st.pyplot(fig)

# ===================== Streamlit App =====================
st.set_page_config(page_title="Breakcode4D Predictor", layout="wide")
st.title("🔮 Breakcode4D Predictor")

draws = load_draws()

tabs = st.tabs(["📥 Update Draw", "📌 Insight", "🧠 Ramalan", "🚀 AI Tools", "📈 Visual"])

with tabs[0]:
    if st.button("📥 Update Draw Terkini"):
        msg = update_draws()
        st.success(msg)
    st.markdown("### 📋 Base Hari Ini (Salin & Tampal)")
    st.code(display_base_as_text('data/base.txt'), language='text')

with tabs[1]:
    if draws:
        st.info(f"📅 Tarikh terakhir: **{draws[-1]['date']}** | 📊 Jumlah draw: **{len(draws)}**")
        st.markdown(get_last_result_insight(draws))
    else:
        st.warning("⚠️ Tiada data draw. Sila update terlebih dahulu.")

with tabs[2]:
    base_digits = load_base_from_file('data/base_super.txt') if os.path.exists('data/base_super.txt') else load_base_from_file('data/base.txt')
    preds = generate_predictions(base_digits)
    for i, pick in enumerate(base_digits):
        st.write(f"Pick {i+1}: {' '.join(pick)}")
    st.markdown("📊 10 Ramalan Terpilih:")
    col1, col2 = st.columns(2)
    for i in range(5):
        col1.text(preds[i])
        col2.text(preds[i+5])

with tabs[3]:
    if st.button("🔁 Cross Pick Analysis"):
        st.text(cross_pick_analysis(draws))
    if st.button("🚀 Jana Super Base"):
        super_base = generate_super_base(draws)
        save_base_to_file(super_base, 'data/base_super.txt')
        st.success("Super Base disimpan ke 'base_super.txt'")
        st.code(display_base_as_text('data/base_super.txt'), language='text')
    if st.button("🧪 AI Tuner"):
        tuned = ai_tuner(draws)
        for i, pick in enumerate(tuned):
            st.write(f"Tuned Pick {i+1}: {' '.join(pick)}")

with tabs[4]:
    show_digit_distribution(draws)
    show_digit_heatmap(draws)
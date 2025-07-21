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

# ===================== MUAT & SIMPAN BASE =====================
def load_draws(file_path='data/draws.txt'):
    if not os.path.exists(file_path):
        return []
    draws = []
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2 and re.match(r"^\d{4}$", parts[1]):
                draws.append({'date': parts[0], 'number': parts[1]})
    return draws

def save_base_to_file(base_digits, file_path='data/base.txt'):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        for pick in base_digits:
            f.write(' '.join(pick) + '\n')

def load_base_from_file(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r') as f:
        return [line.strip().split() for line in f if line.strip()]

def display_base_as_text(file_path):
    if not os.path.exists(file_path):
        return "⚠️ Tiada fail dijumpai."
    with open(file_path, 'r') as f:
        return '\n'.join([f"Pick {i+1}: {line.strip()}" for i, line in enumerate(f) if line.strip()])

# ===================== UPDATE DRAW =====================
def get_1st_prize(date_str):
    url = f"https://gdlotto.net/results/ajax/_result.aspx?past=1&d={date_str}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code != 200:
            return None
        html = resp.text
        m = re.search(r'id="1stPz">(\d{4})<', html)
        return m.group(1) if m else None
    except requests.RequestException:
        return None

def update_draws(file_path='data/draws.txt', max_days_back=60):
    draws = load_draws(file_path)
    last_date = (datetime.today() - timedelta(days=max_days_back)) if not draws else datetime.strptime(draws[-1]['date'], "%Y-%m-%d")
    yesterday = datetime.today() - timedelta(days=1)
    current = last_date + timedelta(days=1)
    added = []

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'a') as f:
        while current.date() <= yesterday.date():
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

# ===================== ANALISIS BASE & SUPER =====================
def score_digits(draws, recent_n=30):
    recent = draws[-recent_n:] if len(draws) >= recent_n else draws
    weights = [Counter() for _ in range(4)]
    for idx, draw in enumerate(reversed(recent)):
        for pos, digit in enumerate(draw['number']):
            weights[pos][digit] += idx + 1
    return [[d for d, _ in w.most_common(5)] for w in weights]

def generate_super_base(draws):
    b30 = score_digits(draws, 30)
    b60 = score_digits(draws, 60)
    b120 = score_digits(draws, 120)
    superb = []
    for i in range(4):
        common = set(b30[i]) & set(b60[i]) & set(b120[i])
        combined = list(common) + [d for d in b30[i] if d not in common]
        superb.append(combined[:5])
    return superb

# ===================== RAMALAN =====================
def generate_predictions(base_digits, n=10):
    combos = set()
    while len(combos) < n:
        combos.add(''.join(random.choice(base_digits[i]) for i in range(4)))
    return sorted(combos)

def cross_pick_analysis(draws):
    cnt = [defaultdict(int) for _ in range(4)]
    for d in draws:
        for i, digit in enumerate(d['number']):
            cnt[i][digit] += 1
    lines = []
    for i, pd in enumerate(cnt):
        top5 = sorted(pd.items(), key=lambda x: -x[1])[:5]
        lines.append(f"Pick {i+1}: " + ", ".join(f"{d} ({c}x)" for d, c in top5))
    return '\n'.join(lines)

# ===================== INSIGHT TERAKHIR =====================
def get_last_result_insight(draws):
    if not draws:
        return "Tiada data draw tersedia."

    today = datetime.today().strftime("%Y-%m-%d")
    last_valid = next((d for d in reversed(draws) if d['date'] < today), None)
    if not last_valid:
        return "Tiada data draw semalam tersedia."

    ln, ld = last_valid['number'], last_valid['date']
    lines = [f"📅 **Nombor terakhir naik:** `{ln}` pada `{ld}`\n"]

    alln = [d['number'] for d in draws if len(d['number']) == 4]
    digi_cnt = [Counter() for _ in range(4)]
    for num in alln:
        for i, ch in enumerate(num):
            digi_cnt[i][ch] += 1

    base_path = 'data/base_last.txt'
    if not os.path.exists(base_path):
        save_base_to_file(score_digits(draws[:-1]), base_path)
    base = load_base_from_file(base_path)

    cross_cnt = [Counter() for _ in range(4)]
    for num in alln:
        for i, ch in enumerate(num):
            cross_cnt[i][ch] += 1
    cross_top = [ [d for d,_ in cross_cnt[i].most_common(5)] for i in range(4) ]

    lines.append("📋 **Base Digunakan:**")
    for i, p in enumerate(base):
        lines.append(f"- Pick {i+1}: {' '.join(p)}")
    lines.append("")

    lines.append("🔍 **Analisis Setiap Digit:**")
    for i, ch in enumerate(ln):
        freq = digi_cnt[i][ch]
        rank = sorted(digi_cnt[i].values(), reverse=True).index(freq) + 1
        ib = "✅" if ch in base[i] else "❌"
        ic = "✅" if ch in cross_top[i] else "❌"
        s = (2 if rank<=3 else 1 if rank<=5 else 0)+(2 if ib=="✅" else 0)+(1 if ic=="✅" else 0)
        lbl = "🔥 Sangat berpotensi" if s>=4 else "👍 Berpotensi" if s>=3 else "❓ Kurang pasti"
        lines.append(f"- **Pick {i+1}**: Digit `{ch}` - Rank #{rank}, Base: {ib}, Cross: {ic} → **{lbl}**")

    lines.append("\n💡 **AI Insight:**")
    lines.append("- Digit dalam Base & Cross berkemungkinan besar naik semula.")
    lines.append("- Ranking tinggi (Top 3) menunjukkan konsistensi kuat.")
    return '\n'.join(lines)

# ===================== AI TUNER =====================
def ai_tuner(draws):
    return [[d for d in pick if int(d)%2==0 or d in '579'] for pick in score_digits(draws,30)]

# ===================== VISUALISASI =====================
def show_digit_heatmap(draws):
    df = pd.DataFrame([list(d['number']) for d in draws[-100:]], columns=[f"P{i+1}" for i in range(4)])
    fig, ax = plt.subplots(figsize=(8,4))
    sns.heatmap(df.apply(pd.Series.value_counts).T.fillna(0), annot=True, cmap="YlGnBu", ax=ax)
    st.pyplot(fig)

def show_digit_distribution(draws):
    df = pd.DataFrame([list(d['number']) for d in draws], columns=[f"P{i+1}" for i in range(4)])
    fig, axes = plt.subplots(2,2, figsize=(10,6))
    for i, ax in enumerate(axes.flatten()):
        sns.countplot(x=df.iloc[:,i], ax=ax, palette="Set2")
        ax.set_title(f"Digit di Pick {i+1}")
    st.pyplot(fig)

# ===================== STREAMLIT UI =====================
st.set_page_config(page_title="Breakcode4D Visual", layout="centered")
st.title("🔮 Breakcode4D Predictor (GD Lotto)")

col1, col2 = st.columns(2)
with col1:
    if st.button("📥 Update Draw Terkini"):
        msg = update_draws()
        st.success(msg)
        st.markdown("### 📋 Base Hari Ini (Salin & Tampal)")
        st.code(display_base_as_text('data/base.txt'), language='text')

with col2:
    st.markdown("""
        <a href="https://batman11.net/RegisterByReferral.aspx?MemberCode=BB1845" target="_blank">
            <button style="width:100%; padding:0.6em; font-size:16px; background:#4CAF50; color:white; border:none; border-radius:5px;">
                📝 Register Sini Batman 11 dan dapatkan BONUS!!!
            </button>
        </a>
    """, unsafe_allow_html=True)

draws = load_draws()
if not draws:
    st.warning("⚠️ Sila klik '📥 Update Draw Terkini' untuk mula.")
else:
    st.info(f"📅 Tarikh terakhir: **{draws[-1]['date']}** | 📊 Jumlah draw: **{len(draws)}**")

    tabs = st.tabs(["📌 Insight Terakhir","🧠 Ramalan","🔁 Cross & Super","🧪 AI Tuner","📊 Visualisasi","📂 Draws List"])
    with tabs[0]:
        st.markdown(get_last_result_insight(draws))
    with tabs[1]:
        base = []
        if os.path.exists('data/base_super.txt'):
            base = load_base_from_file('data/base_super.txt')
        elif os.path.exists('data/base.txt'):
            base = load_base_from_file('data/base.txt')
        else:
            st.warning("Tiada fail base ditemui. Sila update draw dahulu.")
        if base:
            for i,p in enumerate(base):
                st.write(f"Pick {i+1}: {' '.join(p)}")
            preds = generate_predictions(base)
            c1, c2 = st.columns(2)
            for i in range(min(5,len(preds))):
                c1.text(preds[i])
            for i in range(5,len(preds)):
                c2.text(preds[i])
    with tabs[2]:
        if st.button("🔁 Lihat Analisis Cross"):
            st.text(cross_pick_analysis(draws))
        if st.button("🚀 Jana & Simpan Super Base"):
            sb = generate_super_base(draws)
            save_base_to_file(sb, 'data/base_super.txt')
            st.success("Super Base disimpan ke 'data/base_super.txt'")
        if os.path.exists('data/base_super.txt'):
            st.markdown("### 📋 Super Base (Salin & Tampal)")
            st.code(display_base_as_text('data/base_super.txt'), language='text')
    with tabs[3]:
        if st.button("🧪 Jana AI Tuned Base"):
            tuned = ai_tuner(draws)
            for i,p in enumerate(tuned):
                st.write(f"Tuned Pick {i+1}: {' '.join(p)}")
    with tabs[4]:
        show_digit_distribution(draws)
        st.markdown("---")
        show_digit_heatmap(draws)
    with tabs[5]:
        st.markdown("### 📂 Senarai Penuh Draws")
        df = pd.DataFrame(draws)[::-1]
        st.dataframe(df, use_container_width=True)
        st.download_button("💾 Muat Turun Semua Draws", df.to_csv(index=False), "draws_list.csv", "text/csv")
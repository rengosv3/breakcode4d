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

def update_draws(file_path='data/draws.txt', max_days_back=61):
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

# ===================== ANALISIS & BASE =====================
# ===================== PENJANAAN BASE STRATEGI MODULAR =====================

def generate_base(draws, method='frequency', recent_n=10):
    if method == 'frequency':
        return generate_by_frequency(draws, recent_n)
    elif method == 'gap':
        return generate_by_gap(draws, recent_n)
    elif method == 'hybrid':
        return generate_hybrid(draws, recent_n)
    else:
        return generate_by_frequency(draws, recent_n)  # default fallback


def generate_by_frequency(draws, recent_n=10):
    recent_draws = [d[1] for d in draws[-recent_n:]]
    counter = [Counter() for _ in range(4)]
    for number in recent_draws:
        for i, digit in enumerate(number):
            counter[i][digit] += 1

    picks = []
    for pos_counter in counter:
        top_digits = [int(d) for d, _ in pos_counter.most_common(5)]
        while len(top_digits) < 5:
            top_digits.append(random.randint(0, 9))
        picks.append(top_digits)
    return picks


def generate_by_gap(draws, recent_n=10):
    recent_draws = [d[1] for d in draws[-recent_n:]]
    last_seen = [defaultdict(lambda: -1) for _ in range(4)]
    gap_scores = [defaultdict(int) for _ in range(4)]

    for idx, number in enumerate(recent_draws[::-1]):
        for pos, digit in enumerate(number):
            digit = int(digit)
            if last_seen[pos][digit] != -1:
                gap = idx - last_seen[pos][digit]
                gap_scores[pos][digit] += gap
            last_seen[pos][digit] = idx

    picks = []
    for pos_gap in gap_scores:
        sorted_digits = sorted(pos_gap.items(), key=lambda x: -x[1])
        top_digits = [d for d, _ in sorted_digits[:5]]
        while len(top_digits) < 5:
            top_digits.append(random.randint(0, 9))
        picks.append(top_digits)
    return picks


def generate_hybrid(draws, recent_n=10):
    freq_picks = generate_by_frequency(draws, recent_n)
    gap_picks = generate_by_gap(draws, recent_n)
    picks = []

    for f, g in zip(freq_picks, gap_picks):
        combo = list(set(f + g))
        random.shuffle(combo)
        final = combo[:5]
        while len(final) < 5:
            final.append(random.randint(0, 9))
        picks.append(final)
    return picks

# ===================== RAMALAN & AI =====================
def generate_predictions(base_digits, n=10):
    combos = set()
    while len(combos) < n:
        combos.add(''.join(random.choice(base_digits[i]) for i in range(4)))
    return sorted(combos)

def ai_tuner(draws):
    return [[d for d in pick if int(d)%2==0 or d in '579'] for pick in score_digits(draws,30)]

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

# ===================== BACKTEST (DINAMIK) =====================
def run_backtest(draws, num_days=10):
    if len(draws) < num_days:
        st.warning("❗ Tidak cukup draw untuk backtest.")
        return

    def match_insight_by_column(first_prize, base):
        insight = []
        for i in range(4):
            digit = first_prize[i]
            insight.append("✅" if digit in base[i] else "❌")
        return insight

    results = []
    st.markdown(f"### 🔁 Backtest {num_days} Hari Terakhir")

    for i in range(num_days):
        test_draw = draws[-(i+1)]
        draw_date, first_prize = test_draw['date'], test_draw['number']

        base_draws = draws[:-(i+1)]
        if len(base_draws) < 10:
            st.warning(f"❗ Tidak cukup data sebelum {draw_date} untuk jana base.")
            continue

        base = score_digits(base_draws)
        insight = match_insight_by_column(first_prize, base)

        results.append({
            "Tarikh": draw_date,
            "Result 1st": first_prize,
            "Insight": f"P1:{insight[0]} P2:{insight[1]} P3:{insight[2]} P4:{insight[3]}"
        })

        st.markdown(f"""
        ### 🎯 Tarikh: {draw_date}
        **Result 1st**: `{first_prize}`  
        **Base (sebelum {draw_date}):**
        """)
        for j, b in enumerate(base):
            st.text(f"P{j+1}: {' '.join(str(d) for d in b)}")
        st.markdown(f"**Insight:** `P1:{insight[0]} P2:{insight[1]} P3:{insight[2]} P4:{insight[3]}`")
        st.markdown("---")

    df = pd.DataFrame(results[::-1])
    success_count = sum(1 for r in results if "✅" in r["Insight"])
    st.success(f"🎉 Jumlah digit match: {success_count} daripada {num_days}")
    st.markdown("### 📊 Ringkasan Backtest:")
    st.dataframe(df, use_container_width=True)

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
st.set_page_config(page_title="Breakcode4D Predictor", layout="wide")
st.title("🔮 Breakcode4D Predictor (GD Lotto)")

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("📥 Update Draw Terkini"):
        msg = update_draws()
        st.success(msg)
        st.markdown("### 📋 Base Hari Ini")
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
    st.warning("⚠️ Sila klik 'Update Draw Terkini' untuk mula.")
else:
    st.info(f"📅 Tarikh terakhir: **{draws[-1]['date']}** | 📊 Jumlah draw: **{len(draws)}**")
    tabs = st.tabs(["📌 Insight Terakhir", "🧠 Ramalan", "🔁 Cross & Super", "🧪 AI Tuner", "📊 Visualisasi", "🔁 Backtest", "📂 Draws List"])

    with tabs[0]:
        st.markdown("### 📌 Insight Terakhir")
        st.markdown(get_last_result_insight(draws))

    with tabs[1]:
        st.markdown("### 🧠 Ramalan Berdasarkan Base")
        base = []
        if os.path.exists('data/base_super.txt'):
            base = load_base_from_file('data/base_super.txt')
            st.info("Menggunakan Super Base")
        elif os.path.exists('data/base.txt'):
            base = load_base_from_file('data/base.txt')
            st.info("Menggunakan Base Biasa")
        else:
            st.warning("❗ Tiada fail base ditemui.")
        if base:
            for i, p in enumerate(base):
                st.text(f"Pick {i+1}: {' '.join(p)}")
            preds = generate_predictions(base)
            st.code('\n'.join([' '.join(preds[i:i+5]) for i in range(0, len(preds), 5)]), language='text')

    with tabs[2]:
        st.markdown("### 🔁 Cross Pick & Super Base")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Lihat Cross Pick"):
                st.text(cross_pick_analysis(draws))
        with col2:
            if st.button("🚀 Jana Super Base"):
                sb = generate_super_base(draws)
                save_base_to_file(sb, 'data/base_super.txt')
                st.success("Super Base disimpan.")
        if os.path.exists('data/base_super.txt'):
            st.code(display_base_as_text('data/base_super.txt'), language='text')

    with tabs[3]:
        st.markdown("### 🧪 AI Tuner")
        if st.button("🔧 Jana AI Tuned Base"):
            tuned = ai_tuner(draws)
            for i, p in enumerate(tuned):
                st.text(f"Tuned Pick {i+1}: {' '.join(p)}")
            preds = generate_predictions(tuned)
            st.markdown("#### 🔮 Ramalan Berdasarkan AI Tuned:")
            st.code('\n'.join([' '.join(preds[i:i+5]) for i in range(0, len(preds), 5)]), language='text')

    with tabs[4]:
        st.markdown("### 📊 Visualisasi Data Digit")
        show_digit_distribution(draws)
        st.markdown("---")
        st.markdown("#### 🔥 Heatmap (100 Draw Terakhir)")
        show_digit_heatmap(draws)

    with tabs[5]:
        run_backtest(draws)

    with tabs[6]:
        st.markdown("### 📂 Senarai Penuh Draws")
        df = pd.DataFrame(draws)[::-1]
        st.dataframe(df, use_container_width=True)
        st.download_button("💾 Muat Turun Semua Draws", df.to_csv(index=False), "draws_list.csv", "text/csv")
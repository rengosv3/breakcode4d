import streamlit as st
import os
import re
import requests
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import random
import pandas as pd

# ===================== Load & Save =====================
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
            f.write(' '.join(str(d) for d in pick) + '\n')

def load_base_from_file(file_path='data/base.txt'):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r') as f:
        return [line.strip().split() for line in f if line.strip()]

# ===================== Update Draws =====================
def get_1st_prize(date_str):
    url = f"https://gdlotto.net/results/ajax/_result.aspx?past=1&d={date_str}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code != 200:
            return None
        m = re.search(r'id="1stPz">(\d{4})<', resp.text)
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
        latest_base = generate_base(draws, method='hybrid', recent_n=30)
        save_base_to_file(latest_base, 'data/base.txt')
        save_base_to_file(latest_base, 'data/base_last.txt')
    return f"✔ {len(added)} draw baru ditambah." if added else "✔ Tiada draw baru ditambah."

# ===================== Strategy Base =====================
def generate_base(draws, method='frequency', recent_n=10):
    if method == 'frequency':
        return generate_by_frequency(draws, recent_n)
    elif method == 'gap':
        return generate_by_gap(draws, recent_n)
    elif method == 'hybrid':
        return generate_hybrid(draws, recent_n)
    else:
        return generate_by_frequency(draws, recent_n)

def generate_by_frequency(draws, recent_n=10):
    recent_draws = [d['number'] for d in draws[-recent_n:]]
    counters = [Counter() for _ in range(4)]
    for number in recent_draws:
        for i, digit in enumerate(number):
            counters[i][digit] += 1

    picks = []
    for c in counters:
        top5 = [d for d, _ in c.most_common(5)]
        while len(top5) < 5:
            top5.append(str(random.randint(0,9)))
        picks.append(top5)
    return picks

def generate_by_gap(draws, recent_n=10):
    recent_draws = [d['number'] for d in draws[-recent_n:]]
    last_seen = [defaultdict(lambda: -1) for _ in range(4)]
    gap_scores = [defaultdict(int) for _ in range(4)]

    for idx, number in enumerate(recent_draws[::-1]):
        for pos, digit in enumerate(number):
            if last_seen[pos][digit] != -1:
                gap = idx - last_seen[pos][digit]
                gap_scores[pos][digit] += gap
            last_seen[pos][digit] = idx

    picks = []
    for gs in gap_scores:
        sorted_digits = sorted(gs.items(), key=lambda x: -x[1])
        top5 = [d for d, _ in sorted_digits[:5]]
        while len(top5) < 5:
            top5.append(str(random.randint(0,9)))
        picks.append(top5)
    return picks

def generate_hybrid(draws, recent_n=10):
    freq_picks = generate_by_frequency(draws, recent_n)
    gap_picks = generate_by_gap(draws, recent_n)
    picks = []

    for f, g in zip(freq_picks, gap_picks):
        combined = list(set(f + g))
        random.shuffle(combined)
        final = combined[:5]
        while len(final) < 5:
            final.append(str(random.randint(0,9)))
        picks.append(final)
    return picks

# ===================== Backtest =====================
def run_backtest(draws, strategy='hybrid', recent_n=10):
    if len(draws) < recent_n + 10:
        st.warning("❗ Tidak cukup draw untuk backtest.")
        return

    def match_insight(first_prize, base):
        insight = []
        for i in range(4):
            digit = first_prize[i]
            insight.append("✅" if digit in base[i] else "❌")
        return insight

    results = []
    st.markdown(f"### 🔁 Backtest {recent_n} Hari Terakhir (Strategi: {strategy})")

    for i in range(recent_n):
        test_draw = draws[-(i+1)]
        draw_date, first_prize = test_draw['date'], test_draw['number']
        base_draws = draws[:-(i+1)]
        if len(base_draws) < 10:
            continue
        base = generate_base(base_draws, method=strategy, recent_n=recent_n)
        insight = match_insight(first_prize, base)
        results.append({
            "Tarikh": draw_date,
            "Result 1st": first_prize,
            "Insight": f"P1:{insight[0]} P2:{insight[1]} P3:{insight[2]} P4:{insight[3]}"
        })

    df = pd.DataFrame(results[::-1])
    success_count = sum("✅" in r["Insight"] for r in results)
    st.success(f"🎉 Jumlah digit match: {success_count} daripada {recent_n}")
    st.markdown("### 📊 Ringkasan Backtest:")
    st.dataframe(df, use_container_width=True)

# ===================== UI =====================
st.set_page_config(page_title="Breakcode4D Predictor", layout="wide")
st.title("🔮 Breakcode4D Predictor (GD Lotto)")

col1, col2 = st.columns([1,1])
with col1:
    if st.button("📥 Update Draw Terkini"):
        msg = update_draws()
        st.success(msg)
        st.markdown("### 📋 Base Hari Ini")
        if os.path.exists('data/base.txt'):
            st.code('\n'.join([' '.join(p) for p in load_base_from_file()]), language='text')
        else:
            st.warning("❗ Tiada base fail ditemui.")

with col2:
    st.markdown("""
    <a href="https://batman11.net/RegisterByReferral.aspx?MemberCode=BB1845" target="_blank">
        <button style="width:100%;padding:0.6em;font-size:16px;background:#4CAF50;color:white;border:none;border-radius:5px;">
            📝 Register Sini Batman 11 dan dapatkan BONUS!!!
        </button>
    </a>
    """, unsafe_allow_html=True)

draws = load_draws()
if not draws:
    st.warning("⚠️ Sila klik 'Update Draw Terkini' untuk mula.")
else:
    st.info(f"📅 Tarikh terakhir: **{draws[-1]['date']}** | 📊 Jumlah draw: **{len(draws)}**")
    tabs = st.tabs(["📋 Draw List", "📌 Insight", "🧠 Ramalan", "🔁 Backtest"])

    with tabs[0]:
    st.markdown("### 📌 Insight Terakhir")

    if len(draws) < 1:
        st.warning("⚠️ Tiada draw untuk dianalisis.")
    else:
        last_draw = draws[-1]
        base = load_base_from_file()

        if not base or len(base) != 4:
            st.warning("⚠️ Base belum dijana atau tidak lengkap.")
        else:
            st.markdown(f"**Tarikh Draw:** `{last_draw['date']}`")
            st.markdown(f"**Nombor 1st Prize:** `{last_draw['number']}`")

            cols = st.columns(4)
            for i in range(4):
                digit = last_draw['number'][i]
                if digit in base[i]:
                    cols[i].success(f"Pos {i+1}: ✅ `{digit}` ada dalam {base[i]}")
                else:
                    cols[i].error(f"Pos {i+1}: ❌ `{digit}` tiada dalam {base[i]}")

            st.markdown("### 📋 Base Digunakan:")
            for i, b in enumerate(base):
                st.text(f"Pos {i+1}: {' '.join(b)}")

    with tabs[1]:
        st.markdown("### 🧠 Ramalan Base")
        base_strategy = st.selectbox("Pilih strategi base untuk ramalan:", ['hybrid', 'frequency', 'gap'])
        recent_n = st.slider("Jumlah draw terkini digunakan untuk base:", 5, 100, 30, 5)
        base = generate_base(draws, method=base_strategy, recent_n=recent_n)
        for i, p in enumerate(base):
            st.text(f"Pick {i+1}: {' '.join(p)}")
        preds = []
        while len(preds) < 10:
            pred = ''.join(random.choice(base[i]) for i in range(4))
            if pred not in preds:
                preds.append(pred)
        st.code('\n'.join(preds), language='text')

    with tabs[2]:
        st.markdown("### 🔁 Backtest Base")
        backtest_strategy = st.selectbox("Pilih strategi base untuk backtest:", ['hybrid', 'frequency', 'gap'])
        backtest_recent_n = st.slider("Jumlah draw terkini untuk backtest:", 5, 50, 10, 1)
        if st.button("🚀 Jalankan Backtest"):
            run_backtest(draws, strategy=backtest_strategy, recent_n=backtest_recent_n)
            
      with tabs[3]:
          st.markdown("### 📋 Senarai Semua Draw")
          df = pd.DataFrame(draws)
          st.dataframe(df, use_container_width=True)
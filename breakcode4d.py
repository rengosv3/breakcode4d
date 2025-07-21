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

# ===================== DATA I/O =====================
DRAW_PATH = 'data/draws.txt'
BASE_PATH = 'data/base.txt'
BASE_LAST_PATH = 'data/base_last.txt'

def load_draws(file_path=DRAW_PATH):
    draws = []
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2 and re.match(r'^\d{4}$', parts[1]):
                    draws.append({'date': parts[0], 'number': parts[1]})
    return draws

def save_draws(draws, file_path=DRAW_PATH):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        for d in draws:
            f.write(f"{d['date']} {d['number']}\n")

def save_base_to_file(base, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        for pick in base:
            f.write(' '.join(map(str, pick)) + '\n')

def load_base_from_file(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r') as f:
        return [list(map(int, line.strip().split())) for line in f if line.strip()]

def display_base_as_text(file_path):
    if not os.path.exists(file_path):
        return "⚠️ Tiada fail dijumpai."
    with open(file_path, 'r') as f:
        return '\n'.join([f"Pick {i+1}: {line.strip()}" for i, line in enumerate(f) if line.strip()])

# ===================== UPDATE DRAW =====================
def get_1st_prize(date_str):
    url = f"https://gdlotto.net/results/ajax/_result.aspx?past=1&d={date_str}"
    try:
        resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if resp.status_code != 200: return None
        m = re.search(r'id="1stPz">(\d{4})<', resp.text)
        return m.group(1) if m else None
    except:
        return None

def update_draws(file_path=DRAW_PATH, max_days_back=61):
    draws = load_draws(file_path)
    last_date = (datetime.today() - timedelta(days=max_days_back)) if not draws else datetime.strptime(draws[-1]['date'], "%Y-%m-%d")
    yesterday = datetime.today() - timedelta(days=1)
    current = last_date + timedelta(days=1)
    added = []
    while current.date() <= yesterday.date():
        ds = current.strftime("%Y-%m-%d")
        prize = get_1st_prize(ds)
        if prize:
            draws.append({'date': ds, 'number': prize})
            added.append(ds)
        current += timedelta(days=1)
    if added:
        save_draws(draws, file_path)
        # Jana base baru
        base = generate_base(draws, method='hybrid', recent_n=10)
        save_base_to_file(base, BASE_PATH)
        save_base_to_file(base, BASE_LAST_PATH)
    return f"✔ {len(added)} draw baru ditambah." if added else "✔ Tiada draw baru ditambah."

# ===================== BASE GENERATION =====================
def generate_by_frequency(draws, recent_n=10):
    recent = [d['number'] for d in draws[-recent_n:]]
    cnt = [Counter() for _ in range(4)]
    for num in recent:
        for i, ch in enumerate(num):
            cnt[i][ch] += 1
    picks = []
    for c in cnt:
        top = [int(d) for d,_ in c.most_common(5)]
        while len(top) < 5:
            top.append(random.randint(0,9))
        picks.append(top)
    return picks

def generate_by_gap(draws, recent_n=10):
    recent = [d['number'] for d in draws[-recent_n:]]
    last_seen = [defaultdict(lambda:-1) for _ in range(4)]
    score = [defaultdict(int) for _ in range(4)]
    for idx, num in enumerate(recent[::-1]):
        for i,ch in enumerate(num):
            d = int(ch)
            if last_seen[i][d] != -1:
                gap = idx - last_seen[i][d]
                score[i][d] += gap
            last_seen[i][d] = idx
    picks = []
    for s in score:
        top = [d for d,_ in sorted(s.items(), key=lambda x:-x[1])[:5]]
        while len(top)<5:
            top.append(random.randint(0,9))
        picks.append(top)
    return picks

def generate_hybrid(draws, recent_n=10):
    f = generate_by_frequency(draws, recent_n)
    g = generate_by_gap(draws, recent_n)
    out = []
    for a,b in zip(f,g):
        combo = list(dict.fromkeys(a+b))
        while len(combo)>5: combo.pop()
        while len(combo)<5: combo.append(random.randint(0,9))
        out.append(combo)
    return out

def generate_base(draws, method='hybrid', recent_n=10):
    if method=='frequency': return generate_by_frequency(draws, recent_n)
    if method=='gap':       return generate_by_gap(draws, recent_n)
    return generate_hybrid(draws, recent_n)

# ===================== BACKTEST =====================
def run_backtest(draws, num_days=10):
    if len(draws)<num_days:
        st.warning("Tidak cukup data untuk backtest.")
        return
    results=[]
    for i in range(num_days):
        d = draws[-(i+1)]
        date, prize = d['date'], d['number']
        base = generate_base(draws[:-(i+1)], method='hybrid', recent_n=10)
        match = [ "✅" if prize[i] in map(str,base[i]) else "❌" for i in range(4)]
        results.append({'Tarikh':date, 'Result':prize, 'Insight':match})
    df = pd.DataFrame(results[::-1])
    st.success(f"Menang digit: {sum(m.count('✅') for m in df['Insight'])}")
    st.dataframe(df)

# ===================== STREAMLIT UI =====================
st.set_page_config(page_title="Breakcode4D Predictor", layout="wide")
st.title("🔮 Breakcode4D Predictor (GD Lotto)")

# Tabs
tabs = st.tabs(["📥 Update","📌 Base","🧠 Ramalan","🔁 Backtest","📂 Draws"])

with tabs[0]:
    if st.button("📥 Update Draw Terkini"):
        st.success(update_draws())

with tabs[1]:
    st.markdown("### 📋 Base Hari Ini")
    st.code(display_base_as_text(BASE_PATH), language='text')

with tabs[2]:
    method = st.selectbox("Strategi Base",["hybrid","frequency","gap"])
    if st.button("🚀 Jana Base"):
        draws=load_draws(); base=generate_base(draws,method,10)
        save_base_to_file(base, BASE_PATH)
        st.success(f"Base dijana ({method})")
        st.code(display_base_as_text(BASE_PATH), language='text')

with tabs[3]:
    st.markdown("### 🔁 Backtest 10 Hari Terakhir")
    draws=load_draws()
    run_backtest(draws,10)

with tabs[4]:
    st.markdown("### 📂 Senarai Draws")
    df=pd.DataFrame(load_draws())[::-1]
    st.dataframe(df)
    csv = df.to_csv(index=False)
    st.download_button("💾 Download CSV", csv, "draws.csv", "text/csv")
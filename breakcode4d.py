# ===================== IMPORT =====================
import streamlit as st
import os
import re
import requests
import random
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo  # Python 3.9+

# ===================== COUNTDOWN DRAW =====================
def get_draw_countdown_from_last_8pm():
    now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    today_8pm = now.replace(hour=20, minute=0, second=0, microsecond=0)
    last_8pm = today_8pm - timedelta(days=1) if now < today_8pm else today_8pm
    return (last_8pm + timedelta(days=1)) - now

# ===================== LOAD & SAVE DRAWs/BASE =====================
def load_draws(file_path='data/draws.txt'):
    if not os.path.exists(file_path): return []
    draws = []
    with open(file_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts)==2 and re.match(r"^\d{4}$", parts[1]):
                draws.append({'date': parts[0], 'number': parts[1]})
    return draws

def save_base_to_file(base_digits, file_path='data/base.txt'):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        for pick in base_digits:
            f.write(' '.join(pick) + '\n')

def load_base_from_file(file_path='data/base.txt'):
    if not os.path.exists(file_path): return []
    with open(file_path) as f:
        return [line.strip().split() for line in f if line.strip()]

# ===================== UPDATE DRAW =====================
def get_1st_prize(date_str):
    url = f"https://gdlotto.net/results/ajax/_result.aspx?past=1&d={date_str}"
    try:
        resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if resp.status_code!=200: return None
        m = re.search(r'id="1stPz">(\d{4})<', resp.text)
        return m.group(1) if m else None
    except:
        return None

def update_draws(file_path='data/draws.txt', max_days_back=120):
    draws = load_draws(file_path)
    last_date = (datetime.today()-timedelta(days=max_days_back)) if not draws else datetime.strptime(draws[-1]['date'], "%Y-%m-%d")
    yesterday = datetime.today() - timedelta(days=1)
    current = last_date + timedelta(days=1)
    added = []
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path,'a') as f:
        while current.date() <= yesterday.date():
            d = current.strftime("%Y-%m-%d")
            prize = get_1st_prize(d)
            if prize:
                f.write(f"{d} {prize}\n")
                added.append({'date':d,'number':prize})
            current += timedelta(days=1)
    if added:
        draws = load_draws(file_path)
        base = generate_base(draws, method='qaisara', recent_n=50)
        save_base_to_file(base, 'data/base.txt')
        save_base_to_file(base, 'data/base_last.txt')
    return f"✔ {len(added)} draw baru ditambah." if added else "✔ Tiada draw baru ditambah."

# ===================== BASE GENERATION =====================
def generate_base(draws, method='frequency', recent_n=50):
    return {
        'frequency': generate_by_frequency,
        'gap':       generate_by_gap,
        'hybrid':    generate_hybrid,
        'qaisara':   generate_qaisara
    }.get(method, generate_by_frequency)(draws, recent_n)

def generate_by_frequency(draws, recent_n=50):
    recent = [d['number'] for d in draws[-recent_n:]]
    cnts = [Counter() for _ in range(4)]
    for num in recent:
        for i,ch in enumerate(num): cnts[i][ch]+=1
    picks = []
    for c in cnts:
        top = [d for d,_ in c.most_common(5)]
        while len(top)<5: top.append(str(random.randint(0,9)))
        picks.append(top)
    return picks

def generate_by_gap(draws, recent_n=50):
    recent = [d['number'] for d in draws[-recent_n:]]
    last_seen = [defaultdict(lambda:-1) for _ in range(4)]
    gap_scores = [defaultdict(int) for _ in range(4)]
    for idx,num in enumerate(recent[::-1]):
        for pos,ch in enumerate(num):
            if last_seen[pos][ch]!=-1:
                gap_scores[pos][ch]+= idx-last_seen[pos][ch]
            last_seen[pos][ch]=idx
    picks=[]
    for gs in gap_scores:
        top = [d for d,_ in sorted(gs.items(), key=lambda x:-x[1])[:5]]
        while len(top)<5: top.append(str(random.randint(0,9)))
        picks.append(top)
    return picks

def generate_hybrid(draws, recent_n=50):
    f = generate_by_frequency(draws, recent_n)
    g = generate_by_gap(draws, recent_n)
    out=[]
    for a,b in zip(f,g):
        combo = list(set(a+b))
        random.shuffle(combo)
        pick = combo[:5]
        while len(pick)<5: pick.append(str(random.randint(0,9)))
        out.append(pick)
    return out

def generate_qaisara(draws, recent_n=50):
    f = generate_by_frequency(draws, recent_n)
    g = generate_by_gap(draws, recent_n)
    h = generate_hybrid(draws, recent_n)
    out=[]
    for i in range(4):
        all3 = f[i]+g[i]+h[i]
        cnt = Counter(all3)
        top = [d for d,_ in cnt.most_common(5)]
        while len(top)<5: top.append(str(random.randint(0,9)))
        out.append(top)
    return out

# ===================== BACKTEST =====================
def run_backtest(draws, strategy='qaisara', recent_n=10):
    if len(draws)< recent_n+10:
        st.warning("❗ Data tidak cukup untuk backtest.")
        return
    def match(fp,base): return ["✅" if fp[i] in base[i] else "❌" for i in range(4)]
    res=[]
    for i in range(recent_n):
        td=draws[-(i+1)]
        bd = draws[:-(i+1)]
        if len(bd)<10: continue
        base = generate_base(bd, method=strategy, recent_n=recent_n)
        m = match(td['number'], base)
        res.append({"Tarikh":td['date'], "Result":td['number'], 
                    "Insight":' '.join(f"P{i+1}:{s}" for i,s in enumerate(m))})
    df = pd.DataFrame(res[::-1])
    win = sum("✅" in x for x in df['Insight'])
    st.success(f"🎉 Match digit: {win}/{len(df)} ")
    st.dataframe(df, use_container_width=True)

# ===================== UI =====================
st.set_page_config(page_title="Breakcode4D Predictor", layout="wide")
countdown = get_draw_countdown_from_last_8pm()
st.markdown(f"⏳ Next draw: `{str(countdown).split('.')[0]}`")
st.title("🔮 Breakcode4D Predictor (GD Lotto)")

# Update & Base display
col1,col2 = st.columns(2)
with col1:
    if st.button("📥 Update Draw Terkini"):
        msg = update_draws()
        st.success(msg)
        st.markdown("### 📋 Base Hari Ini")
        base = load_base_from_file('data/base.txt')
        if base: st.code('\n'.join(' '.join(p) for p in base))
        else:   st.warning("❗ Base belum dijana.")
with col2:
    st.markdown("""
    <a href="https://batman11.net/RegisterByReferral.aspx?MemberCode=BB1845" target="_blank">
      <button style="width:100%;padding:.6em;font-size:16px;background:#4CAF50;color:#fff;border:none;border-radius:5px;">
        📝 Register Batman11 & Bonus!
      </button>
    </a>""", unsafe_allow_html=True)

# Main tabs
draws = load_draws()
if not draws:
    st.warning("⚠️ Sila klik 'Update Draw Terkini' untuk mula.")
else:
    st.info(f"📅 Terakhir: **{draws[-1]['date']}** | 📊 Jumlah draw: **{len(draws)}**")
    tabs = st.tabs(["📌 Insight","🧠 Ramalan","🔁 Backtest","📋 Draw List"])

    with tabs[3]:
        st.dataframe(pd.DataFrame(draws), use_container_width=True)

    with tabs[0]:
        st.markdown("### 📌 Insight Terakhir")
        last = draws[-1]
        base = load_base_from_file('data/base.txt')
        if not base or len(base)!=4:
            st.warning("⚠️ Base belum lengkap.")
        else:
            st.markdown(f"**Tarikh:** `{last['date']}`  •  **1st Prize:** `{last['number']}`")
            cols = st.columns(4)
            for i in range(4):
                d = last['number'][i]
                (cols[i].success if d in base[i] else cols[i].error)(f"Pick{i+1}: {'✅' if d in base[i] else '❌'} `{d}`")
            st.markdown("### 📋 Base Digunakan")
            for i,p in enumerate(base): st.text(f"Pick{i+1}: {' '.join(p)}")

    with tabs[1]:
        st.markdown("### 🧠 Ramalan Base")
        strat = st.selectbox("Strategi:", ['qaisara','hybrid','frequency','gap'])
        rn = st.slider("Recent draw:",5,100,30,5)
        base = generate_base(draws, method=strat, recent_n=rn)
        for i,p in enumerate(base): st.text(f"Pick{i+1}: {' '.join(p)}")
        preds=[]
        while len(preds)<10:
            pr=''.join(random.choice(base[i]) for i in range(4))
            if pr not in preds: preds.append(pr)
        st.code('\n'.join(preds))

    with tabs[2]:
        st.markdown("### 🔁 Backtest Base")
        strat_bt = st.selectbox("Strategi:", ['qaisara','hybrid','frequency','gap'])
        rn_bt = st.slider("Recent draw:",5,50,10,1)
        if st.button("🚀 Run Backtest"):
            run_backtest(draws, strategy=strat_bt, recent_n=rn_bt)
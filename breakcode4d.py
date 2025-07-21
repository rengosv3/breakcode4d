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

# ===================== LOAD & SAVE FILE =====================
def load_draws(file_path='data/draws.txt'):
    if not os.path.exists(file_path): return []
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
    if not os.path.exists(file_path): return []
    with open(file_path, 'r') as f:
        return [line.strip().split() for line in f if line.strip()]

# ===================== UPDATE DRAW =====================
def get_1st_prize(date_str):
    url = f"https://gdlotto.net/results/ajax/_result.aspx?past=1&d={date_str}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code != 200: return None
        m = re.search(r'id="1stPz">(\d{4})<', resp.text)
        return m.group(1) if m else None
    except requests.RequestException:
        return None

def update_draws(file_path='data/draws.txt', max_days_back=121):
    draws = load_draws(file_path)
    last_date = datetime.today() - timedelta(days=max_days_back) if not draws else datetime.strptime(draws[-1]['date'], "%Y-%m-%d")
    yesterday = datetime.today() - timedelta(days=1)
    current = last_date + timedelta(days=1)
    added = []
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'a') as f:
        while current.date() <= yesterday.date():
            ds = current.strftime("%Y-%m-%d")
            prize = get_1st_prize(ds)
            if prize:
                f.write(f"{ds} {prize}\n")
                added.append({'date': ds, 'number': prize})
            current += timedelta(days=1)
    if added:
        draws = load_draws(file_path)
        latest_base = generate_base(draws, method='frequency', recent_n=50)
        save_base_to_file(latest_base, 'data/base.txt')
        save_base_to_file(latest_base, 'data/base_last.txt')
    return f"✔ {len(added)} draw baru ditambah." if added else "✔ Tiada draw baru ditambah."

# ===================== STRATEGI ASAS =====================
def generate_by_frequency(draws, recent_n=50):
    recent = [d['number'] for d in draws[-recent_n:]]
    counters = [Counter() for _ in range(4)]
    for num in recent:
        for i, d in enumerate(num):
            counters[i][d] += 1
    return [[d for d,_ in c.most_common(5)] for c in counters]

def generate_by_gap(draws, recent_n=50):
    recent = [d['number'] for d in draws[-recent_n:]]
    last_seen = [defaultdict(lambda: -1) for _ in range(4)]
    scores = [defaultdict(int) for _ in range(4)]
    for idx, num in enumerate(reversed(recent)):
        for i, d in enumerate(num):
            if last_seen[i][d]>=0:
                scores[i][d] += idx - last_seen[i][d]
            last_seen[i][d] = idx
    picks=[]
    for sc in scores:
        top = [d for d,_ in sorted(sc.items(), key=lambda x:-x[1])[:5]]
        while len(top)<5: top.append(str(random.randint(0,9)))
        picks.append(top)
    return picks

def generate_hybrid(draws, recent_n=50):
    f = generate_by_frequency(draws, recent_n)
    g = generate_by_gap(draws, recent_n)
    picks=[]
    for fa,ga in zip(f,g):
        combo=list(set(fa+ga))
        random.shuffle(combo)
        picks.append(combo[:5])
    return picks

# ===================== STRATEGI QAISARA =====================
def strategy_qaisara(draws, strategy_funcs, lookback=50):
    recent = draws[-lookback:]
    hits = {}
    digit_scores = {name: Counter() for name in strategy_funcs}

    # Kira hit-rate dan kumpul semua digit pos-per-pos
    for name, func in strategy_funcs.items():
        total = 0
        counter = Counter()
        for i, draw in enumerate(recent):
            history = draws[:-(lookback - i)]
            if not history: continue
            base = func(history)
            res = draw['number']
            hit_this=False
            for pos in range(4):
                pos_digits = base[pos]
                counter.update(pos_digits)
                if res[pos] in pos_digits:
                    hit_this = True
            if hit_this:
                total += 1
        hits[name] = total / lookback
        digit_scores[name] = counter

    final = Counter()
    for name, cnt in digit_scores.items():
        w = hits.get(name,0)
        for d, c in cnt.items():
            final[d] += c * w

    sorted_d = [d for d,_ in final.most_common()]
    trimmed = sorted_d[1:-1] if len(sorted_d)>=7 else sorted_d
    # penuhi 5 untuk setiap posisi
    base = [ trimmed[:5] for _ in range(4) ]
    return base

# ===================== GENERATE BASE (FAÇADE) =====================
def generate_base(draws, method='frequency', recent_n=50):
    funcs = {
        'frequency': generate_by_frequency,
        'gap': generate_by_gap,
        'hybrid': generate_hybrid
    }
    if method=='qaisara':
        return strategy_qaisara(draws, funcs, lookback=recent_n)
    return funcs.get(method, generate_by_frequency)(draws, recent_n)

# ===================== BACKTEST =====================
def run_backtest(draws, strategy='hybrid', recent_n=10):
    if len(draws) < recent_n+10:
        st.warning("❗ Tidak cukup draw untuk backtest."); return
    def match(fp, base):
        return ["✅" if fp[i] in base[i] else "❌" for i in range(4)]
    rows=[]
    for i in range(recent_n):
        td=draws[-(i+1)]
        hist=draws[:-(i+1)]
        if len(hist)<10: continue
        b=generate_base(hist, method=strategy, recent_n=recent_n)
        ins=match(td['number'],b)
        rows.append({
            "Tarikh": td['date'],
            "Result 1st": td['number'],
            "Insight": ' '.join(f"P{j+1}:{s}" for j,s in enumerate(ins))
        })
    df=pd.DataFrame(rows[::-1])
    ok=sum("✅" in r["Insight"] for r in rows)
    st.success(f"🎉 Jumlah digit match: {ok} daripada {recent_n}")
    st.dataframe(df, use_container_width=True)

# ===================== UI =====================
st.set_page_config(page_title="Breakcode4D Predictor", layout="wide")
st.markdown(f"⏳ Next draw: `{str(get_draw_countdown_from_last_8pm()).split('.')[0]}`")
st.title("🔮 Breakcode4D Predictor (GD Lotto)")

col1, col2 = st.columns(2)
with col1:
    if st.button("📥 Update Draw Terkini"):
        m=update_draws()
        st.success(m)
        st.markdown("### 📋 Base Hari Ini")
        base=load_base_from_file()
        st.code('\n'.join(' '.join(p) for p in base), language='text')
with col2:
    st.markdown("""
    <a href="https://batman11.net/RegisterByReferral.aspx?MemberCode=BB1845" target="_blank">
      <button style="width:100%;padding:0.6em;font-size:16px;
          background:#4CAF50;color:white;border:none;border-radius:5px;">
        📝 Register Sini Batman 11 dan dapatkan BONUS!!!
      </button>
    </a>
    """, unsafe_allow_html=True)

draws = load_draws()
if not draws:
    st.warning("⚠️ Sila klik 'Update Draw Terkini' untuk mula.")
else:
    st.info(f"📅 Tarikh terakhir: **{draws[-1]['date']}** | 📊 Jumlah draw: **{len(draws)}**")
    tabs = st.tabs(["📌 Insight","🧠 Ramalan","🔁 Backtest","📋 Draw List"])

    with tabs[3]:
        st.dataframe(pd.DataFrame(draws), use_container_width=True)

    with tabs[0]:
        st.markdown("### 📌 Insight Terakhir")
        last = draws[-1]
        base = load_base_from_file()
        if not base or len(base)!=4:
            st.warning("⚠️ Base belum dijana atau tidak lengkap.")
        else:
            st.markdown(f"**Tarikh Draw:** `{last['date']}`")
            st.markdown(f"**Nombor 1st Prize:** `{last['number']}`")
            cols=st.columns(4)
            for i in range(4):
                d=last['number'][i]
                fn = cols[i].success if d in base[i] else cols[i].error
                fn(f"Pos {i+1}: {'✅' if d in base[i] else '❌'} `{d}` dalam {base[i]}")
            st.markdown("### 📋 Base Digunakan:")
            for i,b in enumerate(base):
                st.text(f"Pos {i+1}: {' '.join(b)}")

    with tabs[1]:
        st.markdown("### 🧠 Ramalan Base")
        strat = st.selectbox("Pilih strategi:", ['frequency','gap','hybrid','qaisara'])
        rn = st.slider("Jumlah draw untuk base:",5,100,30,5)
        b = generate_base(draws, method=strat, recent_n=rn)
        for i,p in enumerate(b):
            st.text(f"Pick {i+1}: {' '.join(p)}")
        preds=[]
        while len(preds)<10:
            pr=''.join(random.choice(b[i]) for i in range(4))
            if pr not in preds: preds.append(pr)
        st.code('\n'.join(preds), language='text')

    with tabs[2]:
        st.markdown("### 🔁 Backtest Base")
        strat = st.selectbox("Strategi backtest:", ['frequency','gap','hybrid','qaisara'])
        rn=st.slider("Draw untuk backtest:",5,50,10)
        if st.button("🚀 Jalankan Backtest"):
            run_backtest(draws, strategy=strat, recent_n=rn)
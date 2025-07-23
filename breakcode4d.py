import os
import re
import itertools
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ———————— Helper Functions ————————

def get_draw_countdown():
    now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    today_8pm = now.replace(hour=20, minute=0, second=0, microsecond=0)
    last_8pm = today_8pm if now >= today_8pm else today_8pm - timedelta(days=1)
    return (last_8pm + timedelta(days=1)) - now

def load_draws(path='data/draws.txt'):
    if not os.path.exists(path):
        return []
    draws = []
    with open(path) as f:
        for line in f:
            date, num = line.strip().split()
            if re.fullmatch(r"\d{4}", num):
                draws.append({'date': date, 'number': num})
    return draws

def save_base(base, path='data/base.txt'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        for pick in base:
            f.write(' '.join(pick) + '\n')

def load_base(path='data/base.txt'):
    if not os.path.exists(path):
        return []
    return [line.strip().split() for line in open(path) if line.strip()]

def fetch_1st_prize(date_str):
    url = f"https://gdlotto.net/results/ajax/_result.aspx?past=1&d={date_str}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        tag = soup.find("span", id="1stPz")
        num = tag.text.strip() if tag else ""
        return num if re.fullmatch(r"\d{4}", num) else None
    except requests.RequestException:
        return None

def update_draws(file_path='data/draws.txt', lookback=121):
    draws = load_draws(file_path)
    existing = {d['date'] for d in draws}
    last_date = datetime.strptime(draws[-1]['date'], "%Y-%m-%d") if draws else datetime.today() - timedelta(days=lookback)
    today = datetime.today()
    added = []
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'a') as f:
        current = last_date + timedelta(days=1)
        while current.date() < today.date():
            ds = current.strftime("%Y-%m-%d")
            if ds not in existing:
                prize = fetch_1st_prize(ds)
                if prize:
                    f.write(f"{ds} {prize}\n")
                    added.append({'date': ds, 'number': prize})
            current += timedelta(days=1)
    if added:
        prev = load_draws(file_path)[:-len(added)]
        save_base(generate_base(prev, 'frequency', 50), 'data/base_last.txt')
        save_base(generate_base(load_draws(file_path), 'frequency', 50), 'data/base.txt')
    return f"{len(added)} draw baru ditambah." if added else "Tiada draw baru."

def generate_base(draws, method='frequency', recent_n=50):
    if len(draws) < recent_n:
        st.warning(f"Tidak cukup data ({len(draws)}/{recent_n}) untuk `{method}`.")
        st.stop()
    recent = [d['number'] for d in draws[-recent_n:]]
    if method == 'frequency':
        counters = [Counter() for _ in range(4)]
        for num in recent:
            for i, d in enumerate(num):
                counters[i][d] += 1
        return [[d for d,_ in c.most_common(5)] for c in counters]
    if method == 'gap':
        last_seen = [dict() for _ in range(4)]
        gaps = [Counter() for _ in range(4)]
        for idx, num in enumerate(reversed(recent), start=1):
            for i, d in enumerate(num):
                if d in last_seen[i]:
                    gaps[i][d] += idx - last_seen[i][d]
                last_seen[i][d] = idx
        return [[d for d,_ in g.most_common(5)] for g in gaps]
    if method == 'hybrid':
        f = generate_base(draws, 'frequency', recent_n)
        g = generate_base(draws, 'gap', recent_n)
        return [[d for d,_ in (Counter(f[i] + g[i]).most_common(5))] for i in range(4)]
    if method == 'qaisara':
        f = generate_base(draws, 'frequency', recent_n)
        g = generate_base(draws, 'gap', recent_n)
        h = generate_base(draws, 'hybrid', recent_n)
        final = []
        for i in range(4):
            score = Counter(f[i] + g[i] + h[i]).most_common()
            # buang top & bottom
            if len(score) > 2:
                score = score[1:-1]
            final.append([d for d,_ in score[:5]])
        return final
    if method == 'smartpattern':
        transitions = [defaultdict(Counter) for _ in range(4)]
        for prev, curr in zip(recent, recent[1:]):
            for i in range(4):
                transitions[i][prev[i]][curr[i]] += 1
        base = []
        for t in transitions:
            merged = sum((c for c in t.values()), Counter())
            base.append([d for d,_ in merged.most_common(5)])
        return base
    st.warning(f"Strategi `{method}` tidak dikenali.")
    return [['0']]*4

def run_backtest(draws, strategy, recent_n, arah, rounds):
    if len(draws) < recent_n + rounds:
        st.warning("Tidak cukup draw untuk backtest.")
        return
    def check(fp, base):
        if arah.startswith("Kanan"):
            fp, base = fp[::-1], base[::-1]
        return ["✅" if fp[i] in base[i] else "❌" for i in range(4)]
    records = []
    for i in range(rounds):
        test = draws[-(i+1)]
        past = draws[:-(i+1)]
        if len(past) < recent_n:
            continue
        base = generate_base(past, strategy, recent_n)
        insight = check(test['number'], base)
        records.append({
            "Tarikh": test['date'],
            "1st Prize": test['number'],
            "Insight": ' '.join(f"P{j+1}:{s}" for j,s in enumerate(insight))
        })
    df = pd.DataFrame(records[::-1])
    total = df["Insight"].str.count("✅").sum()
    st.success(f"Jumlah✅: {total} daripada {rounds}")
    st.dataframe(df, use_container_width=True)

def get_like_dislike(draws, recent_n=30):
    last = [d['number'] for d in draws[-recent_n:]]
    cnt = Counter(''.join(last))
    mc = cnt.most_common()
    return [d for d,_ in mc[:3]], [d for d,_ in mc[-3:]]

def apply_filters(combos, draws, no_repeat, no_triple, no_pair, no_ascend, use_hist, sim_limit, likes, dislikes):
    past_nums = {d['number'] for d in draws}
    last = draws[-1]['number'] if draws else "0000"
    out = []
    for e in combos:
        num = e.split('#')[0]
        digs = list(num)
        if no_repeat and len(set(digs)) < 4: continue
        if no_triple and any(digs.count(d)>=3 for d in set(digs)): continue
        if no_pair   and any(digs.count(d)==2 for d in set(digs)): continue
        if no_ascend and num in [ ''.join(str(i+j) for i in range(4)) for j in range(6) ]: continue
        if use_hist  and num in past_nums: continue
        if sum(a==b for a,b in zip(num, last)) > sim_limit: continue
        if likes      and not any(d in likes for d in digs): continue
        if dislikes   and any(d in dislikes for d in digs): continue
        out.append(e)
    return out

# ———————— Streamlit UI ————————

st.set_page_config(page_title="🔮 Breakcode4D Predictor", layout="wide")
st.markdown(f"⏳ Next draw in: `{str(get_draw_countdown()).split('.')[0]}`")
st.title("🔮 Breakcode4D Predictor (GD Lotto)")

col1, col2 = st.columns(2)
with col1:
    if st.button("📥 Update Draw"):
        st.success(update_draws())
        st.markdown("### Base Hari Ini")
        st.code('\n'.join(' '.join(p) for p in load_base()), language='text')
with col2:
    st.markdown(
        '<a href="https://batman11.net/RegisterByReferral.aspx?MemberCode=BB1845" target="_blank">'
        '<button style="width:100%;padding:0.6em;font-size:16px;background:#4CAF50;color:white;'
        'border:none;border-radius:5px;">📝 Register Batman 11 & BONUS!</button></a>',
        unsafe_allow_html=True
    )

draws = load_draws()
if not draws:
    st.warning("Klik ‘📥 Update Draw’ untuk mula.")
else:
    st.info(f"Last Draw: {draws[-1]['date']} | Total: {len(draws)}")
    tabs = st.tabs(["Insight","Ramalan","Backtest","Draw List","Wheelpick"])

    with tabs[0]:
        st.markdown("### 📌 Insight Terakhir")
        base_last = load_base('data/base_last.txt')
        if len(base_last) != 4:
            st.warning("Base belum tersedia. Kemas kini dulu.")
            st.stop()
        last = draws[-1]
        st.write(f"**Tarikh:** {last['date']}  **1st Prize:** {last['number']}")
        cols = st.columns(4)
        for i in range(4):
            dig = last['number'][i]
            (cols[i].success if dig in base_last[i] else cols[i].error)(f"P{i+1}: {dig}")
        st.markdown("**Base Sebelum Draw:**")
        for i,b in enumerate(base_last):
            st.write(f"P{i+1}: {' '.join(b)}")

    with tabs[1]:
        st.markdown("### 🔢 Ramalan Base")
        strat = st.selectbox("Strategi:", ['frequency','gap','hybrid','qaisara','smartpattern'])
        n = st.slider("Draw untuk base:", 5, 120, 30, 5)
        base = generate_base(draws, strat, n)
        for i,p in enumerate(base):
            st.write(f"P{i+1}: {' '.join(p)}")
        preds = [''.join(p) for p in itertools.product(*base)][:10]
        st.markdown("**Top 10 Kombinasi:**")
        st.code('\n'.join(preds), language='text')

    with tabs[2]:
        st.markdown("### 📈 Backtest")
        arah = st.radio("Arah bacaan:", ["Kiri→Kanan","Kanan→Kiri"])
        strat = st.selectbox("Strategi:", ['frequency','gap','hybrid','qaisara','smartpattern'])
        n = st.slider("Draw untuk base:", 5, 120, 30, 5)
        rounds = st.slider("Bilangan backtest:", 5, 50, 10)
        if st.button("▶ Jalankan Backtest"):
            run_backtest(draws, strat, n, arah, rounds)

    with tabs[3]:
        st.markdown("### 📄 Senarai Draw")
        st.dataframe(pd.DataFrame(draws), use_container_width=True)

    with tabs[4]:
        st.markdown("### 🎡 Wheelpick Generator")
        arah_wp = st.radio("Arah:", ["Kiri→Kanan","Kanan→Kiri"])
        like_s, dislike_s = get_like_dislike(draws)
        st.write(f"👍 Saran LIKE: {like_s}   👎 Saran DISLIKE: {dislike_s}")
        user_like    = st.text_input("LIKE:", ' '.join(like_s))
        user_dislike = st.text_input("DISLIKE:", ' '.join(dislike_s))
        likes    = [d for d in user_like.split() if d.isdigit()]
        dislikes = [d for d in user_dislike.split() if d.isdigit()]

        mode = st.radio("Mod Base:", ["Auto","Manual"])
        if mode == "Manual":
            manual = []
            for i in range(4):
                digs = st.text_input(f"P{i+1} (5 digit):", key=f"man{i}").split()
                if len(digs)!=5:
                    st.error("Setiap pick mesti 5 digit."); st.stop()
                manual.append(digs)
        else:
            manual = load_base()
            if len(manual)!=4:
                st.warning("Base tak sah. Update dulu."); st.stop()

        lot = st.text_input("Nilai Lot:", "0.10")
        with st.expander("⚙ Tapisan"):
            no_repeat  = st.checkbox("Buang ulang")
            no_triple  = st.checkbox("Buang triple")
            no_pair    = st.checkbox("Buang pair")
            no_ascend  = st.checkbox("Buang menaik")
            use_hist   = st.checkbox("Buang history")
            sim_limit  = st.slider("Had persamaan:", 0, 4, 2)

        if st.button("🎲 Create Wheelpick"):
            combos = [f"{a}{b}{c}{d}#{lot}"
                      for a in manual[0]
                      for b in manual[1]
                      for c in manual[2]
                      for d in manual[3]]
            st.info(f"Sebelum tapis: {len(combos)}")
            ok = apply_filters(combos, draws, no_repeat, no_triple, no_pair, no_ascend, use_hist, sim_limit, likes, dislikes)
            st.success(f"Selepas tapis: {len(ok)}")
            for i in range(0, len(ok), 30):
                part = ok[i:i+30]
                st.markdown(f"**Bahagian {i//30+1} ({len(part)})**")
                st.code('\n'.join(part), language='text')
            data = '\n'.join(ok).encode()
            fn = f"wheelpick_{datetime.now():%Y%m%d_%H%M%S}.txt"
            st.download_button("⬇️ Muat Turun", data=data, file_name=fn, mime="text/plain")
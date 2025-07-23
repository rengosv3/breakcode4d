import os
import re
import requests
import itertools
import pandas as pd

from datetime import datetime, timedelta
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

import streamlit as st

# ——— Helpers —————————————————————————————————————————————————————————————

def get_draw_countdown():
    now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    today_8pm = now.replace(hour=20, minute=0, second=0, microsecond=0)
    last_8pm = today_8pm - timedelta(days=1) if now < today_8pm else today_8pm
    return (last_8pm + timedelta(days=1)) - now

def load_draws(path='data/draws.txt'):
    if not os.path.exists(path):
        return []
    draws = []
    with open(path, 'r') as f:
        for line in f:
            date, num = line.strip().split()
            if re.fullmatch(r"\d{4}", num):
                draws.append({'date': date, 'number': num})
    return draws

def save_base(base, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        for pick in base:
            f.write(' '.join(pick) + '\n')

def load_base(path='data/base.txt'):
    if not os.path.exists(path):
        return []
    with open(path, 'r') as f:
        return [line.strip().split() for line in f if line.strip()]

def fetch_1st_prize(date_str):
    url = f"https://gdlotto.net/results/ajax/_result.aspx?past=1&d={date_str}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        tag = soup.find("span", id="1stPz")
        prize = tag.text.strip() if tag else ""
        return prize if prize.isdigit() and len(prize) == 4 else None
    except requests.RequestException:
        return None

# ——— Data Update & Base Generation ——————————————————————————————————————————

def update_draws(file_path='data/draws.txt', max_days_back=121):
    draws = load_draws(file_path)
    existing_dates = {d['date'] for d in draws}
    last_date = datetime.strptime(draws[-1]['date'], "%Y-%m-%d") if draws else datetime.today() - timedelta(days=max_days_back)
    added = []

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'a') as f:
        day = last_date + timedelta(days=1)
        while day.date() <= (datetime.today() - timedelta(days=1)).date():
            ds = day.strftime("%Y-%m-%d")
            if ds not in existing_dates:
                prize = fetch_1st_prize(ds)
                if prize:
                    f.write(f"{ds} {prize}\n")
                    added.append({'date': ds, 'number': prize})
            day += timedelta(days=1)

    if added:
        prev_draws = load_draws(file_path)[:-len(added)]
        base_last = generate_base(prev_draws, method='frequency', recent_n=50)
        save_base(base_last, 'data/base_last.txt')

        all_draws = load_draws(file_path)
        base_today = generate_base(all_draws, method='frequency', recent_n=50)
        save_base(base_today, 'data/base.txt')
        return f"{len(added)} draw baru ditambah."
    return "Tiada draw baru ditambah."

def generate_base(draws, method='frequency', recent_n=50):
    if len(draws) < recent_n:
        st.warning(f"Perlu sekurang-kurangnya {recent_n} draw, ada {len(draws)} sahaja.")
        st.stop()

    recent = [d['number'] for d in draws[-recent_n:]]

    if method == "frequency":
        cnts = [Counter(num[i] for num in recent) for i in range(4)]
        return [ [d for d,_ in c.most_common(5)] for c in cnts ]

    if method == "gap":
        last_seen = [dict() for _ in range(4)]
        gaps = [defaultdict(int) for _ in range(4)]
        for idx, num in enumerate(reversed(recent), 1):
            for pos, d in enumerate(num):
                if d in last_seen[pos]:
                    gaps[pos][d] += idx - last_seen[pos][d]
                last_seen[pos][d] = idx
        return [ [d for d,_ in sorted(g.items(), key=lambda x: -x[1])[:5]] for g in gaps ]

    if method == "hybrid":
        f = generate_base(draws, 'frequency', recent_n)
        g = generate_base(draws, 'gap', recent_n)
        return [ [d for d,_ in Counter(f[i] + g[i]).most_common(5)] for i in range(4) ]

    if method == "qaisara":
        b1 = generate_base(draws, 'frequency', recent_n)
        b2 = generate_base(draws, 'gap', recent_n)
        b3 = generate_base(draws, 'hybrid', recent_n)
        final = []
        for i in range(4):
            ranked = Counter(b1[i] + b2[i] + b3[i]).most_common()
            # drop top & bottom if possible
            if len(ranked) > 2:
                ranked = ranked[1:-1]
            final.append([d for d,_ in ranked[:5]])
        return final

    if method == "smartpattern":
        trans = [defaultdict(Counter) for _ in range(4)]
        for a, b in zip(recent, recent[1:]):
            for i in range(4):
                trans[i][a[i]][b[i]] += 1
        base = []
        for i in range(4):
            merged = Counter()
            for nxt in trans[i].values():
                merged += nxt
            base.append([d for d,_ in merged.most_common(5)])
        return base

    st.warning(f"Strategi '{method}' tidak dikenali.")
    return [['0']]*4

# ——— Backtest —————————————————————————————————————————————————————————————

def run_backtest(draws, strategy, recent_n, arah, rounds):
    if len(draws) < recent_n + rounds:
        st.warning("Data draw tidak mencukupi untuk backtest.")
        return

    def check(fp, base):
        if arah == "Kanan ke Kiri (P4→P1)":
            fp, base = fp[::-1], base[::-1]
        return ["✅" if fp[i] in base[i] else "❌" for i in range(4)]

    results = []
    for i in range(rounds):
        test = draws[-(i+1)]
        past = draws[:-(i+1)]
        if len(past) < recent_n:
            continue
        base = generate_base(past, strategy, recent_n)
        insight = ' '.join(f"P{j+1}:{s}" for j, s in enumerate(check(test['number'], base)))
        results.append({"Tarikh": test['date'], "1st Prize": test['number'], "Insight": insight})

    df = pd.DataFrame(results[::-1])
    total_matches = sum(row.count("✅") for row in df["Insight"].str.split())
    st.success(f"Jumlah match: {total_matches} daripada {rounds}")
    st.dataframe(df, use_container_width=True)

# ——— Wheelpick ——————————————————————————————————————————————————————————

def get_like_dislike(draws, recent_n=30):
    recent = [d['number'] for d in draws[-recent_n:]]
    cnt = Counter(''.join(recent))
    mc = cnt.most_common()
    like = [d for d,_ in mc[:3]]
    dislike = [d for d,_ in mc[-3:]] if len(mc) >= 3 else []
    return like, dislike

def apply_filters(combos, draws, no_r, no_t, no_p, no_a, no_h, sim_lim, likes, dislikes):
    past_nums = {d['number'] for d in draws}
    last = draws[-1]['number'] if draws else "0000"
    out = []
    for combo in combos:
        num = combo[:4]
        digs = list(num)
        if no_r and len(set(digs)) < 4: continue
        if no_t and any(digs.count(d) >= 3 for d in digs): continue
        if no_p and any(digs.count(d) == 2 for d in set(digs)): continue
        if no_a and num in [str(i)+str(i+1)+str(i+2)+str(i+3) for i in range(7)]: continue
        if no_h and num in past_nums: continue
        if sum(a==b for a,b in zip(num, last)) > sim_lim: continue
        if likes and not any(d in likes for d in digs): continue
        if dislikes and any(d in dislikes for d in digs): continue
        out.append(combo)
    return out

# ——— Streamlit UI —————————————————————————————————————————————————————

st.set_page_config(page_title="Breakcode4D Predictor", layout="wide")

st.markdown(f"⏳ Next draw in: `{str(get_draw_countdown()).split('.')[0]}`")
st.title("🔮 Breakcode4D Predictor (GD Lotto)")

col1, col2 = st.columns(2)
with col1:
    if st.button("📥 Update Draw Terkini"):
        st.success(update_draws())
        st.markdown("### Base Hari Ini")
        st.code('\n'.join(' '.join(p) for p in load_base()), language='text')

with col2:
    st.markdown(
        '<a href="https://batman11.net/RegisterByReferral.aspx?MemberCode=BB1845" target="_blank">'
        '<button style="width:100%;padding:0.6em;font-size:16px;'
        'background:#4CAF50;color:white;border:none;border-radius:5px;">'
        '📝 Register Sini Batman 11 dan dapatkan BONUS!!!</button></a>',
        unsafe_allow_html=True
    )

draws = load_draws()
if not draws:
    st.warning("Sila klik 'Update Draw Terkini' untuk mula.")
else:
    st.info(f"Tarikh terakhir: {draws[-1]['date']} | Jumlah draw: {len(draws)}")
    tabs = st.tabs(["Insight", "Ramalan", "Backtest", "Draw List", "Wheelpick"])

    with tabs[0]:
        st.markdown("### 📌 Insight Terakhir")
        last = draws[-1]
        base = load_base('data/base_last.txt')
        if len(base) != 4:
            st.warning("Base belum wujud. Tekan 'Update Draw Terkini'.")
            st.stop()
        st.markdown(f"**Tarikh:** `{last['date']}`  •  **1st Prize:** `{last['number']}`")
        cols = st.columns(4)
        for i in range(4):
            fun = cols[i].success if last['number'][i] in base[i] else cols[i].error
            fun(f"P{i+1}: `{last['number'][i]}`")
        st.markdown("**Base Digunakan:**")
        for i, b in enumerate(base):
            st.text(f"P{i+1}: {' '.join(b)}")

    with tabs[1]:
        st.markdown("### 🔢 Ramalan Base")
        strat = st.selectbox("Strategi:", ['frequency','gap','hybrid','qaisara','smartpattern'])
        recent_n = st.slider("Draw untuk base:", 5, 120, 30, 5)
        base = generate_base(draws, strat, recent_n)
        for i, p in enumerate(base):
            st.text(f"P{i+1}: {' '.join(p)}")
        preds = [''.join(p) for p in itertools.product(*base)][:10]
        st.markdown("**Top 10 Kombinasi:**")
        st.code('\n'.join(preds), language='text')

    with tabs[2]:
        st.markdown("### 📊 Backtest Base")
        arah = st.radio("Arah bacaan:", ["Kiri ke Kanan (P1→P4)","Kanan ke Kiri (P4→P1)"])
        strat = st.selectbox("Strategi:", ['frequency','gap','hybrid','qaisara','smartpattern'])
        base_n = st.slider("Draw untuk base:", 5, 120, 30, 5)
        rounds = st.slider("Bilangan backtest:", 5, 50, 10)
        if st.button("Jalankan Backtest"):
            run_backtest(draws, strat, base_n, arah, rounds)

    with tabs[3]:
        st.markdown("### 📜 Senarai Draw")
        st.dataframe(pd.DataFrame(draws), use_container_width=True)

    with tabs[4]:
        st.markdown("### 🎰 Wheelpick Generator")
        arah_wp = st.radio("Arah bacaan:", ["Kiri ke Kanan (P1→P4)","Kanan ke Kiri (P4→P1)"])
        like_s, dislike_s = get_like_dislike(draws)
        st.markdown(f"👍 Cadangan LIKE: `{like_s}`")
        st.markdown(f"👎 Cadangan DISLIKE: `{dislike_s}`")

        user_like = st.text_input("Masukkan LIKE:", ' '.join(like_s))
        user_dislike = st.text_input("Masukkan DISLIKE:", ' '.join(dislike_s))
        like_digits = [d for d in user_like.split() if d.isdigit()]
        dislike_digits = [d for d in user_dislike.split() if d.isdigit()]

        mode = st.radio("Mod Base:", ["Auto","Manual"])
        if mode == "Manual":
            manual_base = []
            for i in range(4):
                digs = st.text_input(f"P{i+1} (5 digits):", key=i).split()
                if len(digs) != 5 or not all(d.isdigit() for d in digs):
                    st.error("Manual input mesti 5 digit.")
                    st.stop()
                manual_base.append(digs)
        else:
            manual_base = load_base()
            if len(manual_base) != 4:
                st.warning("Base tak sah. Update dulu.")
                st.stop()

        lot = st.text_input("Nilai Lot:", "0.10")
        with st.expander("⚙️ Tapisan Tambahan"):
            no_repeat   = st.checkbox("Buang nombor berulang")
            no_triple   = st.checkbox("Buang triple")
            no_pair     = st.checkbox("Buang pair")
            no_ascend   = st.checkbox("Buang menaik")
            use_history = st.checkbox("Buang pernah naik")
            sim_limit   = st.slider("Had persamaan digit dengan terakhir", 0, 4, 2)

        if st.button("Create Wheelpick"):
            combos = [f"{a}{b}{c}{d}#{lot}"
                      for a in manual_base[0]
                      for b in manual_base[1]
                      for c in manual_base[2]
                      for d in manual_base[3]]
            st.info(f"Sebelum tapis: {len(combos)}")
            filtered = apply_filters(
                combos, draws,
                no_repeat, no_triple, no_pair, no_ascend, use_history,
                sim_limit, like_digits, dislike_digits
            )
            st.success(f"Selepas tapis: {len(filtered)}")
            for i in range(0, len(filtered), 30):
                chunk = filtered[i:i+30]
                st.markdown(f"**Bahagian {i//30+1} ({len(chunk)})**")
                st.code('\n'.join(chunk), language='text')

            filename = f"wheelpick_{datetime.now():%Y%m%d_%H%M%S}.txt"
            data = '\n'.join(filtered).encode()
            st.download_button("📥 Muat Turun Semua", data=data, file_name=filename)
import streamlit as st
import os
import re
import requests
import itertools
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

def get_draw_countdown_from_last_8pm():
    now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    today_8pm = now.replace(hour=20, minute=0, second=0, microsecond=0)
    last_8pm = today_8pm - timedelta(days=1) if now < today_8pm else today_8pm
    return (last_8pm + timedelta(days=1)) - now

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

def load_base_from_file(file_path='data/base.txt'):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r') as f:
        return [line.strip().split() for line in f if line.strip()]

def get_1st_prize(date_str):
    url = f"https://gdlotto.net/results/ajax/_result.aspx?past=1&d={date_str}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Status bukan 200 untuk {date_str}: {resp.status_code}")
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        prize_tag = soup.find("span", id="1stPz")
        text = prize_tag.text.strip() if prize_tag else ""
        return text if text.isdigit() and len(text) == 4 else None
    except requests.RequestException as e:
        print(f"❌ Ralat semasa request untuk {date_str}: {e}")
        return None

def update_draws(file_path='data/draws.txt', max_days_back=121):
    draws = load_draws(file_path)
    existing = {d['date'] for d in draws}
    if draws:
        last_date = datetime.strptime(draws[-1]['date'], "%Y-%m-%d")
    else:
        last_date = datetime.today() - timedelta(max_days_back)
    yesterday = datetime.today() - timedelta(days=1)
    current = last_date + timedelta(days=1)
    added = []
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'a') as f:
        while current.date() <= yesterday.date():
            date_str = current.strftime("%Y-%m-%d")
            if date_str not in existing:
                prize = get_1st_prize(date_str)
                if prize:
                    f.write(f"{date_str} {prize}\n")
                    added.append({'date': date_str, 'number': prize})
            current += timedelta(days=1)
    if added:
        previous = load_draws(file_path)[:-len(added)]
        base_last = generate_base(previous, method='frequency', recent_n=50)
        save_base_to_file(base_last, 'data/base_last.txt')
        all_draws = load_draws(file_path)
        latest_base = generate_base(all_draws, method='frequency', recent_n=50)
        save_base_to_file(latest_base, 'data/base.txt')
    return f"✔️ {len(added)} draw baru ditambah." if added else "✔️ Tiada draw baru ditambah."

def generate_base(draws, method='frequency', recent_n=50):
    total = len(draws)
    if total < recent_n:
        st.warning(f"⚠️ Tidak cukup data untuk `{method}`. Perlu {recent_n}, ada {total}.")
        st.stop()
    recent = [d['number'] for d in draws[-recent_n:] if len(d.get('number','')) == 4]
    if method == "smartpattern":
        transitions = [defaultdict(Counter) for _ in range(4)]
        for i in range(1, len(recent)):
            prev, curr = recent[i-1], recent[i]
            for pos in range(4):
                transitions[pos][prev[pos]][curr[pos]] += 1
        base = []
        for pos in range(4):
            merged = Counter()
            for nxt in transitions[pos].values():
                merged += nxt
            common = [d for d,_ in merged.most_common(5)]
            base.append(common or ['0'])
        return base
    if method == "frequency":
        counters = [Counter() for _ in range(4)]
        for num in recent:
            for i, d in enumerate(num):
                counters[i][d] += 1
        return [[d for d,_ in c.most_common(5)] for c in counters]
    if method == "gap":
        last_seen = [defaultdict(lambda: None) for _ in range(4)]
        gaps = [defaultdict(int) for _ in range(4)]
        for idx, d in enumerate(reversed(recent), start=1):
            for pos, dig in enumerate(d):
                if last_seen[pos][dig] is not None:
                    gaps[pos][dig] += idx - last_seen[pos][dig]
                last_seen[pos][dig] = idx
        return [[d for d,_ in sorted(g.items(), key=lambda x:-x[1])[:5]] for g in gaps]
    if method == "hybrid":
        freq = generate_base(draws, 'frequency', recent_n)
        gap  = generate_base(draws, 'gap', recent_n)
        combined = []
        for f, g in zip(freq, gap):
            cnt = Counter(f + g)
            combined.append([d for d,_ in cnt.most_common(5)])
        return combined
    if method == "qaisara":
        b1 = generate_base(draws, 'frequency', recent_n)
        b2 = generate_base(draws, 'gap', recent_n)
        b3 = generate_base(draws, 'hybrid', recent_n)
        final = []
        for pos in range(4):
            score = Counter(b1[pos] + b2[pos] + b3[pos])
            ranked = score.most_common()
            if len(ranked) > 2:
                ranked = ranked[1:-1]
            final.append([d for d,_ in ranked[:5]])
        return final
    st.warning(f"⚠️ Strategi '{method}' tidak dikenali.")
    return [['0'], ['0'], ['0'], ['0']]

def run_backtest(draws, strategy='hybrid', recent_n=10, arah='Kiri ke Kanan (P1→P4)', rounds=10):
    if len(draws) < recent_n + rounds:
        st.warning("⚠️ Tidak cukup draw untuk backtest.")
        return
    def match_insight(fp, base):
        if arah == "Kanan ke Kiri (P4→P1)":
            fp, base = fp[::-1], base[::-1]
        return ["✅" if fp[i] in base[i] else "❌" for i in range(4)]
    results = []
    for i in range(rounds):
        test = draws[-(i+1)]
        past = draws[:-(i+1)]
        if len(past) < recent_n: continue
        base = generate_base(past, method=strategy, recent_n=recent_n)
        insight = match_insight(test['number'], base)
        results.append({
            "Tarikh": test['date'],
            "Result 1st": test['number'],
            "Insight": ' '.join(f"P{j+1}:{s}" for j, s in enumerate(insight))
        })
    df = pd.DataFrame(results[::-1])
    matched = sum("✅" in r for r in df["Insight"])
    st.success(f"🎯 Matched: {matched}/{rounds}")
    st.dataframe(df, use_container_width=True)

def get_like_dislike_digits(draws, recent_n=30):
    last = [d['number'] for d in draws[-recent_n:] if len(d.get('number','')) == 4]
    cnt = Counter()
    for num in last:
        cnt.update(num)
    mc = cnt.most_common()
    like    = [d for d,_ in mc[:3]]
    dislike = [d for d,_ in mc[-3:]] if len(mc) >= 3 else []
    return like, dislike

def generate_predictions_from_base(base, max_preds=10):
    combos = [''.join(p) for p in itertools.product(*base)]
    return combos[:max_preds]

st.set_page_config(page_title="Breakcode4D Predictor", layout="wide")
st.markdown(f"⏳ Next draw in: `{str(get_draw_countdown_from_last_8pm()).split('.')[0]}`")
st.title("🔮 Breakcode4D Predictor (GD Lotto)")

col1, col2 = st.columns(2)
with col1:
    if st.button("📥 Update Draw"):
        msg = update_draws()
        st.success(msg)
        st.markdown("### 📋 Base Hari Ini")
        st.code('\n'.join(' '.join(p) for p in load_base_from_file()), language='text')
with col2:
    st.markdown(
        '<a href="https://batman11.net/RegisterByReferral.aspx?MemberCode=BB1845" target="_blank">'
        '<button style="width:100%;padding:0.6em;font-size:16px;background:#4CAF50;color:white;'
        'border:none;border-radius:5px;">📝 Daftar Batman 11 & dapat BONUS!</button>'
        '</a>',
        unsafe_allow_html=True
    )

draws = load_draws()
if not draws:
    st.warning("⚠️ Klik 'Update Draw' untuk mula.")
else:
    st.info(f"📅 Terakhir: {draws[-1]['date']} | 🔢 Jumlah: {len(draws)}")
    tabs = st.tabs(["📌 Insight", "🧠 Ramalan", "🔁 Backtest", "📋 Draw List", "🎡 Wheelpick"])

    with tabs[0]:
        st.markdown("### 📌 Insight Terakhir")
        last = draws[-1]
        base = load_base_from_file('data/base_last.txt')
        if len(base) != 4:
            st.warning("⚠️ Base terakhir belum wujud. Update dulu.")
            st.stop()
        st.markdown(f"**Tarikh:** `{last['date']}`")
        st.markdown(f"**1st Prize:** `{last['number']}`")
        cols = st.columns(4)
        for i in range(4):
            dig = last['number'][i]
            func = cols[i].success if dig in base[i] else cols[i].error
            func(f"Pos {i+1}: `{dig}`")
        st.markdown("### 📋 Base (Sebelum Draw Ini)")
        for i, b in enumerate(base):
            st.text(f"Pos {i+1}: {' '.join(b)}")

    with tabs[1]:
        st.markdown("### 🧠 Ramalan Base")
        strat = st.selectbox("Strategi:", ['frequency','gap','hybrid','qaisara','smartpattern'])
        recent_n = st.slider("Draw untuk base:", 5, 120, 30, 5)
        base = generate_base(draws, method=strat, recent_n=recent_n)
        for i, p in enumerate(base):
            st.text(f"Pick {i+1}: {' '.join(p)}")
        preds = generate_predictions_from_base(base)
        st.markdown("**🔢 Top 10 Kombinasi:**")
        st.code('\n'.join(preds), language='text')

    with tabs[2]:
        st.markdown("### 🔁 Backtest Base")
        arah = st.radio("🔁 Arah:", ["Kiri→Kanan","Kanan→Kiri"])
        strat = st.selectbox("Strategi:", ['frequency','gap','hybrid','qaisara','smartpattern'])
        base_n = st.slider("Draw untuk base:", 5, 120, 30, 5)
        backtest_n = st.slider("Bilangan backtest:", 5, 50, 10)
        if st.button("🚀 Jalankan"):
            run_backtest(draws, strategy=strat, recent_n=base_n, arah="Kiri ke Kanan (P1→P4)" if arah=="Kiri→Kanan" else "Kanan ke Kiri (P4→P1)", rounds=backtest_n)

    with tabs[3]:
        st.markdown("### 📋 Senarai Draw")
        st.dataframe(pd.DataFrame(draws), use_container_width=True)

    with tabs[4]:
        st.markdown("### 🎡 Wheelpick Generator")
        arah_wp = st.radio("🔁 Arah:", ["Kiri→Kanan","Kanan→Kiri"], key="wp_arah")
        like_sugg, dislike_sugg = get_like_dislike_digits(draws)
        st.markdown(f"👍 LIKE: `{like_sugg}`")
        st.markdown(f"👎 DISLIKE: `{dislike_sugg}`")
        user_like    = st.text_input("Masukkan LIKE:", value=' '.join(like_sugg))
        user_dislike = st.text_input("Masukkan DISLIKE:", value=' '.join(dislike_sugg))
        like_digits    = [d for d in user_like.split() if d.isdigit()]
        dislike_digits = [d for d in user_dislike.split() if d.isdigit()]

        mode = st.radio("Mod Base:", ["Auto","Manual"], key="wp_mode")
        if mode == "Manual":
            manual_base = []
            for i in range(4):
                val = st.text_input(f"Pick {i+1} (5 digit):", key=f"wp_manual_{i}")
                digs = val.split()
                if len(digs) != 5 or not all(d.isdigit() for d in digs):
                    st.error("❌ Manual mesti 5 digit.")
                    st.stop()
                manual_base.append(digs)
        else:
            base = load_base_from_file()
            if len(base) != 4:
                st.warning("⚠️ Base tidak sah. Update dulu.")
                st.stop()
            manual_base = base

        lot = st.text_input("Nilai Lot:", value="0.10")
        with st.expander("⚙️ Tapisan"):
            no_repeat   = st.checkbox("❌ Buang repeat")
            no_triple   = st.checkbox("❌ Buang triple")
            no_pair     = st.checkbox("❌ Buang pair")
            no_ascend   = st.checkbox("❌ Buang menaik")
            use_history = st.checkbox("❌ Buang pernah naik")
            sim_limit   = st.slider("❌ Had persamaan dgn terakhir", 0, 4, 2)

        def apply_filters(combos, draws, nr, nt, npair, na, uh, sl, likes, dislikes):
            past = {d['number'] for d in draws}
            last = draws[-1]['number'] if draws else "0000"
            out = []
            for e in combos:
                num = e[:4]
                digs = list(num)
                if nr and len(set(digs)) < 4: continue
                if nt and any(digs.count(d) >= 3 for d in digs): continue
                if npair and any(digs.count(d) == 2 for d in set(digs)): continue
                if na and num in ["0123","1234","2345","3456","4567","5678","6789"]: continue
                if uh and num in past: continue
                sim = sum(a == b for a, b in zip(num, last))
                if sim > sl: continue
                if likes and not any(d in likes for d in digs): continue
                if dislikes and any(d in dislikes for d in digs): continue
                out.append(e)
            return out

        if st.button("🎰 Create Wheelpick"):
            combos = [f"{a}{b}{c}{d}#{lot}" for a in manual_base[0] for b in manual_base[1] for c in manual_base[2] for d in manual_base[3]]
            st.info(f"🔍 Sebelum tapis: {len(combos)}")
            combos = apply_filters(combos, draws, no_repeat, no_triple, no_pair, no_ascend, use_history, sim_limit, like_digits, dislike_digits)
            st.success(f"✅ Selepas tapis: {len(combos)}")
            for i in range(0, len(combos), 30):
                part = combos[i:i+30]
                st.markdown(f"📦 Bahagian {i//30+1} ({len(part)})")
                st.code('\n'.join(part))
            filename = f"wheelpick_{datetime.now():%Y%m%d_%H%M%S}.txt"
            data = '\n'.join(combos).encode()
            st.download_button("💾 Muat Turun", data=data, file_name=filename, mime="text/plain")
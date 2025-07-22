# ===================== IMPORT =====================
import streamlit as st
import os
import re
import requests
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from itertools import product

# ===================== COUNTDOWN DRAW =====================
def get_draw_countdown_from_last_8pm():
    now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    today_8pm = now.replace(hour=20, minute=0, second=0, microsecond=0)
    last_8pm = today_8pm - timedelta(days=1) if now < today_8pm else today_8pm
    return (last_8pm + timedelta(days=1)) - now

# ===================== LOAD & SAVE FILE =====================
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

# ===================== UPDATE DRAW =====================
def get_1st_prize(date_str):
    url = f"https://gdlotto.net/results/ajax/_result.aspx?past=1&d={date_str}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        prize_tag = soup.find("span", id="1stPz")
        if prize_tag and prize_tag.text.strip().isdigit() and len(prize_tag.text.strip()) == 4:
            return prize_tag.text.strip()
    except:
        return None
    return None

def update_draws(file_path='data/draws.txt', max_days_back=121):
    draws = load_draws(file_path)
    existing = {d['date'] for d in draws}
    last_date = (datetime.today() - timedelta(max_days_back)
                 if not draws else datetime.strptime(draws[-1]['date'], "%Y-%m-%d"))
    yesterday = datetime.today() - timedelta(days=1)
    current = last_date + timedelta(days=1)
    added = []
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'a') as f:
        while current.date() <= yesterday.date():
            ds = current.strftime("%Y-%m-%d")
            if ds in existing:
                current += timedelta(days=1)
                continue
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

# ===================== STRATEGY BASE =====================
def generate_base(draws, method='frequency', recent_n=50):
    total = len(draws)
    if total < recent_n:
        st.warning(
            f"⚠️ Tidak cukup data untuk strategi `{method}`. "
            f"Minimum {recent_n} draws diperlukan, tapi hanya {total} draws tersedia."
        )
        st.stop()
    recent = draws[-recent_n:]
    func = {
        'frequency': generate_by_frequency,
        'gap':       generate_by_gap,
        'hybrid':    generate_hybrid,
        'qaisara':   generate_qaisara
    }.get(method)
    return func(recent, recent_n)

def generate_by_frequency(recent, recent_n):
    counters = [Counter() for _ in range(4)]
    for d in recent:
        for i, dig in enumerate(d['number']):
            counters[i][dig] += 1
    picks = []
    for c in counters:
        picks.append([dig for dig, _ in c.most_common(5)])
    return picks

def generate_by_gap(recent, recent_n):
    last_seen = [defaultdict(lambda: None) for _ in range(4)]
    gaps = [defaultdict(int) for _ in range(4)]
    for idx, d in enumerate(reversed(recent), start=1):
        for pos, dig in enumerate(d['number']):
            if last_seen[pos][dig] is not None:
                gaps[pos][dig] += idx - last_seen[pos][dig]
            last_seen[pos][dig] = idx
    picks = []
    for g in gaps:
        picks.append([dig for dig, _ in sorted(g.items(), key=lambda x: -x[1])[:5]])
    return picks

def generate_hybrid(recent, recent_n):
    freq = generate_by_frequency(recent, recent_n)
    gap  = generate_by_gap(recent, recent_n)
    picks = []
    for f, g in zip(freq, gap):
        cnt = Counter(f + g)
        picks.append([dig for dig, _ in cnt.most_common(5)])
    return picks

def generate_qaisara(recent, recent_n):
    freq   = generate_by_frequency(recent, recent_n)
    gap    = generate_by_gap(recent, recent_n)
    hybrid = generate_hybrid(recent, recent_n)
    picks = []
    for i in range(4):
        cnt = Counter(freq[i] + gap[i] + hybrid[i])
        picks.append([dig for dig, _ in cnt.most_common(5)])
    return picks

# ===================== BACKTEST FUNCTION =====================
def run_backtest(draws, strategy='hybrid', recent_n=10, arah='Kiri ke Kanan (P1→P4)', backtest_rounds=10):
    if len(draws) < recent_n + backtest_rounds:
        st.warning("❗ Tidak cukup draw untuk backtest.")
        return
    def match(fp, base):
        if arah.startswith("Kanan"):
            fp, base = fp[::-1], base[::-1]
        return ["✅" if fp[i] in base[i] else "❌" for i in range(4)]
    results = []
    for i in range(backtest_rounds):
        test = draws[-(i+1)]
        past = draws[:-(i+1)]
        if len(past) < recent_n:
            continue
        base = generate_base(past, method=strategy, recent_n=recent_n)
        ins  = match(test['number'], base)
        results.append({
            "Tarikh": test['date'],
            "Result 1st": test['number'],
            "Insight": ' '.join(f"P{j+1}:{s}" for j, s in enumerate(ins))
        })
    df = pd.DataFrame(results[::-1])
    matched = sum("✅" in r["Insight"] for r in results)
    st.success(f"🎯 Jumlah digit match: {matched} daripada {backtest_rounds}")
    st.dataframe(df, use_container_width=True)

# ===================== LIKE / DISLIKE ANALYSIS =====================
def get_like_dislike_digits(draws, recent_n=30):
    recent = [d['number'] for d in draws[-recent_n:] if len(d['number'])==4]
    cnt = Counter(''.join(recent))
    mc = cnt.most_common()
    return [d for d,_ in mc[:3]], [d for d,_ in mc[-3:]]

# ===================== UI =====================
st.set_page_config(page_title="Breakcode4D Predictor", layout="wide")
st.markdown(f"⏳ Next draw: `{str(get_draw_countdown_from_last_8pm()).split('.')[0]}`")
st.title("🔮 Breakcode4D Predictor (GD Lotto)")

col1, col2 = st.columns(2)
with col1:
    if st.button("📥 Update Draw Terkini"):
        msg = update_draws()
        st.success(msg)
        st.markdown("### 📋 Base Hari Ini")
        st.code('\n'.join([' '.join(p) for p in load_base_from_file()]), language='text')
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
    tabs = st.tabs(["📌 Insight", "🧠 Ramalan", "🔁 Backtest", "📋 Draw List", "🎡 Wheelpick"])

    # Insight Tab
    with tabs[0]:
        st.markdown("### 📌 Insight Terakhir")
        last = draws[-1]
        base = load_base_from_file()
        if not base or len(base)!=4:
            st.warning("⚠️ Base belum dijana.")
        else:
            cols = st.columns(4)
            for i in range(4):
                dig = last['number'][i]
                (cols[i].success if dig in base[i] else cols[i].error)(f"P{i+1}: `{'✅' if dig in base[i] else '❌'} {dig}`")

    # Ramalan Tab
    with tabs[1]:
        st.markdown("### 🧠 Ramalan Base")
        strat = st.selectbox("Strategi:", ['hybrid','frequency','gap','qaisara'])
        rn    = st.slider("Draw untuk base:",5,100,30,5)
        base  = generate_base(draws, strat, rn)
        for i,p in enumerate(base):
            st.text(f"P{i+1}: {' '.join(p)}")
        preds=[]
        for comb in product(*base):
            preds.append(''.join(comb))
            if len(preds)==10: break
        st.code('\n'.join(preds))

    # Backtest Tab
    with tabs[2]:
        st.markdown("### 🔁 Backtest Base")
        arah   = st.radio("Arah:", ["Kiri ke Kanan","Kanan ke Kiri"], key="backtest_arah")
        strat  = st.selectbox("Strategi Backtest:", ['hybrid','frequency','gap','qaisara'])
        bn     = st.slider("Base draw:",5,100,30,5)
        br     = st.slider("Bil. backtest:",5,50,10)
        if st.button("🚀 Jalankan Backtest"):
            run_backtest(draws, strat, bn, "Kanan" if arah=="Kanan ke Kiri" else "Kiri", br)

    # Draw List Tab
    with tabs[3]:
        st.dataframe(pd.DataFrame(draws), use_container_width=True)

    # Wheelpick Tab
    with tabs[4]:
        st.markdown("### 🎡 Wheelpick Generator")

        arah_wp = st.radio(
            "🔁 Arah bacaan:",
            ["Kiri ke Kanan (P1→P4)", "Kanan ke Kiri (P4→P1)"],
            index=0, key="wheelpick_arah"
        )

        like_s, dislike_s = get_like_dislike_digits(draws)
        st.markdown(f"👍 Cadangan LIKE: `{like_s}`")
        st.markdown(f"👎 Cadangan DISLIKE: `{dislike_s}`")

        user_like    = st.text_input("LIKE (pisah ruang):", ' '.join(like_s))
        user_dislike = st.text_input("DISLIKE (pisah ruang):", ' '.join(dislike_s))
        like_digits  = [d for d in user_like.split() if d.isdigit()]
        dis_digits   = [d for d in user_dislike.split() if d.isdigit()]

        mode = st.radio("Mod Base:", ["Auto","Manual"], key="wheelpick_mode")
        manual_base=[]
        if mode=="Manual":
            for i in range(4):
                v = st.text_input(f"P{i+1} digits (5):", key=f"m{i}")
                digs = v.split()
                if len(digs)!=5 or not all(d.isdigit() for d in digs):
                    st.warning(f"⚠️ Pos {i+1}: Masuk 5 digit (sekarang {len(digs)})")
                    st.stop()
                manual_base.append(digs)
        else:
            base = load_base_from_file()
            if not base or len(base)!=4:
                st.warning("⚠️ Base tidak sah.")
                st.stop()
            manual_base=base

        lot = st.text_input("Nilai Lot:", "0.10", key="lot")

        with st.expander("⚙️ Tapisan Tambahan"):
            no_repeat   = st.checkbox("❌ No-repeat")
            no_triple   = st.checkbox("❌ No-triple")
            no_pair     = st.checkbox("❌ No-pair")
            no_ascend   = st.checkbox("❌ No-ascend")
            use_hist    = st.checkbox("❌ No history")
            sim_lim     = st.slider("Max same pos:",0,4,2)

        def apply_filters(combos):
            past = {d['number'] for d in draws}
            last = draws[-1]['number']
            out=[]
            for e in combos:
                num=list(e[:4])
                if no_repeat   and len(set(num))<4: continue
                if no_triple   and any(num.count(d)>=3 for d in num): continue
                if no_pair     and any(num.count(d)==2 for d in set(num)): continue
                if no_ascend   and ''.join(num) in ["0123","1234","2345","3456","4567","5678","6789"]: continue
                if use_hist    and ''.join(num) in past: continue
                if sum(a==b for a,b in zip(num,last))>sim_lim: continue
                if like_digits and not any(d in like_digits for d in num): continue
                if dis_digits  and any(d in dis_digits for d in num): continue
                out.append(e)
            return out

        if st.button("🎰 Create Wheelpick"):
            combos=[f"{''.join(p)}##### {lot}" for p in product(*manual_base)]
            st.info(f"Sebelum tapis: {len(combos)}")
            combos=apply_filters(combos)
            st.success(f"Selepas tapis: {len(combos)}")
            for i in range(0,len(combos),30):
                st.code('\n'.join(combos[i:i+30]))
            fname=f"wheelpick_{datetime.now():%Y%m%d_%H%M%S}.txt"
            st.download_button("💾 Download", '\n'.join(combos), file_name=fname)
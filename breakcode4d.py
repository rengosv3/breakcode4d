# ===================== IMPORT =====================
import streamlit as st
import os
import re
import requests
import random
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

# ===================== GLOBAL EXPIRY CHECK =====================
global_expired = st.secrets.get("expired_until", "2099-12-31 23:59")
global_expired_date = datetime.strptime(global_expired, "%Y-%m-%d %H:%M")
if datetime.now() > global_expired_date:
    st.title("🔒 Akses Disekat")
    st.error("Access disekat. Sila hubungi admin [@rengosv3](https://t.me/rengosv3) di Telegram untuk maklumat lanjut.")
    st.stop()

# ===================== SESSION-STATE LOGIN INIT =====================
if "login_success" not in st.session_state:
    st.session_state.login_success = False

# ===================== MULTI-USER LOGIN WITH PER-USER EXPIRY =====================
if not st.session_state.login_success:
    st.title("🔐 Sila Login Dahulu")
    st.info(
        "Jika tiada akses, anda boleh guna akaun percuma:\n\n"
        "hubungi admin [@rengosv3](https://t.me/rengosv3) di Telegram untuk maklumat lanjut.\n"
        "🆓 **ID:** `breakcode4d`\n"
        "🔑 **Password:** `1234`"
    )

    username = st.text_input("🧑 ID Pengguna")
    password = st.text_input("🔑 Kata Laluan", type="password")

    if st.button("Login"):
        auth_users = st.secrets.get("auth_users", {})
        user_expiry = st.secrets.get("user_expiry", {})

        # validasi credentials
        if username in auth_users and password == auth_users[username]:
            # per-user expiry check
            expiry_str = user_expiry.get(username, "2099-12-31 23:59")
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M")
            if datetime.now() > expiry_date:
                st.title("🔒 Akses Tamat")
                st.error(f"Akses untuk '{username}' telah tamat. Sila hubungi admin [@rengosv3](https://t.me/rengosv3).")
                st.stop()
            # mark login success & rerun
            st.session_state.login_success = True
            st.session_state.logged_user = username
            st.experimental_rerun()
        else:
            st.error("ID atau Kata Laluan salah.")
    st.stop()

# ========== USER IS LOGGED IN BELOW ==========
st.sidebar.success(f"✔️ Logged in as: {st.session_state.logged_user}")

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

def load_base_from_file(file_path='data/base.txt'):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r') as f:
        return [line.strip().split() for line in f if line.strip()]

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
    return f"✔️ {len(added)} draw baru ditambah." if added else "✔️ Tiada draw baru."

# ===================== STRATEGIES =====================
def generate_base(draws, method='frequency', recent_n=50):
    return {
        'frequency': generate_by_frequency,
        'gap': generate_by_gap,
        'hybrid': generate_hybrid,
        'qaisara': generate_qaisara
    }.get(method, generate_by_frequency)(draws, recent_n)

def generate_by_frequency(draws, recent_n=50):
    recent = [d['number'] for d in draws[-recent_n:]]
    counters = [Counter() for _ in range(4)]
    for num in recent:
        for i, dig in enumerate(num):
            counters[i][dig] += 1
    picks = []
    for c in counters:
        top = [d for d, _ in c.most_common(5)]
        while len(top) < 5:
            top.append(str(random.randint(0,9)))
        picks.append(top)
    return picks

def generate_by_gap(draws, recent_n=50):
    recent = [d['number'] for d in draws[-recent_n:]]
    last_seen = [defaultdict(lambda: -1) for _ in range(4)]
    gap_scores = [defaultdict(int) for _ in range(4)]
    for idx, num in enumerate(recent[::-1]):
        for pos, dig in enumerate(num):
            if last_seen[pos][dig] != -1:
                gap_scores[pos][dig] += idx - last_seen[pos][dig]
            last_seen[pos][dig] = idx
    picks = []
    for gs in gap_scores:
        top = [d for d, _ in sorted(gs.items(), key=lambda x: -x[1], reverse=True)[:5]]
        while len(top) < 5:
            top.append(str(random.randint(0,9)))
        picks.append(top)
    return picks

def generate_hybrid(draws, recent_n=10):
    f = generate_by_frequency(draws, recent_n)
    g = generate_by_gap(draws, recent_n)
    picks = []
    for a, b in zip(f, g):
        combo = list(set(a + b))
        random.shuffle(combo)
        top = combo[:5]
        while len(top) < 5:
            top.append(str(random.randint(0,9)))
        picks.append(top)
    return picks

def generate_qaisara(draws, recent_n=10):
    f = generate_by_frequency(draws, recent_n)
    g = generate_by_gap(draws, recent_n)
    h = generate_hybrid(draws, recent_n)
    combined = []
    for i in range(4):
        cnt = Counter(f[i] + g[i] + h[i])
        top = [d for d, _ in cnt.most_common(5)]
        while len(top) < 5:
            top.append(str(random.randint(0,9)))
        combined.append(top)
    return combined

# ===================== BACKTEST =====================
def run_backtest(draws, strategy='hybrid', recent_n=10,
                 arah='Kiri ke Kanan (P1→P4)', backtest_rounds=10):
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
        ins = match(test['number'], base)
        results.append({
            "Tarikh": test['date'],
            "Result 1st": test['number'],
            "Insight": ' '.join(f"P{j+1}:{s}" for j, s in enumerate(ins))
        })

    df = pd.DataFrame(results[::-1])
    matched = sum("✅" in r["Insight"] for r in results)
    st.success(f"🎯 Jumlah digit match: {matched} daripada {backtest_rounds}")
    st.dataframe(df, use_container_width=True)

# ===================== LIKE / DISLIKE =====================
def get_like_dislike_digits(draws, recent_n=30):
    recent = [d['number'] for d in draws[-recent_n:]]
    cnt = Counter(''.join(recent))
    mc = cnt.most_common()
    like = [d for d, _ in mc[:3]]
    dislike = [d for d, _ in mc[-3:]]
    return like, dislike

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
        last = draws[-1]
        base = load_base_from_file()
        if not base or len(base) != 4:
            st.warning("⚠️ Base belum dijana.")
        else:
            st.markdown(f"**Tarikh Draw:** `{last['date']}`  **1st Prize:** `{last['number']}`")
            cols = st.columns(4)
            for i in range(4):
                dig = last['number'][i]
                (cols[i].success if dig in base[i] else cols[i].error)(f"P{i+1}:{dig}")
            st.markdown("### Base Digunakan:")
            for i, b in enumerate(base):
                st.text(f"P{i+1} → {' '.join(b)}")
    # Ramalan Tab
    with tabs[1]:
        strat = st.selectbox("Strategi:", ['hybrid','frequency','gap','qaisara'])
        rn = st.slider("Draw untuk base:", 5,100,30,5)
        base = generate_base(draws, strat, rn)
        for i, p in enumerate(base):
            st.text(f"P{i+1}: {' '.join(p)}")
        preds = []
        while len(preds) < 10:
            p = ''.join(random.choice(base[i]) for i in range(4))
            if p not in preds: preds.append(p)
        st.code('\n'.join(preds))
    # Backtest Tab
    with tabs[2]:
        arah = st.radio("Arah bacaan:", ["Kiri ke Kanan (P1→P4)","Kanan ke Kiri (P4→P1)"])
        strat = st.selectbox("Strategi Backtest:", ['hybrid','frequency','gap','qaisara'])
        bn = st.slider("Base draw:",5,100,30,5)
        br = st.slider("Bil. backtest:",5,50,10)
        if st.button("🚀 Jalankan Backtest"):
            run_backtest(draws, strat, bn, arah, br)
    # Draw List Tab
    with tabs[3]:
        st.dataframe(pd.DataFrame(draws), use_container_width=True)
    # Wheelpick Tab
    with tabs[4]:
        st.markdown("### 🎡 Wheelpick Generator")
        arah_wp = st.radio("Arah:", ["Kiri ke Kanan (P1→P4)","Kanan ke Kiri (P4→P1)"])
        like_s, dislike_s = get_like_dislike_digits(draws)
        st.markdown(f"👍 Cadangan LIKE: `{like_s}`  👎 Cadangan DISLIKE: `{dislike_s}`")
        user_like = st.text_input("LIKE (pisahkan ruang):", ' '.join(like_s))
        user_dislike = st.text_input("DISLIKE (pisahkan ruang):", ' '.join(dislike_s))
        lik = [d for d in user_like.split() if d.isdigit()]
        dis = [d for d in user_dislike.split() if d.isdigit()]
        mode = st.radio("Mod Base:", ["Auto","Manual"], key="wp_mode")
        if mode == "Manual":
            manual = []
            for i in range(4):
                v = st.text_input(f"P{i+1} digits (5):", key=f"m{i}")
                ds = v.split()
                manual.append(ds if len(ds) == 5 else [str(random.randint(0,9)) for _ in range(5)])
        else:
            manual = load_base_from_file()
            if not manual or len(manual) != 4:
                st.warning("⚠️ Base tidak sah.")
                st.stop()
        lot = st.text_input("Lot setiap nombor:", "0.10", key="lot")
        no_repeat = st.checkbox("❌ No-repeat")
        no_triple = st.checkbox("❌ No-triple")
        no_pair = st.checkbox("❌ No-pair")
        no_ascend = st.checkbox("❌ No-ascend")
        use_hist = st.checkbox("❌ No history")
        sim_lim = st.slider("Max same pos:", 0,4,2)

        def apply_filters(combos):
            past = {d['number'] for d in draws}
            lastn = draws[-1]['number'] if draws else "0000"
            out = []
            for e in combos:
                num = e[:4]
                digs = list(num)
                if no_repeat and len(set(digs)) < 4: continue
                if no_triple and any(digs.count(d)>=3 for d in digs): continue
                if no_pair and any(digs.count(d)==2 for d in set(digs)): continue
                if no_ascend and num in ["0123","1234","2345","3456","4567","5678","6789"]: continue
                if use_hist and num in past: continue
                if sum(a==b for a,b in zip(num,lastn)) > sim_lim: continue
                if lik and not any(d in lik for d in num): continue
                if dis and any(d in dis for d in num): continue
                out.append(e)
            return out

        combos = []
        if st.button("🎰 Create Wheelpick"):
            for a in manual[0]:
                for b in manual[1]:
                    for c in manual[2]:
                        for d in manual[3]:
                            combos.append(f"{a}{b}{c}{d}##### {lot}")
            st.info(f"💡 Sebelum tapis: {len(combos)} nombor")
            combos = apply_filters(combos)
            st.success(f"✅ Selepas tapis: {len(combos)} nombor")
            for i in range(0, len(combos), 30):
                st.code('\n'.join(combos[i:i+30]))
            data = '\n'.join(combos).encode("utf-8")
            st.download_button("💾 Download", data=data,
                               file_name=f"wheelpick_{datetime.now():%Y%m%d_%H%M%S}.txt",
                               mime="text/plain")
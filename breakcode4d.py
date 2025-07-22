# ===================== IMPORT =====================
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

# ===================== COUNTDOWN DRAW =====================
def get_draw_countdown_from_last_8pm():
    now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    today_8pm = now.replace(hour=20, minute=0, second=0, microsecond=0)
    last_8pm = today_8pm - timedelta(days=1) if now < today_8pm else today_8pm
    return (last_8pm + timedelta(days=1)) - now

# ===================== LOAD & SAVE FILE =====================
@st.cache_data
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

@st.cache_data
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
            print(f"❌ Status bukan 200 untuk {date_str}: {resp.status_code}")
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        prize_tag = soup.find("span", id="1stPz")
        if prize_tag and prize_tag.text.strip().isdigit() and len(prize_tag.text.strip()) == 4:
            return prize_tag.text.strip()
        else:
            print(f"❌ Tidak jumpa 1st Prize untuk {date_str}")
            return None
    except requests.RequestException as e:
        print(f"❌ Ralat semasa request untuk {date_str}: {e}")
        return None

def update_draws(file_path='data/draws.txt', max_days_back=121):
    st.cache_data.clear()
    draws = load_draws(file_path)
    existing_dates = set(d['date'] for d in draws)
    last_date = (datetime.today() - timedelta(max_days_back)
                 if not draws else datetime.strptime(draws[-1]['date'], "%Y-%m-%d"))
    yesterday = datetime.today() - timedelta(days=1)
    current = last_date + timedelta(days=1)
    added = []

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'a') as f:
        while current.date() <= yesterday.date():
            date_str = current.strftime("%Y-%m-%d")
            if date_str in existing_dates:
                current += timedelta(days=1)
                continue
            prize = get_1st_prize(date_str)
            if prize:
                f.write(f"{date_str} {prize}\n")
                added.append({'date': date_str, 'number': prize})
            current += timedelta(days=1)

    if added:
        draws = load_draws(file_path)
        latest_base = generate_base(draws, method='frequency', recent_n=50)
        save_base_to_file(latest_base, 'data/base.txt')
        save_base_to_file(latest_base, 'data/base_last.txt')
    return f"✔ {len(added)} draw baru ditambah." if added else "✔ Tiada draw baru ditambah."

# ===================== STRATEGY BASE =====================
@st.cache_data
def generate_base(draws, method='frequency', recent_n=50):
    total = len(draws)
    if total < recent_n:
        st.warning(
            f"⚠️ Tidak cukup data untuk strategi `{method}`. "
            f"Minimum {recent_n} draws diperlukan, tapi hanya {total} draws tersedia."
        )
        st.stop()

    func = {
        'frequency': generate_by_frequency,
        'gap':       generate_by_gap,
        'hybrid':    generate_hybrid,
        'qaisara':   generate_qaisara
    }.get(method)

    return func(draws[-recent_n:], recent_n)

def generate_by_frequency(recent, recent_n):
    counters = [Counter() for _ in range(4)]
    for d in recent:
        for i, dig in enumerate(d['number']):
            counters[i][dig] += 1
    return [[dig for dig, _ in c.most_common(5)] for c in counters]

def generate_by_gap(recent, recent_n):
    last_seen = [defaultdict(lambda: None) for _ in range(4)]
    gaps = [defaultdict(int) for _ in range(4)]
    for idx, d in enumerate(reversed(recent), start=1):
        for pos, dig in enumerate(d['number']):
            if last_seen[pos][dig] is not None:
                gaps[pos][dig] += idx - last_seen[pos][dig]
            last_seen[pos][dig] = idx
    return [[dig for dig, _ in sorted(g.items(), key=lambda x: -x[1])[:5]] for g in gaps]

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

    def match_insight(fp, base):
        if arah == "Kanan ke Kiri (P4→P1)":
            fp = fp[::-1]
            base = base[::-1]
        return ["✅" if fp[i] in base[i] else "❌" for i in range(4)]

    results = []
    for i in range(backtest_rounds):
        test = draws[-(i+1)]
        past = draws[:-(i+1)]
        if len(past) < recent_n:
            continue
        base = generate_base(past, method=strategy, recent_n=recent_n)
        insight = match_insight(test['number'], base)
        results.append({
            "Tarikh": test['date'],
            "Result 1st": test['number'],
            "Insight": ' '.join(f"P{j+1}:{s}" for j, s in enumerate(insight))
        })

    df = pd.DataFrame(results[::-1])
    matched = sum("✅" in r["Insight"] for r in results)
    st.success(f"🎯 Jumlah digit match: {matched} daripada {backtest_rounds}")
    st.dataframe(df, use_container_width=True)

# ===================== LIKE / DISLIKE ANALYSIS =====================
def get_like_dislike_digits(draws, recent_n=30):
    last = [d['number'] for d in draws[-recent_n:] if 'number' in d and len(d['number']) == 4]
    cnt = Counter()
    for num in last:
        cnt.update(num)
    mc = cnt.most_common()
    like = [d for d, _ in mc[:3]]
    dislike = [d for d, _ in mc[-3:]] if len(mc) >= 3 else []
    return like, dislike

# ===================== PREDICTION DETERMINISTIK =====================
@st.cache_data
def generate_predictions_from_base(base, max_preds=10):
    combos = [''.join(p) for p in itertools.product(*base)]
    return combos[:max_preds]

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
    st.warning("⚠️ Sila klik 'Update Draw Terkini' untuk mula. Proses ini hanya mengambil masa 1-5 minit sahaja.")
else:
    st.info(f"📅 Tarikh terakhir: **{draws[-1]['date']}** | 📊 Jumlah draw: **{len(draws)}**")
    tabs = st.tabs(["📌 Insight", "🧠 Ramalan", "🔁 Backtest", "📋 Draw List", "🎡 Wheelpick"])

    # === Insight Tab ===
    with tabs[0]:
        st.markdown("### 📌 Insight Terakhir")
        last = draws[-1]
        base = load_base_from_file()
        if not base or len(base) != 4:
            st.warning("⚠️ Base belum dijana atau tidak lengkap.")
        else:
            st.markdown(f"**Tarikh Draw:** `{last['date']}`")
            st.markdown(f"**Nombor 1st Prize:** `{last['number']}`")
            cols = st.columns(4)
            for i in range(4):
                dig = last['number'][i]
                (cols[i].success if dig in base[i] else cols[i].error)(
                    f"Pos {i+1}: {'✅' if dig in base[i] else '❌'} `{dig}`"
                )
            st.markdown("### 📋 Base Digunakan:")
            for i, b in enumerate(base):
                st.text(f"Pos {i+1}: {' '.join(b)}")

    # === Ramalan Tab ===
    with tabs[1]:
        st.markdown("### 🧠 Ramalan Base (Deterministik)")
        strat = st.selectbox("Pilih strategi base untuk ramalan:", ['hybrid', 'frequency', 'gap', 'qaisara'])
        recent_n = st.slider("Jumlah draw terkini digunakan untuk base:", 5, 100, 30, 5)
        base = generate_base(draws, method=strat, recent_n=recent_n)
        for i, p in enumerate(base):
            st.text(f"Pick {i+1}: {' '.join(p)}")

        preds = generate_predictions_from_base(base, max_preds=10)
        st.markdown("**🔢 Ramalan Kombinasi 4D (Top 10):**")
        st.code('\n'.join(preds), language='text')

    # === Backtest Tab ===
    with tabs[2]:
        st.markdown("### 🔁 Backtest Base")
        arah_pilihan = st.radio(
            "🔁 Pilih arah bacaan digit:",
            ["Kiri ke Kanan (P1→P4)", "Kanan ke Kiri (P4→P1)"],
            index=0,
            key="backtest_arah"
        )
        strat = st.selectbox("Pilih strategi base untuk backtest:", ['hybrid', 'frequency', 'gap', 'qaisara'])
        base_n = st.slider("Jumlah draw terkini digunakan untuk jana base:", 5, 100, 30, 5)
        backtest_n = st.slider("Jumlah draw yang diuji (berapa kali backtest):", 5, 50, 10)
        if st.button("🚀 Jalankan Backtest"):
            run_backtest(draws, strategy=strat, recent_n=base_n, arah=arah_pilihan, backtest_rounds=backtest_n)

    # === Draw List Tab ===
    with tabs[3]:
        st.dataframe(pd.DataFrame(draws), use_container_width=True)

    # === Wheelpick Tab ===
    with tabs[4]:
        st.markdown("### 🎡 Wheelpick Generator")

        arah_pilihan_wp = st.radio(
            "🔁 Pilih arah bacaan digit:",
            ["Kiri ke Kanan (P1→P4)", "Kanan ke Kiri (P4→P1)"],
            index=0,
            key="wheelpick_arah"
        )

        like_sugg, dislike_sugg = get_like_dislike_digits(draws)
        st.markdown(f"👍 **Cadangan LIKE (Top 3):** `{like_sugg}`")
        st.markdown(f"👎 **Cadangan DISLIKE (Bottom 3):** `{dislike_sugg}`")

        user_like = st.text_input("🟢 Masukkan digit LIKE (pisahkan ruang):", value=' '.join(like_sugg))
        user_dislike = st.text_input("🔴 Masukkan digit DISLIKE (pisahkan ruang):", value=' '.join(dislike_sugg))
        like_digits = [d for d in user_like.strip().split() if d.isdigit() and len(d)==1]
        dislike_digits = [d for d in user_dislike.strip().split() if d.isdigit() and len(d)==1]

        mode = st.radio("Mod Input Base:", ["Auto (dari Base)", "Manual Input"], key="wheelpick_mode")
        if mode == "Manual Input":
            manual_base = []
            # Mesti 4 baris input, setiap satu 5 digit
            for i in range(4):
                val = st.text_input(f"Digit Pilihan untuk Pick {i+1} (cth: 1 3 5 7 9):", key=f"wp_manual_{i}")
                digs = val.strip().split()
                if len(digs) != 5 or not all(d.isdigit() and len(d)==1 for d in digs):
                    st.error("❌ Manual input mesti 5 digit 0-9 dipisah ruang. Proses dihentikan.")
                    st.stop()
                manual_base.append(digs)
        else:
            base = load_base_from_file()
            if not base or len(base) != 4:
                st.warning("⚠️ Base tidak sah. Sila klik 'Update Draw' dahulu.")
                st.stop()
            manual_base = base

        lot = st.text_input("Nilai Lot Setiap Nombor (cth: 0.10):", value="0.10", key="wheelpick_lot")

        with st.expander("⚙️ Tapisan Tambahan"):
            no_repeat = st.checkbox("❌ Buang nombor dengan digit berulang (contoh: 1123)")
            no_triple = st.checkbox("❌ Buang nombor triple (contoh: 1112)")
            no_pair = st.checkbox("❌ Buang nombor pair (contoh: 1123)")
            no_ascend = st.checkbox("❌ Buang nombor menaik (contoh: 1234)")
            use_history = st.checkbox("❌ Buang nombor yang pernah naik")
            sim_limit = st.slider("❌ Had maksimum persamaan digit dengan draw terakhir", 0, 4, 2)

        def apply_filters(combos, draws, no_repeat, no_triple, no_pair, no_ascend, use_history, sim_limit, like_digits, dislike_digits):
            past = set(d['number'] for d in draws)
            last_num = draws[-1]['number'] if draws else "0000"
            filtered = []
            for entry in combos:
                num = entry[:4]
                digits = list(num)
                if no_repeat and len(set(digits)) < 4:
                    continue
                if no_triple and any(digits.count(d)>=3 for d in digits):
                    continue
                if no_pair and any(digits.count(d)==2 for d in set(digits)):
                    continue
                if no_ascend and num in ["0123","1234","2345","3456","4567","5678","6789"]:
                    continue
                if use_history and num in past:
                    continue
                sim = sum(1 for a,b in zip(num, last_num) if a==b)
                if sim > sim_limit:
                    continue
                if like_digits and not any(d in like_digits for d in num):
                    continue
                if dislike_digits and any(d in dislike_digits for d in num):
                    continue
                filtered.append(entry)
            return filtered

        combos = []
        if st.button("🎰 Create Wheelpick"):
            for a in manual_base[0]:
                for b in manual_base[1]:
                    for c in manual_base[2]:
                        for d in manual_base[3]:
                            combos.append(f"{a}{b}{c}{d}##### {lot}")
            st.info(f"💡 Sebelum tapis: {len(combos)} nombor")

            combos = apply_filters(
                combos, draws,
                no_repeat, no_triple, no_pair, no_ascend, use_history, sim_limit,
                like_digits, dislike_digits
            )

            st.success(f"✅ {len(combos)} nombor selepas ditapis.")
            part_size = 30
            for i in range((len(combos) + part_size - 1)//part_size):
                section = combos[i*part_size:(i+1)*part_size]
                if not section:
                    break
                st.markdown(f"**📦 Bahagian {i+1}** ({len(section)} nombor)")
                st.code('\n'.join(section))

            filename = f"wheelpick_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            data = '\n'.join(combos).encode('utf-8')
            st.download_button("💾 Muat Turun Semua Nombor", data=data, file_name=filename, mime='text/plain')
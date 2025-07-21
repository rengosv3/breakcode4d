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

def update_draws(file_path='data/draws.txt', max_days_back=30):
    draws = load_draws(file_path)
    last_date = datetime.today() - timedelta(max_days_back) if not draws else datetime.strptime(draws[-1]['date'], "%Y-%m-%d")
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
        latest_base = generate_base(draws, method='frequency', recent_n=50)
        save_base_to_file(latest_base, 'data/base.txt')
        save_base_to_file(latest_base, 'data/base_last.txt')
    return f"✔ {len(added)} draw baru ditambah." if added else "✔ Tiada draw baru ditambah."

# ===================== STRATEGY BASE =====================
def generate_base(draws, method='frequency', recent_n=50):
    return {
        'frequency': generate_by_frequency,
        'gap': generate_by_gap,
        'hybrid': generate_hybrid,
        'qaisara': generate_qaisara
    }.get(method, generate_by_frequency)(draws, recent_n)

def generate_by_frequency(draws, recent_n=50):
    recent_draws = [d['number'] for d in draws[-recent_n:]]
    counters = [Counter() for _ in range(4)]
    for number in recent_draws:
        for i, digit in enumerate(number):
            counters[i][digit] += 1
    return [[d for d, _ in c.most_common(5)] + [str(random.randint(0,9)) for _ in range(5 - len(c))] for c in counters]

def generate_by_gap(draws, recent_n=50):
    recent_draws = [d['number'] for d in draws[-recent_n:]]
    last_seen = [defaultdict(lambda: -1) for _ in range(4)]
    gap_scores = [defaultdict(int) for _ in range(4)]

    for idx, number in enumerate(recent_draws[::-1]):
        for pos, digit in enumerate(number):
            if last_seen[pos][digit] != -1:
                gap_scores[pos][digit] += idx - last_seen[pos][digit]
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
    freq = generate_by_frequency(draws, recent_n)
    gap = generate_by_gap(draws, recent_n)
    picks = []
    for f, g in zip(freq, gap):
        combo = list(set(f + g))
        random.shuffle(combo)
        picks.append(combo[:5] + [str(random.randint(0,9)) for _ in range(5 - len(combo))])
    return picks

def generate_qaisara(draws, recent_n=10):
    base_freq = generate_by_frequency(draws, recent_n)
    base_gap = generate_by_gap(draws, recent_n)
    base_hybrid = generate_hybrid(draws, recent_n)

    combined = []
    for i in range(4):
        all_digits = base_freq[i] + base_gap[i] + base_hybrid[i]
        counter = Counter(all_digits)
        top_5 = [d for d, _ in counter.most_common(5)]
        while len(top_5) < 5:
            top_5.append(str(random.randint(0, 9)))
        combined.append(top_5)
    return combined
    
# ===================== BACKTEST =====================
def run_backtest(draws, strategy='hybrid', recent_n=10):
    if len(draws) < recent_n + 10:
        st.warning("❗ Tidak cukup draw untuk backtest.")
        return

    def match_insight(fp, base):
        return ["✅" if fp[i] in base[i] else "❌" for i in range(4)]

    results = []
    for i in range(recent_n):
        test_draw = draws[-(i+1)]
        base_draws = draws[:-(i+1)]
        if len(base_draws) < 10: continue
        base = generate_base(base_draws, method=strategy, recent_n=recent_n)
        results.append({
            "Tarikh": test_draw['date'],
            "Result 1st": test_draw['number'],
            "Insight": ' '.join(f"P{i+1}:{s}" for i, s in enumerate(match_insight(test_draw['number'], base)))
        })

    df = pd.DataFrame(results[::-1])
    matched = sum("✅" in r["Insight"] for r in results)
    st.success(f"🎉 Jumlah digit match: {matched} daripada {recent_n}")
    st.dataframe(df, use_container_width=True)

def get_like_dislike_digits(draws, top_n=3):
    # Ambil hanya draw ke-30 terbaru
    last_30 = draws[-30:]

    # Ambil hanya 4 digit dari setiap draw
    all_digits = "".join(draw[1] for draw in last_30 if len(draw[1]) == 4)

    # Kira frekuensi
    counter = Counter(all_digits)

    # LIKE = top 3 paling kerap
    like = [item[0] for item in counter.most_common(top_n)]

    # DISLIKE = bottom 3 paling kurang
    dislike = [item[0] for item in sorted(counter.items(), key=lambda x: x[1])[:top_n]]

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
    st.warning("⚠️ Sila klik 'Update Draw Terkini' untuk mula. Proses ambil masa 1-5 minit.")
else:
    st.info(f"📅 Tarikh terakhir: **{draws[-1]['date']}** | 📊 Jumlah draw: **{len(draws)}**")
    tabs = st.tabs(["📌 Insight", "🧠 Ramalan", "🔁 Backtest", "📋 Draw List", "🎡 Wheelpick"])
        
    with tabs[0]:
        st.markdown("### 📌 Insight Terakhir")
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
                (cols[i].success if digit in base[i] else cols[i].error)(
                    f"Pos {i+1}: {'✅' if digit in base[i] else '❌'} `{digit}` {'' if digit in base[i] else 'tiada'} dalam {base[i]}"
                )
            st.markdown("### 📋 Base Digunakan:")
            for i, b in enumerate(base):
                st.text(f"Pos {i+1}: {' '.join(b)}")

    with tabs[1]:
        st.markdown("### 🧠 Ramalan Base")
        strat = st.selectbox("Pilih strategi base untuk ramalan:", ['hybrid', 'frequency', 'gap', 'qaisara'])
        recent_n = st.slider("Jumlah draw terkini digunakan untuk base:", 5, 100, 30, 5)
        base = generate_base(draws, method=strat, recent_n=recent_n)
        for i, p in enumerate(base): st.text(f"Pick {i+1}: {' '.join(p)}")
        preds = []
        while len(preds) < 10:
            pred = ''.join(random.choice(base[i]) for i in range(4))
            if pred not in preds: preds.append(pred)
        st.code('\n'.join(preds), language='text')

    with tabs[2]:
        st.markdown("### 🔁 Backtest Base")
        strat = st.selectbox("Pilih strategi base untuk backtest:", ['hybrid', 'frequency', 'gap', 'qaisara'])
        recent_n = st.slider("Jumlah draw terkini untuk backtest:", 5, 50, 10)
        if st.button("🚀 Jalankan Backtest"):
            run_backtest(draws, strategy=strat, recent_n=recent_n)
            
    with tabs[3]:
        st.dataframe(pd.DataFrame(draws), use_container_width=True)
            
    with tabs[4]:
        st.markdown("### 🎡 Wheelpick Generator")

    # Muat draw
    draws = load_draws()
    if not draws:
        st.warning("⚠️ Sila klik 'Update Draw Terkini' dahulu.")
        st.stop()

    # Auto-saranan LIKE / DISLIKE
    try:
          last_30 = [d for d in draws[-30:] if isinstance(d, tuple) and len(d) == 2 and len(d[1]) == 4 and d[1].isdigit()]
    all_digits = "".join(d[1] for d in last_30)
    digit_counter = Counter(all_digits)
    most_common = digit_counter.most_common()
    like_suggest = [d for d, _ in most_common[:3]]
    dislike_suggest = [d for d, _ in most_common[-3:]]
    st.markdown(f"📈 **Cadangan LIKE digit:** {' '.join(like_suggest)}")
    st.markdown(f"📉 **Cadangan DISLIKE digit:** {' '.join(dislike_suggest)}")
except Exception as e:
    st.warning(f"❌ Ralat semasa jana cadangan: {e}")
    
    # Pilihan Mod Input
    mode = st.radio("Mod Input:", ["Auto (dari Base)", "Manual Input"])
    if mode == "Manual Input":
        manual_base = []
        for i in range(4):
            val = st.text_input(f"Digit Pilihan untuk Pick {i+1} (cth: 1 3 5 7 9):")
            digits = val.strip().split()
            if len(digits) != 5 or not all(d.isdigit() and len(d) == 1 for d in digits):
                st.warning("⚠️ Masukkan 5 digit (0-9) dipisah ruang.")
            manual_base.append(digits if len(digits) == 5 else [str(random.randint(0, 9)) for _ in range(5)])
    else:
        base = load_base_from_file()
        if not base or len(base) != 4:
            st.warning("⚠️ Base tidak sah. Sila klik 'Update Draw' dahulu.")
            st.stop()
        manual_base = base

    # Nilai Lot
    lot = st.text_input("Nilai Lot Setiap Nombor (cth: 0.10):", value="0.10")

    # Filter Asal (apply_filters)
    no_repeat = st.checkbox("❌ Buang Nombor Berulang", value=True)
    no_pair = st.checkbox("❌ Buang Pasangan Sama", value=False)
    no_triple = st.checkbox("❌ Buang Tiga Digit Sama", value=False)
    no_ascend = st.checkbox("❌ Buang Urutan Menaik", value=False)
    use_history = st.checkbox("📜 Guna Sejarah Draw", value=True)
    sim_limit = st.slider("🔁 Had Maksimum Persamaan Dengan Draw Sebelum Ini", 0, 4, 2)

    # Filter Like & Dislike
    like_input = st.text_input("👍 Digit WAJIB ADA (cth: 1 3 5)", value="")
    like_digits = like_input.strip().split() if like_input else []

    dislike_input = st.text_input("👎 Digit WAJIB DIBUANG jika lebih 2 (cth: 6 8 9)", value="")
    dislike_digits = dislike_input.strip().split() if dislike_input else []

    combos = []

    if st.button("🎰 Create Wheelpick"):
        # Jana kombinasi
        for a in manual_base[0]:
            for b in manual_base[1]:
                for c in manual_base[2]:
                    for d in manual_base[3]:
                        combos.append(f"{a}{b}{c}{d}#####${lot}")

        st.info(f"Jumlah asal kombinasi: {len(combos)}")

        # Apply filter asal
        combos = apply_filters(
            combos, draws,
            no_repeat=no_repeat,
            no_triple=no_triple,
            no_pair=no_pair,
            no_ascend=no_ascend,
            use_history=use_history,
            sim_limit=sim_limit
        )

        # Apply like/dislike filter
        def filter_like_dislike(combo):
            num = combo[:4]
            like_count = sum(1 for d in like_digits if d in num)
            dislike_count = sum(1 for d in dislike_digits if d in num)
            if like_digits and like_count == 0:
                return False
            if dislike_digits and dislike_count >= 3:
                return False
            return True

        combos = [c for c in combos if filter_like_dislike(c)]
        total = len(combos)

        st.success(f"✅ {total} nombor akhir selepas ditapis.")

        # Papar dalam 21 bahagian (30 setiap satu)
        part_size = 30
        for i in range(21):
            start = i * part_size
            end = start + part_size
            section = combos[start:end]
            if not section: break
            st.markdown(f"**📦 Bahagian {i+1}** ({len(section)} nombor)")
            st.code('\n'.join(section))

        # Muat Turun
        wheel_text = '\n'.join(combos)
        filename = f"wheelpick_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        st.download_button("💾 Muat Turun Semua Nombor", data=wheel_text, file_name=filename, mime='text/plain')
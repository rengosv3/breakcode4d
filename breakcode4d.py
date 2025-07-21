
import streamlit as st
import os
import re
import requests
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import random

# === Fungsi Utiliti Fail ===
def load_draws(file_path='data/draws.txt'):
    if not os.path.exists(file_path):
        return []
    draws = []
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                draws.append({'date': parts[0], 'number': parts[1]})
    return draws

def save_base_to_file(base_digits, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        for pick in base_digits:
            f.write(' '.join(pick) + '\n')

def load_base_from_file(file_path):
    if not os.path.exists(file_path):
        return []
    base = []
    with open(file_path, 'r') as f:
        for line in f:
            digits = line.strip().split()
            if digits:
                base.append(digits)
    return base

def display_base_as_text(file_path):
    if not os.path.exists(file_path):
        return "⚠️ Tiada fail dijumpai."
    lines = []
    with open(file_path, 'r') as f:
        for i, line in enumerate(f):
            digits = line.strip()
            if digits:
                lines.append(f"Pick {i+1}: {digits}")
    return '\n'.join(lines)

# === Fungsi Update Draw ===
def get_1st_prize(date_str):
    url = f"https://gdlotto.net/results/ajax/_result.aspx?past=1&d={date_str}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if resp.status_code != 200:
            return None
        html = resp.text
        match = re.search(r'id="1stPz">(\d{4})<', html)
        return match.group(1) if match else None
    except:
        return None

def update_draws(file_path='data/draws.txt', max_days_back=30):
    draws = load_draws(file_path)
    if not draws:
        last_date = datetime.today() - timedelta(days=max_days_back)
    else:
        last_date = datetime.strptime(draws[-1]['date'], "%Y-%m-%d")
    today = datetime.today()
    current = last_date + timedelta(days=1)
    added = []
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'a') as f:
        while current <= today:
            date_str = current.strftime("%Y-%m-%d")
            prize = get_1st_prize(date_str)
            if prize:
                f.write(f"{date_str} {prize}\n")
                added.append(prize)
            current += timedelta(days=1)
    return f"✔ {len(added)} draw baru ditambah." if added else "✔ Tiada draw baru ditambah."

# === Fungsi Skor Base ===
def score_digits(draws, recent_n=30):
    weights = [Counter() for _ in range(4)]
    for i, draw in enumerate(draws[-recent_n:]):
        for j, digit in enumerate(draw['number']):
            weights[j][digit] += recent_n - i
    base = []
    for pick in weights:
        base.append([digit for digit, _ in pick.most_common(5)])
    return base

# === Fungsi Insight Nombor Terakhir ===
def get_last_result_insight(draws, base_digits):
    if not draws:
        return "Tiada data draw tersedia."

    today_str = datetime.today().strftime("%Y-%m-%d")
    last_valid = None
    for d in reversed(draws):
        if d['date'] < today_str:
            last_valid = d
            break

    if not last_valid:
        return "Tiada data draw semalam tersedia."

    last_number = last_valid['number']
    last_date = last_valid['date']
    insight_lines = [f"📅 Nombor terakhir naik: **{last_number}** pada {last_date}\n"]

    all_numbers = [d['number'] for d in draws if len(d['number']) == 4]
    digit_counter = [Counter() for _ in range(4)]
    for number in all_numbers:
        for i, digit in enumerate(number):
            digit_counter[i][digit] += 1

    cross_data = [defaultdict(int) for _ in range(4)]
    for number in all_numbers:
        for i, digit in enumerate(number):
            cross_data[i][digit] += 1
    cross_top = [[d for d, _ in sorted(c.items(), key=lambda x: -x[1])[:5]] for c in cross_data]

    insight_lines.append("Base (Semalam):")
    for i, pick in enumerate(base_digits):
        insight_lines.append(f"Pick {i+1}: {' '.join(pick)}")
    insight_lines.append("")

    for i, digit in enumerate(last_number):
        freq = digit_counter[i][digit]
        rank = sorted(digit_counter[i].values(), reverse=True).index(freq) + 1
        in_base = "✅" if digit in base_digits[i] else "❌"
        in_cross = "✅" if digit in cross_top[i] else "❌"
        score = 0
        if rank <= 3: score += 2
        elif rank <= 5: score += 1
        if in_base == "✅": score += 2
        if in_cross == "✅": score += 1
        label = "🔥 Sangat berpotensi" if score >= 4 else "👍 Berpotensi" if score >= 3 else "❓ Kurang pasti"
        insight_lines.append(f"Pick {i+1}: Digit '{digit}' - Ranking #{rank}, Base: {in_base}, Cross: {in_cross} → **{label}**")

    insight_lines.append("\n💡 AI Insight:")
    insight_lines.append("- Digit dalam Base & Cross sangat konsisten untuk muncul.")
    insight_lines.append("- Ranking tinggi memberi petunjuk kekuatan digit.")

    return '\n'.join(insight_lines)

# === Fungsi Ramalan AI ===
def generate_predictions(base_digits, n=10):
    all_combinations = set()
    while len(all_combinations) < n:
        combo = ''.join(random.choice(base_digits[i]) for i in range(4))
        all_combinations.add(combo)
    return sorted(list(all_combinations))

# === Fungsi Perbandingan Base ===
def compare_bases(base_a, base_b, base_c):
    result = []
    for i in range(4):
        pick_a = set(base_a[i])
        pick_b = set(base_b[i])
        pick_c = set(base_c[i])
        common = pick_a & pick_b & pick_c
        line = f"Pick {i+1}: "
        for d in sorted(pick_a | pick_b | pick_c):
            if d in common:
                line += f"**{d}** "
            else:
                line += f"{d} "
        result.append(line.strip())
    return '\n'.join(result)

# === UI Streamlit ===
st.set_page_config(page_title="Breakcode4D", layout="centered")
st.title("🔮 Breakcode4D — Profesional AI 4D Analyzer")

if st.button("📥 Update Draw Terkini"):
    msg = update_draws()
    st.success(msg)

    draws_now = load_draws()
    base_today = score_digits(draws_now)
    save_base_to_file(base_today, "data/base.txt")

    st.markdown("### 📊 Base Hari Ini (Disimpan sebagai base.txt)")
    st.code(display_base_as_text("data/base.txt"))

draws = load_draws()
if draws:
    st.subheader("🧠 AI Insight Nombor Terakhir")

    base_last_path = 'data/base_last.txt'
    if not os.path.exists(base_last_path):
        base_auto = score_digits(draws[:-1])
        save_base_to_file(base_auto, base_last_path)
        base_last = base_auto
    else:
        base_last = load_base_from_file(base_last_path)

    st.text(get_last_result_insight(draws, base_last))

    st.subheader("📊 Perbandingan Base")
    base_txt = load_base_from_file("data/base.txt")
    base_super = load_base_from_file("data/base_super.txt")
    st.code(compare_bases(base_txt, base_last, base_super))

    st.subheader("🎯 Ramalan AI Berdasarkan Base Semalam")
    predictions = generate_predictions(base_last, n=10)
    col1, col2 = st.columns(2)
    for i in range(5):
        col1.text(predictions[i])
        col2.text(predictions[i+5])
else:
    st.warning("⚠️ Tiada data draw. Klik butang di atas dahulu.")
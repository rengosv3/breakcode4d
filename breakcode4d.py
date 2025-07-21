# === [Imports dan Fungsi Asal Tidak Diubah] ===
# Letakkan semua fungsi dari kod asal yang kau dah beri di atas, tak berubah
# Daripada: import streamlit as st ... hingga ke show_digit_heatmap(draws)

# ======================================================
# UI Streamlit (Disusun Semula Dalam Tab Layout)
# ======================================================
st.set_page_config(page_title="Breakcode4D Visual", layout="centered")
st.title("🔮 Breakcode4D Predictor")

# --- Butang Update & Register (Sebaris) ---
col_u, col_r = st.columns([1, 1])
with col_u:
    if st.button("📥 Update Draw Terkini"):
        msg = update_draws()
        st.success(msg)
        st.markdown("### 📋 Base Hari Ini (Salin & Tampal)")
        st.code(display_base_as_text('data/base.txt'), language='text')

with col_r:
    st.markdown(
        """
        <a href="https://batman11.net/RegisterByReferral.aspx?MemberCode=BB1845" target="_blank">
            <button style="width:100%;padding:8px;background-color:#4CAF50;color:white;border:none;border-radius:5px;">🔗 Register Sini</button>
        </a>
        """,
        unsafe_allow_html=True
    )

draws = load_draws()

if draws:
    st.info(f"📅 Tarikh terakhir: **{draws[-1]['date']}** | 📊 Jumlah draw: **{len(draws)}**")

    # === Tabs UI Layout ===
    tabs = st.tabs(["📌 Insight", "🧠 Ramalan", "🔁 Cross", "🚀 Super Base", "🧪 AI Tuner", "📈 Visual"])

    with tabs[0]:  # Insight
        st.subheader("📌 Insight Nombor Terakhir")
        st.markdown(get_last_result_insight(draws))

    with tabs[1]:  # Ramalan
        st.subheader("🧠 Ramalan Berdasarkan Super/Base")
        base_digits = load_base_from_file('data/base_super.txt') if os.path.exists('data/base_super.txt') else load_base_from_file('data/base.txt')
        preds = generate_predictions(base_digits)
        for i, pick in enumerate(base_digits):
            st.write(f"Pick {i+1}: {' '.join(pick)}")

        st.markdown("📊 10 Ramalan Terpilih:")
        col1, col2 = st.columns(2)
        for i in range(5):
            col1.text(preds[i])
            col2.text(preds[i+5])

    with tabs[2]:  # Cross Pick
        if st.button("🔁 Cross Pick Analysis"):
            st.text(cross_pick_analysis(draws))

    with tabs[3]:  # Super Base
        if st.button("🚀 Jana Super Base (30,60,120)"):
            super_base = generate_super_base(draws)
            save_base_to_file(super_base, 'data/base_super.txt')
            st.success("Super Base disimpan ke 'base_super.txt'")
            st.markdown("### 📋 Super Base (Salin & Tampal)")
            st.code(display_base_as_text('data/base_super.txt'), language='text')

    with tabs[4]:  # AI Tuner
        if st.button("🧪 Tuner AI (Auto Filter)"):
            tuned = ai_tuner(draws)
            for i, pick in enumerate(tuned):
                st.write(f"Tuned Pick {i+1}: {' '.join(pick)}")

    with tabs[5]:  # Visualisasi
        st.subheader("📈 Visualisasi Analisis")
        show_digit_distribution(draws)
        show_digit_heatmap(draws)

else:
    st.warning("⚠️ Sila klik '📥 Update Draw Terkini' untuk mula.")
# backtest_app.py

import streamlit as st
import pandas as pd
from modules.base_analysis import load_draws, load_base_from_file
from modules.ai_prediction import generate_predictions

def run_backtest(draws, base_path='data/base.txt', num_days=10):
    if len(draws) < num_days:
        st.warning("❗ Tidak cukup draw untuk backtest.")
        return

    results = []
    st.markdown("### 🔁 Backtest 10 Hari Terakhir")

    for i in range(num_days):
        draw = draws[-(i+1)]
        draw_date, first_prize = draw[0], draw[1]

        base = load_base_from_file(base_path)
        if not base:
            st.error(f"❗ Base tidak dijumpai atau kosong di: `{base_path}`")
            return

        predictions = generate_predictions(base, n=4)
        insight = ["✅" if p == first_prize else "❌" for p in predictions]

        results.append({
            "Tarikh": draw_date,
            "Result 1st": first_prize,
            "P1": predictions[0],
            "P2": predictions[1],
            "P3": predictions[2],
            "P4": predictions[3],
            "Insight": f"P1:{insight[0]} P2:{insight[1]} P3:{insight[2]} P4:{insight[3]}"
        })

        st.markdown(f"""
        ### 🎯 Tarikh: {draw_date}
        **Result 1st**: `{first_prize}`  
        **Base (sebelum {draw_date}):**
        """)
        for j, b in enumerate(base):
            st.text(f"P{j+1}: {' '.join(str(d) for d in b)}")
        st.markdown(f"**Insight:** `{results[-1]['Insight']}`")
        st.markdown("---")

    df = pd.DataFrame(results[::-1])

    success_count = sum(1 for r in results if "✅" in r["Insight"])
    st.success(f"🎉 Jumlah menang tepat: {success_count} daripada {num_days}")

    st.markdown("### 📊 Ringkasan Backtest:")
    st.dataframe(df, use_container_width=True)

# Jalankan jika standalone atau multipage
if __name__ == "__main__" or st._is_running_with_streamlit:
    draws = load_draws()
    if not draws:
        st.warning("❗ Tiada data draw dijumpai.")
    else:
        run_backtest(draws)
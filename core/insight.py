# core/insight.py

from collections import Counter

def ai_insight_explainer(result_number, base_digits, cross_pick_data, recent_draws):
    """
    Terangkan kenapa dan bagaimana nombor result terkini boleh naik.
    
    Params:
        result_number: str - contoh '1066'
        base_digits: dict - base digit per pick (contoh {'Pick1': [...], 'Pick2': [...]})
        cross_pick_data: dict - digit kerap dalam pick silang
        recent_draws: list[str] - 20-30 draw terkini (format: ['1234', '5689', ...])
    
    Return:
        dict dengan penjelasan setiap digit dan struktur keseluruhan.
    """
    explanation = {
        'number': result_number,
        'digits': [],
        'structure': '',
        'summary': ''
    }

    # Ulasan setiap digit
    for i, digit in enumerate(result_number):
        digit_info = {
            'digit': digit,
            'pick': f'Pick {i+1}',
            'in_base': digit in base_digits.get(f'Pick {i+1}', []),
            'in_cross': digit in [d for d, _ in cross_pick_data.get(f'Pick {i+1}', [])],
            'recent_hits': sum(1 for draw in recent_draws if digit in draw),
        }
        explanation['digits'].append(digit_info)

    # Struktur kombinasi
    even_count = sum(1 for d in result_number if int(d) % 2 == 0)
    odd_count = 4 - even_count
    repeat_digits = [item for item, count in Counter(result_number).items() if count > 1]

    explanation['structure'] = f"{odd_count} Ganjil / {even_count} Genap. " + \
        ("Ada ulangan digit: " + ", ".join(repeat_digits) if repeat_digits else "Tiada ulangan digit.")

    # Rumusan akhir
    reasons = []
    for info in explanation['digits']:
        reason = f"• {info['digit']} dalam {info['pick']}: "
        if info['in_base']:
            reason += "✅ Ada dalam base. "
        if info['in_cross']:
            reason += "🔥 Muncul dalam cross-pick. "
        if info['recent_hits'] >= 3:
            reason += f"📈 Muncul {info['recent_hits']} kali dalam 30 draw terakhir."
        reasons.append(reason)

    explanation['summary'] = "\n".join(reasons)
    return explanation

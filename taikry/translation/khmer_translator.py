"""
Natural Khmer Translation Engine for TAIKRY AI MARKET INTELLIGENCE PRO
Produces high-fidelity, institutional Cambodian financial market translations.
Preserves all prices, numbers, risk-reward ratios, and timestamps exactly.
"""
from typing import Dict, Any

BIAS_KHMER_MAP = {
    "STRONG BULLISH": "ទំនោរឡើងខ្លាំង (STRONG BULLISH)",
    "BULLISH": "ទំនោរឡើង (BULLISH)",
    "NEUTRAL": "អព្យាក្រឹត / គ្មានទិសដៅច្បាស់ (NEUTRAL)",
    "BEARISH": "ទំនោរចុះ (BEARISH)",
    "STRONG BEARISH": "ទំនោរចុះខ្លាំង (STRONG BEARISH)",
    "WAIT FOR CONFIRMATION": "រង់ចាំការបញ្ជាក់សញ្ញា (WAIT FOR CONFIRMATION)",
    "NO TRADE": "គ្មានការជួញដូរ (NO TRADE)"
}

STATUS_KHMER_MAP = {
    "APPROVED": "បានអនុម័ត (APPROVED)",
    "REJECTED": "បដិសេធ (REJECTED)",
    "WAIT": "រង់ចាំ (WAIT)",
    "NO TRADE": "គ្មានការជួញដូរ (NO TRADE)"
}

DECISION_KHMER_MAP = {
    "LONG": "ទំនោរទិញ (BUY BIAS)",
    "SHORT": "ទំនោរលក់ (SELL BIAS)",
    "NONE": "គ្មានការជួញដូរ (NO TRADE)",
    "FLAT": "អព្យាក្រឹត (FLAT)"
}

def translate_to_khmer(report_data: Dict[str, Any]) -> str:
    """
    Constructs a professional, natural Khmer market intelligence report.
    """
    symbol = report_data.get("symbol", "XAUUSD")
    verified_price = report_data.get("verified_price", 0.0)
    price_source = report_data.get("price_source", "Multi-Provider")
    time_utc = report_data.get("timestamp_utc", "")
    time_kh = report_data.get("timestamp_cambodia", "")
    bias = report_data.get("market_bias", "NEUTRAL")
    bias_khmer = BIAS_KHMER_MAP.get(bias, bias)

    setup_status = report_data.get("setup_status", "NO TRADE")
    status_khmer = STATUS_KHMER_MAP.get(setup_status, setup_status)

    entry = report_data.get("entry_price")
    sl = report_data.get("stop_loss")
    tp1 = report_data.get("take_profit_1")
    tp2 = report_data.get("take_profit_2")
    rr = report_data.get("risk_reward_ratio", "N/A")
    invalidation = report_data.get("invalidation_rules", "N/A")

    # Final decision tag
    proposed_dir = report_data.get("proposed_direction", "NONE")
    decision_khmer = DECISION_KHMER_MAP.get(proposed_dir, proposed_dir)

    # Agents findings
    a1_findings = report_data.get("agent_1_summary", "គ្មានទិន្នន័យ")
    a2_findings = report_data.get("agent_2_summary", "គ្មានទិន្នន័យ")
    a3_findings = report_data.get("agent_3_summary", "គ្មានទិន្នន័យ")
    a4_findings = report_data.get("agent_4_summary", "គ្មានទិន្នន័យ")

    # Smart Analysis Causes
    smart = report_data.get("smart_analysis", {})
    synthesis_kh = smart.get("synthesis_summary_kh") or "ការវិភាគស្រុះស្រួលគ្នារវាងគ្រប់ភ្នាក់ងារ AI ទាំងអស់។"
    tech_causes = "\n".join([f"  • {c}" for c in smart.get("technical_causes", [])[:3]]) if smart.get("technical_causes") else a1_findings
    smc_causes = "\n".join([f"  • {c}" for c in smart.get("smc_causes", [])[:3]]) if smart.get("smc_causes") else a2_findings
    macro_causes = "\n".join([f"  • {c}" for c in smart.get("macro_causes", [])[:3]]) if smart.get("macro_causes") else a3_findings
    risk_causes = "\n".join([f"  • {c}" for c in smart.get("risk_causes", [])[:3]]) if smart.get("risk_causes") else a4_findings

    khmer_report = f"""📊 <b>TAIKRY AI MARKET INTELLIGENCE PRO (របាយការណ៍ទីផ្សារ)</b>

⏱ <b>ពេលវេលា:</b> {time_utc} (UTC) | {time_kh} (ម៉ោងនៅកម្ពុជា)
🪙 <b>គូរូបិយវត្ថុ/ទ្រព្យសកម្ម:</b> {symbol}
💵 <b>តម្លៃផ្ទៀងផ្ទាត់ជាក់ស្តែង:</b> <code>{verified_price}</code> (ប្រភព: {price_source})
📈 <b>ទំនោរទិសដៅទីផ្សារ:</b> {bias_khmer}
🚦 <b>ស្ថានភាពរៀបចំការជួញដូរ:</b> {status_khmer}

━━━━━━━━━━━━━━━━━━━━
🔭 <b>ការវិភាគក្របខ័ណ្ឌពេលវេលាធំ (D1 / H4 / H1):</b>
{report_data.get('htf_analysis_khmer', 'រចនាសម្ព័ន្ធទីផ្សារស្ថិតក្នុងទំនោរតាមក្របខ័ណ្ឌពេលវេលាខ្ពស់។')}

⚡ <b>ការវិភាគរៀបចំចំណុចចូល (M15 / M5):</b>
{report_data.get('ltf_analysis_khmer', 'ចំណុចប្រតិបត្តិការត្រូវបានត្រួតពិនិត្យលើក្របខ័ណ្ឌពេលវេលាប្រតិបត្តិ។')}

━━━━━━━━━━━━━━━━━━━━
🧠 <b>ការវិភាគមូលហេតុឆ្លាតវៃពីគ្រប់ AI AGENTS (SMART CAUSE ANALYSIS)</b>

💡 <b>ការសង្ខេបមូលហេតុរួមឆ្លាតវៃ:</b>
<i>{synthesis_kh}</i>

🤖 <b>ភ្នាក់ងារទី ១ — មូលហេតុបច្ចេកទេស (Technical Causes):</b>
{tech_causes}

🏛 <b>ភ្នាក់ងារទី ២ — មូលហេតុរចនាសម្ព័ន្ធស្ថាប័ន SMC (Institutional SMC Causes):</b>
{smc_causes}

🌐 <b>ភ្នាក់ងារទី ៣ — មូលហេតុម៉ាក្រូសេដ្ឋកិច្ច (Macro Causes):</b>
{macro_causes}

🛡 <b>ភ្នាក់ងារទី ៤ — មូលហេតុគ្រប់គ្រងហានិភ័យ (Risk & Safety Causes):</b>
{risk_causes}

━━━━━━━━━━━━━━━━━━━━
🎯 <b>ចំណុចប្រតិបត្តិការជួញដូរ (BUY / SELL ENTRY & SL / TP):</b>
• កម្រិតតម្លៃចូល (Entry): <code>{entry if entry else 'ពុំទាន់មាន (N/A)'}</code>
• កម្រិតកាត់ខាត (Stop Loss): <code>{sl if sl else 'ពុំទាន់មាន (N/A)'}</code>
• កម្រិតយកប្រាក់ចំណេញទី ១ (TP 1): <code>{tp1 if tp1 else 'ពុំទាន់មាន (N/A)'}</code>
• កម្រិតយកប្រាក់ចំណេញទី ២ (TP 2): <code>{tp2 if tp2 else 'ពុំទាន់មាន (N/A)'}</code>
• អនុបាតហានិភ័យធៀបផលចំណេញ: <b>{rr}</b>

⚠️ <b>លក្ខខណ្ឌលុបចោលសុពលភាព (Invalidation):</b>
<i>{invalidation}</i>

🏁 <b>សេចក្តីសម្រេចចុងក្រោយ:</b> <b>{decision_khmer}</b>
"""
    return khmer_report.strip()

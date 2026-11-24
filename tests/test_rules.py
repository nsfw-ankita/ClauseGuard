import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rules import calculate_score, check_rules, merge_missing_clauses


def make_analysis(clauses, missing=None, suggested=None):
    clause_objs = [SimpleNamespace(**c) for c in clauses]
    return SimpleNamespace(
        document_type_ok=True,
        clauses=clause_objs,
        missing_clauses=missing or [],
        suggested_changes=suggested or [],
    )


def test_check_rules_detects_english_keywords():
    text = """
    Security deposit is Rs 50000. Deposit will be refunded within 30 days after vacating.
    Notice period is 2 months. Lock-in period is 6 months. Rent increase 5% every year.
    Tenant pays maintenance for minor repairs. Either party may terminate with notice for eviction.
    Police verification required. Electricity and water bill paid by tenant. Landlord may inspect with 24 hours notice.
    """
    checks = check_rules(text)
    by_key = {c.key: c for c in checks}
    assert by_key["security_deposit"].present is True
    assert by_key["deposit_refund"].present is True
    assert by_key["notice_period"].present is True
    assert by_key["lock_in"].present is True
    assert by_key["rent_increase"].present is True
    assert by_key["maintenance"].present is True
    assert by_key["eviction"].present is True
    assert by_key["police_verification"].present is True
    assert by_key["utilities"].present is True
    assert by_key["inspection"].present is True


def test_check_rules_detects_hindi_keywords():
    text = """
    सुरक्षा जमा 20000 रुपये है। जमा 15 दिन में वापस होगा। नोटिस अवधि 1 महीना है।
    लॉक-इन अवधि 6 महीने। किराया वृद्धि हर साल 5% होगी। रखरखाव किरायेदार करेगा।
    बेदखली के लिए 30 दिन नोटिस। पुलिस सत्यापन जरूरी है। बिजली और पानी बिल किरायेदार देगा।
    मकान मालिक 24 घंटे नोटिस देकर निरीक्षण कर सकता है।
    """
    checks = check_rules(text)
    assert all(c.present for c in checks)


def test_check_rules_missing_items():
    text = "Rent is 10000 per month. Tenant will pay on first day."
    checks = check_rules(text)
    missing = [c.key for c in checks if not c.present]
    assert "security_deposit" in missing
    assert "notice_period" in missing
    assert "police_verification" in missing


def test_merge_missing_clauses_no_duplicates():
    checks = check_rules("Rent is 10000 per month.")
    ai_missing = ["Security deposit amount", "Notice period"]
    merged = merge_missing_clauses(ai_missing, checks, "English")
    lowered = [m.lower() for m in merged]
    assert sum("security deposit" in m for m in lowered) == 1
    assert sum("notice period" in m for m in lowered) == 1


def test_calculate_score_safe():
    analysis = make_analysis(
        [
            {"clause_text": "Rent is clear", "color": "green", "explanation": "Clear."},
            {"clause_text": "Deposit clear", "color": "green", "explanation": "Clear."},
        ]
    )
    checks = check_rules(
        "Security deposit 10000 refund within 30 days notice period 1 month lock-in 6 months rent increase 5% "
        "maintenance by landlord eviction with notice police verification electricity water bill inspection with 24 hour notice"
    )
    result = calculate_score(analysis, checks)
    assert result["score"] == 10.0
    assert result["label_en"] == "Looks safe"
    assert result["color"] == "green"


def test_calculate_score_risky():
    analysis = make_analysis(
        [
            {"clause_text": "Bad", "color": "red", "explanation": "Bad."},
            {"clause_text": "Bad2", "color": "red", "explanation": "Bad."},
            {"clause_text": "Bad3", "color": "red", "explanation": "Bad."},
            {"clause_text": "Warn", "color": "yellow", "explanation": "Warn."},
        ]
    )
    checks = check_rules("Rent is 10000 per month.")
    result = calculate_score(analysis, checks)
    assert result["score"] < 5.0
    assert result["label_en"] == "Risky"
    assert result["color"] == "red"


def test_calculate_score_minimum_zero():
    analysis = make_analysis(
        [{"clause_text": f"R{i}", "color": "red", "explanation": "Bad."} for i in range(20)]
    )
    checks = check_rules("")
    result = calculate_score(analysis, checks)
    assert result["score"] == 0.0

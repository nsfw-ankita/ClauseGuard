import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from report import build_report_pdf
from rules import check_rules


def make_analysis():
    return SimpleNamespace(
        document_type_ok=True,
        clauses=[
            SimpleNamespace(clause_text="Late fee is high", color="red", explanation="Risky."),
            SimpleNamespace(clause_text="Rent increase unclear", color="yellow", explanation="Check."),
            SimpleNamespace(clause_text="Deposit is clear", color="green", explanation="Good."),
        ],
        missing_clauses=["Police verification"],
        suggested_changes=[
            SimpleNamespace(issue="Late fee", polite_request_message="Please reduce the late fee.")
        ],
    )


def test_build_report_pdf_returns_bytes():
    analysis = make_analysis()
    checks = check_rules("Security deposit 10000 notice period 1 month")
    pdf = build_report_pdf(
        analysis=analysis,
        rule_checks=checks,
        missing_clauses=["Police verification"],
        score={"score": 6.5, "label_en": "Be careful", "label_hi": "सावधान रहें", "color": "yellow"},
        language="English",
    )
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000

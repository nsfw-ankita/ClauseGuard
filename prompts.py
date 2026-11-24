"""Prompt templates for Gemini analysis."""

import json


SYSTEM_INSTRUCTIONS = """You are RentRakshak, a careful assistant that helps non-technical people understand rent agreements.
You are NOT a lawyer. You give general guidance only.
Always be clear, calm, and simple.
"""


def build_analysis_prompt(text: str, language: str) -> str:
    lang_name = "Hindi" if language == "Hindi" else "English"
    schema_hint = {
        "document_type_ok": True,
        "clauses": [
            {
                "clause_text": "short clause or summary",
                "color": "red|yellow|green",
                "explanation": "plain words, max 25 words",
            }
        ],
        "missing_clauses": ["missing item"],
        "suggested_changes": [
            {
                "issue": "what is wrong",
                "polite_request_message": "polite message to landlord",
            }
        ],
    }
    return f"""
Analyze the following rent agreement text/image content.

Return ONLY valid JSON. No markdown, no extra text.
Use this exact shape:
{json.dumps(schema_hint, ensure_ascii=False)}

Rules:
- document_type_ok: true only if this is a rent agreement/lease/rental agreement; otherwise false.
- If document_type_ok is false, return empty arrays for clauses, missing_clauses, suggested_changes.
- clauses: include important clauses you find. color meanings: red = risky/unfair, yellow = needs attention/unclear, green = looks fine.
- explanation: very simple words, maximum 25 words.
- missing_clauses: important things not found.
- suggested_changes: for red/yellow issues, give a polite request message the tenant can send.
- All user-facing text values (clause_text, explanation, missing_clauses, issue, polite_request_message) must be in {lang_name}.
- Keep language simple enough for a 12-year-old or grandparent.

Agreement content:
\"\"\"
{text}
\"\"\"
""".strip()

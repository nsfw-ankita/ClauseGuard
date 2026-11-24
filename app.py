"""ClauseGuard - AI rent agreement red-flag detector."""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from analyzer import AnalyzerError, analyze_agreement, extract_pdf_text, is_mock_mode
from report import DISCLAIMER, PRIVACY_NOTE, build_report_pdf
from rules import calculate_score, check_rules, merge_missing_clauses

load_dotenv()

st.set_page_config(page_title="ClauseGuard", page_icon="🛡️", layout="wide")

LANG_COPY = {
    "English": {
        "tagline": "Sign smart, not blind.",
        "language": "Language",
        "upload_pdf": "Upload PDF",
        "upload_photo": "Upload photo",
        "paste_text": "Paste text",
        "check": "Check my agreement",
        "checking": "Checking your agreement...",
        "privacy": "Privacy: your agreement is checked in memory and not saved by this app.",
        "disclaimer": DISCLAIMER,
        "no_input": "Please upload a PDF, upload a photo, or paste text first.",
        "not_rent": "This does not look like a rent agreement. Please upload a rent agreement.",
        "score": "Agreement Score",
        "red": "Red flags",
        "yellow": "Check this",
        "green": "Looks fine",
        "missing": "Missing things",
        "ask": "What to ask the landlord to change",
        "no_red": "No major red flags found.",
        "no_yellow": "No warning items found.",
        "no_green": "No green items found.",
        "no_missing": "No important missing things found.",
        "no_changes": "No changes suggested.",
        "download": "Download report",
        "copy_hint": "You can copy this message:",
        "mock": "Demo mode is ON (MOCK_AI=true). No API key needed.",
        "api_missing": "API key not found. Add GEMINI_API_KEY in .env or set MOCK_AI=true for demo mode.",
    },
    "Hindi": {
        "tagline": "समझदारी से साइन करें।",
        "language": "भाषा",
        "upload_pdf": "PDF अपलोड करें",
        "upload_photo": "फोटो अपलोड करें",
        "paste_text": "टेक्स्ट चिपकाएं",
        "check": "मेरा समझौता जांचें",
        "checking": "आपका समझौता जांचा जा रहा है...",
        "privacy": "गोपनीयता: आपका समझौता सिर्फ अभी जांचने के लिए उपयोग होता है, इसे सेव नहीं किया जाता।",
        "disclaimer": "यह केवल सामान्य जानकारी है, कानूनी सलाह नहीं।",
        "no_input": "कृपया पहले PDF, फोटो या टेक्स्ट डालें।",
        "not_rent": "यह किराये का समझौता नहीं लग रहा है। कृपया किराये का समझौता डालें।",
        "score": "समझौता स्कोर",
        "red": "लाल झंडे",
        "yellow": "ध्यान दें",
        "green": "ठीक लग रहा है",
        "missing": "गायब बातें",
        "ask": "मकान मालिक से क्या बदलने को कहें",
        "no_red": "कोई बड़ा लाल झंडा नहीं मिला।",
        "no_yellow": "कोई चेतावनी नहीं मिली।",
        "no_green": "कोई हरी बात नहीं मिली।",
        "no_missing": "कोई जरूरी बात गायब नहीं मिली।",
        "no_changes": "कोई बदलाव सुझाव नहीं।",
        "download": "रिपोर्ट डाउनलोड करें",
        "copy_hint": "आप यह संदेश कॉपी कर सकते हैं:",
        "mock": "डेमो मोड चालू है (MOCK_AI=true)। API key की जरूरत नहीं।",
        "api_missing": "API key नहीं मिली। .env में GEMINI_API_KEY डालें या डेमो के लिए MOCK_AI=true करें।",
    },
}


def t(language: str, key: str) -> str:
    return LANG_COPY.get(language, LANG_COPY["English"])[key]


def inject_css() -> None:
    st.markdown(
        """
        <style>
        html, body, [class*="css"]  { font-size: 18px; }
        .stButton>button { width: 100%; font-size: 1.2rem; padding: 0.8rem 1rem; border-radius: 12px; }
        .score-card { padding: 1.2rem; border-radius: 16px; color: #111; margin-bottom: 1rem; }
        .score-green { background: #d4f4dd; border: 2px solid #2e7d32; }
        .score-yellow { background: #fff3cd; border: 2px solid #b28704; }
        .score-red { background: #fde2e1; border: 2px solid #c62828; }
        .flag-card { padding: 0.9rem; border-radius: 12px; margin-bottom: 0.6rem; }
        .flag-red { background: #fff5f5; border-left: 8px solid #d32f2f; }
        .flag-yellow { background: #fffaf0; border-left: 8px solid #ed6c02; }
        .flag-green { background: #f4fff6; border-left: 8px solid #2e7d32; }
        .small-note { font-size: 0.95rem; color: #444; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    st.session_state.setdefault("result", None)
    st.session_state.setdefault("error", None)
    st.session_state.setdefault("report", None)


def render_score(score: dict, language: str) -> None:
    color = score["color"]
    label = score["label_hi"] if language == "Hindi" else score["label_en"]
    st.markdown(
        f"""
        <div class="score-card score-{color}">
            <div style="font-size:1.1rem;">{t(language, 'score')}</div>
            <div style="font-size:3rem; font-weight:700; line-height:1.1;">{score['score']}/10</div>
            <div style="font-size:1.4rem; font-weight:600;">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_clauses(clauses: list, color: str, language: str, empty_key: str) -> None:
    items = [c for c in clauses if c.color == color]
    if not items:
        st.info(t(language, empty_key))
        return
    for c in items:
        st.markdown(
            f"""<div class="flag-card flag-{color}"><b>{c.clause_text}</b><br><span class="small-note">{c.explanation}</span></div>""",
            unsafe_allow_html=True,
        )


def get_agreement_text_from_pdf(pdf_file) -> str | None:
    try:
        return extract_pdf_text(pdf_file.getvalue())
    except Exception:
        return None


def run_analysis(language: str, input_mode: str, pdf_file, image_file, pasted_text: str) -> None:
    st.session_state.error = None
    st.session_state.result = None
    st.session_state.report = None

    kwargs = {"language": language}
    if input_mode == "pdf":
        if pdf_file is None:
            st.session_state.error = t(language, "no_input")
            return
        kwargs["pdf_bytes"] = pdf_file.getvalue()
    elif input_mode == "image":
        if image_file is None:
            st.session_state.error = t(language, "no_input")
            return
        mime = image_file.type or "image/jpeg"
        kwargs["image_bytes"] = image_file.getvalue()
        kwargs["image_mime"] = mime
    else:
        if not pasted_text.strip():
            st.session_state.error = t(language, "no_input")
            return
        kwargs["text"] = pasted_text

    try:
        analysis = analyze_agreement(**kwargs)
    except AnalyzerError as exc:
        st.session_state.error = str(exc)
        return
    except Exception:
        st.session_state.error = "Something went wrong. Please try again." if language == "English" else "कुछ गलत हुआ। कृपया फिर कोशिश करें।"
        return

    if not analysis.document_type_ok:
        st.session_state.error = t(language, "not_rent")
        return

    # For rule checks, prefer extracted/pasted text; for image-only/scanned, use clause text as fallback.
    rule_text = ""
    if input_mode == "pdf" and pdf_file is not None:
        rule_text = get_agreement_text_from_pdf(pdf_file) or ""
    elif input_mode == "text":
        rule_text = pasted_text
    if not rule_text.strip():
        rule_text = "\n".join([c.clause_text for c in analysis.clauses] + analysis.missing_clauses)

    rule_checks = check_rules(rule_text)
    missing = merge_missing_clauses(analysis.missing_clauses, rule_checks, language)
    score = calculate_score(analysis, rule_checks)
    report = build_report_pdf(
        analysis=analysis,
        rule_checks=rule_checks,
        missing_clauses=missing,
        score=score,
        language=language,
    )
    st.session_state.result = {
        "analysis": analysis,
        "rule_checks": rule_checks,
        "missing": missing,
        "score": score,
    }
    st.session_state.report = report


def main() -> None:
    init_state()
    inject_css()

    st.title("ClauseGuard 🛡️")
    language = st.radio(
        "Language / भाषा",
        ["Hindi", "English"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.markdown(f"### {t(language, 'tagline')}")
    st.caption(t(language, "privacy"))
    st.warning(t(language, "disclaimer"))

    if is_mock_mode():
        st.info(t(language, "mock"))
    elif not os.getenv("GEMINI_API_KEY", "").strip():
        st.info(t(language, "api_missing"))

    tab_pdf, tab_photo, tab_text = st.tabs([t(language, "upload_pdf"), t(language, "upload_photo"), t(language, "paste_text")])
    with tab_pdf:
        pdf_file = st.file_uploader("PDF", type=["pdf"], key="pdf_uploader", label_visibility="collapsed")
    with tab_photo:
        image_file = st.file_uploader("Photo", type=["jpg", "jpeg", "png"], key="img_uploader", label_visibility="collapsed")
    with tab_text:
        pasted_text = st.text_area("Text", height=220, key="pasted_text", label_visibility="collapsed", placeholder="Paste agreement text here / समझौता टेक्स्ट यहाँ चिपकाएं")

    active = st.session_state.get("_active_tab", "pdf")
    # Determine input by which widget has content; prioritize last non-empty in simple order.
    input_mode = "text"
    if pasted_text and pasted_text.strip():
        input_mode = "text"
    if image_file is not None:
        input_mode = "image"
    if pdf_file is not None:
        input_mode = "pdf"
    # Better: use radio-like selection? Keep simple: prefer the tab with content, but user can have multiple; we pick most recent by checking session changes is complex.
    # Use explicit selector for clarity.
    input_mode = st.radio(
        "Input",
        ["pdf", "image", "text"],
        format_func=lambda x: {"pdf": t(language, "upload_pdf"), "image": t(language, "upload_photo"), "text": t(language, "paste_text")}[x],
        horizontal=True,
        index=["pdf", "image", "text"].index(input_mode),
        label_visibility="collapsed",
    )

    if st.button(t(language, "check"), type="primary"):
        with st.spinner(t(language, "checking")):
            run_analysis(language, input_mode, pdf_file, image_file, pasted_text)

    if st.session_state.error:
        st.error(st.session_state.error)

    result = st.session_state.result
    if not result:
        return

    analysis = result["analysis"]
    score = result["score"]
    missing = result["missing"]

    render_score(score, language)

    st.subheader(t(language, "red"))
    render_clauses(analysis.clauses, "red", language, "no_red")

    st.subheader(t(language, "yellow"))
    render_clauses(analysis.clauses, "yellow", language, "no_yellow")

    with st.expander(t(language, "green")):
        render_clauses(analysis.clauses, "green", language, "no_green")

    st.subheader(t(language, "missing"))
    if missing:
        for item in missing:
            st.markdown(f"- {item}")
    else:
        st.info(t(language, "no_missing"))

    st.subheader(t(language, "ask"))
    if analysis.suggested_changes:
        st.caption(t(language, "copy_hint"))
        for change in analysis.suggested_changes:
            st.markdown(f"**{change.issue}**")
            st.code(change.polite_request_message, language=None)
    else:
        st.info(t(language, "no_changes"))

    if st.session_state.report:
        st.download_button(
            t(language, "download"),
            data=st.session_state.report,
            file_name="clauseguard-report.pdf",
            mime="application/pdf",
        )


if __name__ == "__main__":
    main()

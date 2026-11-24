"""ClauseGuard - AI rent agreement red-flag detector."""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from analyzer import AnalyzerError, analyze_agreement, extract_pdf_text, get_model_name, is_mock_mode
from report import DISCLAIMER, PRIVACY_NOTE, build_report_pdf
from rules import calculate_score, check_rules, merge_missing_clauses

load_dotenv()

st.set_page_config(page_title="ClauseGuard", layout="wide")

LANG_COPY = {
    "English": {
        "tagline": "Review rent agreements with clarity.",
        "language": "Language",
        "input_method": "Input method",
        "upload_pdf": "PDF document",
        "upload_photo": "Photo",
        "paste_text": "Pasted text",
        "check": "Review agreement",
        "checking": "Reviewing agreement...",
        "privacy": "Privacy: your agreement is processed in memory and is not saved.",
        "disclaimer": DISCLAIMER,
        "no_input": "Please provide a PDF, photo, or pasted text before continuing.",
        "not_rent": "This document does not appear to be a rent agreement.",
        "score": "Agreement score",
        "red": "High risk",
        "yellow": "Needs attention",
        "green": "Acceptable",
        "missing": "Missing provisions",
        "ask": "Suggested requests",
        "no_red": "No high-risk items identified.",
        "no_yellow": "No items requiring attention.",
        "no_green": "No acceptable items to display.",
        "no_missing": "No missing provisions identified.",
        "no_changes": "No suggested requests at this time.",
        "download": "Download report",
        "copy_hint": "You may copy this message:",
        "mock": "Demo mode is active (MOCK_AI=true). No API key required.",
        "api_missing": "API key not found. Add GEMINI_API_KEY in .env, or set MOCK_AI=true for demo mode.",
        "analyzing_pdf": "Reading PDF...",
        "analyzing_photo": "Reading photo...",
        "analyzing_text": "Reading text...",
        "model": "Model",
    },
    "Hindi": {
        "tagline": "किराया समझौतों की स्पष्ट समीक्षा।",
        "language": "भाषा",
        "input_method": "इनपुट विधि",
        "upload_pdf": "PDF दस्तावेज़",
        "upload_photo": "फोटो",
        "paste_text": "पेस्ट किया गया टेक्स्ट",
        "check": "समझौते की समीक्षा करें",
        "checking": "समझौते की समीक्षा हो रही है...",
        "privacy": "गोपनीयता: आपका समझौता केवल मेमोरी में प्रोसेस होता है और सहेजा नहीं जाता।",
        "disclaimer": "यह केवल सामान्य जानकारी है, कानूनी सलाह नहीं।",
        "no_input": "कृपया आगे बढ़ने से पहले PDF, फोटो, या टेक्स्ट प्रदान करें।",
        "not_rent": "यह दस्तावेज़ किराया समझौता नहीं लगता।",
        "score": "समझौता स्कोर",
        "red": "उच्च जोखिम",
        "yellow": "ध्यान देने योग्य",
        "green": "स्वीकार्य",
        "missing": "अनुपलब्ध प्रावधान",
        "ask": "सुझाए गए अनुरोध",
        "no_red": "कोई उच्च जोखिम वाला बिंदु नहीं मिला।",
        "no_yellow": "ध्यान देने योग्य कोई बिंदु नहीं मिला।",
        "no_green": "दिखाने के लिए कोई स्वीकार्य बिंदु नहीं है।",
        "no_missing": "कोई अनुपलब्ध प्रावधान नहीं मिला।",
        "no_changes": "इस समय कोई सुझाव नहीं है।",
        "download": "रिपोर्ट डाउनलोड करें",
        "copy_hint": "आप इस संदेश को कॉपी कर सकते हैं:",
        "mock": "डेमो मोड सक्रिय है (MOCK_AI=true)। API key आवश्यक नहीं है।",
        "api_missing": "API key नहीं मिली। .env में GEMINI_API_KEY जोड़ें, या डेमो मोड के लिए MOCK_AI=true सेट करें।",
        "analyzing_pdf": "PDF पढ़ा जा रहा है...",
        "analyzing_photo": "फोटो पढ़ी जा रही है...",
        "analyzing_text": "टेक्स्ट पढ़ा जा रहा है...",
        "model": "मॉडल",
    },
}

RISK_ACCENTS = {
    "green": "#5a7a66",
    "yellow": "#8a7a52",
    "red": "#8a5a5a",
}


def t(language: str, key: str) -> str:
    return LANG_COPY.get(language, LANG_COPY["English"])[key]


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --bg: #f7f7f5;
            --surface: #ffffff;
            --text: #1f2328;
            --muted: #6b7280;
            --border: #e5e7eb;
            --accent: #3f4a5a;
        }

        html, body, [class*="css"], .stApp {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            letter-spacing: -0.01em;
        }

        .stApp {
            background: var(--bg);
        }

        .block-container {
            max-width: 980px;
            padding-top: 2.5rem;
            padding-bottom: 3rem;
        }

        #MainMenu, footer, header[data-testid="stHeader"] {
            visibility: hidden;
            height: 0;
        }

        h1, h2, h3 {
            font-family: 'Inter', system-ui, sans-serif;
            letter-spacing: -0.02em;
            font-weight: 600;
            color: var(--text);
        }

        .cg-title {
            font-size: 2rem;
            font-weight: 600;
            letter-spacing: -0.03em;
            margin-bottom: 0.2rem;
            color: var(--text);
        }

        .cg-tagline {
            font-size: 1rem;
            color: var(--muted);
            margin-bottom: 2rem;
            font-weight: 400;
        }

        .cg-meta {
            font-size: 0.8rem;
            color: var(--muted);
            margin-top: 0.25rem;
        }

        .stButton>button {
            width: 100%;
            background: var(--text);
            color: #fff;
            border: none;
            border-radius: 4px;
            padding: 0.7rem 1rem;
            font-size: 0.95rem;
            font-weight: 500;
            letter-spacing: -0.01em;
        }

        .stButton>button:hover {
            background: #374151;
            color: #fff;
        }

        .stButton>button:focus {
            box-shadow: none;
            outline: 1px solid var(--accent);
        }

        div[data-testid="stRadio"] label {
            font-size: 0.9rem;
            color: var(--text);
        }

        .score-card {
            background: var(--surface);
            padding: 1.5rem 1.5rem 1.5rem 1.25rem;
            border: 1px solid var(--border);
            border-left: 3px solid var(--accent);
            border-radius: 2px;
            margin: 1.5rem 0;
        }

        .score-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--muted);
            margin-bottom: 0.5rem;
        }

        .score-value {
            font-size: 2.75rem;
            font-weight: 600;
            line-height: 1;
            letter-spacing: -0.03em;
            color: var(--text);
        }

        .score-max {
            font-size: 1.1rem;
            font-weight: 400;
            color: var(--muted);
            margin-left: 0.15rem;
        }

        .score-status {
            font-size: 0.95rem;
            color: var(--muted);
            margin-top: 0.6rem;
        }

        .section-title {
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--muted);
            margin: 1.75rem 0 0.75rem 0;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
        }

        .flag-card {
            background: var(--surface);
            padding: 1rem 1rem 1rem 1.1rem;
            border: 1px solid var(--border);
            border-left: 2px solid var(--border);
            border-radius: 2px;
            margin-bottom: 0.6rem;
        }

        .flag-red { border-left-color: #8a5a5a; }
        .flag-yellow { border-left-color: #8a7a52; }
        .flag-green { border-left-color: #5a7a66; }

        .flag-title {
            font-size: 0.92rem;
            font-weight: 500;
            color: var(--text);
            margin-bottom: 0.25rem;
            line-height: 1.45;
        }

        .flag-explanation {
            font-size: 0.85rem;
            color: var(--muted);
            line-height: 1.5;
        }

        .empty-note {
            font-size: 0.88rem;
            color: var(--muted);
            padding: 0.5rem 0;
        }

        div[data-testid="stAlert"] {
            border-radius: 2px;
            border: 1px solid var(--border);
        }

        .stTextArea textarea, div[data-testid="stFileUploader"] section {
            border-radius: 2px;
            border-color: var(--border);
        }

        div[data-testid="stExpander"] {
            border: 1px solid var(--border);
            border-radius: 2px;
            background: var(--surface);
        }

        .stDownloadButton>button {
            background: transparent;
            color: var(--text);
            border: 1px solid var(--border);
        }
        .stDownloadButton>button:hover {
            background: var(--surface);
            border-color: #9ca3af;
            color: var(--text);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    st.session_state.setdefault("result", None)
    st.session_state.setdefault("error", None)
    st.session_state.setdefault("report", None)


def render_score(score: dict, language: str) -> None:
    color = score.get("color", "yellow")
    accent = RISK_ACCENTS.get(color, RISK_ACCENTS["yellow"])
    label = score["label_hi"] if language == "Hindi" else score["label_en"]
    st.markdown(
        f"""
        <div class="score-card" style="border-left-color: {accent};">
            <div class="score-label">{t(language, 'score')}</div>
            <div class="score-value">{score['score']}<span class="score-max">/10</span></div>
            <div class="score-status">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_title(title: str) -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def render_clauses(clauses: list, color: str, language: str, empty_key: str) -> None:
    items = [c for c in clauses if c.color == color]
    if not items:
        st.markdown(f'<div class="empty-note">{t(language, empty_key)}</div>', unsafe_allow_html=True)
        return
    for c in items:
        st.markdown(
            f"""<div class="flag-card flag-{color}">
                <div class="flag-title">{c.clause_text}</div>
                <div class="flag-explanation">{c.explanation}</div>
            </div>""",
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

    status_key = {"pdf": "analyzing_pdf", "image": "analyzing_photo", "text": "analyzing_text"}.get(
        input_mode, "checking"
    )
    try:
        with st.status(t(language, status_key), expanded=False) as status:
            analysis = analyze_agreement(**kwargs)
            status.update(label=t(language, "checking"), state="complete")
    except AnalyzerError as exc:
        st.session_state.error = str(exc)
        return
    except Exception:
        st.session_state.error = (
            "Something went wrong. Please try again."
            if language == "English"
            else "कुछ गलत हुआ। कृपया फिर कोशिश करें।"
        )
        return

    if not analysis.document_type_ok:
        st.session_state.error = t(language, "not_rent")
        return

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

    st.markdown('<div class="cg-title">ClauseGuard</div>', unsafe_allow_html=True)
    language = st.radio(
        "Language",
        ["English", "Hindi"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.markdown(f'<div class="cg-tagline">{t(language, "tagline")}</div>', unsafe_allow_html=True)
    st.caption(t(language, "privacy"))
    st.info(t(language, "disclaimer"))

    if is_mock_mode():
        st.info(t(language, "mock"))
    elif not os.getenv("GEMINI_API_KEY", "").strip():
        st.warning(t(language, "api_missing"))
    st.markdown(f'<div class="cg-meta">{t(language, "model")}: {get_model_name()}</div>', unsafe_allow_html=True)

    input_mode = st.radio(
        t(language, "input_method"),
        ["pdf", "image", "text"],
        format_func=lambda x: {
            "pdf": t(language, "upload_pdf"),
            "image": t(language, "upload_photo"),
            "text": t(language, "paste_text"),
        }[x],
        horizontal=True,
    )

    pdf_file = None
    image_file = None
    pasted_text = ""

    if input_mode == "pdf":
        pdf_file = st.file_uploader("PDF", type=["pdf"], key="pdf_uploader", label_visibility="collapsed")
    elif input_mode == "image":
        image_file = st.file_uploader(
            "Photo", type=["jpg", "jpeg", "png"], key="img_uploader", label_visibility="collapsed"
        )
    else:
        pasted_text = st.text_area(
            "Text",
            height=220,
            key="pasted_text",
            label_visibility="collapsed",
            placeholder="Paste agreement text here / समझौता टेक्स्ट यहाँ पेस्ट करें",
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

    render_section_title(t(language, "red"))
    render_clauses(analysis.clauses, "red", language, "no_red")

    render_section_title(t(language, "yellow"))
    render_clauses(analysis.clauses, "yellow", language, "no_yellow")

    with st.expander(t(language, "green")):
        render_clauses(analysis.clauses, "green", language, "no_green")

    render_section_title(t(language, "missing"))
    if missing:
        for item in missing:
            st.markdown(f"- {item}")
    else:
        st.markdown(f'<div class="empty-note">{t(language, "no_missing")}</div>', unsafe_allow_html=True)

    render_section_title(t(language, "ask"))
    if analysis.suggested_changes:
        st.caption(t(language, "copy_hint"))
        for change in analysis.suggested_changes:
            st.markdown(f"**{change.issue}**")
            st.code(change.polite_request_message, language=None)
    else:
        st.markdown(f'<div class="empty-note">{t(language, "no_changes")}</div>', unsafe_allow_html=True)

    if st.session_state.report:
        st.download_button(
            t(language, "download"),
            data=st.session_state.report,
            file_name="clauseguard-report.pdf",
            mime="application/pdf",
        )


if __name__ == "__main__":
    main()

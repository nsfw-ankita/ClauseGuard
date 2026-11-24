"""ClauseGuard - AI rent agreement red-flag detector."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from analyzer import AnalyzerError, analyze_agreement, extract_pdf_text, get_model_name, is_mock_mode
from report import DISCLAIMER, PRIVACY_NOTE, build_report_pdf
from rules import calculate_score, check_rules, merge_missing_clauses

load_dotenv()

st.set_page_config(page_title="ClauseGuard", page_icon="🛡️", layout="centered")

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
INPUT_OPTIONS = ["Upload PDF", "Upload photo", "Paste text"]
SAMPLE_OPTIONS = {
    "safe": "samples/safe_agreement.txt",
    "risky": "samples/risky_agreement.txt",
    "missing": "samples/missing_clauses_agreement.txt",
}

LANG_COPY = {
    "English": {
        "tagline": "Sign smart, not blind.",
        "flow": "Upload → Analyze → Get report",
        "language": "Language",
        "input_label": "Choose input",
        "upload_pdf": "Upload PDF",
        "upload_photo": "Upload photo",
        "paste_text": "Paste text",
        "check": "Check my agreement",
        "checking": "Checking your agreement...",
        "privacy_badge": "🔒 Not stored",
        "disclaimer": DISCLAIMER,
        "no_input": "Please upload a PDF, upload a photo, or paste text first.",
        "not_rent": "This does not look like a rent agreement. Please upload a rent agreement.",
        "score": "Agreement Score",
        "red": "Red flags",
        "yellow": "Check",
        "green": "Fine",
        "missing": "Missing",
        "red_section": "Red flags",
        "yellow_section": "Check this",
        "green_section": "Looks fine",
        "missing_section": "Missing things",
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
        "reading": "Reading document",
        "analyzing": "Analyzing clauses",
        "scoring": "Scoring agreement",
        "try_sample": "Try with a sample",
        "sample_loaded": "Sample loaded. Click “Check my agreement”.",
        "developer_info": "Developer info",
        "model": "Model",
    },
    "Hindi": {
        "tagline": "समझदारी से साइन करें।",
        "flow": "अपलोड करें → जांचें → रिपोर्ट पाएं",
        "language": "भाषा",
        "input_label": "इनपुट चुनें",
        "upload_pdf": "PDF अपलोड करें",
        "upload_photo": "फोटो अपलोड करें",
        "paste_text": "टेक्स्ट चिपकाएं",
        "check": "मेरा समझौता जांचें",
        "checking": "आपका समझौता जांचा जा रहा है...",
        "privacy_badge": "🔒 सेव नहीं होता",
        "disclaimer": "यह केवल सामान्य जानकारी है, कानूनी सलाह नहीं।",
        "no_input": "कृपया पहले PDF, फोटो या टेक्स्ट डालें।",
        "not_rent": "यह किराये का समझौता नहीं लग रहा है। कृपया किराये का समझौता डालें।",
        "score": "समझौता स्कोर",
        "red": "लाल झंडे",
        "yellow": "ध्यान दें",
        "green": "ठीक",
        "missing": "गायब",
        "red_section": "लाल झंडे",
        "yellow_section": "ध्यान दें",
        "green_section": "ठीक लग रहा है",
        "missing_section": "गायब बातें",
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
        "reading": "दस्तावेज़ पढ़ा जा रहा है",
        "analyzing": "शर्तों की जांच हो रही है",
        "scoring": "स्कोर बनाया जा रहा है",
        "try_sample": "नमूना आज़माएं",
        "sample_loaded": "नमूना लोड हो गया। “मेरा समझौता जांचें” पर क्लिक करें।",
        "developer_info": "डेवलपर जानकारी",
        "model": "मॉडल",
    },
}


def t(language: str, key: str) -> str:
    return LANG_COPY.get(language, LANG_COPY["English"])[key]


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2rem; padding-bottom: 2.5rem; max-width: 900px; }
        [data-testid="stMetric"] {
            background: #171B22;
            border: 1px solid #263041;
            border-radius: 14px;
            padding: 0.8rem 1rem;
            box-shadow: 0 6px 18px rgba(0,0,0,0.18);
        }
        .stButton>button {
            border-radius: 12px !important;
            padding: 0.7rem 1.1rem !important;
            font-weight: 600;
            border: 1px solid #263041;
            box-shadow: 0 4px 14px rgba(0,0,0,0.12);
        }
        .stDownloadButton>button {
            border-radius: 12px !important;
            padding: 0.7rem 1.1rem !important;
        }
        div[data-testid="stSegmentedControl"] button {
            border-radius: 10px !important;
            padding: 0.55rem 0.9rem !important;
        }
        .hero { margin-bottom: 1.2rem; }
        .hero h1 { margin-bottom: 0.2rem; font-size: 2.6rem; }
        .hero .tagline { font-size: 1.15rem; color: #D1D5DB; margin-bottom: 0.15rem; }
        .hero .flow { color: #94A3B8; font-size: 0.95rem; }
        .privacy-badge {
            display: inline-block; padding: 0.35rem 0.7rem; border-radius: 999px;
            background: #17212b; border: 1px solid #263041; color: #9FB3C8; font-size: 0.85rem;
            margin-top: 0.3rem;
        }
        .flag-card {
            padding: 1rem 1rem 1rem 1.1rem; border-radius: 14px; margin-bottom: 0.75rem;
            background: #171B22; border: 1px solid #263041; box-shadow: 0 6px 18px rgba(0,0,0,0.12);
        }
        .flag-red { border-left: 5px solid #EF4444; }
        .flag-yellow { border-left: 5px solid #F59E0B; }
        .flag-green { border-left: 5px solid #22C55E; }
        .flag-quote { font-size: 1rem; color: #E6EDF3; margin-bottom: 0.35rem; }
        .flag-explain { font-size: 0.92rem; color: #9FB3C8; }
        .chat-bubble {
            background: #111827; border: 1px solid #263041; border-left: 4px solid #14B8A6;
            border-radius: 14px; padding: 0.9rem 1rem; color: #E6EDF3; margin: 0.35rem 0 0.8rem 0;
        }
        .footer-note { color: #94A3B8; font-size: 0.82rem; margin-top: 2rem; text-align: center; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    st.session_state.setdefault("result", None)
    st.session_state.setdefault("error", None)
    st.session_state.setdefault("report", None)
    st.session_state.setdefault("input_mode", INPUT_OPTIONS[0])
    st.session_state.setdefault("language", "English")
    st.session_state.setdefault("pasted_text", "")
    st.session_state.setdefault("sample_notice", False)


def input_mode_key(language: str, option: str) -> str:
    mapping = {
        "Upload PDF": t(language, "upload_pdf"),
        "Upload photo": t(language, "upload_photo"),
        "Paste text": t(language, "paste_text"),
    }
    return mapping[option]


def mode_from_label(label: str, language: str) -> str:
    for opt in INPUT_OPTIONS:
        if input_mode_key(language, opt) == label:
            return opt
    return INPUT_OPTIONS[0]


def render_score_gauge(score: dict, language: str) -> None:
    value = float(score["score"])
    label = score["label_hi"] if language == "Hindi" else score["label_en"]
    color = {"green": "#22C55E", "yellow": "#F59E0B", "red": "#EF4444"}.get(score.get("color"), "#14B8A6")
    pct = max(0.0, min(10.0, value)) / 10.0
    r = 54
    c = 2 * 3.14159 * r
    dash = c * pct
    gap = c - dash
    svg = f"""
    <div style="display:flex;justify-content:center;margin:0.5rem 0 1rem 0;">
      <div style="position:relative;width:180px;height:180px;">
        <svg width="180" height="180" viewBox="0 0 140 140">
          <circle cx="70" cy="70" r="{r}" stroke="#263041" stroke-width="12" fill="none" />
          <circle cx="70" cy="70" r="{r}" stroke="{color}" stroke-width="12" fill="none"
            stroke-linecap="round" stroke-dasharray="{dash} {gap}" transform="rotate(-90 70 70)" />
        </svg>
        <div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;">
          <div style="font-size:2.4rem;font-weight:700;line-height:1;color:{color};">{value:.1f}</div>
          <div style="font-size:0.9rem;color:#9FB3C8;">/10</div>
          <div style="font-size:0.95rem;color:#E6EDF3;margin-top:0.35rem;text-align:center;padding:0 10px;">{label}</div>
        </div>
      </div>
    </div>
    """
    st.markdown(svg, unsafe_allow_html=True)


def render_clauses(clauses: list, color: str, language: str, empty_key: str) -> None:
    items = [c for c in clauses if c.color == color]
    if not items:
        st.info(t(language, empty_key))
        return
    for c in items:
        st.markdown(
            f"""<div class="flag-card flag-{color}">
                <div class="flag-quote">“{c.clause_text}”</div>
                <div class="flag-explain">{c.explanation}</div>
            </div>""",
            unsafe_allow_html=True,
        )


def get_agreement_text_from_pdf(pdf_file) -> str | None:
    try:
        return extract_pdf_text(pdf_file.getvalue())
    except Exception:
        return None


def load_sample(name: str) -> None:
    path = SAMPLES_DIR / Path(SAMPLE_OPTIONS[name]).name
    text = path.read_text(encoding="utf-8")
    st.session_state.pasted_text = text
    st.session_state.input_mode = "Paste text"
    st.session_state.sample_notice = True
    st.session_state.error = None


def run_analysis(language: str, input_mode: str, pdf_file, image_file, pasted_text: str) -> None:
    st.session_state.error = None
    st.session_state.result = None
    st.session_state.report = None

    kwargs = {"language": language}
    rule_text = ""
    if input_mode == "Upload PDF":
        if pdf_file is None:
            st.session_state.error = t(language, "no_input")
            return
        kwargs["pdf_bytes"] = pdf_file.getvalue()
    elif input_mode == "Upload photo":
        if image_file is None:
            st.session_state.error = t(language, "no_input")
            return
        kwargs["image_bytes"] = image_file.getvalue()
        kwargs["image_mime"] = image_file.type or "image/jpeg"
    else:
        if not pasted_text.strip():
            st.session_state.error = t(language, "no_input")
            return
        kwargs["text"] = pasted_text

    try:
        with st.status(t(language, "reading"), expanded=False) as status:
            status.update(label=t(language, "analyzing"))
            analysis = analyze_agreement(**kwargs)
            status.update(label=t(language, "scoring"))
            if not analysis.document_type_ok:
                st.session_state.error = t(language, "not_rent")
                status.update(label=t(language, "checking"), state="error")
                return

            if input_mode == "Upload PDF" and pdf_file is not None:
                rule_text = get_agreement_text_from_pdf(pdf_file) or ""
            elif input_mode == "Paste text":
                rule_text = pasted_text
            if not rule_text.strip():
                rule_text = "\n".join([c.clause_text for c in analysis.clauses] + analysis.missing_clauses)

            rule_checks = check_rules(rule_text)
            missing = merge_missing_clauses(analysis.missing_clauses, rule_checks, language)
            score = calculate_score(analysis, rule_checks)
            report = build_report_pdf(
                analysis=analysis, rule_checks=rule_checks, missing_clauses=missing, score=score, language=language
            )
            status.update(label=t(language, "checking"), state="complete")
    except AnalyzerError as exc:
        st.session_state.error = str(exc)
        return
    except Exception:
        st.session_state.error = "Something went wrong. Please try again." if language == "English" else "कुछ गलत हुआ। कृपया फिर कोशिश करें।"
        return

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

    with st.sidebar:
        st.session_state.language = st.radio(
            t(st.session_state.language, "language"),
            ["English", "Hindi"],
            index=["English", "Hindi"].index(st.session_state.get("language", "English")),
        )
        st.caption(t(st.session_state.language, "privacy_badge"))
        if not is_mock_mode():
            with st.expander(t(st.session_state.language, "developer_info")):
                st.caption(f"{t(st.session_state.language, 'model')}: {get_model_name()}")

    language = st.session_state.language

    st.markdown(
        f"""<div class="hero">
            <h1>🛡️ ClauseGuard</h1>
            <div class="tagline">{t(language, 'tagline')}</div>
            <div class="flow">{t(language, 'flow')}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    if is_mock_mode():
        st.info(t(language, "mock"))
    elif not os.getenv("GEMINI_API_KEY", "").strip():
        st.info(t(language, "api_missing"))

    labels = [input_mode_key(language, opt) for opt in INPUT_OPTIONS]
    current_label = input_mode_key(language, st.session_state.input_mode)
    selected_label = st.segmented_control(
        t(language, "input_label"),
        options=labels,
        selection_mode="single",
        default=current_label,
    ) if hasattr(st, "segmented_control") else st.radio(
        t(language, "input_label"), options=labels, index=labels.index(current_label), horizontal=True
    )
    if selected_label:
        st.session_state.input_mode = mode_from_label(selected_label, language)

    input_mode = st.session_state.input_mode
    pdf_file = image_file = None
    pasted_text = st.session_state.pasted_text

    if input_mode == "Upload PDF":
        pdf_file = st.file_uploader(t(language, "upload_pdf"), type=["pdf"], key="pdf_uploader")
    elif input_mode == "Upload photo":
        image_file = st.file_uploader(t(language, "upload_photo"), type=["jpg", "jpeg", "png"], key="img_uploader")
    else:
        pasted_text = st.text_area(
            t(language, "paste_text"),
            height=220,
            key="pasted_text",
            placeholder="Paste agreement text here / समझौता टेक्स्ट यहाँ चिपकाएं",
        )

    sample_cols = st.columns([1, 1, 1, 1])
    if sample_cols[0].button(t(language, "try_sample"), use_container_width=True):
        load_sample("risky")
        st.rerun()
    with sample_cols[1]:
        st.markdown(f'<div class="privacy-badge">{t(language, "privacy_badge")}</div>', unsafe_allow_html=True)

    if st.session_state.sample_notice:
        st.success(t(language, "sample_loaded"))
        st.session_state.sample_notice = False

    if st.button(t(language, "check"), type="primary", use_container_width=True):
        run_analysis(language, input_mode, pdf_file, image_file, st.session_state.get("pasted_text", pasted_text))

    if st.session_state.error:
        st.error(st.session_state.error)

    result = st.session_state.result
    if not result:
        st.markdown(f'<div class="footer-note">{t(language, "disclaimer")}</div>', unsafe_allow_html=True)
        return

    analysis = result["analysis"]
    score = result["score"]
    missing = result["missing"]

    render_score_gauge(score, language)

    counts = {"red": 0, "yellow": 0, "green": 0}
    for c in analysis.clauses:
        counts[c.color] = counts.get(c.color, 0) + 1
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t(language, "red"), counts["red"])
    m2.metric(t(language, "yellow"), counts["yellow"])
    m3.metric(t(language, "green"), counts["green"])
    m4.metric(t(language, "missing"), len(missing))

    st.subheader(t(language, "red_section"))
    render_clauses(analysis.clauses, "red", language, "no_red")

    st.subheader(t(language, "yellow_section"))
    render_clauses(analysis.clauses, "yellow", language, "no_yellow")

    with st.expander(t(language, "green_section")):
        render_clauses(analysis.clauses, "green", language, "no_green")

    st.subheader(t(language, "missing_section"))
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
            st.markdown(f'<div class="chat-bubble">{change.polite_request_message}</div>', unsafe_allow_html=True)
            st.code(change.polite_request_message, language=None)
    else:
        st.info(t(language, "no_changes"))

    if st.session_state.report:
        st.download_button(
            t(language, "download"),
            data=st.session_state.report,
            file_name="clauseguard-report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.markdown(f'<div class="footer-note">{t(language, "disclaimer")}</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()

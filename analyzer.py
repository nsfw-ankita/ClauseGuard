"""Input handling and Gemini-powered analysis for ClauseGuard."""

from __future__ import annotations

import json
import os
from typing import Any

import fitz  # PyMuPDF
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError

from prompts import SYSTEM_INSTRUCTIONS, build_analysis_prompt
from schemas import AnalysisResult

load_dotenv()

DEFAULT_MODEL = "gemini-2.5-flash"  # Check https://ai.google.dev/gemini-api/docs/models for current model names.


class AnalyzerError(Exception):
    """User-facing analyzer error."""


def get_model_name() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def is_mock_mode() -> bool:
    return os.getenv("MOCK_AI", "false").strip().lower() in {"1", "true", "yes", "on"}


def extract_pdf_text(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        parts = []
        for page in doc:
            parts.append(page.get_text("text"))
        return "\n".join(parts).strip()
    finally:
        doc.close()


def render_pdf_pages(file_bytes: bytes, max_pages: int = 5) -> list[bytes]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    images: list[bytes] = []
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            images.append(pix.tobytes("png"))
        return images
    finally:
        doc.close()


def is_scanned_pdf(text: str) -> bool:
    cleaned = "".join(ch for ch in text if not ch.isspace())
    return len(cleaned) < 120


def _mock_result(language: str) -> dict[str, Any]:
    if language == "Hindi":
        return {
            "document_type_ok": True,
            "clauses": [
                {
                    "clause_text": "सुरक्षा जमा ₹50,000 है।",
                    "color": "green",
                    "explanation": "जमा राशि साफ लिखी है।",
                },
                {
                    "clause_text": "मकान मालिक कभी भी बिना नोटिस आ सकता है।",
                    "color": "red",
                    "explanation": "बिना सूचना घर आना आपकी निजता के लिए जोखिम है।",
                },
                {
                    "clause_text": "किराया बढ़ोतरी हर साल होगी, सीमा नहीं लिखी।",
                    "color": "yellow",
                    "explanation": "किराया कितना बढ़ेगा, यह साफ नहीं है।",
                },
            ],
            "missing_clauses": ["पुलिस सत्यापन", "जमा वापसी की समय सीमा"],
            "suggested_changes": [
                {
                    "issue": "बिना नोटिस निरीक्षण",
                    "polite_request_message": "कृपया समझौते में लिखें कि घर देखने से पहले कम से कम 24 घंटे का नोटिस दिया जाएगा।",
                },
                {
                    "issue": "किराया बढ़ोतरी सीमा नहीं है",
                    "polite_request_message": "कृपया हर साल किराया बढ़ोतरी की अधिकतम सीमा, जैसे 5%, समझौते में जोड़ें।",
                },
            ],
        }
    return {
        "document_type_ok": True,
        "clauses": [
            {
                "clause_text": "Security deposit is Rs. 50,000.",
                "color": "green",
                "explanation": "Deposit amount is clearly written.",
            },
            {
                "clause_text": "Landlord may enter the property anytime without notice.",
                "color": "red",
                "explanation": "Entry without notice is risky for your privacy.",
            },
            {
                "clause_text": "Rent will increase every year, but no limit is mentioned.",
                "color": "yellow",
                "explanation": "The rent increase amount is not clear.",
            },
        ],
        "missing_clauses": ["Police verification", "Deposit refund timeline"],
        "suggested_changes": [
            {
                "issue": "Inspection without notice",
                "polite_request_message": "Could you please add that you will give at least 24 hours notice before visiting the property?",
            },
            {
                "issue": "No rent increase cap",
                "polite_request_message": "Could you please add a maximum yearly rent increase, such as 5%, to the agreement?",
            },
        ],
    }


def _get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise AnalyzerError(
            "GEMINI_API_KEY is missing. Add it to your .env file. You can also set MOCK_AI=true to try demo mode."
        )
    return genai.Client(api_key=api_key)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _call_gemini(contents: list[Any], language: str) -> dict[str, Any]:
    client = _get_client()
    prompt = build_analysis_prompt("", language) if not any(isinstance(c, str) for c in contents) else None
    # Build content parts: system + prompt + user content
    parts: list[Any] = [SYSTEM_INSTRUCTIONS]
    if prompt:
        parts.append(prompt)
    for c in contents:
        parts.append(c)
    # If text was passed, prompt was built with text inside; handle that.
    response = client.models.generate_content(
        model=get_model_name(),
        contents=parts,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    raw = response.text or ""
    return _extract_json(raw)


def analyze_agreement(
    *,
    language: str,
    text: str | None = None,
    pdf_bytes: bytes | None = None,
    image_bytes: bytes | None = None,
    image_mime: str = "image/jpeg",
) -> AnalysisResult:
    if is_mock_mode():
        return AnalysisResult.model_validate(_mock_result(language))

    contents: list[Any] = []
    if text is not None:
        cleaned = text.strip()
        if not cleaned:
            raise AnalyzerError("Please paste some agreement text first.")
        contents = [build_analysis_prompt(cleaned, language), cleaned]
    elif pdf_bytes is not None:
        extracted = extract_pdf_text(pdf_bytes)
        if is_scanned_pdf(extracted):
            images = render_pdf_pages(pdf_bytes)
            if not images:
                raise AnalyzerError("Could not read this PDF. Please try another file.")
            contents = [build_analysis_prompt("[Scanned PDF pages attached as images]", language)]
            for img in images:
                contents.append(types.Part.from_bytes(data=img, mime_type="image/png"))
        else:
            contents = [build_analysis_prompt(extracted, language), extracted]
    elif image_bytes is not None:
        contents = [
            build_analysis_prompt("[Rent agreement image attached]", language),
            types.Part.from_bytes(data=image_bytes, mime_type=image_mime),
        ]
    else:
        raise AnalyzerError("Please upload a file or paste agreement text.")

    last_error: Exception | None = None
    for _ in range(2):
        try:
            data = _call_gemini(contents, language)
            return AnalysisResult.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            contents = contents + [
                "Your previous response was not valid JSON for the required schema. Return ONLY valid JSON matching the schema."
            ]
        except AnalyzerError:
            raise
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "api key" in msg or "permission" in msg or "unauth" in msg:
                raise AnalyzerError("There is a problem with the API key. Please check GEMINI_API_KEY in .env.") from exc
            if "quota" in msg or "rate" in msg or "429" in msg:
                raise AnalyzerError("The AI service is busy right now. Please wait a minute and try again.") from exc
            if "timeout" in msg or "connection" in msg or "network" in msg:
                raise AnalyzerError("Network problem while contacting AI. Please check your internet and try again.") from exc
            raise AnalyzerError("Something went wrong while checking the agreement. Please try again.") from exc

    raise AnalyzerError("The AI response was not in the expected format. Please try again.") from last_error

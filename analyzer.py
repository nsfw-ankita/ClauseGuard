"""Input handling and Gemini-powered analysis for ClauseGuard."""

from __future__ import annotations

import io
import json
import os
from typing import Any

import fitz  # PyMuPDF
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from pydantic import ValidationError

from prompts import SYSTEM_INSTRUCTIONS, build_analysis_prompt
from schemas import AnalysisResult

load_dotenv()

DEFAULT_MODEL = "gemini-3.5-flash"  # Check https://ai.google.dev/gemini-api/docs/models for current model names.
MAX_PDF_PAGES = 8
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_TEXT_CHARS = 30000


class AnalyzerError(Exception):
    """User-facing analyzer error."""


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


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


def render_pdf_pages(file_bytes: bytes, max_pages: int = MAX_PDF_PAGES) -> list[bytes]:
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


def normalize_image_bytes(image_bytes: bytes, image_mime: str = "image/jpeg") -> tuple[bytes, str]:
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.load()
            if img.width < 20 or img.height < 20:
                raise AnalyzerError("Image is too small or unreadable. Please upload a clearer photo.")
            fmt = (img.format or "").upper()
            if fmt in {"JPEG", "JPG", "PNG", "WEBP"}:
                mime = {"JPEG": "image/jpeg", "JPG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[fmt]
                return image_bytes, mime
            out = io.BytesIO()
            converted = img.convert("RGB")
            converted.save(out, format="PNG")
            return out.getvalue(), "image/png"
    except AnalyzerError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AnalyzerError("Could not read this image. Please upload a clear JPG/PNG photo.") from exc


def prepare_image_for_ocr(image_bytes: bytes) -> bytes:
    """Best-effort local preprocessing for scanned/low-quality images."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("L")
            # Simple contrast boost and resize for readability; keeps it dependency-light.
            if img.width < 1200:
                ratio = 1200 / max(1, img.width)
                img = img.resize((int(img.width * ratio), int(img.height * ratio)))
            img = img.point(lambda p: 255 if p > 180 else (0 if p < 60 else int(p * 1.2)))
            out = io.BytesIO()
            img.save(out, format="PNG")
            return out.getvalue()
    except Exception:
        return image_bytes


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


def _friendly_api_error(exc: Exception) -> AnalyzerError:
    msg = str(exc).lower()
    if "api key" in msg or "permission" in msg or "unauth" in msg or "invalid argument" in msg:
        return AnalyzerError("There is a problem with the API key or request. Please check GEMINI_API_KEY in .env.")
    if "quota" in msg or "rate" in msg or "429" in msg or "resource_exhausted" in msg:
        return AnalyzerError("The AI service is busy or quota is reached. Please wait a minute and try again.")
    if "timeout" in msg or "timed out" in msg or "deadline" in msg:
        return AnalyzerError("The AI took too long to respond. Please try again with a smaller file or less text.")
    if "connection" in msg or "network" in msg or "dns" in msg or "unavailable" in msg:
        return AnalyzerError("Network problem while contacting AI. Please check your internet and try again.")
    if "too large" in msg or "payload" in msg or "size" in msg:
        return AnalyzerError("The file is too large for analysis. Try a smaller file or fewer pages.")
    return AnalyzerError("Something went wrong while checking the agreement. Please try again.")


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise json.JSONDecodeError("Empty response", text, 0)
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


def _call_gemini(contents: list[Any]) -> dict[str, Any]:
    client = _get_client()
    parts: list[Any] = [SYSTEM_INSTRUCTIONS]
    for c in contents:
        parts.append(c)
    try:
        response = client.models.generate_content(
            model=get_model_name(),
            contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        raise _friendly_api_error(exc) from exc
    raw = getattr(response, "text", None) or ""
    return _extract_json(raw)


def _validate_input_size(*, text: str | None, pdf_bytes: bytes | None, image_bytes: bytes | None) -> None:
    if text is not None and len(text) > _env_int("MAX_TEXT_CHARS", MAX_TEXT_CHARS):
        raise AnalyzerError("The pasted text is too long. Please paste only the rent agreement text.")
    if pdf_bytes is not None and len(pdf_bytes) > _env_int("MAX_PDF_BYTES", MAX_PDF_BYTES):
        raise AnalyzerError("This PDF is too large. Please upload a smaller PDF.")
    if image_bytes is not None and len(image_bytes) > _env_int("MAX_IMAGE_BYTES", MAX_IMAGE_BYTES):
        raise AnalyzerError("This image is too large. Please upload a smaller image.")


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

    _validate_input_size(text=text, pdf_bytes=pdf_bytes, image_bytes=image_bytes)

    contents: list[Any] = []
    if text is not None:
        cleaned = text.strip()
        if not cleaned:
            raise AnalyzerError("Please paste some agreement text first.")
        contents = [build_analysis_prompt(cleaned, language), cleaned]
    elif pdf_bytes is not None:
        try:
            extracted = extract_pdf_text(pdf_bytes)
        except AnalyzerError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AnalyzerError("Could not read this PDF. Please try another file.") from exc
        if is_scanned_pdf(extracted):
            images = render_pdf_pages(pdf_bytes)
            if not images:
                raise AnalyzerError("Could not read this scanned PDF. Please try a clearer file.")
            contents = [build_analysis_prompt("[Scanned PDF pages attached as images. Use OCR to read them carefully.]", language)]
            for img in images:
                contents.append(types.Part.from_bytes(data=img, mime_type="image/png"))
        else:
            contents = [build_analysis_prompt(extracted, language), extracted]
    elif image_bytes is not None:
        normalized, mime = normalize_image_bytes(image_bytes, image_mime)
        ocr_ready = prepare_image_for_ocr(normalized)
        contents = [
            build_analysis_prompt("[Rent agreement image attached. Read any visible text carefully.]", language),
            types.Part.from_bytes(data=ocr_ready, mime_type="image/png" if ocr_ready != normalized else mime),
        ]
    else:
        raise AnalyzerError("Please upload a file or paste agreement text.")

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            data = _call_gemini(contents)
            return AnalysisResult.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            contents = contents + [
                "Your previous response was not valid JSON for the required schema. Return ONLY valid JSON matching the schema."
            ]
        except AnalyzerError as exc:
            # One automatic retry for transient-looking AI failures.
            if attempt == 0 and any(k in str(exc).lower() for k in ["busy", "quota", "network", "too long", "try again"]):
                last_error = exc
                continue
            raise

    raise AnalyzerError("The AI response was not in the expected format. Please try again.") from last_error

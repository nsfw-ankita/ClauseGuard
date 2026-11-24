import io
import json
import os
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import analyzer


def make_png_bytes(color=(255, 255, 255), size=(100, 100)):
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


def test_mock_mode_returns_valid_result(monkeypatch):
    monkeypatch.setenv("MOCK_AI", "true")
    result = analyzer.analyze_agreement(language="English", text="any text")
    assert result.document_type_ok is True
    assert len(result.clauses) >= 1


def test_extract_json_plain_and_fenced():
    data = {"document_type_ok": True, "clauses": [], "missing_clauses": [], "suggested_changes": []}
    assert analyzer._extract_json(json.dumps(data)) == data
    fenced = "```json\n" + json.dumps(data) + "\n```"
    assert analyzer._extract_json(fenced) == data


def test_extract_json_empty_raises():
    with pytest.raises(json.JSONDecodeError):
        analyzer._extract_json("")


def test_normalize_image_bytes_accepts_png():
    png = make_png_bytes()
    out, mime = analyzer.normalize_image_bytes(png, "image/png")
    assert out == png
    assert mime == "image/png"


def test_normalize_image_bytes_rejects_tiny_image():
    tiny = make_png_bytes(size=(10, 10))
    with pytest.raises(analyzer.AnalyzerError):
        analyzer.normalize_image_bytes(tiny, "image/png")


def test_validate_input_size_text(monkeypatch):
    monkeypatch.setenv("MAX_TEXT_CHARS", "10")
    with pytest.raises(analyzer.AnalyzerError):
        analyzer._validate_input_size(text="x" * 11, pdf_bytes=None, image_bytes=None)


def test_analyze_agreement_empty_text_raises(monkeypatch):
    monkeypatch.setenv("MOCK_AI", "false")
    with pytest.raises(analyzer.AnalyzerError):
        analyzer.analyze_agreement(language="English", text="   ")


def test_analyze_agreement_missing_api_key(monkeypatch):
    monkeypatch.setenv("MOCK_AI", "false")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(analyzer.AnalyzerError) as exc:
        analyzer.analyze_agreement(language="English", text="This is a rent agreement")
    assert "GEMINI_API_KEY" in str(exc.value)


def test_analyze_agreement_retries_on_invalid_json(monkeypatch):
    monkeypatch.setenv("MOCK_AI", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = {"n": 0}
    valid = {
        "document_type_ok": True,
        "clauses": [{"clause_text": "Rent", "color": "green", "explanation": "Clear."}],
        "missing_clauses": [],
        "suggested_changes": [],
    }

    def fake_call(contents):
        calls["n"] += 1
        if calls["n"] == 1:
            return json.loads("not json")
        return valid

    monkeypatch.setattr(analyzer, "_call_gemini", fake_call)
    result = analyzer.analyze_agreement(language="English", text="Rent agreement text")
    assert result.document_type_ok is True
    assert calls["n"] == 2

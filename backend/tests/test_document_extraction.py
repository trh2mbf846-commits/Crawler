"""Tests für app/agents/document_extraction.py.

Nutzt ein von Hand gebautes, minimales aber gültiges PDF (xref-Tabelle + %%EOF, damit pypdf es
akzeptiert) statt eines externen Downloads - hermetisch, kein Netzwerk nötig, deterministisch.
"""
from __future__ import annotations

import httpx
import pytest

from app.agents import document_extraction
from app.agents.document_extraction import extract_pdf_text


def _minimal_pdf(text: str) -> bytes:
    objekte = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
    ]
    stream = f"BT /F1 24 Tf 10 100 Td ({text}) Tj ET".encode()
    objekte.append(b"<</Length " + str(len(stream)).encode() + b">>\nstream\n" + stream + b"\nendstream")
    objekte.append(b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objekte, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(objekte) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer<</Size {len(objekte) + 1}/Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF".encode()
    return bytes(out)


_ECHTER_HTTPX_CLIENT = httpx.Client


def _mock_client_factory(handler):
    def _factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _ECHTER_HTTPX_CLIENT(*args, **kwargs)

    return _factory


def test_extrahiert_text_aus_gueltigem_pdf(monkeypatch):
    pdf_bytes = _minimal_pdf("Testinhalt PDF")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf_bytes)

    monkeypatch.setattr(document_extraction.httpx, "Client", _mock_client_factory(handler))

    text = extract_pdf_text("https://example.invalid/vergabeunterlagen.pdf")

    assert text == "Testinhalt PDF"


def test_liefert_none_bei_nicht_pdf_content_type(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    monkeypatch.setattr(document_extraction.httpx, "Client", _mock_client_factory(handler))

    assert extract_pdf_text("https://example.invalid/seite.html") is None


def test_erkennt_pdf_ueber_dateiendung_ohne_content_type(monkeypatch):
    pdf_bytes = _minimal_pdf("Ohne Content-Type")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={}, content=pdf_bytes)

    monkeypatch.setattr(document_extraction.httpx, "Client", _mock_client_factory(handler))

    text = extract_pdf_text("https://example.invalid/unterlagen.pdf")

    assert text == "Ohne Content-Type"


def test_liefert_none_bei_http_fehler(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    monkeypatch.setattr(document_extraction.httpx, "Client", _mock_client_factory(handler))

    assert extract_pdf_text("https://example.invalid/nicht-vorhanden.pdf") is None


def test_liefert_none_bei_kaputtem_pdf(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"nicht wirklich ein pdf")

    monkeypatch.setattr(document_extraction.httpx, "Client", _mock_client_factory(handler))

    assert extract_pdf_text("https://example.invalid/kaputt.pdf") is None


def test_liefert_none_bei_verbindungsfehler(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Verbindung fehlgeschlagen", request=request)

    monkeypatch.setattr(document_extraction.httpx, "Client", _mock_client_factory(handler))

    assert extract_pdf_text("https://example.invalid/unerreichbar.pdf") is None


def test_bricht_ab_wenn_download_zu_gross(monkeypatch):
    monkeypatch.setattr(document_extraction, "_MAX_DOWNLOAD_BYTES", 10)
    pdf_bytes = _minimal_pdf("Dieser Text ist laenger als zehn Byte")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf_bytes)

    monkeypatch.setattr(document_extraction.httpx, "Client", _mock_client_factory(handler))

    assert extract_pdf_text("https://example.invalid/riesig.pdf") is None

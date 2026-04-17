"""Tests for mathpix_client — all HTTP calls are mocked."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mathpix_client import API_BASE, MathpixClient, MathpixError


@pytest.fixture
def client() -> MathpixClient:
    return MathpixClient(app_id="id", app_key="key")


def _mock_response(status_code: int = 200, json_data=None, content: bytes = b""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = json_data or {}
    resp.content = content
    resp.text = "err body" if not resp.ok else ""
    return resp


def test_missing_creds_raises(monkeypatch):
    monkeypatch.delenv("MATHPIX_APP_ID", raising=False)
    monkeypatch.delenv("MATHPIX_APP_KEY", raising=False)
    with pytest.raises(MathpixError):
        MathpixClient()


def test_upload_pdf_returns_id(client, tmp_path: Path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    with patch("mathpix_client.requests.post") as mock_post:
        mock_post.return_value = _mock_response(200, {"pdf_id": "abc123"})
        pdf_id = client.upload_pdf(pdf)

    assert pdf_id == "abc123"
    args, kwargs = mock_post.call_args
    assert args[0] == f"{API_BASE}/pdf"
    assert kwargs["headers"] == {"app_id": "id", "app_key": "key"}
    assert "options_json" in kwargs["data"]
    assert "file" in kwargs["files"]


def test_upload_pdf_http_error_raises(client, tmp_path: Path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF\n")
    with patch("mathpix_client.requests.post") as mock_post:
        mock_post.return_value = _mock_response(401)
        with pytest.raises(MathpixError):
            client.upload_pdf(pdf)


def test_upload_missing_pdf_id_raises(client, tmp_path: Path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF\n")
    with patch("mathpix_client.requests.post") as mock_post:
        mock_post.return_value = _mock_response(200, {"unexpected": True})
        with pytest.raises(MathpixError):
            client.upload_pdf(pdf)


def test_get_status(client):
    with patch("mathpix_client.requests.get") as mock_get:
        mock_get.return_value = _mock_response(200, {"status": "completed"})
        s = client.get_status("pid")
    assert s == {"status": "completed"}
    mock_get.assert_called_once()
    assert mock_get.call_args.args[0] == f"{API_BASE}/pdf/pid"


def test_wait_until_done_polls_then_completes(client):
    responses = [
        _mock_response(200, {"status": "split"}),
        _mock_response(200, {"status": "processing", "percent_done": 50}),
        _mock_response(200, {"status": "completed"}),
    ]
    with patch("mathpix_client.requests.get", side_effect=responses), patch(
        "mathpix_client.time.sleep"
    ) as sleep:
        s = client.wait_until_done("pid", interval=0.01)
    assert s["status"] == "completed"
    assert sleep.call_count >= 2


def test_wait_until_done_error_raises(client):
    with patch(
        "mathpix_client.requests.get",
        return_value=_mock_response(200, {"status": "error", "error": "bad"}),
    ):
        with pytest.raises(MathpixError):
            client.wait_until_done("pid", interval=0.01)


def test_wait_until_done_timeout(client):
    with patch(
        "mathpix_client.requests.get",
        return_value=_mock_response(200, {"status": "processing"}),
    ), patch("mathpix_client.time.sleep"):
        with pytest.raises(MathpixError):
            client.wait_until_done("pid", timeout=0.0, interval=0.01)


def test_download_writes_file(client, tmp_path: Path):
    dest = tmp_path / "sub" / "out.tex.zip"
    payload = b"ZIP_BYTES"
    with patch("mathpix_client.requests.get") as mock_get:
        mock_get.return_value = _mock_response(200, content=payload)
        result = client.download("pid", "tex.zip", dest)
    assert result == dest
    assert dest.read_bytes() == payload
    assert mock_get.call_args.args[0] == f"{API_BASE}/pdf/pid.tex.zip"


def test_download_http_error_raises(client, tmp_path: Path):
    dest = tmp_path / "out.zip"
    with patch("mathpix_client.requests.get") as mock_get:
        mock_get.return_value = _mock_response(404)
        with pytest.raises(MathpixError):
            client.download("pid", "tex.zip", dest)

"""Thin wrapper around the Mathpix PDF API.

Docs: https://docs.mathpix.com/#process-a-pdf
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

API_BASE = "https://api.mathpix.com/v3"

DEFAULT_CONVERSION_FORMATS = {
    "tex.zip": True,
    "md": True,
    "docx": True,
}

DEFAULT_OPTIONS: dict[str, Any] = {
    "conversion_formats": DEFAULT_CONVERSION_FORMATS,
    "math_inline_delimiters": ["$", "$"],
    "math_display_delimiters": ["$$", "$$"],
    "rm_spaces": True,
    "enable_tables_fallback": True,
}


class MathpixError(RuntimeError):
    pass


class MathpixClient:
    def __init__(self, app_id: str | None = None, app_key: str | None = None):
        self.app_id = app_id or os.environ.get("MATHPIX_APP_ID")
        self.app_key = app_key or os.environ.get("MATHPIX_APP_KEY")
        if not self.app_id or not self.app_key:
            raise MathpixError(
                "MATHPIX_APP_ID and MATHPIX_APP_KEY must be set (env or constructor)."
            )

    @property
    def _headers(self) -> dict[str, str]:
        return {"app_id": self.app_id, "app_key": self.app_key}

    def upload_pdf(self, pdf_path: Path, options: dict[str, Any] | None = None) -> str:
        opts = options or DEFAULT_OPTIONS
        with open(pdf_path, "rb") as f:
            r = requests.post(
                f"{API_BASE}/pdf",
                headers=self._headers,
                data={"options_json": json.dumps(opts)},
                files={"file": (pdf_path.name, f, "application/pdf")},
                timeout=120,
            )
        if not r.ok:
            raise MathpixError(f"upload failed ({r.status_code}): {r.text}")
        body = r.json()
        pdf_id = body.get("pdf_id")
        if not pdf_id:
            raise MathpixError(f"upload response missing pdf_id: {body}")
        return pdf_id

    def get_status(self, pdf_id: str) -> dict[str, Any]:
        r = requests.get(
            f"{API_BASE}/pdf/{pdf_id}", headers=self._headers, timeout=30
        )
        if not r.ok:
            raise MathpixError(f"status failed ({r.status_code}): {r.text}")
        return r.json()

    def wait_until_done(
        self,
        pdf_id: str,
        timeout: float = 600.0,
        interval: float = 2.0,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.get_status(pdf_id)
            state = status.get("status")
            if state == "completed":
                return status
            if state == "error":
                raise MathpixError(f"Mathpix reported error: {status}")
            time.sleep(interval)
        raise MathpixError(f"Mathpix timed out after {timeout}s (pdf_id={pdf_id})")

    def download(self, pdf_id: str, fmt: str, dest: Path) -> Path:
        """Download a converted artifact.

        fmt examples: "tex.zip", "md", "docx", "html", "mmd", "lines.json"
        """
        url = f"{API_BASE}/pdf/{pdf_id}.{fmt}"
        r = requests.get(url, headers=self._headers, timeout=120)
        if not r.ok:
            raise MathpixError(f"download {fmt} failed ({r.status_code}): {r.text}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return dest

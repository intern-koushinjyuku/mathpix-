"""Celery tasks for PDF -> Mathpix processing."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from celery_app import celery_app
from mathpix_client import MathpixClient, MathpixError

POLL_INTERVAL = 2.0


@celery_app.task(bind=True, name="tasks.process_pdf")
def process_pdf(self, tmp_path: str, options: dict[str, Any], original_name: str) -> dict[str, Any]:
    """Upload a PDF to Mathpix and poll until conversion completes.

    Returns a dict containing the Mathpix pdf_id and original filename
    (without extension). The actual artifact is fetched on-demand by the
    /download endpoint so any output format can be served.
    """
    tmp = Path(tmp_path)
    client = MathpixClient()
    self.update_state(state="PROGRESS", meta={"stage": "uploading", "percent": 0})
    try:
        pdf_id = client.upload_pdf(tmp, options=options)
        while True:
            s = client.get_status(pdf_id)
            state = s.get("status")
            pct = s.get("percent_done") or 0
            self.update_state(
                state="PROGRESS",
                meta={"stage": state, "percent": pct, "pdf_id": pdf_id},
            )
            if state == "completed":
                return {"pdf_id": pdf_id, "name": original_name}
            if state == "error":
                raise MathpixError(f"Mathpix reported error: {s}")
            time.sleep(POLL_INTERVAL)
    finally:
        tmp.unlink(missing_ok=True)

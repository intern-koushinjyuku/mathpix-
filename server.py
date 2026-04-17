"""FastAPI server: upload PDF -> Celery -> Mathpix -> download."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from celery.result import AsyncResult
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from celery_app import celery_app
from mathpix_client import DEFAULT_CONVERSION_FORMATS, MathpixClient, MathpixError
from tasks import process_pdf

load_dotenv()

ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / "outputs"
UPLOAD_DIR = ROOT / "uploads"
OUTPUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_FORMATS = {"tex.zip", "docx", "md", "html", "mmd"}

app = FastAPI(title="PDF -> Mathpix -> ZIP")
templates = Jinja2Templates(directory=str(ROOT / "templates"))


def get_client() -> MathpixClient:
    try:
        return MathpixClient()
    except MathpixError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    rm_spaces: bool = Form(True),
    math_inline: str = Form("$"),
    numbers_default_to_math: bool = Form(False),
    include_line_data: bool = Form(False),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDFファイルをアップロードしてください。")

    inline_map = {"$": ["$", "$"], "paren": ["\\(", "\\)"]}
    display_map = {"$": ["$$", "$$"], "paren": ["\\[", "\\]"]}
    if math_inline not in inline_map:
        raise HTTPException(status_code=400, detail=f"未対応の math_inline: {math_inline}")

    options = {
        "conversion_formats": DEFAULT_CONVERSION_FORMATS,
        "math_inline_delimiters": inline_map[math_inline],
        "math_display_delimiters": display_map[math_inline],
        "rm_spaces": rm_spaces,
        "numbers_default_to_math": numbers_default_to_math,
        "include_line_data": include_line_data,
        "enable_tables_fallback": True,
    }

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=str(UPLOAD_DIR)) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    original_name = Path(file.filename).stem
    async_result = process_pdf.delay(str(tmp_path), options, original_name)
    return {"task_id": async_result.id, "filename": file.filename}


@app.get("/status/{task_id}")
async def status(task_id: str):
    res: AsyncResult = AsyncResult(task_id, app=celery_app)
    info = res.info if isinstance(res.info, dict) else {}
    payload = {
        "task_id": task_id,
        "state": res.state,
        "percent": info.get("percent", 0),
        "stage": info.get("stage"),
        "pdf_id": info.get("pdf_id"),
    }
    if res.state == "FAILURE":
        payload["error"] = str(res.info)
    elif res.state == "SUCCESS":
        result = res.result or {}
        payload["pdf_id"] = result.get("pdf_id")
        payload["percent"] = 100
        payload["stage"] = "completed"
    return payload


@app.get("/download/{task_id}")
async def download(task_id: str, fmt: str = "tex.zip"):
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"未対応のフォーマット: {fmt}")

    res: AsyncResult = AsyncResult(task_id, app=celery_app)
    if res.state != "SUCCESS":
        raise HTTPException(
            status_code=409, detail=f"まだ処理中 or 失敗しています (state={res.state})"
        )
    result = res.result or {}
    pdf_id = result.get("pdf_id")
    base = result.get("name") or pdf_id or task_id
    if not pdf_id:
        raise HTTPException(status_code=500, detail="pdf_id が見つかりません")

    dest = OUTPUT_DIR / f"{base}.{fmt}"
    if not dest.exists():
        client = get_client()
        try:
            client.download(pdf_id, fmt, dest)
        except MathpixError as e:
            raise HTTPException(status_code=502, detail=str(e))

    media_type = "application/zip" if fmt.endswith("zip") else "application/octet-stream"
    return FileResponse(dest, filename=dest.name, media_type=media_type)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)

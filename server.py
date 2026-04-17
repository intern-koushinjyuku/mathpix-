"""FastAPI server: upload PDF -> Mathpix -> download ZIP (with figures)."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

from mathpix_client import MathpixClient, MathpixError

load_dotenv()

ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="PDF -> Mathpix -> ZIP")
templates = Jinja2Templates(directory=str(ROOT / "templates"))


def get_client() -> MathpixClient:
    try:
        return MathpixClient()
    except MathpixError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDFファイルをアップロードしてください。")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        client = get_client()
        pdf_id = client.upload_pdf(tmp_path)
    except MathpixError as e:
        raise HTTPException(status_code=502, detail=f"Mathpixアップロード失敗: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

    original_name = Path(file.filename).stem
    (OUTPUT_DIR / f"{pdf_id}.name").write_text(original_name, encoding="utf-8")
    return {"pdf_id": pdf_id, "filename": file.filename}


@app.get("/status/{pdf_id}")
async def status(pdf_id: str):
    client = get_client()
    try:
        s = client.get_status(pdf_id)
    except MathpixError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {
        "status": s.get("status"),
        "percent_done": s.get("percent_done"),
        "num_pages": s.get("num_pages"),
        "num_pages_completed": s.get("num_pages_completed"),
    }


@app.get("/download/{pdf_id}")
async def download(pdf_id: str, fmt: str = "tex.zip"):
    if fmt not in {"tex.zip", "docx", "md", "html", "mmd"}:
        raise HTTPException(status_code=400, detail=f"未対応のフォーマット: {fmt}")

    name_file = OUTPUT_DIR / f"{pdf_id}.name"
    base = name_file.read_text(encoding="utf-8").strip() if name_file.exists() else pdf_id

    ext = fmt  # e.g. "tex.zip", "docx"
    dest = OUTPUT_DIR / f"{base}.{ext}"

    client = get_client()
    try:
        s = client.get_status(pdf_id)
        if s.get("status") != "completed":
            raise HTTPException(
                status_code=409,
                detail=f"まだ処理中です (status={s.get('status')})",
            )
        client.download(pdf_id, fmt, dest)
    except MathpixError as e:
        raise HTTPException(status_code=502, detail=str(e))

    media_type = "application/zip" if fmt.endswith("zip") else "application/octet-stream"
    return FileResponse(dest, filename=dest.name, media_type=media_type)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)

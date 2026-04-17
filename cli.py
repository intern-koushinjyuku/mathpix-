"""CLI for batch-converting PDFs via the Mathpix PDF API.

Usage:
    python cli.py input.pdf                 # -> outputs/input.tex.zip
    python cli.py *.pdf --fmt docx          # batch, DOCX output
    python cli.py a.pdf --fmt md -o ./out
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from mathpix_client import MathpixClient, MathpixError

ALLOWED_FORMATS = ("tex.zip", "docx", "md", "html", "mmd")


def convert_one(client: MathpixClient, pdf: Path, fmt: str, out_dir: Path) -> Path:
    print(f"[{pdf.name}] uploading...", flush=True)
    pdf_id = client.upload_pdf(pdf)
    print(f"[{pdf.name}] pdf_id={pdf_id}, waiting...", flush=True)

    last_pct = -1
    while True:
        status = client.get_status(pdf_id)
        state = status.get("status")
        pct = status.get("percent_done", 0)
        if pct != last_pct:
            print(f"[{pdf.name}] {state} {pct}%", flush=True)
            last_pct = pct
        if state == "completed":
            break
        if state == "error":
            raise MathpixError(f"Mathpix error: {status}")
        import time
        time.sleep(2.0)

    dest = out_dir / f"{pdf.stem}.{fmt}"
    client.download(pdf_id, fmt, dest)
    print(f"[{pdf.name}] saved -> {dest}", flush=True)
    return dest


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="PDF -> Mathpix -> file")
    parser.add_argument("pdfs", nargs="+", type=Path, help="PDFファイル(複数可)")
    parser.add_argument(
        "--fmt",
        default="tex.zip",
        choices=ALLOWED_FORMATS,
        help="出力フォーマット (default: tex.zip = 図版入りLaTeX)",
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("outputs"),
        help="出力ディレクトリ (default: ./outputs)",
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    try:
        client = MathpixClient()
    except MathpixError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    exit_code = 0
    for pdf in args.pdfs:
        if not pdf.exists():
            print(f"SKIP: {pdf} not found", file=sys.stderr)
            exit_code = 1
            continue
        try:
            convert_one(client, pdf, args.fmt, args.out)
        except MathpixError as e:
            print(f"FAIL [{pdf.name}]: {e}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

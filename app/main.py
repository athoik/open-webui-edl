"""
External Document Loader for Open-WebUI
Wraps Docling with image extraction → Azure Blob Storage upload.

PUT /process  →  { page_content: str, metadata: dict }
"""

import logging
import os
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import JSONResponse

from app.config import settings
from app.docling_client import fetch_markdown_with_images
from app.image_processor import replace_images_with_blob_urls
from app.text_processor import processor as text_processor

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(
    title="Docling Image Loader",
    description="Open-WebUI external document loader that extracts images to Azure Blob Storage",
    version="1.0.0",
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.put("/process")
async def process_document(
    request: Request,
    authorization: str | None = Header(default=None),
    content_type: str | None = Header(default=None),
    x_filename: str | None = Header(default=None),
):
    # ── Auth ──────────────────────────────────────────────────────────────────
    if settings.api_key:
        if not authorization or authorization != f"Bearer {settings.api_key}":
            raise HTTPException(status_code=401, detail="Unauthorized")

    # ── Read body ─────────────────────────────────────────────────────────────
    file_bytes = await request.body()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty request body")

    filename = unquote(x_filename) if x_filename else "document"
    mime_type = content_type or "application/octet-stream"

    log.info("Processing '%s' (%s, %d bytes)", filename, mime_type, len(file_bytes))

    # ── Call Docling (embedded images) ────────────────────────────────────────
    try:
        raw_markdown = await fetch_markdown_with_images(
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type,
        )
    except Exception as exc:
        log.error("Docling error: %s", exc)
        raise HTTPException(status_code=502, detail=f"Docling error: {exc}")

    # ── Extract base64 images → Azure Blob URLs ───────────────────────────────
    try:
        clean_markdown, image_count = await replace_images_with_blob_urls(raw_markdown)
    except Exception as exc:
        log.error("Image processing error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Image processing error: {exc}")

    log.info("Done. Replaced %d image(s) with blob URLs.", image_count)

    # ── Post-process text (clean banners, footers, whitespace, etc.) ──────────
    clean_markdown = text_processor.process(clean_markdown)

    metadata: dict = {"source": filename}
    if mime_type:
        metadata["Content-Type"] = mime_type

    return JSONResponse(
        content={
            "page_content": clean_markdown,
            "metadata": metadata,
        }
    )

"""
Production-ready FastAPI server for invoice extraction (Gemini-only mode).

Design decisions:
- Gemini Vision API is the primary and ONLY extraction engine in cloud.
- Local OCR (pytesseract) and multipage parsers are intentionally disabled
  to avoid native dependency issues on Render.
- Barcode extraction is optional, safe, and non-fatal.
- App must NEVER fail at startup due to missing native libraries.

Endpoints:
- GET  /         : health check
- POST /convert  : upload PDF/image -> JSON invoice
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from typing import List
import os
import json
from io import BytesIO
import logging

app = FastAPI(title="Invoice Conversion API")
logger = logging.getLogger("invoice_api")


# -------------------------------------------------------------------
# Optional, SAFE barcode extraction (QR only if OpenCV exists)
# -------------------------------------------------------------------
def _safe_extract_barcodes(images: List[bytes]) -> List[dict]:
    """
    Optional barcode extraction.
    - Render-safe: returns [] if OpenCV is unavailable.
    - Does NOT raise errors.
    """
    try:
        import cv2
        import numpy as np

        results = []
        detector = cv2.QRCodeDetector()

        for b in images:
            img = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue
            data, _, _ = detector.detectAndDecode(img)
            if data:
                results.append({
                    "type": "QR",
                    "value": data,
                    "confidence": 1.0
                })
        return results
    except Exception:
        return []


# -------------------------------------------------------------------
# PDF -> image conversion (lazy, Render-safe)
# -------------------------------------------------------------------
def _convert_pdf_to_images_bytes(pdf_bytes: bytes, dpi: int = 300) -> List[bytes] | None:
    try:
        from pdf2image import convert_from_bytes

        pages = convert_from_bytes(pdf_bytes, dpi=dpi)
        images = []

        for page in pages:
            buf = BytesIO()
            page.save(buf, format="JPEG")
            images.append(buf.getvalue())

        return images
    except Exception as e:
        logger.warning("PDF to image conversion failed: %s", e)
        return None


# -------------------------------------------------------------------
# Gemini extraction (ONLY engine used)
# -------------------------------------------------------------------
def _extract_with_gemini(images: List[bytes]) -> dict | None:
    if not os.getenv("GEMINI_API_KEY"):
        return None

    try:
        from invoice_engine.vision_llm_gemini import extract_invoice_with_gemini

        return extract_invoice_with_gemini(images)
    except Exception as e:
        logger.exception("Gemini extraction failed: %s", e)
        return None


# -------------------------------------------------------------------
# Health check
# -------------------------------------------------------------------
@app.get("/")
def health():
    return {
        "status": "Invoice API running",
        "endpoint": "/convert",
        "method": "POST"
    }


# -------------------------------------------------------------------
# Convert endpoint
# -------------------------------------------------------------------
@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    """
    Accept a PDF or image and return structured invoice JSON.

    Rules:
    - Gemini Vision is REQUIRED.
    - If Gemini fails, return NEEDS_REVIEW.
    - No local OCR fallback in cloud.
    """
    try:
        content = await file.read()
        filename = file.filename or "upload"
        suffix = filename.lower().split(".")[-1]

        images: List[bytes] = []

        # PDF handling
        if suffix == "pdf":
            images = _convert_pdf_to_images_bytes(content, dpi=300) or []
            if not images:
                return JSONResponse(
                    content={
                        "status": "NEEDS_REVIEW",
                        "reason": "pdf_to_image_failed"
                    }
                )
        else:
            images = [content]

        # Optional barcode extraction
        codes = _safe_extract_barcodes(images)

        # Gemini extraction (MANDATORY)
        result = _extract_with_gemini(images)
        if result is None:
            return JSONResponse(
                content={
                    "status": "NEEDS_REVIEW",
                    "reason": "gemini_extraction_failed",
                    "codes": codes
                }
            )

        # Normalize Gemini response
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                result = {
                    "status": "NEEDS_REVIEW",
                    "raw_text": result,
                    "codes": codes
                }

        if isinstance(result, dict):
            result.setdefault("codes", codes)
        else:
            result = {
                "status": "NEEDS_REVIEW",
                "raw_response": str(result),
                "codes": codes
            }

        return JSONResponse(content=result)

    except Exception as e:
        logger.exception("Unhandled error in /convert: %s", e)
        raise HTTPException(status_code=500, detail="internal_server_error")

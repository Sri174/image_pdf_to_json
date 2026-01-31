from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
"""
Production-ready FastAPI server for invoice extraction.

Design decisions (brief):
- Avoid heavy/native imports at module import time to ensure the app never
  fails at startup on platforms (like Render) that may lack native libraries.
- Barcode extraction is optional and modular; by default it returns an
  empty list so the service is Render-safe. Extensions can add OpenCV or
  cloud-based barcode extraction without changing core code.
- Gemini Vision is used when `GEMINI_API_KEY` is present; otherwise the
  app falls back to local OCR. All external integrations are attempted
  lazily and errors are caught and returned as structured JSON.

Endpoints:
- GET /        : health check
- POST /convert: multipart/form-data upload (file) -> JSON invoice

"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import List, Optional
import os
import json
import tempfile
from io import BytesIO
import logging

app = FastAPI(title="Invoice Conversion API")
logger = logging.getLogger("invoice_api")


@app.get("/")
def health():
    return {"status": "Invoice API running", "endpoint": "/convert", "method": "POST"}


def _safe_extract_barcodes(images: List[bytes]) -> List[dict]:
    """Attempt barcode extraction using optional libraries.

    - This function performs dynamic imports and will return an empty list
      if no safe barcode provider is available. Do not raise on missing
      native libs.
    - Current default: return [] (Render-safe). Later this can try
      OpenCV QRCodeDetector or call an external microservice.
    """
    try:
        # Example optional OpenCV-based QR detection (only if installed)
        import cv2

        results = []
        qr = cv2.QRCodeDetector()
        for b in images:
            arr = None
            try:
                import numpy as np

                arr = np.frombuffer(b, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is None:
                    continue
                data, points, _ = qr.detectAndDecode(img)
                if data:
                    results.append({"type": "QR", "value": data, "confidence": 1.0})
            except Exception:
                continue
        return results
    except Exception:
        # No optional barcode libs available — return empty list (safe)
        return []


def _convert_pdf_to_images_bytes(pdf_bytes: bytes, dpi: int = 300) -> Optional[List[bytes]]:
    """Try to convert PDF bytes to a list of JPEG-encoded page bytes.

    This function attempts `pdf2image.convert_from_bytes` lazily. If the
    conversion is not possible (missing poppler or pdf2image), it returns
    None and the caller can fall back to text-based extraction.
    """
    try:
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(pdf_bytes, dpi=dpi)
        out = []
        for page in images:
            buf = BytesIO()
            page.save(buf, format="JPEG")
            out.append(buf.getvalue())
        return out
    except Exception as e:
        logger.warning("PDF->image conversion unavailable or failed: %s", e)
        return None


def _use_gemini_if_available(images: List[bytes]) -> Optional[dict]:
    """Call Gemini Vision path if `GEMINI_API_KEY` is present.

    Errors are caught and None returned on failure so callers can fallback.
    """
    if not os.getenv("GEMINI_API_KEY"):
        return None
    try:
        from invoice_engine.vision_llm_gemini import extract_invoice_with_gemini

        return extract_invoice_with_gemini(images)
    except Exception as e:
        logger.exception("Gemini extraction failed: %s", e)
        return None


def _local_extraction_from_image(image_bytes: bytes, lang: Optional[str] = None) -> dict:
    """Fallback local OCR-based extraction.

    This imports local extraction functions lazily to avoid startup-time
    failures when optional packages (like pytesseract) are missing.
    """
    try:
        from invoice_engine.local_extraction import local_extract_invoice

        return local_extract_invoice(image_bytes, lang=lang)
    except Exception as e:
        logger.exception("Local extraction failed: %s", e)
        return {"status": "NEEDS_REVIEW", "error": "local_extraction_failed", "error_detail": str(e)}


def _local_multipage_extraction(pdf_path: str) -> dict:
    try:
        from invoice_engine.multipage_parser import parse_multipage_invoice

        return parse_multipage_invoice(pdf_path)
    except Exception as e:
        logger.exception("Multipage extraction failed: %s", e)
        return {"status": "NEEDS_REVIEW", "error": "multipage_extraction_failed", "error_detail": str(e)}

@app.get("/")
def health():
    return {
        "status": "Invoice API running",
        "endpoint": "/convert",
        "method": "POST"
    }


@app.post("/convert")
async def convert(file: UploadFile = File(...), request: Request = None):
    """Accept a PDF/image file and return structured invoice JSON.

    Behavior:
    - If PDF: try to convert to images (dpi=300). If conversion is unavailable,
      fall back to multipage/text extraction when possible.
    - If `GEMINI_API_KEY` present: prefer Gemini vision API.
    - Always keep barcode extraction optional and non-fatal.
    """
    try:
        content = await file.read()
        filename = file.filename or "upload"
        suffix = os.path.splitext(filename)[1].lower()

        page_bytes = None
        page_bytes_list = None

        if suffix == ".pdf":
            page_bytes_list = _convert_pdf_to_images_bytes(content, dpi=300)
            # If conversion failed, try multipage parser path later
            if page_bytes_list:
                page_bytes = page_bytes_list[0]
        else:
            page_bytes = content

        # Barcode extraction (optional and safe)
        try:
            barcode_list = _safe_extract_barcodes(page_bytes_list if page_bytes_list else ([page_bytes] if page_bytes else []))
        except Exception:
            barcode_list = []

        # Prefer Gemini when available
        result_json = None
        if (page_bytes_list or page_bytes) and os.getenv("GEMINI_API_KEY"):
            imgs = page_bytes_list if page_bytes_list else [page_bytes]
            try:
                result_json = _use_gemini_if_available(imgs)
            except Exception:
                result_json = None

        # Local extraction fallback
        if result_json is None:
            if suffix == ".pdf":
                # If we have page images, use multipage/local logic; otherwise write temp PDF and try multipage parser
                if page_bytes_list:
                    # Use first page local OCR for a quick pass
                    result_json = _local_extraction_from_image(page_bytes_list[0])
                else:
                    # write temp pdf and call multipage parser
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
                            tf.write(content)
                            tmp_path = tf.name
                        result_json = _local_multipage_extraction(tmp_path)
                    finally:
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
            else:
                result_json = _local_extraction_from_image(page_bytes)

        # Normalize response and ensure barcode field present
        if isinstance(result_json, str):
            try:
                result_json = json.loads(result_json)
            except Exception:
                result_json = {"status": "NEEDS_REVIEW", "raw_text": result_json}

        if isinstance(result_json, dict):
            result_json.setdefault("codes", barcode_list)
        else:
            result_json = {"status": "NEEDS_REVIEW", "raw_response": str(result_json), "codes": barcode_list}

        return JSONResponse(content=result_json)

    except Exception as e:
        logger.exception("Unhandled error in /convert: %s", e)
        raise HTTPException(status_code=500, detail="internal_server_error")

        raise HTTPException(status_code=500, detail=str(e))

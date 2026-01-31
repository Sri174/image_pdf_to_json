from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os
import json
import tempfile
from io import BytesIO

from invoice_engine.barcode_extraction import extract_codes_from_images
from invoice_engine.local_extraction import local_extract_invoice
from invoice_engine.multipage_parser import parse_multipage_invoice
from PIL import Image
import cv2
import numpy as np

app = FastAPI(title="Invoice Conversion API")

@app.get("/")
def health():
    return {
        "status": "Invoice API running",
        "endpoint": "/convert",
        "method": "POST"
    }


@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    """Accept a PDF or image upload and return the converted invoice JSON.

    - Supports PDF and common image formats.
    - Prefers Gemini if `GEMINI_API_KEY` is present, otherwise falls back to local extraction.
    """
    try:
        content = await file.read()
        suffix = os.path.splitext(file.filename or "")[1].lower()

        page_bytes_list = None
        # Convert PDF to images when necessary (use higher DPI)
        if suffix == ".pdf":
            try:
                from pdf2image import convert_from_bytes

                images = convert_from_bytes(content, dpi=300)
                page_bytes_list = []
                for page in images:
                    buf = BytesIO()
                    page.save(buf, format="JPEG")
                    page_bytes_list.append(buf.getvalue())
                image_bytes = page_bytes_list[0] if page_bytes_list else b""
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"PDF->image conversion failed: {e}")
        else:
            image_bytes = content

        def preprocess_image_bytes(img_bytes):
            try:
                arr = np.frombuffer(img_bytes, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is None:
                    # fallback via PIL
                    pil = Image.open(BytesIO(img_bytes)).convert("RGB")
                    arr = np.array(pil)[:, :, ::-1].copy()
                    img = arr

                # convert to grayscale
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                # denoise
                den = cv2.fastNlMeansDenoising(gray, None, h=10)
                # adaptive threshold
                th = cv2.adaptiveThreshold(den, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

                # optional deskew: compute moments / angle
                coords = np.column_stack(np.where(th > 0))
                if coords.shape[0] > 0:
                    rect = cv2.minAreaRect(coords)
                    angle = rect[-1]
                    if angle < -45:
                        angle = -(90 + angle)
                    else:
                        angle = -angle
                    if abs(angle) > 0.1:
                        (h, w) = th.shape
                        center = (w // 2, h // 2)
                        M = cv2.getRotationMatrix2D(center, angle, 1.0)
                        th = cv2.warpAffine(th, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

                # encode back to JPEG bytes
                ok, enc = cv2.imencode('.jpg', th)
                if ok:
                    return enc.tobytes()
            except Exception:
                pass
            return img_bytes

        # Preprocess pages/images to improve OCR
        if page_bytes_list:
            page_bytes_list = [preprocess_image_bytes(b) for b in page_bytes_list]
            image_bytes = page_bytes_list[0] if page_bytes_list else image_bytes
        else:
            image_bytes = preprocess_image_bytes(image_bytes)

        # Extract barcodes deterministically
        try:
            codes = extract_codes_from_images(page_bytes_list if page_bytes_list else [image_bytes])
        except Exception:
            codes = []

        result_json = None
        prefer_gemini = bool(os.getenv("GEMINI_API_KEY"))
        if prefer_gemini:
            try:
                from invoice_engine.vision_llm_gemini import extract_invoice_with_gemini

                gemini_images = page_bytes_list if page_bytes_list else [image_bytes]
                result_json = extract_invoice_with_gemini(gemini_images)
            except Exception:
                result_json = None

        if result_json is None:
            try:
                if page_bytes_list and len(page_bytes_list) > 1:
                    # parse_multipage_invoice expects a file path, write a temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
                        tf.write(content)
                        tmp_path = tf.name
                    try:
                        result_json = parse_multipage_invoice(tmp_path)
                    finally:
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                else:
                    result_json = local_extract_invoice(image_bytes, lang=None)
            except Exception as e:
                result_json = {"status": "NEEDS_REVIEW", "error": str(e), "codes": codes}

        # Normalize result
        if isinstance(result_json, str):
            try:
                result_json = json.loads(result_json)
            except Exception:
                result_json = {"status": "NEEDS_REVIEW", "raw_text": result_json}

        if isinstance(result_json, dict):
            result_json.setdefault("codes", codes)
        else:
            result_json = {"status": "NEEDS_REVIEW", "raw_response": str(result_json), "codes": codes}

        return JSONResponse(content=result_json)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

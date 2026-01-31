from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os
import json
import tempfile
from io import BytesIO

from invoice_engine.barcode_extraction import extract_codes_from_images
from invoice_engine.local_extraction import local_extract_invoice
from invoice_engine.multipage_parser import parse_multipage_invoice

app = FastAPI(title="Invoice Conversion API")


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
        # Convert PDF to images when necessary
        if suffix == ".pdf":
            try:
                from pdf2image import convert_from_bytes

                images = convert_from_bytes(content)
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

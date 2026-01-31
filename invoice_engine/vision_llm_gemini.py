# invoice_engine/vision_llm_gemini.py
# Gemini Vision invoice extraction (API-key only, Render-safe)

import requests
import json
import base64
import os
from typing import List, Union

# ✅ CORRECT Gemini Vision model
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1/models/"
    "gemini-1.5-flash:generateContent"
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


SYSTEM_PROMPT = (
    "You are an AI specialized in understanding invoice documents. "
    "Return ONLY a valid JSON object that exactly matches the schema below. "
    "Do not include explanations, markdown, or extra text. "
    "If a value is missing, return null or empty string. "
    "STRICTLY FOLLOW THE SCHEMA."
)

USER_PROMPT = "Analyze the invoice image(s) and return JSON using this schema."

with open("invoice_engine/universal_schema.json", "r") as f:
    UNIVERSAL_SCHEMA = f.read()


def extract_invoice_with_gemini(image_bytes: Union[bytes, List[bytes]]) -> dict:
    if not GEMINI_API_KEY:
        return {
            "status": "ERROR",
            "reason": "GEMINI_API_KEY_NOT_FOUND"
        }

    images = image_bytes if isinstance(image_bytes, list) else [image_bytes]

    parts = [
        {
            "text": SYSTEM_PROMPT + "\n\n" + USER_PROMPT + "\n\n" + UNIVERSAL_SCHEMA
        }
    ]

    for img in images:
        img_b64 = base64.b64encode(img).decode("utf-8")
        parts.append(
            {
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_b64,
                }
            }
        )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ]
    }

    try:
        response = requests.post(
            GEMINI_API_URL,
            params={"key": GEMINI_API_KEY},
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=90,
        )
    except Exception as e:
        return {
            "status": "NEEDS_REVIEW",
            "reason": "gemini_request_failed",
            "error": str(e),
        }

    if response.status_code != 200:
        return {
            "status": "NEEDS_REVIEW",
            "reason": "gemini_http_error",
            "http_status": response.status_code,
            "raw_response": response.text,
        }

    try:
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return {
            "status": "NEEDS_REVIEW",
            "reason": "gemini_response_parse_failed",
            "raw_response": response.text,
        }

    # Strip code fences if Gemini adds them
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except Exception as e:
        return {
            "status": "NEEDS_REVIEW",
            "reason": "json_parse_failed",
            "error": str(e),
            "raw_text": text,
        }

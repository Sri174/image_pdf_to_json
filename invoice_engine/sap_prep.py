"""
sap_prep.py
------------
SAP payload preparation logic.
- Prepares validated JSON and attachment metadata
- Sets upload status
"""

import hashlib
import os
from typing import Dict, Any

def compute_file_hash(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def prepare_sap_payload(invoice_json: Dict[str, Any], file_path: str, status: str) -> dict:
    file_name = os.path.basename(file_path)
    file_type = os.path.splitext(file_name)[1].lstrip('.')
    file_hash = compute_file_hash(file_path)
    return {
        "invoice": invoice_json,
        "attachment": {
            "file_name": file_name,
            "file_type": file_type,
            "file_hash": file_hash
        },
        "status": status
    }

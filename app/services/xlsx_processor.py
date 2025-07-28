# app/services/xlsx_processor.py

import os
import json
from cryptography.fernet import Fernet
from openpyxl import load_workbook
from app.services.pii_main import extract_all_pii

def mask_xlsx_sensitive_text(xlsx_path: str, key_path: str = None):
    if key_path is None:
        key_path = xlsx_path.replace(".xlsx", ".key")

    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)

    fernet = Fernet(key)
    wb = load_workbook(xlsx_path)
    masked_pii = []

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    for ent in extract_all_pii(cell.value):
                        encrypted = fernet.encrypt(ent["entity"].encode()).decode()
                        masked = f"[ENC:{ent['label']}]"
                        cell.value = cell.value.replace(ent["entity"], masked)
                        masked_pii.append({
                            "original": ent["entity"],
                            "encrypted": encrypted,
                            "label": ent["label"],
                            "masked": masked
                        })

    masked_path = xlsx_path.replace(".xlsx", ".masked.xlsx")
    wb.save(masked_path)

    json_path = xlsx_path.replace(".xlsx", ".masked.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(masked_pii, f, ensure_ascii=False, indent=2)

    return masked_path, json_path, key_path

def run_xlsx_processing(xlsx_path: str):
    try:
        key_path = xlsx_path.replace(".xlsx", ".key")
        masked_xlsx, json_path, key_file = mask_xlsx_sensitive_text(
            xlsx_path, key_path
        )
        return {
            "status": "success",
            "masked_xlsx": masked_xlsx,
            "json_output": json_path,
            "key_file": key_file
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

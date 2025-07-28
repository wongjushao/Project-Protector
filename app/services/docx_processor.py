# app/services/docx_processor.py

import os
import json
from cryptography.fernet import Fernet
from docx import Document
from app.services.pii_main import extract_all_pii

def mask_docx_sensitive_text(docx_path: str, key_path: str = None):
    if key_path is None:
        key_path = docx_path.replace(".docx", ".key")

    # 加载或生成密钥
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)

    fernet = Fernet(key)
    document = Document(docx_path)
    masked_pii = []
    
    for para in document.paragraphs:
        for ent in extract_all_pii(para.text):
            encrypted = fernet.encrypt(ent["entity"].encode()).decode()
            masked = f"[ENC:{ent['label']}]"
            para.text = para.text.replace(ent["entity"], masked)
            masked_pii.append({
                "original": ent["entity"],
                "encrypted": encrypted,
                "label": ent["label"],
                "masked": masked
            })

    # 输出文件
    masked_path = docx_path.replace(".docx", ".masked.docx")
    document.save(masked_path)

    json_path = docx_path.replace(".docx", ".masked.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(masked_pii, f, ensure_ascii=False, indent=2)

    return masked_path, json_path, key_path

def run_docx_processing(docx_path: str):
    try:
        key_path = docx_path.replace(".docx", ".key")
        masked_docx, json_path, key_file = mask_docx_sensitive_text(
            docx_path, key_path
        )
        return {
            "status": "success",
            "masked_docx": masked_docx,
            "json_output": json_path,
            "key_file": key_file
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

from docx import Document
import base64
import json

def decrypt_masked_docx(masked_path: str, json_path: str, key_path: str):
    from cryptography.fernet import Fernet

    with open(key_path, "rb") as f:
        key = f.read()
    fernet = Fernet(key)

    with open(json_path, "r", encoding="utf-8") as f:
        masked_info = json.load(f)

    document = Document(masked_path)

    # Create a mapping from masked tags to original text
    tag_to_original = {entry["masked"]: entry["original"] for entry in masked_info}

    for para in document.paragraphs:
        para_text = para.text
        # Replace all masked tags with original text
        for masked_tag, original_text in tag_to_original.items():
            para_text = para_text.replace(masked_tag, original_text)
        para.text = para_text

    decrypted_path = masked_path.replace(".masked.docx", ".decrypted.docx")
    document.save(decrypted_path)
    return {
        "status": "success",
        "decrypted_file": decrypted_path
    }

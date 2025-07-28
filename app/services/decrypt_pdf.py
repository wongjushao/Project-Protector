import os
import tempfile
from pdf2image import convert_from_path
from scipy import io
from app.services.decrypt_jpeg import decrypt_masked_image_to_bytes
from PIL import Image
import re

def decrypt_masked_pdf(masked_pdf_path: str, json_path: str, key_path: str):
    temp_dir = tempfile.mkdtemp()
    output_dir = os.path.join(temp_dir, "decrypted_pages")
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: PDF → Images
    try:
        pages = convert_from_path(masked_pdf_path, dpi=150)
    except Exception as e:
        return {"status": "error", "message": f"PDF 解密失败: {e}"}

    decrypted_images = []
    for i, page in enumerate(pages):
        page_path = os.path.join(temp_dir, f"page_{i+1}_masked.jpg")
        page.save(page_path, "JPEG")

        # Step 2: 解码图像
        decrypted_img_bytes = decrypt_masked_image_to_bytes(page_path, json_path, key_path)
        decrypted_images.append(Image.open(io.BytesIO(decrypted_img_bytes)).convert("RGB"))

    # Step 3: 合并 PDF
    output_pdf = os.path.splitext(masked_pdf_path)[0] + ".decrypted.pdf"
    decrypted_images[0].save(output_pdf, save_all=True, append_images=decrypted_images[1:])

    return {
        "status": "success",
        "decrypted_file": output_pdf
    }
